"""Stdlib-only finalizer, available even before notebook dependency installation."""

def write_analysis_zip(work, target, run_id, plan_digest):
    import hashlib
    import json
    import os
    from pathlib import Path
    import zipfile
    if target.exists():
        raise RuntimeError("analysis ZIP already exists")
    # Retain only declared truth-free inputs and diagnostic outputs. No weights,
    # dependencies, source/wheel archives, optimizer shards or temporary files.
    root_names = {"plan.json", "seed.json", "prompts.json", "visible.json", "source-config.json",
        "training-evidence.json", "model-manifest.json", "wheel-manifest.json", "startup-events.jsonl",
        "hardware-raw.json", "hardware-inventory.json", "hardware.json", "mount-preflight.json",
        "aggregate-terminal.json"}
    files = []
    for path in sorted(work.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("analysis evidence symlink")
        if not path.is_file():
            continue
        name = path.relative_to(work).as_posix()
        if name in root_names or name.startswith("workers/") and path.suffix in {".json", ".jsonl", ".log"}:
            if any(p.is_symlink() for p in path.parents) or path.stat().st_size > 16*1024*1024:
                raise RuntimeError("analysis evidence bound differs")
            files.append((name,path))
    inventory = {name:{"sha256":hashlib.sha256(path.read_bytes()).hexdigest(), "bytes":path.stat().st_size}
                 for name,path in files}
    if sum(v["bytes"] for v in inventory.values()) > 64*1024*1024:
        raise RuntimeError("analysis evidence exceeds 64 MiB")
    manifest = {"format":"irisx/nvarc-editor008-analysis-zip-v1", "run_id":run_id,
        "plan_digest":plan_digest, "files":inventory, "contains_evaluator_truth":False,
        "note":"Raw replies, budgets and failure evidence; no ARC scoring or promotion."}
    temporary = target.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        for name,path in files:
            archive.write(path,name)
        archive.writestr("analysis-manifest.json",json.dumps(manifest,sort_keys=True,ensure_ascii=False))
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(inventory)|{"analysis-manifest.json"}:
            raise RuntimeError("analysis ZIP inventory differs")
        for name,binding in inventory.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != binding["sha256"]:
                raise RuntimeError("analysis ZIP digest differs")
    os.replace(temporary,target)
    return {"path":str(target),"sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"artifacts":len(inventory)}
