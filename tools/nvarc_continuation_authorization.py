"""Bind the owner's Decision 0033 to one unchanged reviewed draft."""

import hashlib
import json
from pathlib import Path

from irisx.errors import ValidationError

DECISION = "Decision 0033"
RUNS = {"nvarc-m2-source-cont-001", "nvarc-m3-teacher-small-004"}


def authorize(plan: dict, draft: bytes, path: Path) -> dict:
    binding = json.loads(path.read_bytes())
    run = plan.get("run_id")
    if (run not in RUNS or plan.get("approved") is not False or
            plan.get("owner_decision") is not None or
            binding.get("approved") is not True or
            binding.get("owner_decision") != DECISION or
            binding.get("run_id") != run or
            binding.get("kernel_id") != "danielwuu/" + run or
            binding.get("draft_plan_sha256") != hashlib.sha256(draft).hexdigest()):
        raise ValidationError("exact Decision 0033 continuation authorization differs")
    return {**plan, "approved": True, "owner_decision": DECISION,
            "kernel_id": binding["kernel_id"]}
