"""Offline append-only accounting for one consolidated experiment identity.

Every dispatch must follow a successful ``reserve`` return. A reservation ID
can never be reused, including after a crash. Sessions hold an OS file lock;
there is no unsafe PID-based stale-lock deletion. Responses are immutable files
bound into a fsynced, hash-chained journal. A torn journal, missing response or
orphan response is rejected intact for explicit forensic recovery.

Wall time uses a *new* monotonic clock each session. The session's entire wall
allowance is reserved durably before work; an interrupted session consumes that
full allowance on recovery. Clean exits charge elapsed time instead. Checkpoints
are evidence, not permission to refund an interrupted session. Set a smaller
``session_seconds`` explicitly to preserve a later resume allowance. Deadlines
are admission checks, not process preemption or proof that a VM stopped billing.

Only stdlib is imported; this module never loads a model or executes a plan.
"""

from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import uuid


FORMAT = "irisx-consolidated-ledger-v1"
REQUIRED_BINDINGS = frozenset({"source", "task", "model", "prompt", "sampling", "budget", "mode"})
REQUIRED_LIMITS = frozenset({"physical_calls", "cpu_checks", "wall_seconds", "unknown_calls"})
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,239}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_COUNTS = frozenset({"physical_calls", "cpu_checks", "coverage_checks", "model_checks", "search_checks",
                     "unknown_calls", "unknown_verifications", "unknown_model_calls",
                     "prompt_tokens", "output_tokens", "gas"})


class LedgerError(RuntimeError):
    """No dispatch is permitted when accounting cannot be established."""


class IntegrityError(LedgerError):
    """Retained bytes or event ordering are inconsistent; nothing was repaired."""


class BindingMismatch(LedgerError):
    pass


class BudgetExceeded(LedgerError):
    pass


class ControllerBusy(LedgerError):
    pass


