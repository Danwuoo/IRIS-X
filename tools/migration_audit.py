import hashlib
import json
import os
import argparse
import subprocess
import tempfile
from pathlib import Path

def git(root: Path, args: list[str], env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        env=env,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def audit() -> None:
    ROOT = Path.cwd()
    SOURCES = json.loads((ROOT / "corpus/sources.yaml").read_text(encoding="utf-8"))
    ARTIFACTS = json.loads((ROOT / "corpus/artifacts.yaml").read_text(encoding="utf-8"))
    COMMIT = SOURCES["import_commit"]

    descriptor, index_name = tempfile.mkstemp(prefix="irisx-audit-", suffix=".index")
    os.close(descriptor)
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = index_name
    try:
        git(ROOT, ["read-tree", "--empty"], env)
        source_paths = [record["current_path"] for record in SOURCES["records"]]
        git(ROOT, ["add", "--force", "--", *source_paths], env)
        tree = git(ROOT, ["write-tree"], env)
        for record in SOURCES["records"]:
            original = record["original_import_path"]
            current = record["current_path"]
            historical = git(ROOT, ["rev-parse", f"{COMMIT}:{original}"])
            current_tree = git(ROOT, ["rev-parse", f"{tree}:{current}"], env)
            status = "PRESERVED" if historical == current_tree else "CHANGED"
            print(f"{status}\t{original}\t{current}\t{historical}")
            assert status == "PRESERVED"
    finally:
        try:
            os.unlink(index_name)
        except FileNotFoundError:
            pass

    for record in ARTIFACTS["records"]:
        original = record["original_import_path"]
        current = record["current_path"]
        data = (ROOT / current).read_bytes()
        header = b"blob " + str(len(data)).encode("ascii") + b"\0"
        blob = hashlib.sha1(header + data).hexdigest()
        digest = hashlib.sha256(data).hexdigest()
        historical_blob = git(ROOT, ["rev-parse", f"{COMMIT}:{original}"])
        snapshot = next(item for item in record["snapshots"] if item["event"] == "initial-import")
        assert blob == historical_blob == snapshot["blob_oid"]
        assert digest == snapshot["sha256"]
        assert len(data) == snapshot["bytes"]
        print(f"PRESERVED\t{original}\t{current}\t{blob}\t{digest}")

    print(
        f"migration audit: PASS "
        f"({len(SOURCES['records'])} trees, {len(ARTIFACTS['records'])} artifacts)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        audit()
    except (OSError, RuntimeError, AssertionError, json.JSONDecodeError) as exc:
        print(f"migration audit: FAIL ({exc})")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
