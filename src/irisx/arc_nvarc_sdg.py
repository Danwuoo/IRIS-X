"""Resumable NVARC SDG stages and a fail-closed generated-program boundary."""

from __future__ import annotations

import json
import ast
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Mapping, Protocol

from .arc_nvarc_runtime import atomic_json
from .canonical import canonical_bytes, digest_value
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


def _response_text(value: Any) -> str:
    result = value.get("content", value.get("text")) if isinstance(value, dict) else value
    if not isinstance(result, str) or not result.strip():
        raise ValidationError("SDG teacher response is empty or not text")
    return result


def extract_teacher_program(raw: str, function: str) -> str:
    """Parse complete source only; generated code is never executed here."""
    if raw.count("```") % 2:
        raise ValidationError("SDG teacher program has an unclosed code block")
    blocks = re.findall(r"```(?:python)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
    candidates = []
    for code in blocks or [raw]:
        try:
            tree = ast.parse(code.strip())
        except SyntaxError as error:
            raise ValidationError("SDG teacher program is not complete Python") from error
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == function]
        if functions:
            if len(functions) != 1:
                raise ValidationError("SDG teacher program repeats its entry function")
            args = functions[0].args
            positional = args.posonlyargs + args.args
            if (len(positional) != 1 or args.vararg or args.kwarg or args.kwonlyargs or
                    positional[0].arg != ("seed" if function == "generate_puzzle_input" else "input_grid")):
                raise ValidationError("SDG teacher entry signature differs")
            candidates.append(code.strip())
    if len(candidates) != 1:
        raise ValidationError("SDG teacher response lacks one unambiguous program function")
    return candidates[0]


def validate_teacher_response(stage: str, response: dict[str, Any]) -> None:
    """A completed model call may still be rejected as an unusable stage."""
    if response.get("finish_reason") != "eos":
        raise ValidationError("teacher output did not finish with EOS")
    raw = response.get("text", "").strip()
    if not raw or "<think>" in raw or "</think>" in raw:
        raise ValidationError("teacher final content is absent or contains thinking markers")
    if stage in {"input-logic", "output-logic"}:
        content = extract_teacher_program(raw, "generate_puzzle_" +
                                          ("input" if stage == "input-logic" else "output"))
    elif stage in {"summary", "mix"}:
        if "```" in raw:
            raise ValidationError("teacher description contains an unexpected code block")
        content = raw
    else:
        raise ValidationError("unknown validated teacher stage")
    response["content"] = content
    response["content_sha256"] = hashlib.sha256(content.encode()).hexdigest()
    response["validation_profile"] = "qwen-direct-complete-v1"


def render_source_teacher_prompt(stage: str, item: Mapping[str, Any], template: str) -> str:
    """Fill the four pinned v1 templates from public demos and prior replies."""
    history = item.get("stage_responses", {})
    if stage == "summary":
        demos = item.get("train_demos", [])
        if len(demos) < 2:
            raise ValidationError("SDG summary requires two public train demonstrations")
        values = {"INPUT_IMAGE1": json.dumps(demos[0]["input"]),
                  "OUTPUT_IMAGE1": json.dumps(demos[0]["output"]),
                  "INPUT_IMAGE2": json.dumps(demos[1]["input"]),
                  "OUTPUT_IMAGE2": json.dumps(demos[1]["output"]),
                  "USER_COMMENTS": item.get("source_comments", "No source comments supplied.")}
    elif stage == "mix":
        values = {"PUZZLE1": _response_text(history["summary"]),
                  "PUZZLE2": item["second_description"]}
    elif stage == "input-logic":
        values = {"PUZZLE": _response_text(history["mix"])}
    elif stage == "output-logic":
        values = {"PUZZLE": _response_text(history["mix"]),
                  "INPUT_CODE": _response_text(history["input-logic"])}
    else:
        raise ValidationError("SDG teacher stage differs")
    for key, value in values.items():
        if not isinstance(value, str) or not value:
            raise ValidationError("SDG teacher source value is empty")
        if "{" + key + "}" not in template:
            raise ValidationError("pinned source prompt placeholder differs: " + key)
        template = template.replace("{" + key + "}", value)
    return template


