"""Pinned tokenizer-only context measurements on authored, non-proof fixtures.

This does not adopt a completion cap, freeze a panel, load weights, execute Lean,
or qualify model/TPU performance. Run with task Python -P -s -B and seed zero.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from common import atomic_json, digest, file_digest
from controller import solver_view

FILES = ("config.json", "tokenizer.json", "tokenizer_config.json")
FEEDBACK_PREFIX = "Repair the same statement using this tool feedback:\n"


def retrieve(candidate, destination, deadline):
    """Public HTTPS only; no Hub client, authentication, weights or remote code."""
    destination.mkdir(parents=True, exist_ok=True)
    if set(p.name for p in destination.iterdir()) - set(FILES):
        raise ValueError("Unexpected files in tokenizer-only directory")
    revision = candidate["tokenizer_revision"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Full immutable tokenizer revision required")
    pinned = {entry["path"]: entry for entry in candidate["files"]}
    receipts = []
    for name in FILES:
        expected = pinned[name]
        path = destination / name
        if path.is_symlink():
            raise ValueError("Tokenizer asset symlink forbidden")
        url = f"https://huggingface.co/{candidate['repo_id']}/resolve/{revision}/{name}"
        start = time.monotonic()
        network_bytes = 0
        cached = path.exists()
        if not cached:
            request = urllib.request.Request(url, headers={"User-Agent": "IRIS-X-MATH-002-context-control"})
            chunks = []
            with urllib.request.urlopen(request, timeout=min(30, max(1, deadline - start))) as response:
                if not response.url.startswith("https://"):
                    raise ValueError("HTTPS redirect required")
                while chunk := response.read(1024 * 1024):
                    network_bytes += len(chunk)
                    if network_bytes > expected["bytes"] or time.monotonic() > deadline:
                        raise ValueError("Pinned asset size or download deadline exceeded")
                    chunks.append(chunk)
            content = b"".join(chunks)
            if len(content) != expected["bytes"] or hashlib.sha256(content).hexdigest() != expected["sha256"]:
                raise ValueError("Downloaded tokenizer asset identity mismatch")
            path.write_bytes(content)
        if path.stat().st_size != expected["bytes"] or file_digest(path) != expected["sha256"]:
            raise ValueError("Local tokenizer asset identity mismatch")
        receipts.append({**expected, "url": url, "cache_hit": cached,
                         "network_bytes": network_bytes, "wall_seconds": time.monotonic() - start})
    return receipts


def authored_problem(size):
    """Only text for tokenization: no reference proof or verified problem claim."""
    declaration = ("theorem irisx_context_fixture " + " ".join(
        f"(x{i} : Nat) (h{i} : x{i} <= x{i} + 7)" for i in range(size)) +
        " : " + " + ".join(f"x{i}" for i in range(size)) + " <= " +
        " + ".join(f"x{i}" for i in range(size)) + " + 7")
    statement = {"id": f"authored-context-{size}", "imports": ["Mathlib.Tactic.Omega"],
                 "declaration": declaration, "fidelity": "authored_tokenization_only_not_reviewed"}
    statement["sha256"] = digest({k: statement[k] for k in ("id", "imports", "declaration", "fidelity")})
    return {"id": statement["id"], "natural_language":
            "Authored capacity fixture only. Prove the fixed displayed inequality. "
            "No proof, evaluator answer, or benchmark material is supplied.",
            "answer_mode": "proof_only", "statement": statement}


def token_ids(tokenizer, text):
    return tokenizer.encode(text, add_special_tokens=False)


def synthetic_candidate(tokenizer, count):
    """Candidate-shaped, deliberately non-proof text at an exact raw token length."""
    for unit in (" placeholder", " draft", " x", " a"):
        repeats = count
        for _ in range(12):
            text = json.dumps({"answer": None, "proof_body": "AUTHORED_NONPROOF" + unit * repeats})
            actual = len(token_ids(tokenizer, text))
            if actual == count:
                return text
            repeats += count - actual
            if repeats < 0:
                break
    raise ValueError("Cannot construct exact-length authored candidate")


def bounded_feedback(tokenizer, text, budget):
    """Experiment-only prefix policy; not installed in the scoring controller."""
    ids = token_ids(tokenizer, text)[:budget]
    while True:
        prefix = tokenizer.decode(ids, skip_special_tokens=False)
        if len(token_ids(tokenizer, prefix)) <= budget:
            return prefix
        ids = ids[:-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--download-timeout", type=int, default=180)
    parser.add_argument("--prior-acquisition-report", type=Path)
    args = parser.parse_args()
    start, cpu_start = time.monotonic(), time.process_time()
    begun = datetime.now(timezone.utc).isoformat()
    if not (os.environ.get("PYTHONHASHSEED") == "0" and sys.flags.hash_randomization == 0
            and sys.flags.safe_path and sys.flags.no_user_site and sys.flags.dont_write_bytecode):
        raise RuntimeError("Controlled seed-zero -P -s -B startup required")
    repo = ROOT.parents[2]
    source_base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    sources = [Path(__file__), ROOT / "protocol.json", ROOT / "model-candidates.json",
               ROOT / "controller.py", ROOT / "common.py", ROOT / "model_adapter.py"]
    source_hashes = {p.relative_to(repo).as_posix(): file_digest(p) for p in sources}
    spec = json.loads((ROOT / "model-candidates.json").read_text(encoding="utf-8"))
    protocol = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))
    packages = {name: importlib.metadata.version(name) for name in
                ("transformers", "tokenizers", "huggingface-hub", "Jinja2")}
    for name, version in packages.items():
        if version != spec["runtime"]["packages"][name]:
            raise RuntimeError("Tokenizer package pin mismatch: " + name)
    downloads = {}
    for candidate in spec["candidates"]:
        downloads[candidate["key"]] = retrieve(candidate, args.asset_dir / candidate["key"],
                                               start + args.download_timeout)
    # The only network stage is complete before importing/tokenizing. No model
    # backends or credentials are needed by the pinned fast tokenizer.
    overrides = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "USE_TORCH": "0",
                 "USE_TF": "0", "USE_FLAX": "0", "TOKENIZERS_PARALLELISM": "false"}
    os.environ.update(overrides)
    from transformers import AutoTokenizer

    controls, observations = [], []
    def check(name, condition):
        controls.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    for candidate in spec["candidates"]:
        tick = time.monotonic()
        tokenizer = AutoTokenizer.from_pretrained(args.asset_dir / candidate["key"],
                                                  trust_remote_code=False, local_files_only=True)
        template_hash = hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()
        check(candidate["key"] + ":template_identity", template_hash == candidate["chat_template_sha256"])
        check(candidate["key"] + ":fast_tokenizer", tokenizer.is_fast)
        raw_feedback = ("Authored tool diagnostic: 未解決目標：αβγ≤δ； " * 200)[:4000]
        feedback = bounded_feedback(tokenizer, raw_feedback, 512)
        check(candidate["key"] + ":feedback_token_bound", len(token_ids(tokenizer, feedback)) <= 512)
        previous = {cap: synthetic_candidate(tokenizer, cap) for cap in (2048, 4096)}
        cases = []
        for size in (1, 16, 64, 256):
            problem = solver_view(authored_problem(size))
            base = [{"role": "system", "content": protocol["system_prompt"]},
                    {"role": "user", "content": json.dumps(problem, ensure_ascii=False)}]
            for cap in (4096, 2048):
                for arm in ("independent", "repair"):
                    prompt = list(base)
                    if arm == "repair":
                        prompt += [{"role": "assistant", "content": previous[cap]},
                                   {"role": "user", "content": FEEDBACK_PREFIX + feedback}]
                    cases.append((f"parameters_{size}_{arm}_{cap}_feedback512", size, arm, cap, prompt))
            if size == 64:
                prompt = base + [{"role": "assistant", "content": previous[2048]},
                                 {"role": "user", "content": FEEDBACK_PREFIX + raw_feedback}]
                cases.append(("parameters_64_repair_2048_feedback4000chars", size, "repair", 2048, prompt))
        records = []
        for name, size, arm, cap, messages in cases:
            ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                                enable_thinking=False)
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                                     enable_thinking=False)
            record = {"id": name, "authored_parameter_count": size, "arm_shape": arm,
                      "completion_cap": cap, "prompt_tokens": len(ids), "total_reserved_tokens": len(ids) + cap,
                      "context_length": 8192, "fits": len(ids) + cap <= 8192,
                      "slack_tokens": 8192 - len(ids) - cap, "messages_sha256": digest(messages),
                      "rendered_utf8_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                      "token_ids_sha256": digest(ids),
                      "previous_candidate_raw_tokens": cap if arm == "repair" else 0,
                      "feedback_content_tokens": len(token_ids(tokenizer, messages[-1]["content"][len(FEEDBACK_PREFIX):]))
                      if arm == "repair" else 0}
            records.append(record)
        lookup = {r["id"]: r for r in records}
        check(candidate["key"] + ":4096_full_previous_exceeds_context",
              not lookup["parameters_1_repair_4096_feedback512"]["fits"])
        check(candidate["key"] + ":2048_authored_64_parameter_repair_fits",
              lookup["parameters_64_repair_2048_feedback512"]["fits"])
        check(candidate["key"] + ":oversize_statement_still_fails",
              not lookup["parameters_256_repair_2048_feedback512"]["fits"])
        behavior_messages = [{"role": "user", "content": "Authored capacity fixture"},
                             {"role": "assistant", "content": "<think>AUTHORED_REASONING_MARKER</think>AUTHORED_DRAFT_MARKER"},
                             {"role": "user", "content": "Authored feedback"}]
        rendered = tokenizer.apply_chat_template(behavior_messages, tokenize=False, add_generation_prompt=True,
                                                 enable_thinking=False)
        check(candidate["key"] + ":historical_think_content_removed", "AUTHORED_REASONING_MARKER" not in rendered)
        check(candidate["key"] + ":historical_draft_retained", "AUTHORED_DRAFT_MARKER" in rendered)
        check(candidate["key"] + ":empty_thinking_generation_prefix",
              rendered.endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n"))
        observations.append({"candidate": candidate["key"], "repo_id": candidate["repo_id"],
                             "tokenizer_revision": candidate["tokenizer_revision"],
                             "chat_template_sha256": template_hash, "tokenizer_class": type(tokenizer).__name__,
                             "files_verified_before_load": downloads[candidate["key"]],
                             "feedback_raw_chars": len(raw_feedback),
                             "feedback_raw_tokens": len(token_ids(tokenizer, raw_feedback)),
                             "feedback_bounded_tokens": len(token_ids(tokenizer, feedback)),
                             "cases": records, "maximum_observed_total_reserved_tokens": max(r["total_reserved_tokens"] for r in records),
                             "maximum_observed_fitting_repair_2048_prompt_tokens": max(r["prompt_tokens"] for r in records
                                 if r["fits"] and r["arm_shape"] == "repair" and r["completion_cap"] == 2048),
                             "maximum_observed_fitting_repair_2048_prompt_tokens_feedback_at_most512": max(r["prompt_tokens"] for r in records
                                 if r["fits"] and r["arm_shape"] == "repair" and r["completion_cap"] == 2048 and r["feedback_content_tokens"] <= 512),
                             "template_behavior_rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                             "tokenization_wall_seconds": time.monotonic() - tick})
    check("candidate_case_counts_equal", len(observations[0]["cases"]) == len(observations[1]["cases"]))
    check("candidate_full_prompt_encodings_equal", [r["token_ids_sha256"] for r in observations[0]["cases"]]
          == [r["token_ids_sha256"] for r in observations[1]["cases"]])
    check("sources_unchanged_during_run", all(file_digest(repo / path) == value for path, value in source_hashes.items()))
    check("no_model_backend_imported", not {"torch", "jax", "tensorflow", "flax"}.intersection(sys.modules))
    prior_acquisition = None
    if args.prior_acquisition_report:
        prior = json.loads(args.prior_acquisition_report.read_text(encoding="utf-8"))
        def asset_identities(rows):
            return [(row["repo_id"], row["tokenizer_revision"],
                     [(f["path"], f["bytes"], f["sha256"]) for f in row["files_verified_before_load"]]) for row in rows]
        check("prior_acquisition_exact_assets", asset_identities(prior["observations"]) == asset_identities(observations))
        prior_acquisition = {"receipt_path": str(args.prior_acquisition_report),
                             "receipt_sha256": file_digest(args.prior_acquisition_report),
                             "started_at_utc": prior["started_at_utc"], "cost": prior["cost"]}
    report = {"format": "irisx.math.context-controls.v1", "task": "MATH-002", "started_at_utc": begun,
              "source_base_sha": source_base, "tested_code_commit": None,
              "tested_source_scope": "Working bytes, including this new uncommitted control script; bound by source_hashes. No tested-commit claim.",
              "source_hashes": source_hashes, "command": [sys.executable, "-P", "-s", "-B", str(Path(__file__).resolve()), *sys.argv[1:]],
              "environment": {"python": platform.python_version(), "platform": platform.platform(), "packages": packages,
                              "hash_randomization": sys.flags.hash_randomization, "safe_path": sys.flags.safe_path,
                              "no_user_site": sys.flags.no_user_site, "dont_write_bytecode": sys.flags.dont_write_bytecode,
                              "explicit_overrides": {"PYTHONHASHSEED": "0", **overrides}},
              "exit_code": 0, "controls_count": len(controls), "controls": controls,
              "observation_count": sum(len(o["cases"]) for o in observations), "observations": observations,
              "prior_acquisition": prior_acquisition,
              "cost": {"wall_seconds": time.monotonic() - start, "cpu_seconds": time.process_time() - cpu_start,
                       "network_bytes": sum(f["network_bytes"] for rows in downloads.values() for f in rows),
                       "verified_local_asset_bytes": sum(f["bytes"] for rows in downloads.values() for f in rows),
                       "model_generations": 0, "weight_bytes": 0, "tpu_seconds": 0, "lean_executions": 0},
              "scope": "Implementer tokenizer engineering experiment; authored invalid proof placeholders only. No benchmark, gold answers, weights, model generation, Lean, TPU or independent verification.",
              "limitations": ["The fixture grid maximum is observed, not a universal bound over future statements or model text.",
                              "2048 is provisional and not adopted; protocol/controller remain unchanged at 4096 and 4000 feedback characters.",
                              "A future scoring rule must check the exact full templated prompt <=6144 with a shared 2048 cap, predeclare feedback/history overflow policy, and never truncate the fixed statement.",
                              "Actual target-model TPU parity, long-prefill/decode cost, 600-second arm feasibility and panel qualification remain open."]}
    atomic_json(args.report, report)
    print(json.dumps({"controls": len(controls), "observations": report["observation_count"],
                      "network_bytes": report["cost"]["network_bytes"], "wall_seconds": report["cost"]["wall_seconds"],
                      "report": str(args.report)}, indent=2))


if __name__ == "__main__":
    main()
