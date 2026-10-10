"""Pre-write path separation without inspecting declared immutable inputs.

Only lexical normalization is used for input roots. Link checks inspect the
source/write paths, root first, and never resolve or scan an input Dataset.
Input-side symlinks and bind-mount aliases cannot be discovered under that
no-inspection contract; post-gate asset/link checks remain independently required.
"""
from __future__ import annotations

import os
from pathlib import Path

ROLES = frozenset({"runtime", "model", "wheels", "interpreter", "adapter"})


def normalized_path(value, *, declared_input=False):
    """Normalize native lexical aliases, rejecting traversal before collapsing."""
    value = os.fspath(value) if isinstance(value, os.PathLike) else value
    if (type(value) is not str or not value or len(value) > 4096
            or any(ord(c) < 32 for c in value)
            or ".." in value.replace("\\", "/").split("/")):
        raise ValueError("invalid path or parent traversal forbidden")
    if declared_input and (not value.startswith("/") or "\\" in value or ":" in value):
        raise ValueError("Dataset roots must be bounded absolute Linux paths")
    if os.name != "nt" and ("\\" in value or ":" in value):
        raise ValueError("ambiguous non-native path forbidden")
    normalized = os.path.normcase(os.path.abspath(value))
    # POSIX normpath preserves exactly two leading slashes; treating these as
    # disjoint would let //kaggle/input bypass the /kaggle/input boundary.
    if os.name == "posix":
        normalized = "/" + normalized.lstrip("/")
    return Path(normalized)


def environment_path(output_root):
    root = normalized_path(output_root)
    return root.parent / (root.name + "-environment")


def guard_paths(model_config, paths, *, check_links=True):
    """Reject equal/ancestor/descendant input overlap before any path inspection.

    Callers supply every source/cache/output/environment root before writes.
    check_links=False is for pure bootstrap planning; actual entrypoints also
    check writable path components before creating anything.
    """
    config = {} if model_config is None else model_config
    if type(config) is not dict:
        raise ValueError("model configuration must be a dictionary")
    explicit = config.get("explicit_roots", {})
    if type(explicit) is not dict or set(explicit) - ROLES:
        raise ValueError("explicit_roots may override only the five pinned Dataset roles")
    declared = {"input_root": normalized_path(config.get("input_root", "/kaggle/input"),
                                               declared_input=True)}
    declared.update({"explicit_roots." + role: normalized_path(value, declared_input=True)
                     for role, value in explicit.items() if value is not None})
    normalized = {name: normalized_path(value) for name, value in paths.items()}
    # Complete every lexical check before even lstat on a writable component:
    # a rejected path may itself name a Dataset or one of its descendants.
    for name, path in normalized.items():
        for input_name, immutable in declared.items():
            if path == immutable or path in immutable.parents or immutable in path.parents:
                raise ValueError(name + " overlaps declared immutable input " + input_name)
    if check_links:
        for path in normalized.values():
            # Check the ancestor link before examining anything below it.
            for part in (*reversed(path.parents), path):
                if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                    raise ValueError("Source/output/environment symlink or junction forbidden")
    return normalized