class BoundedLocalHFTeacher:
    """Offline text teacher adapter. Model/provider execution needs owner approval.

    The caller supplies an already loaded full-vocabulary model/tokenizer and
    exact material digest. The compact 16-symbol solver model is invalid here.
    """

    billed_calls = 1

    def __init__(self, model: Any, tokenizer: Any, *, model_material_digest: str,
                 maximum_input_tokens: int, maximum_output_tokens: int,
                 maximum_total_tokens: int,
                 stage_limits: Mapping[str, Mapping[str, int]] | None = None,
                 enable_thinking: bool | None = None,
                 require_complete: bool = False) -> None:
        if (not model_material_digest.startswith("sha256:") or
                min(maximum_input_tokens, maximum_output_tokens, maximum_total_tokens) < 1 or
                maximum_input_tokens + maximum_output_tokens > maximum_total_tokens):
            raise ValidationError("local SDG teacher bounds differ")
        self.model, self.tokenizer = model, tokenizer
        self.model_material_digest = model_material_digest
        self.maximum_input_tokens = maximum_input_tokens
        self.maximum_output_tokens = maximum_output_tokens
        self.maximum_total_tokens = maximum_total_tokens
        self.reserved_tokens = 0
        self.stage_limits = dict(stage_limits) if stage_limits is not None else None
        self.enable_thinking, self.require_complete = enable_thinking, require_complete
        if self.stage_limits is not None and (
                set(self.stage_limits) != set(STAGES[:4]) or
                any(set(limits) != {"input", "output"} or
                    any(type(v) is not int or v < 1 for v in limits.values())
                    for limits in self.stage_limits.values()) or
                sum(sum(limits.values()) for limits in self.stage_limits.values()) != maximum_total_tokens):
            raise ValidationError("teacher stage token reservations differ")
        if require_complete and (enable_thinking is not False or self.stage_limits is None):
            raise ValidationError("validated teacher requires explicit direct mode and stage budgets")
        identity = {
            "model_material_digest": model_material_digest,
            "maximum_input_tokens": maximum_input_tokens,
            "maximum_output_tokens": maximum_output_tokens,
            "maximum_total_tokens": maximum_total_tokens}
        if stage_limits is not None or enable_thinking is not None or require_complete:
            identity.update(stage_limits=self.stage_limits, enable_thinking=enable_thinking,
                            validation_profile="qwen-direct-complete-v1" if require_complete else None,
                            do_sample=False)
        self.identity = "offline-local-hf:" + digest_value(identity)

    def validate_response(self, stage: str, value: dict[str, Any]) -> None:
        if self.require_complete:
            validate_teacher_response(stage, value)

    def complete(self, stage: str, item: Mapping[str, Any], prompt: str) -> dict[str, Any]:
        import torch

        limits = (self.stage_limits[stage] if self.stage_limits is not None else
                  {"input": self.maximum_input_tokens, "output": self.maximum_output_tokens})
        if self.reserved_tokens + limits["input"] + limits["output"] > self.maximum_total_tokens:
            raise ValidationError("local SDG teacher total token ceiling exhausted")
        rendered = render_source_teacher_prompt(stage, item, prompt)
        template_options = {} if self.enable_thinking is None else {"enable_thinking": self.enable_thinking}
        tokens = self.tokenizer.apply_chat_template(
            [{"role": "user", "content": rendered}], tokenize=True,
            add_generation_prompt=True, return_tensors="pt", return_dict=False, **template_options)
        if not isinstance(tokens, torch.Tensor) or tokens.ndim != 2 or tokens.shape[0] != 1:
            raise ValidationError("local SDG teacher chat template did not return one token tensor")
        input_tokens = int(tokens.shape[-1])
        if input_tokens > limits["input"]:
            raise ValidationError("local SDG teacher input token ceiling exceeded")
        # Reserve the full call before model generation; failure consumes it.
        self.reserved_tokens += limits["input"] + limits["output"]
        with torch.inference_mode():
            generated = self.model.generate(tokens.to(self.model.device),
                                            max_new_tokens=limits["output"],
                                            do_sample=False,
                                            pad_token_id=self.tokenizer.eos_token_id)
        output_ids = generated[0, input_tokens:]
        value = self.tokenizer.decode(output_ids, skip_special_tokens=True)
        if not value.strip():
            raise ValidationError("local SDG teacher returned no text")
        result = {"text": value, "input_tokens": input_tokens,
                "output_tokens": int(output_ids.numel()),
                "model_material_digest": self.model_material_digest}
        if self.require_complete:
            eos = getattr(getattr(self.model, "generation_config", None), "eos_token_id", None)
            eos = eos if eos is not None else self.tokenizer.eos_token_id
            eos_ids = eos if isinstance(eos, (list, tuple)) else [eos]
            result.update(output_token_ids=output_ids.detach().cpu().tolist(),
                          finish_reason=("eos" if output_ids.numel() and int(output_ids[-1]) in eos_ids
                                         else "length" if output_ids.numel() == limits["output"] else "other"),
                          enable_thinking=False)
        return result


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
        if (ledger.get("format") != "irisx/nvarc-sdg-stage" or
                ledger.get("stage") != stage or
                not isinstance(ledger.get("records"), dict) or
                not set(ledger["records"]).issubset(identifiers) or
                type(ledger.get("reserved_calls")) is not int or
                not 0 <= ledger["reserved_calls"] <= maximum_calls):
            raise ValidationError("SDG resumed stage ledger is invalid")
        by_id = {item["record_id"]: item for item in inputs}
        costs = 0
        for key, record in ledger["records"].items():
            if (not isinstance(record, dict) or
                    record.get("input_digest") != digest_value(by_id[key]) or
                    record.get("status") not in {"pending", "failed", "complete", "rejected"} or
                    type(record.get("provider_calls")) is not int or
                    record["provider_calls"] not in (0, 1)):
                raise ValidationError("SDG resumed stage record differs")
            if record["status"] in {"complete", "rejected"} and (
                    "response" not in record or
                    record.get("response_digest") != digest_value(record["response"])):
                raise ValidationError("SDG resumed response digest differs")
            costs += record["provider_calls"]
        if costs != ledger["reserved_calls"]:
            raise ValidationError("SDG resumed call accounting differs")
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
            status = "complete"
            if hasattr(provider, "validate_response"):
                try:
                    provider.validate_response(stage, value)
                except ValidationError as error:
                    status = "rejected"
                    ledger["records"][key]["rejection_reason"] = str(error)
            ledger["records"][key].update({"status": status, "response": value,
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
        records = [{**item,
                    "stage_responses": {**item.get("stage_responses", {}),
                                        stage: ledger["records"][item["record_id"]]["response"]}}
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


class WSLNamespaceProgramExecutor:
    """Generated Python runs in WSL user/mount/PID/network namespaces and chroot.

    The namespace script bind mounts only read-only /usr and /dev/null into a
    disposable tmpfs root, then enforces address-space, process, CPU and wall
    limits. The host never imports or executes the submitted Python.
    """

    def __init__(self, *, distribution: str = "Ubuntu-24.04", wall_seconds: int = 15,
                 output_bytes: int = 65536) -> None:
        if (not re.fullmatch(r"[A-Za-z0-9.-]+", distribution) or
                not 8 <= wall_seconds <= 60 or not 1 <= output_bytes <= 65536):
            raise ValidationError("WSL SDG sandbox bounds invalid")
        self.distribution, self.wall_seconds, self.output_bytes = distribution, wall_seconds, output_bytes

    def command(self) -> list[str]:
        script = Path(__file__).resolve().parents[2] / "tools/nvarc_sdg_namespace.sh"
        if not script.is_file():
            raise ValidationError("WSL namespace launcher missing")
        resolved = script.resolve()
        if resolved.drive.lower() != "c:":
            raise ValidationError("WSL namespace launcher needs a C: workspace path")
        linux_path = "/mnt/c" + resolved.as_posix()[2:]
        return ["wsl", "-d", self.distribution, "--", "sh", linux_path]

    def execute_entry(self, code: str, entry: str, *, input_grid: Any | None = None,
                      seed: int | None = None) -> Any:
        from .arc_nvarc_data import grid

        if not shutil.which("wsl") or entry not in {"transform", "generate_puzzle_input",
                                                       "generate_puzzle_output"}:
            raise ValidationError("WSL sandbox unavailable or SDG entry unknown")
        if not isinstance(code, str) or not code or len(code.encode()) > self.output_bytes:
            raise ValidationError("SDG program exceeds input bound")
        if entry == "generate_puzzle_input":
            if type(seed) is not int or not 0 <= seed <= 1000000:
                raise ValidationError("SDG input generation seed differs")
            argument = {"seed": seed}
        else:
            argument = {"grid": grid(input_grid)}
        payload = json.dumps({"code": code, "entry": entry, **argument}).encode()
        scratch = Path(".irisx") / "nvarc-sdg-sandbox"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            stdout, stderr = Path(temp) / "stdout", Path(temp) / "stderr"
            with stdout.open("wb") as out, stderr.open("wb") as err:
                process = subprocess.Popen(self.command(), stdin=subprocess.PIPE,
                                           stdout=out, stderr=err)
                assert process.stdin is not None
                process.stdin.write(payload)
                process.stdin.close()
                started = time.monotonic()
                while process.poll() is None:
                    if stdout.stat().st_size > self.output_bytes or stderr.stat().st_size > self.output_bytes:
                        process.kill()
                        process.wait(timeout=5)
                        raise ValidationError("WSL SDG sandbox output exceeded bound")
                    if time.monotonic() - started >= self.wall_seconds:
                        process.kill()
                        process.wait(timeout=5)
                        raise ValidationError("WSL SDG sandbox wall time exceeded")
                    time.sleep(0.02)
            if process.returncode or stderr.stat().st_size or stdout.stat().st_size > self.output_bytes:
                raise ValidationError("WSL SDG sandbox failed or output exceeded bound")
            return grid(json.loads(stdout.read_bytes()))

    def execute(self, code: str, input_grid: Any) -> Any:
        return self.execute_entry(code, "transform", input_grid=input_grid)


def replay_pinned_ten_stage_sdg(fixture_path: Path, source_root: Path,
                                output: Path, executor: WSLNamespaceProgramExecutor) -> dict[str, Any]:
    """Replay ten NVARC stages with saved responses and real isolated Python.

    Caller first verifies the complete pinned source tree. Source cleaning and
    validation functions are trusted code; only generated functions enter WSL.
    """
    from .arc_nvarc_data import source_sdg_messages
    from .arc_nvarc_upstream import sdg_build_datasets

    if output.exists():
        raise ValidationError("SDG replay output must be new")
    fixture = json.loads(fixture_path.read_bytes())
    if fixture.get("format") != "irisx/nvarc-sdg-saved-fixture-v1" or len(fixture.get("seeds", [])) != 5:
        raise ValidationError("saved SDG fixture differs")
    script_root = source_root / "NVARC/SDG/scripts"
    prompt_root = source_root / "NVARC/SDG/prompts"

    def checked_function(path: Path, names: tuple[str, ...]) -> dict[str, Any]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        if set(node.name for node in nodes) != set(names):
            raise ValidationError("source SDG cleaning function missing")
        namespace: dict[str, Any] = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
        return namespace

    h_arc = checked_function(script_root / "h_arc_clean.py", ("clean_solution",))
    barc = checked_function(script_root / "utils_barc.py", ("clean_comments", "clean_description"))
    cleaned_h_arc = h_arc["clean_solution"](fixture["h_arc_solution"])
    cleaned_barc = barc["clean_description"](fixture["barc_comments"])
    if not cleaned_h_arc or not cleaned_barc:
        raise ValidationError("SDG source cleaning produced no description")
    prompt_names = {"summary": "summary_v1.md", "mix": "mix_v1.md",
                    "input-logic": "generate_puzzle_input.md",
                    "output-logic": "generate_puzzle_output.md"}
    prompts = {stage: (prompt_root / name).read_text(encoding="utf-8")
               for stage, name in prompt_names.items()}
    prompt_hashes = {stage: hashlib.sha256(prompts[stage].encode()).hexdigest()
                     for stage in prompt_names}
    output.mkdir(parents=True)
    record = {"record_id": fixture["record_id"], "parent_id": fixture["record_id"],
              "source_id": "saved-replay-fixture", "h_arc": cleaned_h_arc, "barc": cleaned_barc}
    ledgers = run_teacher_pipeline([record], prompts, SavedTeacher(fixture["responses"]),
                                   output / "teacher-ledgers", seed=24, maximum_calls=0)
    if ledgers["reserved_calls"] or len(ledgers["stages"]) != 4:
        raise ValidationError("saved SDG replay did not complete teacher stages")
    response = {stage: ledgers["stages"][stage]["records"][fixture["record_id"]]["response"]
                for stage in prompt_names}
    inputs = [executor.execute_entry(response["input-logic"], "generate_puzzle_input", seed=seed)
              for seed in fixture["seeds"]]
    outputs = [executor.execute_entry(response["output-logic"], "generate_puzzle_output",
                                      input_grid=value) for value in inputs]
    pairs = [{"input": input_grid, "output": output_grid}
             for input_grid, output_grid in zip(inputs, outputs)]
    source = sdg_build_datasets()
    accepted = all(source.validate_grid(item["input"]) and source.validate_grid(item["output"])
                   for item in pairs) and source.validate_pairs(pairs)
    if not accepted:
        raise ValidationError("source SDG pair/filter rejected saved replay")
    augmented = source_sdg_messages(pairs, seed=2400, augment=True)
    stages = ["h-arc-clean", "barc-clean", "summary", "mix", "input-logic",
              "output-logic", "execute-input", "execute-output", "pair-filter", "dataset-augment"]
    report = {"format": "irisx/nvarc-m3-sdg-replay-v1", "stages": stages,
              "stage_count": len(stages), "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
              "prompt_sha256": prompt_hashes,
              "saved_response_digests": {key: digest_value(value) for key, value in response.items()},
              "sandbox": "WSL2 user/mount/PID/network namespace + chroot + resource limits",
              "generated_program_invocations": 10, "teacher_calls": 0,
              "pair_count": len(pairs), "source_pair_filter_passed": accepted,
              "augmented_message_count": len(augmented["messages"]),
              "augmented_messages_digest": digest_value(augmented["messages"]),
              "generated_puzzle_claim": False, "fixture_only": True}
    (output / "report.json").write_bytes(canonical_bytes(report, newline=True))
    return report


def replay_teacher_program_ledgers(ledger_root: Path, seed_path: Path, output: Path,
                                   executor: WSLNamespaceProgramExecutor) -> dict[str, Any]:
    """Turn retained teacher program replies into isolated pairs, never host exec.

    This post-retrieval route has six stages. HARC/BARC cleaning is specific to
    the separate ten-stage fixture replay and is not claimed for this ARC seed.
    """
    from .arc_nvarc_data import source_sdg_messages
    from .arc_nvarc_upstream import sdg_build_datasets

    if output.exists():
        raise ValidationError("new SDG teacher replay output required")
    seed = json.loads(seed_path.read_bytes())
    if seed.get("format") != "irisx/nvarc-m3-teacher-seed-v1":
        raise ValidationError("SDG teacher seed format differs")
    record_id = seed["record"]["record_id"]
    responses = {}
    for stage in STAGES[:4]:
        ledger = json.loads((ledger_root / f"{stage}.json").read_bytes())
        record = ledger.get("records", {}).get(record_id)
        if (ledger.get("stage") != stage or record is None or
                record.get("status") != "complete" or
                record.get("response_digest") != digest_value(record.get("response"))):
            raise ValidationError("SDG teacher saved response binding differs")
        responses[stage] = _response_text(record["response"])

    input_code = extract_teacher_program(responses["input-logic"], "generate_puzzle_input")
    output_code = extract_teacher_program(responses["output-logic"], "generate_puzzle_output")
    seeds = list(range(5))
    inputs = [executor.execute_entry(input_code, "generate_puzzle_input", seed=value)
              for value in seeds]
    outputs = [executor.execute_entry(output_code, "generate_puzzle_output",
                                      input_grid=value) for value in inputs]
    pairs = [{"input": before, "output": after} for before, after in zip(inputs, outputs)]
    source = sdg_build_datasets()
    accepted = all(source.validate_grid(pair["input"]) and source.validate_grid(pair["output"])
                   for pair in pairs) and source.validate_pairs(pairs)
    if not accepted:
        raise ValidationError("source SDG pair/filter rejected teacher output")
    augmented = source_sdg_messages(pairs, seed=2400, augment=True)
    report = {"format": "irisx/nvarc-m3-teacher-program-replay-v1",
              "seed_sha256": hashlib.sha256(seed_path.read_bytes()).hexdigest(),
              "response_digests": {stage: digest_value(value) for stage, value in responses.items()},
              "input_code_sha256": hashlib.sha256(input_code.encode()).hexdigest(),
              "output_code_sha256": hashlib.sha256(output_code.encode()).hexdigest(),
              "generated_program_invocations": 10, "pair_count": len(pairs),
              "source_pair_filter_passed": accepted,
              "augmented_messages_digest": digest_value(augmented["messages"]),
              "contains_evaluator_truth": False,
              "claim": "six-stage ARC-seeded teacher program replay; no HARC/BARC cleaning parity"}
    output.mkdir(parents=True)
    artifacts = {"pairs.json": {"parent_ids": seed.get("parent_ids", []), "seeds": seeds, "pairs": pairs},
                 "messages.json": augmented,
                 "programs.json": {"input": input_code, "output": output_code}}
    report["artifacts"] = {}
    report["ledger_sha256"] = {stage: hashlib.sha256((ledger_root / f"{stage}.json").read_bytes()).hexdigest()
                                for stage in STAGES[:4]}
    for name, value in artifacts.items():
        payload = canonical_bytes(value, newline=True)
        (output / name).write_bytes(payload)
        report["artifacts"][name] = {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
    (output / "report.json").write_bytes(canonical_bytes(report, newline=True))
    return report
