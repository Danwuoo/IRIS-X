"""Deliberately fetch only the pinned teacher tokenizer, separately from execution."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
FILES = {"config.json", "tokenizer.json", "tokenizer_config.json",
         "chat_template.jinja", "vocab.json", "merges.txt"}


def materialize(output: Path) -> None:
    manifest = json.loads((ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/base-model-manifest.json").read_bytes())
    if manifest["revision"] != "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a":
        raise ValueError("pinned teacher revision differs")
    output.mkdir(parents=True, exist_ok=True)
    for entry in manifest["files"]:
        name = entry["path"]
        if name not in FILES:
            continue
        path = output / name
        if path.exists():
            payload = path.read_bytes()
        else:
            url = f"https://huggingface.co/{manifest['repository']}/resolve/{manifest['revision']}/{name}"
            with urlopen(url, timeout=60) as response:
                payload = response.read(entry["byte_size"] + 1)
        if (len(payload) != entry["byte_size"] or
                "sha256:" + hashlib.sha256(payload).hexdigest() != entry["content_digest"]):
            raise ValueError("pinned tokenizer material differs: " + name)
        if not path.exists():
            path.write_bytes(payload)
        print(name + ": verified", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    materialize(parser.parse_args().output)
