"""Resume a retained SDG partial through Kaggle's validator-bound downloader.

The original timed-out bytes stay frozen. A new material identity copies both
the partial ZIP and its exact official ETag/size marker before requesting a
range resume. A changed provider identity causes the CLI to restart safely.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import inventory_archive, sha_file


def resume():
    original = ROOT / ".irisx/nvarc-original/materials/sdg-artifacts-20261002"
    folder = ROOT / ".irisx/nvarc-original/materials/sdg-artifacts-20261002-resume-001"
    ledger = json.loads((original / "acquisition.json").read_bytes())
    metadata = json.loads((original / "provider-metadata.json").read_bytes())
    expected = json.loads((original / "provider-closed-inventory.json").read_bytes())
    archive_name = "nvarc-artifacts-puzzles.zip"
    marker_name = archive_name + ".kaggle-partial"
    archive, marker = original / archive_name, original / marker_name
    marker_value = json.loads(marker.read_bytes())
    if (ledger["state"] != "incomplete-retained" or folder.exists() or
            ledger["dataset"] != "sorokin/nvarc-artifacts-puzzles/1" or
            metadata["currentVersionNumber"] != 1 or len(expected) != 192 or
            sum(expected.values()) != metadata["totalBytes"] or
            not isinstance(marker_value.get("validator"), str) or
            type(marker_value.get("size")) is not int or
            not 0 < archive.stat().st_size <= marker_value["size"]):
        raise ValueError("frozen partial SDG acquisition/validator differs")
    process_check = subprocess.run(
        ["tasklist", "/FI", f"PID eq {ledger['local_download_pid']}", "/FO", "CSV", "/NH"],
        capture_output=True, timeout=15)
    if b'"' + str(ledger["local_download_pid"]).encode() + b'"' in process_check.stdout:
        raise ValueError("original SDG downloader has not stopped")
    if shutil.disk_usage(original).free < marker_value["size"] + 15 * 1024**3:
        raise ValueError("resumed archive exceeds retained-source/model disk reserve")
    frozen = {"original_acquisition_sha256": sha_file(original / "acquisition.json"),
              "original_partial_sha256": sha_file(archive), "original_partial_bytes": archive.stat().st_size,
              "original_marker_sha256": sha_file(marker), "expected_archive_bytes": marker_value["size"]}
    folder.mkdir(parents=True)
    for name in (archive_name, marker_name, "provider-metadata.json", "provider-closed-inventory.json"):
        shutil.copyfile(original / name, folder / name)
    if (sha_file(folder / archive_name) != frozen["original_partial_sha256"] or
            sha_file(folder / marker_name) != frozen["original_marker_sha256"]):
        raise ValueError("new SDG resume material differs from frozen partial")
    current = {"owner_decision": "Decision 0053", "dataset": ledger["dataset"],
               "parent_material": original.name, **frozen, "download_reserved": 1,
               "maximum_download_seconds": 10800, "model_calls": 0, "program_executions": 0,
               "maximum_paid_usd": 0, "parent_pid": os.getpid(), "state": "downloading"}
    atomic(folder / "acquisition.json", current)
    command = [sys.executable, "-m", "kaggle", "datasets", "download", "-d", current["dataset"],
               "-p", str(folder), "--quiet"]
    started = time.monotonic()
    try:
        with (folder / "download.log").open("wb") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            current["local_download_pid"] = process.pid
            atomic(folder / "acquisition.json", current)
            try:
                code = process.wait(timeout=10800)
            finally:
                if process.poll() is None:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   capture_output=True, timeout=15)
                    process.wait(timeout=15)
        if code:
            raise ValueError("SDG resume process failed; retain partial and diagnostic")
        current["state"] = "inventory-verification"
        atomic(folder / "acquisition.json", current)
        report = inventory_archive(folder / archive_name, folder / "archive-inventory.json")
        if {item["path"]: item["bytes"] for item in report["members"]} != expected:
            raise ValueError("resumed SDG archive differs from exact version-1 closed inventory")
        current.update(state="verified-published-raw-artifacts", archive_sha256=report["archive_sha256"],
                       archive_bytes=report["archive_bytes"], raw_bytes=report["uncompressed_bytes"],
                       inventory_sha256=sha_file(folder / "archive-inventory.json"),
                       file_count=report["member_count"], crc_verified=True, extracted=False,
                       elapsed_seconds=time.monotonic() - started)
        atomic(folder / "acquisition.json", current)
        print(json.dumps(current), flush=True)
    except BaseException as error:
        current.update(state="incomplete-retained", error_type=type(error).__name__,
                       elapsed_seconds=time.monotonic() - started)
        atomic(folder / "acquisition.json", current)
        raise


if __name__ == "__main__":
    resume()
