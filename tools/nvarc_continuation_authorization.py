"""Bind an exact owner decision and run identity to a reviewed draft."""

import hashlib
import json
from pathlib import Path

from irisx.errors import ValidationError

DECISIONS = {
    "nvarc-m2-source-cont-001": "Decision 0033",
    "nvarc-m3-teacher-small-004": "Decision 0033",
    "nvarc-m2-source-cont-002": "Decision 0034",
    "nvarc-m3-teacher-small-005": "Decision 0034",
}


def authorize(plan: dict, draft: bytes, path: Path) -> dict:
    binding = json.loads(path.read_bytes())
    run = plan.get("run_id")
    if (run not in DECISIONS or plan.get("approved") is not False or
            plan.get("owner_decision") is not None or
            binding.get("approved") is not True or
            binding.get("owner_decision") != DECISIONS[run] or
            binding.get("run_id") != run or
            binding.get("kernel_id") != "danielwuu/" + run or
            binding.get("draft_plan_sha256") != hashlib.sha256(draft).hexdigest()):
        raise ValidationError("exact continuation decision/run authorization differs")
    return {**plan, "approved": True, "owner_decision": DECISIONS[run],
            "kernel_id": binding["kernel_id"]}
