"""Read exact Kaggle source identity without exposing source or account material.

Kaggle CLI 2.2.4's pull writes selected metadata but omits the SDK's
ApiKernelMetadata.current_version_number. This bounded helper reads that actual
field through the same get_kernel endpoint used by the installed CLI. It never
pushes, edits, publishes or deletes a kernel.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from importlib.metadata import version
import io
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import digest


def notebook_source_identity(source: str | dict) -> str:
    """Hash only executable cells, identically for local and remote notebooks."""
    data = json.loads(source) if isinstance(source, str) else source
    cells = [{"cell_type": cell["cell_type"],
              "source": "".join(cell["source"]) if isinstance(cell["source"], list)
              else cell["source"]} for cell in data["cells"]]
    return digest(cells)


def parse_reference(reference: str) -> tuple[str, str, int | None]:
    match = re.fullmatch(r"([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)(?:/([1-9][0-9]*))?", reference)
    if match is None:
        raise ValueError("expected owner/slug or owner/slug/positive-version")
    return match[1], match[2], int(match[3]) if match[3] else None


def readback(reference: str) -> dict:
    owner, slug, requested_version = parse_reference(reference)
    if version("kaggle") != "2.2.4":
        raise RuntimeError("readback adapter requires inspected Kaggle 2.2.4")
    # Imports and authentication occur only for this explicit read operation.
    # Suppress third-party informational output; never print credentials, full
    # exception responses, source bodies or whole metadata dictionaries.
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from kaggle.api.kaggle_api_extended import KaggleApi
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest

        api = KaggleApi()
        api.authenticate()
        with api.build_kaggle_client() as client:
            request = ApiGetKernelRequest()
            request.user_name = owner
            request.kernel_slug = f"{slug}/{requested_version}" if requested_version else slug
            response = client.kernels.kernels_api_client.get_kernel(request)

    metadata = response.metadata
    actual_ref = metadata.ref
    current_version = metadata.current_version_number
    is_private = metadata.is_private
    if actual_ref != f"{owner}/{slug}":
        raise ValueError("remote notebook reference mismatch")
    if type(current_version) is not int or current_version <= 0:
        raise ValueError("remote current version unavailable")
    if type(is_private) is not bool:
        raise ValueError("remote privacy status unavailable")
    if not isinstance(response.blob.source, str):
        raise ValueError("remote source unavailable")
    # current_version_number is reported as observed, never replaced with the
    # requested version. Callers must require current_version == target version
    # around latest-only status/log/output operations.
    return {"ref": actual_ref, "current_version_number": current_version,
            "is_private": is_private,
            "notebook_sha256": notebook_source_identity(response.blob.source)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference")
    args = parser.parse_args()
    try:
        result = readback(args.reference)
    except Exception as exc:
        print("Kaggle source identity readback failed: " + type(exc).__name__, file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
