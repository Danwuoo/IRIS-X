"""Resumable NVARC SDG stages and a fail-closed generated-program boundary."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Mapping, Protocol

from .arc_nvarc_runtime import atomic_json
from .canonical import digest_value
from .errors import ValidationError


STAGES = ("summary", "mix", "input-logic", "output-logic", "pair", "filter")


class Teacher(Protocol):
    identity: str
    billed_calls: int

    def complete(self, stage: str, item: Mapping[str, Any], prompt: str) -> Any: ...


class SavedTeacher:
    identity = "saved-response"
    billed_calls = 0

    def __init__(self, responses: Mapping[str, Any]) -> None:
        self.responses = responses

    def complete(self, stage: str, item: Mapping[str, Any], prompt: str) -> Any:
        key = f"{stage}:{item['record_id']}"
        if key not in self.responses:
            raise ValidationError(f"saved SDG response missing: {key}")
        return self.responses[key]


def run_stage(stage: str, inputs: list[Mapping[str, Any]], prompt: str,
              provider: Teacher, output: Path, *, seed: int,
              maximum_calls: int) -> dict[str, Any]:
    """Reserve a provider call before it happens; uncertain calls are never retried."""
    if stage not in STAGES or not prompt or maximum_calls < 0 or not provider.identity:
        raise ValidationError("SDG stage binding is invalid")
    identifiers = [item["record_id"] for item in inputs]
    if len(set(identifiers)) != len(identifiers):
        raise ValidationError("SDG record identifiers repeat")
    binding = digest_value({"stage": stage, "inputs": inputs, "prompt": prompt,
                            "provider": provider.identity, "seed": seed})
    path = output / f"{stage}.json"
    if path.exists():
        ledger = json.loads(path.read_bytes())
        if ledger.get("binding") != binding or ledger.get("maximum_calls") != maximum_calls:
            raise ValidationError("SDG resumed stage identity differs")
    else:
        ledger = {"format": "irisx/nvarc-sdg-stage", "binding": binding,
                  "stage": stage, "maximum_calls": maximum_calls, "reserved_calls": 0,
                  "records": {}}
        atomic_json(path, ledger)
    for item in inputs:
        key = item["record_id"]
        if key in ledger["records"]:
            continue
        cost = provider.billed_calls
        if type(cost) is not int or cost not in (0, 1):
            raise ValidationError("SDG provider call accounting is invalid")
        if ledger["reserved_calls"] + cost > maximum_calls:
            raise ValidationError("SDG stage call ceiling exhausted")
        ledger["reserved_calls"] += cost
        ledger["records"][key] = {"status": "pending", "input_digest": digest_value(item),
                                  "provider_calls": cost}
        atomic_json(path, ledger)
        try:
            value = provider.complete(stage, item, prompt)
            ledger["records"][key].update({"status": "complete", "response": value,
                                           "response_digest": digest_value(value)})
        except Exception as error:
            ledger["records"][key].update({"status": "failed",
                                           "error_type": type(error).__name__})
        atomic_json(path, ledger)
    return ledger


def stage_responses(ledger: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record["response"] for key, record in ledger["records"].items()
            if record["status"] == "complete"}


def run_teacher_pipeline(seed_records: list[Mapping[str, Any]],
                         prompts: Mapping[str, str], provider: Teacher,
                         output: Path, *, seed: int,
                         maximum_calls: int) -> dict[str, Any]:
    """Resume the four source teacher stages in order with a shared call ceiling."""
    records = seed_records
    ledgers = {}
    for stage in STAGES[:4]:
        if stage not in prompts:
            raise ValidationError(f"SDG prompt missing for {stage}")
        spent = sum(value["reserved_calls"] for value in ledgers.values())
        ledger = run_stage(stage, records, prompts[stage], provider, output,
                           seed=seed, maximum_calls=maximum_calls - spent)
        ledgers[stage] = ledger
        if any(value["status"] != "complete" for value in ledger["records"].values()):
            break
        records = [{**item, "upstream_response": ledger["records"][item["record_id"]]["response"]}
                   for item in records]
    return {"stages": ledgers, "reserved_calls": sum(value["reserved_calls"]
                                                       for value in ledgers.values())}


class DockerProgramExecutor:
    """Optional local Docker isolation; a fixture command builder is testable offline."""

    _WRAPPER = ("import contextlib, io, json, sys\n"
                "p = json.load(sys.stdin)\nns = {}\ns = io.StringIO()\n"
                "with contextlib.redirect_stdout(s):\n"
                "    exec(p['code'], ns)\n    r = ns['transform'](p['grid'])\n"
                "sys.stdout.write(json.dumps(r))\n")

    def __init__(self, image: str, *, wall_seconds: int = 5, output_bytes: int = 65536) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9._/-]+@sha256:[0-9a-f]{64}", image):
            raise ValidationError("SDG sandbox image must be pinned by digest")
        if not 1 <= wall_seconds <= 60 or not 1 <= output_bytes <= 65536:
            raise ValidationError("SDG sandbox resource limits invalid")
        self.image, self.wall_seconds, self.output_bytes = image, wall_seconds, output_bytes

    def command(self, *, cidfile: Path | None = None) -> list[str]:
        command = ["docker", "run", "--rm", "-i", "--pull=never", "--network=none",
                "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "--cpus=1", "--memory=256m", "--memory-swap=256m", "--pids-limit=64",
                "--user=65534:65534", "--tmpfs=/tmp:rw,noexec,nosuid,size=8m"]
        if cidfile is not None:
            command.extend(["--cidfile", str(cidfile)])
        return command + [self.image, "python", "-I", "-c", self._WRAPPER]

    def execute(self, code: str, input_grid: Any) -> Any:
        from .arc_nvarc_data import grid

        if not shutil.which("docker"):
            raise ValidationError("Docker sandbox runtime unavailable")
        try:
            inspect = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", self.image],
                                     capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValidationError("pinned local sandbox image inspection failed") from error
        if inspect.returncode or not inspect.stdout.strip().decode().startswith("sha256:"):
            raise ValidationError("pinned local sandbox image unavailable")
        payload = json.dumps({"code": code, "grid": grid(input_grid)}).encode()
        if len(payload) > self.output_bytes:
            raise ValidationError("SDG program input exceeds bound")
        scratch = Path(".irisx") / "nvarc-sdg-sandbox"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            root = Path(temp)
            stdout, stderr, cid = root / "stdout", root / "stderr", root / "cid"
            with stdout.open("wb") as out, stderr.open("wb") as err:
                process = subprocess.Popen(self.command(cidfile=cid), stdin=subprocess.PIPE,
                                           stdout=out, stderr=err)
                assert process.stdin is not None
                process.stdin.write(payload)
                process.stdin.close()
                started = time.monotonic()
                while process.poll() is None:
                    if stdout.stat().st_size > self.output_bytes or stderr.stat().st_size > self.output_bytes:
                        self._stop_container(process, cid)
                        raise ValidationError("SDG sandbox output exceeded bound")
                    if time.monotonic() - started >= self.wall_seconds:
                        self._stop_container(process, cid)
                        raise ValidationError("SDG sandbox wall time exceeded")
                    time.sleep(0.02)
            if (process.returncode or stdout.stat().st_size > self.output_bytes or
                    stderr.stat().st_size):
                raise ValidationError("SDG sandbox failed or output exceeded bound")
            return grid(json.loads(stdout.read_bytes()))

    @staticmethod
    def _stop_container(process: subprocess.Popen[Any], cid: Path) -> None:
        if cid.is_file():
            subprocess.run(["docker", "rm", "-f", cid.read_text().strip()],
                           capture_output=True, timeout=5, check=False)
        process.kill()
        process.wait(timeout=5)
