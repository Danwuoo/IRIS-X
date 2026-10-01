"""Retain pinned published TRM arrays, with evaluation labels quarantined.

This command acquires/inventories bytes only. It never trains, scores, extracts
the complete archive, or stages evaluation arrays into a solver package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools.execute_nvarc_overnight_sft import token, client_for
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import inventory_archive, sha_file
from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest, ApiGetDatasetRequest, ApiListDatasetFilesRequest


def acquire(role, attempt):
    slug = "arc-prize-trm-" + ("training-data" if role == "train" else "evaluation-data")
    area = "materials" if role == "train" else "evaluator-materials"
    folder = ROOT / ".irisx/nvarc-original" / area / ("trm-published-" + role + "-20261002-" + attempt)
    if folder.exists():
        raise ValueError("new published TRM material identity required")
    folder.mkdir(parents=True)
    ledger = {"owner_decision": "Decision 0053", "dataset": "cpmpml/" + slug + "/1",
              "role": role, "contains_evaluation_labels": True, "solver_staging_authorized": False,
              "metadata_request_reserved": 1, "file_list_requests_reserved": 0, "download_reserved": 0,
              "model_calls": 0, "correctness_scored": False, "maximum_paid_usd": 0,
              "parent_pid": os.getpid(), "state": "provider-inventory"}
    atomic(folder / "acquisition.json", ledger)
    started = time.monotonic()
    try:
        with client_for(token()) as client:
            request = ApiGetDatasetRequest()
            request.owner_slug = "cpmpml"
            request.dataset_slug = slug
            metadata = client.datasets.dataset_api_client.get_dataset(request).to_dict()
            if metadata["ref"] != "cpmpml/" + slug:
                raise ValueError("published TRM provider reference differs")
            atomic(folder / "provider-metadata.json", metadata)
            entries, page = [], ""
            for index in range(5):
                ledger["file_list_requests_reserved"] += 1
                atomic(folder / "acquisition.json", ledger)
                request = ApiListDatasetFilesRequest()
                request.owner_slug = "cpmpml"
                request.dataset_slug = slug
                request.dataset_version_number = 1
                request.page_size = 100
                request.page_token = page
                listing = client.datasets.dataset_api_client.list_dataset_files(request).to_dict()
                atomic(folder / f"version-1-page-{index + 1}.json", listing)
                entries.extend(listing["datasetFiles"])
                page = listing.get("nextPageToken", "")
                if not page:
                    break
        expected = {entry["name"]: entry["totalBytes"] for entry in entries}
        if page or len(expected) != len(entries) or not expected or sum(expected.values()) > 48 * 1024**3:
            raise ValueError("closed bounded TRM version-1 provider inventory differs")
        maximum_zip_bytes = 4 * 1024**3
        sdg = ROOT / ".irisx/nvarc-original/materials/sdg-artifacts-20261002-resume-001"
        sdg_remaining = 0
        if (sdg / "acquisition.json").exists():
            ongoing = json.loads((sdg / "acquisition.json").read_bytes())
            if ongoing["state"] == "downloading":
                sdg_remaining = max(0, ongoing["expected_archive_bytes"] -
                                    (sdg / "nvarc-artifacts-puzzles.zip").stat().st_size)
        if shutil.disk_usage(folder).free < maximum_zip_bytes + sdg_remaining + 10 * 1024**3:
            raise ValueError("TRM archive would consume the retained-model/material reserve")
        atomic(folder / "provider-closed-inventory.json", expected)
        ledger.update(state="downloading", download_reserved=1, maximum_download_seconds=2700,
                      maximum_zip_bytes=maximum_zip_bytes, other_reserved_download_bytes=sdg_remaining,
                      provider_raw_bytes=sum(expected.values()), provider_file_count=len(expected),
                      provider_metadata_sha256=sha_file(folder / "provider-metadata.json"),
                      provider_inventory_sha256=sha_file(folder / "provider-closed-inventory.json"))
        atomic(folder / "acquisition.json", ledger)
        archive_path = folder / (slug + ".zip")
        request = ApiDownloadDatasetRequest()
        request.owner_slug = "cpmpml"
        request.dataset_slug = slug
        request.dataset_version_number = 1
        written, download_hash = 0, hashlib.sha256()
        with client_for(token()) as client:
            with client.datasets.dataset_api_client.download_dataset(request) as response:
                response.raise_for_status()
                content_length = int(response.headers.get("Content-Length", 0))
                if content_length > maximum_zip_bytes:
                    raise ValueError("published TRM ZIP exceeds compressed-byte bound")
                ledger["provider_zip_content_length"] = content_length
                atomic(folder / "acquisition.json", ledger)
                with archive_path.open("xb") as stream:
                    for chunk in response.iter_content(1024**2):
                        if time.monotonic() - started > 2700:
                            raise TimeoutError("published TRM ZIP download expired")
                        written += len(chunk)
                        if written > maximum_zip_bytes:
                            raise ValueError("published TRM ZIP exceeds compressed-byte bound")
                        stream.write(chunk)
                        download_hash.update(chunk)
        if content_length and written != content_length:
            raise ValueError("published TRM ZIP content length differs")
        ledger["state"] = "inventory-verification"
        atomic(folder / "acquisition.json", ledger)
        with zipfile.ZipFile(archive_path) as archive:
            if {row.filename: row.file_size for row in archive.infolist() if not row.is_dir()} != expected:
                raise ValueError("published TRM ZIP header inventory differs before payload read")
        report = inventory_archive(archive_path, folder / "archive-inventory.json")
        if {row["path"]: row["bytes"] for row in report["members"]} != expected:
            raise ValueError("published TRM archive differs from exact version-1 provider files")
        import numpy as np
        arrays, dataset_metadata = {}, {}
        with zipfile.ZipFile(archive_path) as archive:
            for name in expected:
                if name.endswith(".npy"):
                    with archive.open(name) as stream:
                        version = np.lib.format.read_magic(stream)
                        if version == (1, 0):
                            shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream)
                        elif version == (2, 0):
                            shape, fortran, dtype = np.lib.format.read_array_header_2_0(stream)
                        else:
                            raise ValueError("published TRM numeric NPY header version differs")
                        if dtype.hasobject:
                            raise ValueError("published TRM arrays may not contain pickle objects")
                        arrays[name] = {"shape": list(shape), "dtype": str(dtype), "fortran_order": fortran}
                elif name in {"train/dataset.json", "test/dataset.json"}:
                    dataset_metadata[name] = json.loads(archive.read(name))
        atomic(folder / "array-header-observation.json", {"arrays": arrays, "datasets": dataset_metadata,
            "array_payloads_loaded": False, "labels_staged_to_solver": False, "correctness_scored": False})
        ledger.update(state="verified-published-trm-arrays", archive_sha256=report["archive_sha256"],
                      archive_bytes=report["archive_bytes"], raw_bytes=report["uncompressed_bytes"],
                      inventory_sha256=sha_file(folder / "archive-inventory.json"),
                      header_observation_sha256=sha_file(folder / "array-header-observation.json"),
                      crc_verified=True, extracted=False, elapsed_seconds=time.monotonic() - started)
        atomic(folder / "acquisition.json", ledger)
        print(json.dumps(ledger), flush=True)
    except BaseException as error:
        ledger.update(state="incomplete-retained", error_type=type(error).__name__,
                      elapsed_seconds=time.monotonic() - started)
        atomic(folder / "acquisition.json", ledger)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", required=True, choices=("train", "eval"))
    parser.add_argument("--attempt", default="001")
    args = parser.parse_args()
    if len(args.attempt) != 3 or not args.attempt.isascii() or not args.attempt.isdigit():
        raise ValueError("exact three-digit material attempt required")
    acquire(args.role, args.attempt)
