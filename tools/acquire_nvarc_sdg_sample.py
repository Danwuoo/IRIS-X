"""Retain four pinned SDG first shards for bounded schema/program replay.

This is an explicitly partial material acquisition, independent of the complete
192-member archive. Downloading or reading Parquet never executes its programs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools.execute_nvarc_overnight_sft import token, client_for
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest


def acquire():
    original = ROOT / ".irisx/nvarc-original/materials/sdg-artifacts-20261002"
    folder = ROOT / ".irisx/nvarc-original/materials/sdg-first-shards-20261002-001"
    if folder.exists():
        raise ValueError("new partial SDG material identity required")
    metadata = json.loads((original / "provider-metadata.json").read_bytes())
    inventory = json.loads((original / "provider-closed-inventory.json").read_bytes())
    if (metadata["ref"] != "sorokin/nvarc-artifacts-puzzles" or
            metadata["currentVersionNumber"] != 1 or len(inventory) != 192 or
            sum(inventory.values()) != metadata["totalBytes"]):
        raise ValueError("closed published SDG version-1 inventory differs")
    selected = {f"{group}/data-00000.parquet": inventory[f"{group}/data-00000.parquet"]
                for group in ("summaries", "mixtures", "inputs", "outputs")}
    if shutil.disk_usage(original).free < sum(selected.values()) + 2 * 1024**3:
        raise ValueError("partial SDG acquisition disk reserve differs")
    folder.mkdir(parents=True)
    ledger = {"owner_decision": "Decision 0053", "dataset": "sorokin/nvarc-artifacts-puzzles/1",
              "provider_metadata_sha256": sha_file(original / "provider-metadata.json"),
              "provider_inventory_sha256": sha_file(original / "provider-closed-inventory.json"),
              "expected_members": selected, "download_requests_reserved": len(selected),
              "maximum_download_seconds": 1800, "model_calls": 0, "program_executions": 0,
              "maximum_paid_usd": 0, "complete_dataset": False,
              "state": "downloading", "members": []}
    atomic(folder / "acquisition.json", ledger)
    started = time.monotonic()
    try:
        for name, expected in selected.items():
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            request = ApiDownloadDatasetRequest()
            request.owner_slug = "sorokin"
            request.dataset_slug = "nvarc-artifacts-puzzles"
            request.dataset_version_number = 1
            request.file_name = name
            request.raw = True
            written = 0
            digest = hashlib.sha256()
            with client_for(token()) as client:
                with client.datasets.dataset_api_client.download_dataset(request) as response:
                    response.raise_for_status()
                    with path.open("xb") as stream:
                        for chunk in response.iter_content(1024**2):
                            if time.monotonic() - started > 1800:
                                raise TimeoutError("partial SDG acquisition expired")
                            written += len(chunk)
                            if written > expected:
                                raise ValueError("partial SDG member exceeds provider size")
                            stream.write(chunk)
                            digest.update(chunk)
            if written != expected:
                raise ValueError("partial SDG member byte count differs")
            member = {"path": name, "bytes": written, "sha256": digest.hexdigest()}
            ledger["members"].append(member)
            atomic(folder / "acquisition.json", ledger)
            print(json.dumps({"verified_member": member}), flush=True)
        ledger.update(state="verified-partial-published-artifacts",
                      elapsed_seconds=time.monotonic() - started)
        atomic(folder / "acquisition.json", ledger)
    except BaseException as error:
        ledger.update(state="incomplete-retained", error_type=type(error).__name__,
                      elapsed_seconds=time.monotonic() - started)
        atomic(folder / "acquisition.json", ledger)
        raise


if __name__ == "__main__":
    acquire()
