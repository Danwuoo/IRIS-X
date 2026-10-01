"""Read exact public TRM notebook v18 using the official CLI slug convention."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools.execute_nvarc_overnight_sft import token, client_for
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest


def acquire():
    folder = ROOT / ".irisx/nvarc-original/materials/trm-submission-v18-20261002-002"
    if folder.exists():
        raise ValueError("new exact public source acquisition identity required")
    folder.mkdir(parents=True)
    ledger = {"owner_decision": "Decision 0053", "ref": "cpmpml/arc2-trm-v31/18",
              "request_reserved": 1, "requested_version_number": 18,
              "source_reference_script_version_id": 278223801,
              "request_encoding": "kernel_slug includes /18; official CLI kernels_pull convention",
              "model_calls": 0, "maximum_paid_usd": 0, "state": "request-reserved"}
    atomic(folder / "acquisition.json", ledger)
    try:
        request = ApiGetKernelRequest()
        request.user_name = "cpmpml"
        request.kernel_slug = "arc2-trm-v31/18"
        with client_for(token()) as client:
            response = client.kernels.kernels_api_client.get_kernel(request).to_dict()
        metadata = response["metadata"]
        notebook = response["blob"]["source"].encode("utf-8")
        json.loads(notebook)
        atomic(folder / "provider-metadata.json", metadata)
        (folder / "notebook.ipynb").write_bytes(notebook)
        exact = metadata.get("currentVersionNumber") == 18
        ledger.update(state="verified-version-18-source" if exact else "retained-version-not-confirmed",
                      returned_version_number=metadata.get("currentVersionNumber"),
                      notebook_sha256=sha_file(folder / "notebook.ipynb"), notebook_bytes=len(notebook),
                      provider_metadata_sha256=sha_file(folder / "provider-metadata.json"),
                      exact_script_version_id_independently_returned=False)
    except BaseException as error:
        ledger.update(state="request-failed", error_type=type(error).__name__,
                      http_status=getattr(getattr(error, "response", None), "status_code", None))
        atomic(folder / "acquisition.json", ledger)
        raise
    atomic(folder / "acquisition.json", ledger)
    print(json.dumps(ledger), flush=True)


if __name__ == "__main__":
    acquire()
