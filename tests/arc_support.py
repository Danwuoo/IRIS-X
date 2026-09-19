from __future__ import annotations

from pathlib import Path
from typing import Any

from irisx.arc_agi2 import SourceProfile, create_source_provenance
from irisx.canonical import digest_bytes, write_json
from irisx.contracts import CandidateConfiguration, load_contract
from irisx.kaggle import build_model_package, create_model_provenance


def make_arc_source(root: Path, *, training_count: int = 2, evaluation_count: int = 120) -> SourceProfile:
    upstream = root / "upstream"
    (upstream / "data/training").mkdir(parents=True)
    (upstream / "data/evaluation").mkdir(parents=True)
    (upstream / "LICENSE").write_text("Apache License\n", encoding="utf-8")
    (upstream / "readme.md").write_text("Synthetic official-shape fixture for offline tests.\n", encoding="utf-8")
    for index in range(training_count):
        value = index % 10
        write_json(
            upstream / f"data/training/t{index:04d}.json",
            {
                "train": [{"input": [[value]], "output": [[(value + 1) % 10]]}],
                "test": [{"input": [[(value + 2) % 10]], "output": [[(value + 3) % 10]]}],
            },
        )
    (upstream / "data/training.txt").write_text(
        "\n".join(f"t{index:04d}" for index in range(training_count)) + "\n", encoding="utf-8"
    )
    for index in range(evaluation_count):
        value = index % 10
        write_json(
            upstream / f"data/evaluation/e{index:04d}.json",
            {
                "train": [{"input": [[value]], "output": [[(value + 1) % 10]]}],
                "test": [{"input": [[(value + 2) % 10]], "output": [[(value + 3) % 10]]}],
            },
        )
    (upstream / "data/evaluation.txt").write_text(
        "\n".join(f"e{index:04d}" for index in range(evaluation_count)) + "\n", encoding="utf-8"
    )
    profile = SourceProfile(training_count=training_count, evaluation_count=evaluation_count, require_git_identity=False)
    create_source_provenance(upstream, root / "provenance.json", profile=profile)
    return profile


def make_model_package(root: Path) -> Path:
    source = root / "model-source/source"
    source.mkdir(parents=True)
    write_json(source / "config.json", {"architectures": ["SyntheticQwenForCausalLM"]})
    (source / "README.md").write_text("---\nlicense: apache-2.0\n---\n", encoding="utf-8")
    (source / "model.safetensors").write_bytes(b"small synthetic model fixture")
    create_model_provenance(source, root / "model-source/provenance.json", require_git_identity=False)
    package = root / "model-package.zip"
    build_model_package(root / "model-source", package, require_git_identity=False)
    return package


def dataset_binding(slug: str) -> dict[str, Any]:
    return {"owner": "fixture-owner", "slug": slug, "version": 1, "private": True, "immutable": True}


def write_outbound_binding(root: Path, bundle_id: str = "run-001") -> Path:
    path = root / "outbound-binding.json"
    write_json(
        path,
        {
            "bundle_id": bundle_id,
            "model_dataset": dataset_binding("qwen-model"),
            "repository": {"revision": "a" * 40, "clean": True},
            "runtime_dependencies": {"python": "3.11.9", "torch": "2.8.0", "transformers": "4.57.0", "source": "bound-private-runtime"},
            "retention": {
                "model_dataset": "delete after owner review",
                "trial_dataset": "delete after verified import",
                "notebook_output": "download complete output then delete after verified import",
                "local_evidence": "retain through Domain Package verification and owner review",
            },
        },
    )
    return path


def prediction_document(trial_root: Path, configuration_name: str, passed_cases: int) -> dict[str, Any]:
    configuration = load_contract(trial_root / f"{configuration_name}.json", CandidateConfiguration)
    assert isinstance(configuration, CandidateConfiguration)
    solver = __import__("json").loads((trial_root / "solver-cases.json").read_text(encoding="utf-8"))
    cases = []
    for case_index, case in enumerate(solver["payload"]["cases"]):
        tests = []
        for test_index in range(len(case["test"])):
            expected_value = (case_index % 10 + 3) % 10
            correct = [[expected_value]]
            wrong = [[(expected_value + 1) % 10]]
            grids = [correct, wrong] if case_index < passed_cases else [wrong, wrong]
            attempts = [
                {
                    "attempt_index": attempt_index,
                    "status": "ok",
                    "grid": grid,
                    "raw_output_digest": digest_bytes(str(grid).encode("utf-8")),
                }
                for attempt_index, grid in enumerate(grids)
            ]
            tests.append({"test_index": test_index, "attempts": attempts})
        cases.append({"case_id": case["case_id"], "tests": tests})
    return {
        "format": "irisx/arc-agi-2-predictions",
        "format_version": "1.0",
        "configuration_ref": configuration.ref(),
        "cases": cases,
    }


def observations() -> dict[str, Any]:
    return {
        "format": "irisx/arc-agi-2-execution-observations",
        "format_version": "1.0",
        "hardware": {"gpu_count": 1, "gpu_model": "NVIDIA RTX PRO 6000", "gpu_memory_mib": 98304},
        "software": {"python": "3.11.9", "torch": "2.8.0", "transformers": "4.57.0"},
        "internet_disabled": True,
        "credentials_present": False,
        "network_calls": 0,
        "provider_calls": 0,
        "external_paid_cost_usd": 0,
        "evaluation_leaks": 0,
        "identity_binding_failures": 0,
        "wall_clock_seconds": 100.0,
        "gpu_seconds_state": "unknown",
        "gpu_seconds": None,
        "timeout_policy": 600,
        "seed_policy": "sha256(configuration-ref,case-id,test-index,attempt-index) reduced to uint32",
        "attempts_per_test_input": 2,
        "stop_conditions_triggered": [],
    }


def runner_logs(trial_root: Path, baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    events = []
    for label, document in (("baseline", baseline), ("candidate", candidate)):
        for case in document["cases"]:
            for test in case["tests"]:
                for attempt in test["attempts"]:
                    events.append(
                        {
                            "event": "invocation_complete",
                            "configuration": label,
                            "case_id": case["case_id"],
                            "test_index": test["test_index"],
                            "attempt_index": attempt["attempt_index"],
                            "status": attempt["status"],
                            "elapsed_seconds": 0.1,
                        }
                    )
    return {"events": events}
