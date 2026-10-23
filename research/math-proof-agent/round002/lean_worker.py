"""Fail-closed, restricted Lean verifier for the MATH-002 research pilot.

This is deliberately not a general Lean-code execution service. Model input is
parsed as a small tactic language, never as a command or an arbitrary term.
Linux bubblewrap isolation must pass measured controls before Lean is invoked.
The pinned trusted libraries and Lean kernel remain part of the trust base.
"""
from __future__ import annotations

import dataclasses
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any


POLICY_VERSION = "math002-restricted-lean-v1"
ALLOWED_AXIOMS = frozenset({"propext", "Quot.sound", "Classical.choice"})
THEOREM_NAME = "irisx_final"
ANSWER_BINDING_KIND = "closed_exists_nat_v1"
IDENT = r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*"
SIMPLE_TACTICS = frozenset({"rfl", "assumption", "constructor", "left", "right",
                           "trivial", "contradiction", "omega", "ring", "ring_nf",
                           "norm_num", "simp", "simp_all", "decide"})


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(root: Path) -> str:
    """Fingerprint every byte and symlink target, without following symlinks."""
    records = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            target = os.readlink(path)
            resolved = path.resolve()
            if not resolved.is_relative_to(root.resolve()):
                raise ValueError("runtime symlink escapes its pinned root")
            records.append([relative, "symlink", target])
        elif path.is_file():
            records.append([relative, "file", file_sha256(path)])
    return canonical_sha256(records)


def statement_digest(statement: dict[str, Any]) -> str:
    """Only immutable statement fields enter this digest; no answer/proof field."""
    return canonical_sha256({key: statement[key] for key in
                             ("id", "imports", "declaration", "fidelity")})


def normalize_nat_answer(answer: str) -> str:
    """Accept a canonical decimal numeral only; never parse an arbitrary term."""
    if not isinstance(answer, str) or re.fullmatch(r"(?:0|[1-9][0-9]{0,59})", answer) is None:
        raise ValueError("answer_must_be_canonical_Nat_numeral_at_most_60_digits")
    return answer


def normalized_answer_sha256(answer: str) -> str:
    return hashlib.sha256(normalize_nat_answer(answer).encode("utf-8")).hexdigest()


def answer_candidate_digest(answer: str, proof_body: str) -> str:
    if not isinstance(proof_body, str):
        raise ValueError("proof_body_must_be_text")
    return canonical_sha256({"answer": normalize_nat_answer(answer), "proof_body": proof_body})


