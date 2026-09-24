"""Hash-gated entrances into the pinned NVARC, Qwen and TRM source snapshots.

No upstream code is copied into the package. Notebook install/run cells are
excluded; the original definitions in their writefile cells execute locally.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import types
from typing import Any

from .errors import ValidationError


REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / ".irisx/arc-agi-2/qwen35-nvarc/source"
MANIFEST = REPO / "trials/arc-agi-2-qwen35-nvarc/source-manifest.json"


def _binding() -> dict[str, Any]:
    if not MANIFEST.is_file():
        raise ValidationError("NVARC source manifest is missing")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("format") != "irisx/nvarc-source-manifest-v1":
        raise ValidationError("NVARC source manifest format differs")
    return manifest


def _checked(path: Path, expected: str) -> Path:
    from hashlib import sha256

    if path.is_symlink() or not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected:
        raise ValidationError(f"pinned upstream source missing or changed: {path}")
    return path


def _module(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValidationError(f"cannot load upstream source: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def qwen_cell(writefile: str) -> types.ModuleType:
    """Load the real notebook's arc_loader.py, arc_decoder.py or arc_solver.py.

    Solver imports Unsloth, so its DFS and NLL definitions are extracted from
    the unchanged cell AST to avoid installing or running notebook side effects.
    """
    allowed = {"arc_loader.py", "arc_decoder.py", "arc_solver.py"}
    if writefile not in allowed:
        raise ValidationError("not an approved Qwen notebook writefile cell")
    binding = _binding()["notebooks"]["qwen"]
    path = _checked(SOURCE / binding["path"], binding["sha256"])
    notebook = json.loads(path.read_text(encoding="utf-8"))
    marker = f"%%writefile {writefile}\n"
    for cell in notebook["cells"]:
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        if source.startswith(marker):
            body = source[len(marker):]
            module = types.ModuleType(f"_nvarc_qwen_{writefile.replace('.', '_')}")
            module.__file__ = f"{path}::{writefile}"
            if writefile == "arc_solver.py":
                import time
                from collections import defaultdict
                import numpy as np
                import torch
                from typing import Any, Union

                tree = ast.parse(body, filename=module.__file__)
                names = {"turbo_dfs", "inference_turbo_dfs", "calc_scores"}
                constants = {"ARC_VOCAB", "ARC_TOKENS", "USER_TOKEN_ID",
                             "ASSISTANT_TOKEN_ID", "PAD_ID", "EOS_ID"}
                selected = [node for node in tree.body if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names) or
                    (isinstance(node, ast.ClassDef) and node.name == "QwenDataCollatorForCompletionOnlyLM") or
                    (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and
                     target.id in constants for target in node.targets))]
                if ({node.name for node in selected if isinstance(node, ast.FunctionDef)} != names or
                        not any(isinstance(node, ast.ClassDef) for node in selected)):
                    raise ValidationError("Qwen solver source definitions missing")

                class FixedBatchBase:
                    def torch_call(self, examples):
                        ids = torch.tensor(examples, dtype=torch.long)
                        return {"input_ids": ids, "labels": ids.clone()}

                module.__dict__.update({"torch": torch, "time": time, "defaultdict": defaultdict,
                                        "np": np, "Any": Any, "Union": Union,
                                        "DataCollatorForLanguageModeling": FixedBatchBase})
                exec(compile(ast.Module(body=selected, type_ignores=[]), module.__file__, "exec"), module.__dict__)
            else:
                exec(compile(body, module.__file__, "exec"), module.__dict__)
            return module
    raise ValidationError(f"Qwen notebook cell {writefile} missing")


def sdg_build_datasets() -> types.ModuleType:
    manifest = _binding()
    rel = "SDG/scripts/build_datasets.py"
    path = _checked(SOURCE / "NVARC" / rel, manifest["code_files"][rel]["sha256"])
    return _module("_nvarc_sdg_build_datasets", path)


def sft_data_entry() -> types.ModuleType:
    """Load original SFT dataset loader; NeMo-only training imports stay gated."""
    manifest = _binding()
    rel = "ARChitects/run_sft.py"
    path = _checked(SOURCE / "NVARC" / rel, manifest["code_files"][rel]["sha256"])
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "load_datasets"]
    if len(selected) != 1:
        raise ValidationError("upstream SFT dataset loader missing")
    from datasets import concatenate_datasets, load_from_disk

    module = types.ModuleType("_nvarc_sft_data")
    module.__dict__.update({"load_from_disk": load_from_disk,
                            "concatenate_datasets": concatenate_datasets})
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), module.__dict__)
    return module


def trm_dataset_entry() -> types.ModuleType:
    manifest = _binding()
    rel = "external/TinyRecursiveModels/dataset/build_arc_dataset.py"
    path = _checked(SOURCE / "NVARC" / rel, manifest["code_files"][rel]["sha256"])
    trm_root = path.parents[1]
    added = str(trm_root) not in sys.path
    if added:
        sys.path.insert(0, str(trm_root))
    try:
        return _module("_nvarc_trm_dataset", path)
    finally:
        if added:
            sys.path.remove(str(trm_root))