def canonical(value):
    """Canonical JSON bytes used for both budget binding and artifact hashing."""
    def validate(item):
        if item is None or isinstance(item, (str, bool, int)):
            return
        if isinstance(item, float) and math.isfinite(item):
            return
        if isinstance(item, list):
            for child in item:
                validate(child)
            return
        if isinstance(item, dict) and all(isinstance(key, str) for key in item):
            for child in item.values():
                validate(child)
            return
        raise ValueError("only finite, string-keyed JSON data is accepted")
    validate(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    if name in _COUNTS and not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _fsync_directory(path):
    # Windows has no supported stdlib directory-fsync handle. File contents are
    # fsynced there; filesystem/power-loss guarantees remain platform dependent.
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


class Ledger:
    """Use ``with Ledger(...).session(...):`` before reading or mutating state.

    ``limits`` includes physical_calls, cpu_checks, wall_seconds, unknown_calls
    and optional dimensions such as tokens, gas, load_seconds or archive_seconds.
    ``bindings['budget']`` is ``digest(limits)``. All bindings are lowercase
    SHA-256 hex strings. Extra bindings are permitted and immutable on resume.

    ``reserve('model', id, budget)`` adds physical_calls=1. CPU reservations must
    declare cpu_checks >= 1. An ``overhead`` reservation can account installation,
    loading or archiving without claiming a model call. ``finish`` can release
    unused numeric reservation, but never the physical call/check itself; omitted
    usage dimensions stay charged at their full reservation. Unknown operations
    always retain every reserved dimension, and cannot subsequently be finished.
    """

    def __init__(self, root, bindings, limits):
        if not isinstance(limits, dict) or not REQUIRED_LIMITS <= limits.keys():
            raise ValueError("limits require physical_calls, cpu_checks, wall_seconds, unknown_calls")
        if not all(isinstance(key, str) and key for key in limits):
            raise ValueError("limit names must be nonempty strings")
        self.limits = {key: _number(value, key) for key, value in limits.items()}
        if self.limits["wall_seconds"] <= 0:
            raise ValueError("wall_seconds must be positive")
        if not isinstance(bindings, dict) or not REQUIRED_BINDINGS <= bindings.keys():
            raise ValueError("missing source/task/model/prompt/sampling/budget/mode binding")
        if not all(isinstance(key, str) and isinstance(value, str) and _HASH.fullmatch(value)
                   for key, value in bindings.items()):
            raise ValueError("bindings must be SHA-256 hashes")
        if bindings["budget"] != digest(self.limits):
            raise BindingMismatch("budget hash differs from exact canonical limits")
        self.bindings = dict(bindings)
        self.root = Path(root)
        self.journal_path = self.root / "journal.jsonl"
        self.responses_path = self.root / "responses"
        self._lock = None
        self._active = False
        self._poisoned = False
        self._reset()

    def _reset(self):
        self._operations = {}
        self._totals = {key: 0 for key in self.limits if key not in {"wall_seconds", "unknown_calls"}}
        self._unknown_count = 0
        self._overrun = False
        self._wall_consumed = 0.0
        self._open_session = None
        self._run_state = "partial"
        self._reason = ""
        self._sequence = 0
        self._previous = "0" * 64
        self._journal_bytes = 0

    def _require_session(self):
        if not self._active or self._poisoned:
            raise LedgerError("a healthy exclusive ledger session is required")

    def _acquire(self):
        if self._active or self._lock is not None:
            raise ControllerBusy("this ledger already has a controller")
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise IntegrityError("ledger root cannot be a symlink")
        _fsync_directory(self.root.parent)
        path = self.root / "controller.lock"
        if path.is_symlink():
            raise IntegrityError("controller lock cannot be a symlink")
        handle = open(path, "a+b")
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise ControllerBusy("another controller holds this ledger") from exc
        self._lock = handle

    def _release(self):
        if self._lock is not None:
            try:
                self._lock.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self._lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._lock.fileno(), fcntl.LOCK_UN)
            finally:
                self._lock.close()
                self._lock = None

    @contextmanager
    def session(self, session_seconds=None, prior_elapsed_seconds=0):
        """Acquire, validate, conservatively recover, then reserve session wall.

        ``prior_elapsed_seconds`` includes trusted, already measured bootstrap
        work before this context (for example source extraction). It consumes
        this session's allowance; it never extends the session deadline.
        A zero-second session is allowed only for inspection/finalization; it
        admits no operations. Always use a supervisor for hard worker deadlines.
        """
        prior_elapsed_seconds = _number(prior_elapsed_seconds, "prior_elapsed_seconds")
        if session_seconds is not None:
            session_seconds = _number(session_seconds, "session_seconds")
            if prior_elapsed_seconds > session_seconds:
                raise BudgetExceeded("prior bootstrap time exceeds requested session allowance")
        session_start_clock = time.monotonic() - prior_elapsed_seconds
        self._acquire()
        started = False
        try:
            self._reset()
            self._poisoned = False
            self._load()
            self._active = True
            self._recover()
            remaining = max(0.0, self.limits["wall_seconds"] - self._wall_consumed)
            allowance = remaining if session_seconds is None else _number(session_seconds, "session_seconds")
            if allowance > remaining:
                raise BudgetExceeded("requested session allowance exceeds remaining wall budget")
            if prior_elapsed_seconds > allowance:
                raise BudgetExceeded("prior bootstrap time exceeds remaining wall budget")
            self._start_clock = session_start_clock
            self._deadline = self._start_clock + allowance
            self._append("session_start", {"id": uuid.uuid4().hex, "allowance": allowance,
                                           "prior_elapsed_seconds": prior_elapsed_seconds})
            started = True
            try:
                yield self
            except BaseException as exc:
                if not self._poisoned:
                    self._append("state", {"state": "fail", "reason": f"controller exception: {type(exc).__name__}"})
                raise
        finally:
            try:
                if started and not self._poisoned:
                    self._settle_unknown()
                    elapsed = max(0.0, time.monotonic() - self._start_clock)
                    if elapsed > self._open_session["allowance"] and self._open_session["allowance"] > 0:
                        self._append("state", {"state": "fail", "reason": "session wall allowance exceeded"})
                    self._append("session_end", {"id": self._open_session["id"], "elapsed": elapsed})
            finally:
                self._active = False
                self._release()

    def _load(self):
        if self.responses_path.is_symlink() or self.journal_path.is_symlink():
            raise IntegrityError("ledger artifacts cannot be symlinks")
        self.responses_path.mkdir(exist_ok=True)
        if not self.journal_path.exists():
            if any(self.responses_path.iterdir()):
                raise IntegrityError("orphan responses without a journal; preserve for review")
            self._append("header", {"format": FORMAT, "bindings": self.bindings, "limits": self.limits}, create=True)
        else:
            raw = self.journal_path.read_bytes()
            if not raw or not raw.endswith(b"\n"):
                raise IntegrityError("empty or truncated journal; retained bytes require review")
            try:
                for line in raw.splitlines(keepends=True):
                    record = _strict_json(line)
                    if not isinstance(record, dict) or set(record) != {"seq", "prev", "event", "data", "sha256"}:
                        raise ValueError("journal record schema")
                    if record["seq"] != self._sequence or record["prev"] != self._previous:
                        raise ValueError("journal sequence/hash chain")
                    body = {key: record[key] for key in ("seq", "prev", "event", "data")}
                    if digest(body) != record["sha256"] or canonical(record) + b"\n" != line:
                        raise ValueError("journal digest/canonical bytes")
                    self._apply(record["event"], record["data"])
                    self._sequence += 1
                    self._previous = record["sha256"]
                self._journal_bytes = len(raw)
            except BindingMismatch:
                raise
            except (ValueError, KeyError, TypeError, LedgerError) as exc:
                raise IntegrityError(f"journal rejected without repair: {exc}") from exc
        expected = {}
        for operation in self._operations.values():
            if "response" in operation:
                expected[operation["response"]["file"]] = operation["response"]["sha256"]
        actual = {path.name: path for path in self.responses_path.iterdir()}
        if set(actual) != set(expected):
            raise IntegrityError("orphan or missing response files; preserve for review")
        for name, path in actual.items():
            if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected[name]:
                raise IntegrityError("response artifact hash/type mismatch")

    def _append(self, event, data, create=False):
        body = {"seq": self._sequence, "prev": self._previous, "event": event, "data": data}
        record = dict(body, sha256=digest(body))
        raw = canonical(record) + b"\n"
        try:
            if not create and self.journal_path.stat().st_size != self._journal_bytes:
                raise IntegrityError("journal changed outside the exclusive controller")
            with open(self.journal_path, "xb" if create else "ab") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            if create:
                _fsync_directory(self.root)
            self._apply(event, data)
        except BaseException:
            self._poisoned = True
            raise
        self._sequence += 1
        self._previous = record["sha256"]
        self._journal_bytes += len(raw)

    def _apply(self, event, data):
        if event == "header":
            if self._sequence != 0 or data.get("format") != FORMAT:
                raise IntegrityError("unexpected ledger header")
            if data.get("bindings") != self.bindings or data.get("limits") != self.limits:
                raise BindingMismatch("resume requires exact bindings and cumulative limits")
        elif self._sequence == 0:
            raise IntegrityError("journal must begin with header")
        elif event == "session_start":
            if self._open_session is not None:
                raise IntegrityError("overlapping sessions")
            _number(data["allowance"], "allowance")
            prior = _number(data.get("prior_elapsed_seconds", 0), "prior_elapsed_seconds")
            if prior > data["allowance"]:
                raise IntegrityError("session bootstrap exceeds its allowance")
            if data["allowance"] > max(0, self.limits["wall_seconds"] - self._wall_consumed):
                raise IntegrityError("session wall overreservation")
            self._open_session = dict(data)
        elif event in {"session_end", "session_lost"}:
            if self._open_session is None or data["id"] != self._open_session["id"]:
                raise IntegrityError("unmatched session end")
            elapsed = _number(data["elapsed"], "elapsed")
            if event == "session_lost" and elapsed != max(self._open_session["allowance"], self._open_session.get("checkpoint", 0)):
                raise IntegrityError("lost session must consume full allowance")
            self._wall_consumed += elapsed
            self._open_session = None
        elif event == "wall_checkpoint":
            if self._open_session is None or data["id"] != self._open_session["id"]:
                raise IntegrityError("unmatched wall checkpoint")
            elapsed = _number(data["elapsed"], "elapsed")
            if elapsed < self._open_session.get("checkpoint", 0):
                raise IntegrityError("wall checkpoint regressed")
            self._open_session["checkpoint"] = elapsed
        elif event == "reserve":
            self._validate_reservation(data["kind"], data["id"], data["budget"])
            self._operations[data["id"]] = {**copy.deepcopy(data), "status": "reserved"}
            for key, value in data["budget"].items():
                self._totals[key] += value
        elif event == "response":
            operation = self._operations[data["id"]]
            if operation["status"] != "reserved" or data["file"] != self._response_name(data["id"]) or not _HASH.fullmatch(data["sha256"]):
                raise IntegrityError("unexpected response")
            operation["response"] = {"file": data["file"], "sha256": data["sha256"]}
            operation["status"] = "responded"
        elif event in {"finish", "overrun"}:
            operation = self._operations[data["id"]]
            self._validate_finish(operation, data["usage"], data["outcome"], allow_overrun=event == "overrun")
            for key, value in data["usage"].items():
                self._totals[key] += value - operation["budget"][key]
            operation.update(status=data["outcome"], usage=dict(data["usage"]))
            if event == "overrun":
                self._overrun = True
                self._run_state, self._reason = "fail", "observed usage exceeded reservation"
        elif event == "unknown":
            operation = self._operations[data["id"]]
            if operation["status"] != "reserved":
                raise IntegrityError("only a response-less reservation can become unknown")
            operation["status"] = "unknown"
            self._unknown_count += 1
        elif event == "state":
            if data["state"] not in {"partial", "fail", "complete"}:
                raise IntegrityError("invalid run state")
            self._run_state, self._reason = data["state"], data["reason"]
        else:
            raise IntegrityError("unknown ledger event")

    def _recover(self):
        self._settle_unknown()
        if self._open_session is not None:
            self._append("session_lost", {"id": self._open_session["id"],
                                         "elapsed": max(self._open_session["allowance"], self._open_session.get("checkpoint", 0))})

    def _settle_unknown(self):
        for call_id, operation in list(self._operations.items()):
            if operation["status"] == "reserved":
                self._append("unknown", {"id": call_id})

    def _charged(self):
        return dict(self._totals)

    def _validate_reservation(self, kind, call_id, budget):
        if self._overrun:
            raise BudgetExceeded("an observed reservation overrun blocks all further dispatch")
        if kind not in {"model", "cpu", "overhead"} or not isinstance(call_id, str) or not _ID.fullmatch(call_id):
            raise ValueError("invalid operation kind or ID")
        if call_id in self._operations:
            raise LedgerError("reservation IDs are never reused or retried")
        if not isinstance(budget, dict) or not budget or set(budget) - (self.limits.keys() - {"wall_seconds", "unknown_calls"}):
            raise ValueError("operation budget has unbounded or reserved dimensions")
        for key, value in budget.items():
            _number(value, key)
        if kind == "model" and budget.get("physical_calls") != 1:
            raise ValueError("one model reservation consumes exactly one physical call")
        if kind != "model" and budget.get("physical_calls", 0) != 0:
            raise ValueError("only model operations reserve physical calls")
        if kind == "cpu" and budget.get("cpu_checks", 0) < 1:
            raise ValueError("CPU verification requires an explicit check reservation")
        charged = self._charged()
        if any(charged[key] + value > self.limits[key] for key, value in budget.items()):
            raise BudgetExceeded("operation would exceed cumulative reserved budget")
        if self._unknown_count and self._unknown_count >= self.limits["unknown_calls"]:
            raise BudgetExceeded("unknown-operation ceiling reached")

    def reserve(self, kind, call_id, budget, *, metadata=None):
        self._require_session()
        self.check_deadline()
        if self._run_state == "complete":
            raise LedgerError("a completed run cannot dispatch more work")
        if not isinstance(budget, dict):
            raise ValueError("budget must be a mapping")
        budget = dict(budget)
        if kind == "model":
            budget.setdefault("physical_calls", 1)
        self._validate_reservation(kind, call_id, budget)
        canonical(metadata)
        self._append("reserve", {"kind": kind, "id": call_id, "budget": budget, "metadata": copy.deepcopy(metadata)})
        return self.operation(call_id)

    @staticmethod
    def _response_name(call_id):
        return hashlib.sha256(call_id.encode("utf-8")).hexdigest() + ".json"

    def record_response(self, call_id, payload):
        self._require_session()
        operation = self._operations.get(call_id)
        if operation is None or operation["status"] != "reserved":
            raise LedgerError("response requires a new unresolved reservation")
        raw = canonical(payload)
        name = self._response_name(call_id)
        try:
            with open(self.responses_path / name, "xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            _fsync_directory(self.responses_path)
            self._append("response", {"id": call_id, "file": name, "sha256": hashlib.sha256(raw).hexdigest()})
        except BaseException:
            self._poisoned = True
            raise
        return copy.deepcopy(operation["response"])

    def _validate_finish(self, operation, usage, outcome, *, allow_overrun=False):
        if outcome not in {"complete", "fail"} or operation["status"] not in {"reserved", "responded"}:
            raise LedgerError("only unresolved current operations can finish once")
        if operation["kind"] == "model" and operation["status"] != "responded":
            raise LedgerError("model completion requires a durable response, including an error response")
        if set(usage) != set(operation["budget"]):
            raise ValueError("usage dimensions must match the reservation")
        for key, value in usage.items():
            _number(value, key)
            if value > operation["budget"][key] and not allow_overrun:
                raise BudgetExceeded("observed usage exceeds its reservation; retain as unresolved")
        if allow_overrun and (outcome != "fail" or not any(value > operation["budget"][key] for key, value in usage.items())):
            raise ValueError("overrun event requires failed observed excess usage")
        if operation["kind"] == "model" and usage.get("physical_calls") != 1:
            raise ValueError("physical model call cannot be refunded")
        if operation["kind"] == "cpu" and usage.get("cpu_checks", 0) < 1:
            raise ValueError("physical CPU verification cannot be refunded")

    def finish(self, call_id, usage=None, outcome="complete"):
        self._require_session()
        operation = self._operations.get(call_id)
        if operation is None:
            raise LedgerError("unknown reservation ID")
        if usage is not None and (not isinstance(usage, dict) or set(usage) - operation["budget"].keys()):
            raise ValueError("usage contains unreserved dimensions")
        charged = {**operation["budget"], **(usage or {})}
        # Validate the whole observation before persisting it. A real overshoot
        # must remain visible, even though no more work is then admitted.
        try:
            self._validate_finish(operation, charged, outcome)
        except BudgetExceeded:
            self._validate_finish(operation, charged, "fail", allow_overrun=True)
            self._append("overrun", {"id": call_id, "usage": charged, "outcome": "fail"})
            raise BudgetExceeded("observed overrun retained and charged; further dispatch is blocked") from None
        self._append("finish", {"id": call_id, "usage": charged, "outcome": outcome})

    def operation(self, call_id):
        self._require_session()
        return copy.deepcopy(self._operations.get(call_id))

    def get_response(self, call_id):
        self._require_session()
        operation = self._operations.get(call_id)
        if operation is None or "response" not in operation:
            raise LedgerError("no durable response for this reservation")
        path = self.responses_path / operation["response"]["file"]
        if path.is_symlink():
            raise IntegrityError("response cannot be a symlink")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != operation["response"]["sha256"]:
            raise IntegrityError("response hash mismatch")
        return _strict_json(raw)

    @property
    def remaining_wall_seconds(self):
        self._require_session()
        return max(0.0, self._deadline - time.monotonic())

    def check_deadline(self):
        self._require_session()
        if time.monotonic() >= self._deadline:
            raise BudgetExceeded("session deadline reached; no new dispatch")

    def checkpoint_wall(self):
        self._require_session()
        elapsed = max(0.0, time.monotonic() - self._start_clock)
        self._append("wall_checkpoint", {"id": self._open_session["id"], "elapsed": elapsed})
        return elapsed

    def set_state(self, state, reason=""):
        self._require_session()
        if state not in {"partial", "fail", "complete"} or not isinstance(reason, str):
            raise ValueError("invalid state or reason")
        if self._run_state == "complete" and state != "complete":
            raise LedgerError("complete is terminal")
        if state == "complete" and any(op["status"] not in {"complete", "fail"} for op in self._operations.values()):
            raise LedgerError("cannot claim complete with unresolved or unknown operations")
        if state == "complete" and self._overrun:
            raise LedgerError("cannot claim complete after a reservation overrun")
        self._append("state", {"state": state, "reason": reason})

    def summary(self):
        self._require_session()
        counts = {state: sum(op["status"] == state for op in self._operations.values())
                  for state in ("reserved", "responded", "unknown", "complete", "fail")}
        return {"format": FORMAT, "bindings": dict(self.bindings), "limits": dict(self.limits),
                "state": self._run_state, "reason": self._reason, "charged": self._charged(),
                "operation_states": counts, "operations": copy.deepcopy(self._operations),
                "consumed_wall_seconds": self._wall_consumed,
                "session_elapsed_seconds": max(0.0, time.monotonic() - self._start_clock),
                "session_reserved_wall_seconds": self._open_session["allowance"],
                "session_prior_elapsed_seconds": self._open_session.get("prior_elapsed_seconds", 0),
                "remaining_session_wall_seconds": self.remaining_wall_seconds,
                "reservation_overrun": self._overrun, "directory_fsync_supported": os.name != "nt",
                "journal_sha256": self._previous, "journal_records": self._sequence,
                "vm_billing_stopped": False}
