"""Read-only AST checks for mutable core/domain edges, never runtime imports.

Frozen flat ARC modules are retained rather than treated as shared core. Literal
dynamic imports are checked; unresolved import calls fail. This bounded source
check does not prove notebook, generated-code, pickle or runtime compatibility.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import re
import sys

try:
    from .workstream_management import load_json, safe_path
except ImportError:
    from workstream_management import load_json, safe_path

MODULE = re.compile(r"irisx(?:\.[A-Za-z_][A-Za-z_0-9]*)*\Z")
FORBIDDEN = {"tools", "torch", "transformers", "peft", "kaggle", "numpy", "safetensors"}


def _source(root: Path, module: str) -> tuple[Path, bool]:
    base = "src/" + module.replace(".", "/")
    file = safe_path(root, base + ".py")
    package = safe_path(root, base + "/__init__.py")
    if file.is_file() and package.is_file():
        raise ValueError(f"ambiguous source module: {module}")
    if file.is_file():
        return file, False
    if package.is_file():
        return package, True
    raise ValueError(f"missing source module: {module}")


def _config(root: Path) -> dict:
    value = load_json(safe_path(root, "docs/workstreams/dependencies.json"))
    if not isinstance(value, dict) or set(value) != {"format", "core_modules", "router", "facade_legacy"} or value["format"] != "irisx.dependencies.v1":
        raise ValueError("invalid dependency schema fields/format")
    core = value["core_modules"]
    if not isinstance(core, list) or not core or len(set(core)) != len(core) or any(not isinstance(m, str) or not MODULE.fullmatch(m) or m.startswith("irisx.domains") for m in core):
        raise ValueError("invalid core module list")
    for field in ("router", "facade_legacy"):
        if not isinstance(value[field], dict):
            raise ValueError(f"invalid {field} mapping")
        for module, destinations in value[field].items():
            if not MODULE.fullmatch(module) or not isinstance(destinations, list) or not destinations or any(not isinstance(m, str) or not MODULE.fullmatch(m) for m in destinations) or len(set(destinations)) != len(destinations):
                raise ValueError(f"invalid {field} module or destinations")
            if field == "router" and (module.startswith("irisx.domains.") or any(not m.startswith("irisx.domains.") for m in destinations)):
                raise ValueError("router must register core to domain edges only")
            if field == "facade_legacy" and (not module.startswith("irisx.domains.") or any(m.startswith("irisx.domains.") or m in core for m in destinations)):
                raise ValueError("facade legacy must register domain to legacy edges only")
    return value


def _imports(tree: ast.AST, module: str, package: bool):
    """Yield dependencies and unresolved calls, including importlib aliases."""
    importlib_aliases, loader_aliases = {"importlib"}, set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib":
                    importlib_aliases.add(alias.asname or "importlib")
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib" and not node.level:
            loader_aliases.update(alias.asname or alias.name for alias in node.names if alias.name == "import_module")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ""
            if node.level:
                parent = module if package else module.rpartition(".")[0]
                name = importlib.util.resolve_name("." * node.level + name, parent)
            yield name, node.lineno
            # Importing a package attribute can be importing its submodule.
            for alias in node.names:
                if alias.name != "*":
                    yield name + "." + alias.name, node.lineno
        elif isinstance(node, ast.Call):
            fn = node.func
            dynamic = isinstance(fn, ast.Name) and (fn.id == "__import__" or fn.id in loader_aliases)
            dynamic |= isinstance(fn, ast.Attribute) and fn.attr == "import_module" and isinstance(fn.value, ast.Name) and fn.value.id in importlib_aliases
            if dynamic:
                arg = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg in ("name", "module")), None)
                if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str) or arg.value.startswith("."):
                    yield None, node.lineno
                else:
                    yield arg.value, node.lineno


def check_dependencies(root: Path) -> list[str]:
    errors = []
    try:
        config = _config(root)
        # The namespace container is neutral: it must not eagerly import either
        # domain while consumers are merely importing irisx.domains.
        core = set(config["core_modules"]) | set(config["router"]) | {"irisx.domains"}
        modules = set(core) | set(config["facade_legacy"])
        domains = safe_path(root, "src/irisx/domains")
        for path in sorted(domains.rglob("*.py")):
            safe_path(root, path.relative_to(root).as_posix())
            relative = path.relative_to(root / "src").with_suffix("")
            module = ".".join(relative.parts)
            if module.endswith(".__init__"):
                module = module[:-9]
            modules.add(module)
        for destinations in (*config["router"].values(), *config["facade_legacy"].values()):
            for destination in destinations:
                _source(root, destination)
        for module in sorted(modules):
            path, package = _source(root, module)
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as error:
                errors.append(f"{module}: source syntax error: {error.msg}")
                continue
            domain = module.split(".")[2] if module.startswith("irisx.domains.") else None
            for dependency, line in _imports(tree, module, package):
                prefix = f"{module}:{line}"
                if dependency is None:
                    errors.append(f"{prefix}: unresolved dynamic import")
                    continue
                if dependency.split(".")[0] in FORBIDDEN:
                    errors.append(f"{prefix}: forbidden operational/ML dependency {dependency}")
                    continue
                if not dependency.startswith("irisx.") or dependency == "irisx.domains":
                    continue
                is_domain = dependency.startswith("irisx.domains.")
                if module in core:
                    if is_domain and dependency not in config["router"].get(module, []):
                        errors.append(f"{prefix}: forbidden core/domain or unregistered router edge {dependency}")
                    elif not is_domain and not any(dependency == m or (m != "irisx" and dependency.startswith(m + ".")) for m in core):
                        errors.append(f"{prefix}: forbidden core/legacy edge {dependency}")
                elif domain:
                    if is_domain and dependency.split(".")[2] != domain:
                        errors.append(f"{prefix}: forbidden cross-line import {dependency}")
                    elif not is_domain and not any(dependency == m or (m != "irisx" and dependency.startswith(m + ".")) for m in core) and not any(dependency == m or dependency.startswith(m + ".") for m in config["facade_legacy"].get(module, [])):
                        errors.append(f"{prefix}: unregistered legacy import {dependency}")
    except (OSError, ValueError, TypeError, KeyError, ImportError) as error:
        errors.append(f"dependencies: {error}")
    return sorted(set(errors))


if __name__ == "__main__":
    problems = check_dependencies(Path(__file__).resolve().parents[1])
    print("\n".join(problems) if problems else "dependencies: PASS (static mutable source edges only)")
    sys.exit(bool(problems))