def answer_binding_digest(spec: dict[str, Any]) -> str:
    """Validate the versioned binding shape, not the truth of review metadata."""
    if not isinstance(spec, dict) or set(spec) != {
            "kind", "statement_sha256", "review_ref", "answer_mode"}:
        raise ValueError("answer_binding_spec_shape_invalid")
    if (spec["kind"] != ANSWER_BINDING_KIND or spec["answer_mode"] != "find_answer"
            or not isinstance(spec["statement_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", spec["statement_sha256"]) is None
            or not isinstance(spec["review_ref"], str)
            or not spec["review_ref"].strip() or len(spec["review_ref"]) > 1024):
        raise ValueError("answer_binding_spec_values_invalid")
    return canonical_sha256(spec)


def _validate_closed_exists_nat(declaration: str) -> None:
    # A conservative admission grammar, not a replacement for Lean elaboration.
    # The exact original declaration is retained. Its body is a trusted frozen
    # statement, not a predicate translated or supplied by the candidate.
    match = re.fullmatch(r"\s*:\s*∃\s+[A-Za-z_][A-Za-z0-9_']*\s*:\s*"
                         r"(?:_root_\.)?Nat\s*,\s*(.+)", declaration, re.DOTALL)
    if not match or re.search(r"∃|\bExists(?:Unique)?\b", match.group(1)):
        raise ValueError("answer_binding_requires_single_closed_Nat_existential")


def parse_proof_body(body: str) -> str:
    """Parse a conservative line grammar; command/term injection is impossible.

    The grammar intentionally omits `have`, nested terms, tactic quotations,
    `run_tac`, native evaluation, macros, options, arbitrary syntax extensions,
    and custom tactic names. Rejection is recorded as unsupported, not false.
    """
    if not isinstance(body, str) or len(body.encode("utf-8")) > 65536:
        raise ValueError("proof body must be UTF-8 text of at most 65536 bytes")
    lines = body.strip().splitlines()
    if not lines or lines[0].strip() != "by" or len(lines) > 129:
        raise ValueError("expected by followed by at most 128 tactic lines")
    result = ["by"]
    for raw in lines[1:]:
        tactic = raw.strip()
        if not tactic:
            continue
        prefix = ""
        if tactic.startswith("· "):
            prefix, tactic = "· ", tactic[2:]
        valid = tactic in SIMPLE_TACTICS
        valid |= re.fullmatch(r"(?:intro|intros|revert) " + IDENT +
                             r"(?: " + IDENT + r")*", tactic) is not None
        valid |= re.fullmatch(r"(?:exact|apply|symm at) " + IDENT, tactic) is not None
        valid |= re.fullmatch(r"(?:simp|simp_all|norm_num)(?: only)? \[" + IDENT +
                             r"(?:, " + IDENT + r")*\]", tactic) is not None
        if not valid:
            raise ValueError("unsupported tactic grammar")
        # Only whitespace from the original input survives. Lean indentation is
        # represented by two-space increments, not arbitrary Unicode controls.
        indentation = len(raw) - len(raw.lstrip(" "))
        if "\t" in raw or indentation > 32:
            raise ValueError("invalid tactic indentation")
        result.append(" " * max(2, indentation) + prefix + tactic)
    if len(result) == 1:
        raise ValueError("empty proof")
    return "\n".join(result)


@dataclasses.dataclass(frozen=True)
class Limits:
    wall_seconds: int = 30
    cpu_seconds: int = 20
    memory_bytes: int = 2 * 1024**3
    process_count: int = 64
    output_bytes: int = 65536
    open_files: int = 64

    def validate(self) -> None:
        if not (1 <= self.wall_seconds <= 120 and 1 <= self.cpu_seconds <= 120
                and 128 * 1024**2 <= self.memory_bytes <= 8 * 1024**3
                and 8 <= self.process_count <= 64
                and 4096 <= self.output_bytes <= 1024**2
                and 32 <= self.open_files <= 128):
            raise ValueError("worker resource limits outside MATH-002 policy")


def _limit_child(limits: Limits) -> None:
    import resource
    for resource_id, value in (
        (resource.RLIMIT_CPU, limits.cpu_seconds),
        (resource.RLIMIT_AS, limits.memory_bytes),
        (resource.RLIMIT_NPROC, limits.process_count),
        (resource.RLIMIT_FSIZE, limits.output_bytes),
        (resource.RLIMIT_NOFILE, limits.open_files),
        (resource.RLIMIT_CORE, 0),
    ):
        resource.setrlimit(resource_id, (value, value))


def _sandbox_command(bwrap: str, input_root: Path,
                     extra_mounts: list[tuple[Path, str]], command: list[str]) -> list[str]:
    argv = [bwrap, "--unshare-all", "--die-with-parent", "--new-session",
            "--cap-drop", "ALL", "--clearenv"]
    # Only public system runtime files are visible. No /etc, /home, /root,
    # notebook inputs, credentials, host /proc or ambient working tree is bound.
    for name in ("/usr", "/lib", "/lib64", "/bin"):
        path = Path(name)
        if path.is_symlink():
            argv.extend(["--symlink", os.readlink(path), name])
        elif path.exists():
            argv.extend(["--ro-bind", name, name])
    argv += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
             "--tmpfs", "/work", "--dir", "/home", "--dir", "/home/worker",
             "--ro-bind", str(input_root), "/input"]
    for source, destination in extra_mounts:
        argv.extend(["--ro-bind", str(source), destination])
    argv.extend(["--chdir", "/work", "--setenv", "HOME", "/home/worker",
                 "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "LANG", "C.UTF-8"])
    argv.extend(command)
    return argv


def _execute(argv: list[str], limits: Limits, output_root: Path) -> dict[str, Any]:
    limits.validate()
    started = time.monotonic()
    with tempfile.TemporaryFile(dir=output_root) as capture:
        proc = subprocess.Popen(argv, stdout=capture, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin"},
                                close_fds=True, start_new_session=True,
                                preexec_fn=lambda: _limit_child(limits))
        timed_out = False
        try:
            proc.wait(timeout=limits.wall_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        capture.seek(0)
        output = capture.read(limits.output_bytes + 1)
    return {"exit_code": proc.returncode, "timed_out": timed_out,
            "wall_seconds": time.monotonic() - started,
            "output": output[:limits.output_bytes].decode("utf-8", errors="replace"),
            "output_truncated": len(output) >= limits.output_bytes,
            "limits": dataclasses.asdict(limits)}


_PROBE = r'''
import errno, json, os, pathlib, resource, signal, socket
checks = {}
expected = json.loads(pathlib.Path('/input/expected.json').read_text())
checks['environment_cleared'] = (set(os.environ) <= {'HOME', 'PATH', 'LANG', 'LC_CTYPE', 'PWD'}
                                 and os.environ.get('PWD', '/work') == '/work')
checks['credential_sentinel_hidden'] = not pathlib.Path(expected['sentinel']).exists()
checks['home_hidden'] = not pathlib.Path('/root').exists() and not pathlib.Path('/etc').exists()
for namespace, host in expected['namespaces'].items():
    checks['isolated_' + namespace] = os.readlink('/proc/self/ns/' + namespace) != host
try:
    pathlib.Path('/input/forbidden-write').write_text('bad')
    checks['input_readonly'] = False
except OSError as exc:
    checks['input_readonly'] = exc.errno in (errno.EROFS, errno.EACCES)
try:
    connection = socket.create_connection(('127.0.0.1', expected['listener_port']), timeout=.3)
    connection.close()
    checks['host_loopback_unreachable'] = False
except OSError:
    checks['host_loopback_unreachable'] = True
routes = pathlib.Path('/proc/net/route').read_text().splitlines()[1:]
checks['no_network_routes'] = not routes
for label, kind in [('memory', resource.RLIMIT_AS), ('cpu', resource.RLIMIT_CPU),
                    ('processes', resource.RLIMIT_NPROC), ('file_size', resource.RLIMIT_FSIZE),
                    ('open_files', resource.RLIMIT_NOFILE), ('core', resource.RLIMIT_CORE)]:
    checks['limit_' + label] = list(resource.getrlimit(kind)) == expected['limits'][label]
try:
    memory = bytearray(expected['limits']['memory'][0])
    checks['memory_limit_enforced'] = False
except MemoryError:
    checks['memory_limit_enforced'] = True
signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
try:
    with open('/work/size-check', 'wb') as stream:
        stream.write(b'x' * (expected['limits']['file_size'][0] + 1))
    checks['file_size_limit_enforced'] = False
except OSError as exc:
    checks['file_size_limit_enforced'] = exc.errno == errno.EFBIG
children = []
checks['process_limit_enforced'] = False
try:
    for _ in range(expected['limits']['processes'][0] + 2):
        child = os.fork()
        if child == 0:
            signal.pause()
            os._exit(0)
        children.append(child)
except OSError as exc:
    checks['process_limit_enforced'] = exc.errno == errno.EAGAIN
finally:
    for child in children:
        os.kill(child, signal.SIGKILL)
    for child in children:
        os.waitpid(child, 0)
print(json.dumps({'checks': checks}, sort_keys=True), flush=True)
'''


def probe_isolation(bwrap_path: str | None = None,
                    work_root: str | None = None) -> dict[str, Any]:
    """Execute only our authored probe; never substitute unshare for a sandbox."""
    result: dict[str, Any] = {"policy": POLICY_VERSION, "qualified": False, "status": "blocked",
                              "platform": sys.platform}
    if sys.platform != "linux":
        return result | {"blocker": "linux_bubblewrap_required"}
    bwrap = bwrap_path or shutil.which("bwrap")
    if not bwrap or not Path(bwrap).is_file():
        return result | {"blocker": "bubblewrap_missing"}
    parent = Path(work_root).resolve() if work_root else Path(tempfile.gettempdir())
    parent.mkdir(parents=True, exist_ok=True)
    limits = Limits(wall_seconds=20, cpu_seconds=5, memory_bytes=256 * 1024**2)
    with tempfile.TemporaryDirectory(prefix="irisx-isolation-", dir=parent) as folder:
        root = Path(folder)
        inputs = root / "input"
        inputs.mkdir()
        sentinel = root / "credential-sentinel"
        sentinel.write_text("public-control-only-not-a-credential")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            expected = {"sentinel": str(sentinel), "listener_port": listener.getsockname()[1],
                        "namespaces": {key: os.readlink("/proc/self/ns/" + key)
                                       for key in ("mnt", "net", "pid", "user")},
                        "limits": {"memory": [limits.memory_bytes] * 2,
                                   "cpu": [limits.cpu_seconds] * 2,
                                   "processes": [limits.process_count] * 2,
                                   "file_size": [limits.output_bytes] * 2,
                                   "open_files": [limits.open_files] * 2, "core": [0, 0]}}
            (inputs / "expected.json").write_text(json.dumps(expected))
            (inputs / "probe.py").write_text(_PROBE)
            command = _sandbox_command(bwrap, inputs, [], ["/usr/bin/python3", "-I", "/input/probe.py"])
            execution = _execute(command, limits, root)
    result.update({"bwrap_sha256": file_sha256(Path(bwrap)), "execution": execution,
                   "trust_boundary": "Linux kernel, bubblewrap, public system runtime, pinned Lean libraries"})
    try:
        checks = json.loads(execution["output"])["checks"]
    except (KeyError, ValueError):
        return result | {"blocker": "isolation_probe_failed"}
    result["checks"] = checks
    result["qualified"] = (execution["exit_code"] == 0 and not execution["timed_out"]
                           and len(checks) == 19 and all(value is True for value in checks.values()))
    if not result["qualified"]:
        result["blocker"] = "isolation_controls_failed"
    else:
        result["status"] = "passed"
    return result


@dataclasses.dataclass(frozen=True)
class LeanConfig:
    lean_root: str
    expected_runtime_sha256: str
    expected_lean_version: str
    bwrap_path: str | None = None
    project_root: str | None = None
    expected_project_sha256: str | None = None
    mathlib_revision: str | None = None
    lean_paths: tuple[str, ...] = ()
    work_root: str | None = None
    limits: Limits = dataclasses.field(default_factory=Limits)
    statement_sha256s: dict[str, str] = dataclasses.field(default_factory=dict)
    answer_bindings: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    engineering_controls_only: bool = False


class LeanWorker:
    def __init__(self, config: LeanConfig | dict[str, Any]):
        if isinstance(config, dict):
            fields = dict(config)
            if isinstance(fields.get("limits"), dict):
                fields["limits"] = Limits(**fields["limits"])
            config = LeanConfig(**fields)
        # Detach caller-owned maps; admission must not change as a side effect of
        # mutating the dictionaries used to construct this worker.
        self.config = dataclasses.replace(config,
            statement_sha256s=copy.deepcopy(config.statement_sha256s),
            answer_bindings=copy.deepcopy(config.answer_bindings))
        self._preflight: dict[str, Any] | None = None

    def identity(self) -> str:
        """Pinned verifier policy/config, independent of host installation paths.

        preflight must separately measure the runtime/project/bwrap bytes. A
        declared fingerprint alone never qualifies execution.
        """
        config = self.config
        return canonical_sha256({
            "policy": POLICY_VERSION, "allowed_axioms": sorted(ALLOWED_AXIOMS),
            "runtime_sha256": config.expected_runtime_sha256,
            "lean_version": config.expected_lean_version,
            "project_sha256": config.expected_project_sha256,
            "mathlib_revision": config.mathlib_revision,
            "lean_paths": config.lean_paths, "limits": dataclasses.asdict(config.limits),
            "statements": config.statement_sha256s,
            "answer_bindings": config.answer_bindings,
            "engineering_controls_only": config.engineering_controls_only,
        })

    def answer_binding_spec(self, statement_id: str) -> dict[str, Any] | None:
        """Return a detached registration; this does not qualify its provenance."""
        return copy.deepcopy(self.config.answer_bindings.get(statement_id))

    def preflight(self) -> dict[str, Any]:
        config = self.config
        evidence = probe_isolation(config.bwrap_path, config.work_root)
        evidence["runtime_qualified"] = False
        evidence["status"] = "blocked"
        if not evidence["qualified"]:
            self._preflight = evidence
            return evidence
        try:
            root = Path(config.lean_root).resolve(strict=True)
            actual = tree_sha256(root)
            evidence["runtime_sha256"] = actual
            if not config.expected_runtime_sha256 or actual != config.expected_runtime_sha256:
                raise ValueError("runtime_fingerprint_mismatch")
            # Version runs in the same sandbox as proofs, never using an ambient elan proxy.
            execution = self._run_source(None, ["/lean/bin/lean", "-j1", "--version"])
            evidence["lean_version_execution"] = execution
            if execution["exit_code"] or config.expected_lean_version != execution["output"].strip():
                raise ValueError("lean_version_mismatch")
            if config.project_root:
                project = Path(config.project_root).resolve(strict=True)
                actual_project = tree_sha256(project)
                evidence["project_sha256"] = actual_project
                if actual_project != config.expected_project_sha256 or not config.mathlib_revision:
                    raise ValueError("project_fingerprint_or_mathlib_revision_missing")
                if not re.fullmatch(r"[0-9a-f]{40}", config.mathlib_revision):
                    raise ValueError("mathlib_revision_must_be_full_commit")
            elif config.lean_paths or config.mathlib_revision:
                raise ValueError("mathlib_project_missing")
            evidence["runtime_qualified"] = True
            evidence["status"] = "passed"
            evidence["library_scope"] = "pinned_mathlib" if config.project_root else "Lean_core_only"
        except (OSError, ValueError) as exc:
            evidence["blocker"] = str(exc)
        self._preflight = evidence
        return evidence

    def _run_source(self, source: str | None, command: list[str] | None = None,
                    limits: Limits | None = None) -> dict[str, Any]:
        config = self.config
        parent = Path(config.work_root or tempfile.gettempdir()).resolve()
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="irisx-lean-", dir=parent) as folder:
            root = Path(folder)
            inputs = root / "input"
            inputs.mkdir()
            if source is not None:
                (inputs / "Candidate.lean").write_text(source, encoding="utf-8")
            mounts = [(Path(config.lean_root).resolve(), "/lean")]
            if config.project_root:
                mounts.append((Path(config.project_root).resolve(), "/project"))
            lean_command = command or ["/lean/bin/lean", "-j1", "/input/Candidate.lean"]
            if config.lean_paths:
                if any(not re.fullmatch(r"[A-Za-z0-9_./-]+", path) or ".." in Path(path).parts
                       or path.startswith("/") for path in config.lean_paths):
                    raise ValueError("invalid relative lean library path")
                lean_command = ["/usr/bin/env", "LEAN_PATH=" + ":".join(
                    "/project/" + path for path in config.lean_paths)] + lean_command
            bwrap = config.bwrap_path or shutil.which("bwrap")
            if not bwrap:
                raise ValueError("bubblewrap_missing")
            return _execute(_sandbox_command(bwrap, inputs, mounts, lean_command), limits or config.limits, root)

    def verify(self, statement: dict[str, Any], proof_body: str,
               deadline: float | None = None) -> dict[str, Any]:
        return self._verify(statement, proof_body, deadline=deadline)

    def verify_answer(self, statement: dict[str, Any], answer: str, proof_body: str,
                      deadline: float | None = None) -> dict[str, Any]:
        """Prove the unchanged existential with the candidate as a fixed witness.

        The nested tactic body receives only the residual goal for that numeral.
        The final theorem's transitive axiom audit also covers this nested proof.
        No separate predicate template or model-controlled theorem is introduced.
        """
        return self._verify(statement, proof_body, deadline=deadline,
                            answer_route=True, answer=answer)

    def _verify(self, statement: dict[str, Any], proof_body: str,
                deadline: float | None = None, *, answer_route: bool = False,
                answer: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {"policy": POLICY_VERSION, "status": "infrastructure_blocked",
                                 "proof_status": "unsupported", "accepted": False,
                                 "trust_policy_passed": False}
        binding_receipt = None
        try:
            if not isinstance(proof_body, str):
                raise ValueError("proof_body_must_be_text")
            result["candidate_sha256"] = (answer_candidate_digest(answer, proof_body)
                if answer_route else hashlib.sha256(proof_body.encode()).hexdigest())
            digest = statement_digest(statement)
            result["statement_sha256"] = digest
            expected_fidelity = "authored_engineering_control" if self.config.engineering_controls_only else "human_checked"
            if (statement.get("sha256") != digest or statement["fidelity"] != expected_fidelity
                    or self.config.statement_sha256s.get(statement["id"]) != digest):
                raise ValueError("statement_binding_or_fidelity_failed")
            if not re.fullmatch(r"[A-Za-z0-9_-]+", statement["id"]):
                raise ValueError("invalid_statement_id")
            imports = statement["imports"]
            if not isinstance(imports, list) or not imports or any(
                    not re.fullmatch(IDENT, item) for item in imports):
                raise ValueError("invalid_pinned_imports")
            # Declarations are trusted, preregistered panel inputs, never model data.
            declaration = statement["declaration"]
            if not isinstance(declaration, str) or len(declaration) > 16384:
                raise ValueError("invalid_pinned_statement")
            body = parse_proof_body(proof_body)
            spec = self.answer_binding_spec(statement["id"])
            if not answer_route and statement["id"] in self.config.answer_bindings:
                raise ValueError("registered_answer_binding_requires_verify_answer")
            if answer_route:
                spec_digest = answer_binding_digest(spec)
                if spec["statement_sha256"] != digest:
                    raise ValueError("answer_binding_statement_digest_mismatch")
                engineering_ref = spec["review_ref"].startswith("engineering:")
                if engineering_ref != self.config.engineering_controls_only:
                    raise ValueError("answer_binding_review_scope_mismatch")
                _validate_closed_exists_nat(declaration)
                # Only a canonical numeral enters the trusted constructor.
                # The original theorem type is unchanged, so the kernel checks
                # P(answer). The enclosed tactics cannot replace that witness.
                body = ("  _root_.Exists.intro (" + normalize_nat_answer(answer) +
                        " : _root_.Nat) (by\n" +
                        "\n".join("  " + line for line in body.splitlines()[1:]) + "\n  )")
                binding_receipt = {"kind": ANSWER_BINDING_KIND, "status": "kernel_verified",
                    "statement_sha256": digest, "spec_sha256": spec_digest,
                    "normalized_answer_sha256": normalized_answer_sha256(answer),
                    "candidate_sha256": result["candidate_sha256"]}
        except (KeyError, TypeError, ValueError) as exc:
            return result | {"status": "invalid_format", "reason": str(exc)}
        if self._preflight is None:
            self.preflight()
        assert self._preflight is not None
        if not self._preflight.get("runtime_qualified"):
            return result | {"reason": self._preflight.get("blocker", "preflight_failed")}
        source = ("\n".join("import " + item for item in imports) + "\n" +
                  "set_option maxHeartbeats 200000\n" +
                  "theorem " + THEOREM_NAME + " " + declaration + " :=\n" + body + "\n" +
                  "#print axioms " + THEOREM_NAME + "\n")
        result["source_sha256"] = hashlib.sha256(source.encode()).hexdigest()
        limits = self.config.limits
        if deadline is not None:
            remaining = int(deadline - time.monotonic())
            if remaining < 1:
                return result | {"status": "timeout", "proof_status": "incomplete",
                                 "reason": "arm_deadline_reached_before_Lean"}
            limits = dataclasses.replace(limits, wall_seconds=min(limits.wall_seconds, remaining))
        try:
            execution = self._run_source(source, limits=limits)
        except (OSError, ValueError) as exc:
            return result | {"reason": str(exc)}
        result["execution"] = execution
        if execution["timed_out"]:
            return result | {"status": "timeout", "proof_status": "incomplete"}
        # bubblewrap may encode its child signal as 128+signal instead of a
        # negative Popen return code. Neither form is a mathematical rejection.
        if execution["exit_code"] < 0 or 128 <= execution["exit_code"] <= 255:
            return result | {"status": "infrastructure_error", "reason": "Lean_terminated_by_signal"}
        if execution["exit_code"] != 0:
            if "failed to create thread" in execution["output"]:
                return result | {"status": "infrastructure_error", "reason": "Lean_thread_creation_failed"}
            return result | {"status": "rejected", "proof_status": "incomplete"}
        output = execution["output"]
        patterns = [r"'irisx_final' depends on axioms: \[([^\]]*)\]",
                    r"'irisx_final' does not depend on any axioms"]
        dependencies = re.findall(patterns[0], output)
        no_axioms = re.findall(patterns[1], output)
        if len(dependencies) + len(no_axioms) != 1 or execution["output_truncated"]:
            return result | {"status": "trust_rejected", "reason": "missing_or_ambiguous_axiom_audit"}
        axioms = sorted(name.strip() for name in dependencies[0].split(",") if name.strip()) if dependencies else []
        result["axioms"] = axioms
        result["axiom_audit"] = "Lean #print axioms of final theorem, including transitive dependencies"
        if not set(axioms).issubset(ALLOWED_AXIOMS):
            return result | {"status": "trust_rejected", "reason": "axiom_policy_failed"}
        if binding_receipt is not None:
            result["answer_binding"] = binding_receipt
        return result | {"status": "accepted", "proof_status": "kernel_verified", "accepted": True,
                         "trust_policy_passed": True,
                         "trust_base": "pinned Lean kernel/libraries + restricted tactic grammar + measured Linux isolation"}
