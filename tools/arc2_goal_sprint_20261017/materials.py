"""Explicit, source-pinned continuation inputs; no discovery or evaluator reads.

The stdlib checks run before installation. CPU tensor/lineage checks run in the
isolated runtime. Neither check loads a base model or claims PEFT compatibility;
that remains the actual model loader's fail-closed responsibility.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil

from tools.arc2_goal_sprint_20261017.launch import regular, require, sha

FORMAT = "irisx/goal-continuation-materials-v1"
INDEX = "continuation-materials.json"
ROOTS = {"adapter_resume": "materials/adapter-resume", "curriculum": "materials/curriculum"}
MODEL_SOURCE = "qwen-lm/qwen-3/Transformers/14b/1"
MODEL_CONTRACT_SHA256 = "8d26b2f04a91147bbb5e11231f614552d36e2862af9b8d2d2b05b273805b69b0"
SHA_RE = re.compile(r"[a-f0-9]{64}\Z")
PRODUCER_PATHS = frozenset(("tools/arc2_goal_sprint_20261017/curriculum.py",
    "tools/arc2_goal_sprint_20261017/data.py", "src/irisx/arc_nvarc_data.py",
    "src/irisx/canonical.py", "src/irisx/errors.py"))
ALGORITHM_KEYS = frozenset(("sft_loss_mode", "ttt_loss_mode", "candidate_views", "candidate_batch_size", "candidate_ranker",
                          "candidate_pool_limit", "likelihood_normalization", "rerank_fraction"))
LEGACY_KEYS = frozenset(("training_seconds", "sft_steps", "rl_batches", "rl_group_size",
    "rl_parents_per_batch", "ttt_steps", "context_tokens", "generation_tokens", "dev_tasks", "seed"))


def base_identity():
    return {"model_source": MODEL_SOURCE, "material_contract_sha256": MODEL_CONTRACT_SHA256}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode() + b"\n"


def valid_sha(value):
    return isinstance(value, str) and SHA_RE.fullmatch(value) is not None


def validate_solver_parameters(parameters=None, *, runtime=False):
    """No path, source identity, material, clock or arbitrary config overrides."""
    parameters = {} if parameters is None else parameters
    require(type(parameters) is dict and set(parameters) <= LEGACY_KEYS | ALGORITHM_KEYS,
            "unknown or protected solver tuning parameter")
    for name in LEGACY_KEYS & parameters.keys():
        value = parameters[name]
        if name == "training_seconds":
            require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 43200,
                    "bounded finite training_seconds required")
        else:
            low = 0 if name in {"sft_steps", "rl_batches", "ttt_steps", "seed"} else 1
            require(type(value) is int and low <= value <= 2**31 - 1, "bounded integer tuning value required: " + name)
    options = {"sft_loss_mode": parameters.get("sft_loss_mode", "final"),
        "ttt_loss_mode": parameters.get("ttt_loss_mode", "final"),
        "candidate_views": parameters.get("candidate_views", 2),
        "candidate_batch_size": parameters.get("candidate_batch_size", 1),
        "candidate_ranker": parameters.get("candidate_ranker", "first"),
        "candidate_pool_limit": parameters.get("candidate_pool_limit", 16),
        "likelihood_normalization": parameters.get("likelihood_normalization", "sum"),
        "rerank_fraction": parameters.get("rerank_fraction", .25)}
    require(all(type(options[k]) is str and options[k] in ("final", "causal_outputs")
                for k in ("sft_loss_mode", "ttt_loss_mode")), "invalid supervised loss mode")
    require(type(options["candidate_views"]) is int and options["candidate_views"] in (2, 8, 16),
            "candidate_views must be 2, 8, or 16")
    require(type(options["candidate_batch_size"]) is int and options["candidate_batch_size"] in (1, 2, 4, 8),
            "candidate_batch_size must be 1, 2, 4, or 8")
    require(type(options["candidate_pool_limit"]) is int and
            options["candidate_views"] <= options["candidate_pool_limit"] <= 16, "bounded full candidate pool required")
    require(type(options["candidate_ranker"]) is str and options["candidate_ranker"] in
            ("first", "vote", "cross_view_likelihood"), "invalid candidate ranker")
    require(type(options["likelihood_normalization"]) is str and options["likelihood_normalization"] in
            ("sum", "token_mean"), "invalid likelihood normalization")
    require(type(options["rerank_fraction"]) in (int, float) and options["rerank_fraction"] == .25,
            "rerank_fraction is frozen at 0.25")
    if runtime:
        from tools.arc2_goal_sprint_20261017.run import continuation_options
        require(continuation_options(parameters) == options, "package/runtime algorithm API differs")
    # Omitted parameters remain omitted: do not silently change old requests.
    return dict(parameters)


def validate_request_options(request):
    require(not {"model_path", "model_base_identity", "adapter_resume", "curriculum"} & set(request),
            "protected runtime paths and identities cannot come from request")
    return validate_solver_parameters(request.get("solver_parameters"))


def _name(name):
    require(isinstance(name, str) and name and "\\" not in name, "safe material member path required")
    path = PurePosixPath(name)
    require(not path.is_absolute() and not any(p in (".", "..") for p in path.parts)
            and path.as_posix() == name and not any(":" in p for p in path.parts), "unsafe material member path")
    return name


def _root(root):
    root = Path(root).absolute()
    require(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)), "regular material directory required")
    return root


def _json(path, *, expected=None, limit=8 * 1024**2):
    path = regular(path)
    require(path.stat().st_size <= limit, "bounded material JSON required")
    if expected is not None:
        require(valid_sha(expected) and sha(path) == expected, "external material manifest SHA differs")
    raw = path.read_bytes()
    value = json.loads(raw)
    require(type(value) is dict and canonical(value) == raw, "canonical material JSON object required")
    return value


def exact_inventory(root, expected, *, total_limit):
    """Walk only a small exact tree; reject extra directories, links and devices."""
    root = _root(root)
    expected = {_name(name): row for name, row in expected.items()}
    allowed_dirs = {p.as_posix() for name in expected for p in PurePosixPath(name).parents if p.as_posix() != "."}
    actual, visited, total = set(), 0, 0
    for directory, subdirs, files in os.walk(root, followlinks=False):
        for name in subdirs + files:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            visited += 1
            require(visited <= len(expected) + len(allowed_dirs), "unexpected material inventory")
            require(not path.is_symlink(), "material symlink forbidden")
            if path.is_dir():
                require(relative in allowed_dirs, "unexpected material directory")
            else:
                require(path.is_file() and relative in expected, "unexpected material inventory or special file")
                row = expected[relative]
                require(type(row) is dict and set(row) == {"bytes", "sha256"}
                        and type(row["bytes"]) is int and 0 <= row["bytes"] <= total_limit
                        and valid_sha(row["sha256"]), "strict bounded material byte inventory required")
                size = path.stat().st_size
                total += size
                require(total <= total_limit and size == row["bytes"] and sha(regular(path)) == row["sha256"],
                        "material bytes/hash differ")
                actual.add(relative)
    require(actual == set(expected), "missing material inventory")
    return expected


def _manifest_row(root):
    path = regular(Path(root) / "manifest.json")
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def verify_adapter(root, manifest_sha256, *, tensors=False):
    root = _root(root)
    manifest = _json(root / "manifest.json", expected=manifest_sha256)
    require(set(manifest) == {"format", "base_identity", "origin", "files", "exported_tensors", "trainable_tensors", "state_sha256"}
            and manifest["format"] == "irisx/pre-public-adapter-v1" and manifest["base_identity"] == base_identity(),
            "adapter schema or production base identity differs")
    origin = manifest["origin"]
    require(type(origin) is dict and set(origin) == {"run_id", "source_sha256", "phase", "public_ttt_applied", "public_labels_used",
        "run_summary_sha256", "provider_record_sha256"} and type(origin["run_id"]) is str and bool(origin["run_id"])
        and origin["phase"] == "pre_public" and origin["public_ttt_applied"] is False and origin["public_labels_used"] is False
        and all(valid_sha(origin[k]) for k in ("source_sha256", "run_summary_sha256", "provider_record_sha256")),
        "pre-PUBLIC training-only origin required")
    require(type(manifest["files"]) is dict and set(manifest["files"]) == {"adapter_config.json", "adapter_model.safetensors"}
            and valid_sha(manifest["state_sha256"]), "exact adapter file/state inventory required")
    for name, limit in (("adapter_config.json", 8 * 1024**2), ("adapter_model.safetensors", 1024**3)):
        require(type(manifest["files"][name]) is dict and type(manifest["files"][name].get("bytes")) is int
                and 0 < manifest["files"][name]["bytes"] <= limit, "bounded adapter file required")
    rows = {**manifest["files"], "manifest.json": _manifest_row(root)}
    exact_inventory(root, rows, total_limit=1024**3 + 16 * 1024**2)
    config = json.loads((root / "adapter_config.json").read_bytes())
    require(type(config) is dict and config.get("peft_type") == "LORA" and config.get("task_type") == "CAUSAL_LM",
            "LoRA causal language model adapter config required")
    for field in ("exported_tensors", "trainable_tensors"):
        inventory = manifest[field]
        require(type(inventory) is dict and 0 < len(inventory) <= 4096, "bounded adapter tensor inventory required")
        for name, row in inventory.items():
            suffix = r"\.default" if field == "trainable_tensors" else ""
            require(type(name) is str and re.fullmatch(r".+\.lora_[AB]" + suffix + r"\.weight", name)
                    and type(row) is dict and set(row) == {"shape", "dtype", "sha256"}
                    and type(row["shape"]) is list and len(row["shape"]) == 2
                    and all(type(v) is int and 0 < v <= 1_000_000 for v in row["shape"])
                    and row["dtype"] in ("torch.float32", "torch.float16", "torch.bfloat16")
                    and valid_sha(row["sha256"]), "strict adapter tensor inventory required")
    if tensors:
        from tools.arc2_goal_sprint_20261017.model import build_resume_manifest
        rebuilt = build_resume_manifest(root, expected_state_sha256=manifest["state_sha256"],
                                         base_identity=base_identity(), origin=origin)
        require(rebuilt == manifest, "adapter sealed tensor metadata differs")
    return rows


def producer_hashes(value):
    require(type(value) is dict and set(value) == PRODUCER_PATHS and all(valid_sha(v) for v in value.values()),
            "exact curriculum producer hashes required")
    return dict(value)


def verify_curriculum_inventory(root, manifest_sha256, expected_producer_hashes):
    root = _root(root)
    manifest = _json(root / "manifest.json", expected=manifest_sha256)
    from tools.arc2_goal_sprint_20261017.curriculum import FORMAT as CURRICULUM_FORMAT, MAX_ARTIFACT_BYTES
    require(manifest.get("format") == CURRICULUM_FORMAT and manifest.get("mode") == "production",
            "production curriculum required; synthetic fixtures are not deployable")
    require(manifest.get("source", {}).get("implementation_sha256") == producer_hashes(expected_producer_hashes),
            "curriculum producer identity differs")
    bundles = manifest.get("bundles")
    require(type(bundles) is list and 0 < len(bundles) <= 5000, "bounded curriculum bundles required")
    rows = {"manifest.json": _manifest_row(root)}
    for row in bundles:
        require(type(row) is dict and isinstance(row.get("task_id"), str)
                and re.fullmatch(r"rearc\.[0-9a-f]{8}\.[0-9]{3}\.[0-9a-f]{16}", row["task_id"])
                and row.get("path") == "bundles/" + row["task_id"] + ".json", "fixed curriculum bundle path required")
        require(row["path"] not in rows and type(row.get("bytes")) is int and 0 < row["bytes"] <= 128 * 1024,
                "unique bounded curriculum bundle required")
        rows[row["path"]] = {"bytes": row["bytes"], "sha256": row.get("sha256")}
    for key, name, limit in (("ledger", "provenance.jsonl", 32 * 1024**2), ("license", "LICENSE", 4096)):
        row = manifest.get(key)
        require(type(row) is dict and set(row) == {"path", "bytes", "sha256"} and row["path"] == name
                and type(row["bytes"]) is int and 0 < row["bytes"] <= limit, "fixed bounded curriculum ledger/license required")
        rows[name] = {"bytes": row["bytes"], "sha256": row["sha256"]}
    return exact_inventory(root, rows, total_limit=MAX_ARTIFACT_BYTES)


def verify_curriculum(root, manifest_sha256, expected_producer_hashes, *, training_root, training_manifest_path, public_path):
    rows = verify_curriculum_inventory(root, manifest_sha256, expected_producer_hashes)
    from tools.arc2_goal_sprint_20261017.curriculum import load_admission, load_curriculum
    admission = load_admission(training_root, training_manifest_path, public_path)
    _, receipt = load_curriculum(root, admission=admission, expected_manifest_sha256=manifest_sha256,
                                 expected_producer_hashes=expected_producer_hashes)
    return rows, receipt


def package_materials(destination, *, adapter_resume_root=None, adapter_resume_manifest_sha256=None,
                      curriculum_root=None, curriculum_manifest_sha256=None, curriculum_producer_hashes=None,
                      training_root=None, training_manifest_path=None, public_path=None):
    """Validate all inputs first, copy only exact inventories, and seal the index."""
    require((adapter_resume_root is None) == (adapter_resume_manifest_sha256 is None), "adapter root and external hash required together")
    require((curriculum_root is None) == (curriculum_manifest_sha256 is None) == (curriculum_producer_hashes is None),
            "curriculum root, external hash and producer hashes required together")
    records, checked = {}, {}
    if adapter_resume_root is not None:
        checked["adapter_resume"] = (Path(adapter_resume_root), verify_adapter(adapter_resume_root, adapter_resume_manifest_sha256, tensors=True))
        records["adapter_resume"] = {"root": ROOTS["adapter_resume"], "manifest_sha256": adapter_resume_manifest_sha256}
    if curriculum_root is not None:
        require(all(v is not None for v in (training_root, training_manifest_path, public_path)),
                "actual training and solver-only PUBLIC paths required for curriculum admission")
        rows, _ = verify_curriculum(curriculum_root, curriculum_manifest_sha256, curriculum_producer_hashes,
            training_root=training_root, training_manifest_path=training_manifest_path, public_path=public_path)
        checked["curriculum"] = (Path(curriculum_root), rows)
        records["curriculum"] = {"root": ROOTS["curriculum"], "manifest_sha256": curriculum_manifest_sha256,
                                 "producer_hashes": producer_hashes(curriculum_producer_hashes)}
    if not records:
        return None
    destination = Path(destination)
    for role, (origin, rows) in checked.items():
        target = destination / ROOTS[role]
        target.mkdir(parents=True, exist_ok=False)
        for name in rows:
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(regular(origin / name), path)
        exact_inventory(target, rows, total_limit=2 * 1024**3)
    body = canonical({"format": FORMAT, "materials": records})
    with (destination / INDEX).open("xb") as stream:
        stream.write(body)
    return hashlib.sha256(body).hexdigest()


def resolve_materials(source, expected_sha256=None, *, source_files):
    """Resolve only fixed source-relative paths after the outer source is pinned."""
    source = Path(source)
    has_index = INDEX in source_files
    require(has_index == (expected_sha256 is not None), "continuation index and explicit request pin required together")
    if not has_index:
        require(not (source / INDEX).exists() and not any((source / name).exists() for name in ROOTS.values()),
                "unmanifested continuation material forbidden")
        return {}
    value = _json(source / INDEX, expected=expected_sha256, limit=64 * 1024)
    require(set(value) == {"format", "materials"} and value["format"] == FORMAT
            and type(value["materials"]) is dict and bool(value["materials"])
            and set(value["materials"]) <= ROOTS.keys(), "strict continuation material index required")
    result = {}
    for role, row in value["materials"].items():
        fields = {"root", "manifest_sha256"} | ({"producer_hashes"} if role == "curriculum" else set())
        require(type(row) is dict and set(row) == fields and row["root"] == ROOTS[role]
                and valid_sha(row["manifest_sha256"]), "fixed source-relative continuation specification required")
        root = source / ROOTS[role]
        rows = (verify_adapter(root, row["manifest_sha256"]) if role == "adapter_resume" else
                verify_curriculum_inventory(root, row["manifest_sha256"], row["producer_hashes"]))
        expected = {ROOTS[role] + "/" + name: item for name, item in rows.items()}
        actual = {name: item for name, item in source_files.items() if name.startswith(ROOTS[role] + "/")}
        require(actual == expected, "continuation material source closure differs")
        result[role] = {**row, "root": str(root.absolute())}
    for role in ROOTS.keys() - result.keys():
        require(not (source / ROOTS[role]).exists() and not any(n.startswith(ROOTS[role] + "/") for n in source_files),
                "unindexed continuation material forbidden")
    return result


def validate_runtime_materials(specs, parameters, *, training_root, training_manifest_path, public_path):
    """CPU-only readback. Actual PEFT loading/config acceptance remains pending."""
    validate_solver_parameters(parameters, runtime=True)
    receipt = {"model_loaded": False, "adapter_loaded": False, "training_executed": False}
    if "adapter_resume" in specs:
        spec = specs["adapter_resume"]
        verify_adapter(spec["root"], spec["manifest_sha256"], tensors=True)
        receipt["adapter_tensor_bytes_verified"] = True
        receipt["adapter_manifest_sha256"] = spec["manifest_sha256"]
    if "curriculum" in specs:
        spec = specs["curriculum"]
        _, receipt["curriculum"] = verify_curriculum(spec["root"], spec["manifest_sha256"], spec["producer_hashes"],
            training_root=training_root, training_manifest_path=training_manifest_path, public_path=public_path)
    return receipt
