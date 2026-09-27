"""Stdlib-only full GPU UUID binding, shared before and after wheel install."""

import os
import re


def normalize_gpu_uuid(value):
    # CUDA's CUuuid string is bare; NVML/nvidia-smi prefixes the same bytes.
    # Full identity only: no shortened IDs, braces, MIG identifiers or fallback.
    if not isinstance(value, str) or not re.fullmatch(
            r"(?:GPU-)?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", value):
        raise ValueError("full GPU UUID required")
    return "GPU-" + value.removeprefix("GPU-").lower()


def map_hardware_inventory(torch_records, smi_rows):
    by_uuid, physical_indices = {}, set()
    for row in smi_rows:
        if len(row) != 4 or not row[0].isdigit() or not row[2].isdigit():
            raise ValueError("nvidia-smi inventory malformed")
        physical_index, memory_mib = int(row[0]), int(row[2])
        uuid = normalize_gpu_uuid(row[3])
        if uuid in by_uuid or physical_index in physical_indices or memory_mib <= 0:
            raise ValueError("nvidia-smi UUID or physical index duplicate/invalid")
        by_uuid[uuid] = (physical_index, row[1], memory_mib)
        physical_indices.add(physical_index)
    if not torch_records or len(torch_records) > len(smi_rows):
        raise ValueError("Torch and hardware inventory cardinality differs")
    mapped, seen = [], set()
    for index, record in enumerate(torch_records):
        uuid = normalize_gpu_uuid(record["uuid"])
        if type(record["index"]) is not int or record["index"] != index or uuid in seen or uuid not in by_uuid:
            raise ValueError("Torch UUID missing, duplicated or logical index invalid")
        physical_index, name, memory_mib = by_uuid[uuid]
        if (record["name"] != name or type(record["memory_bytes"]) is not int or record["memory_bytes"] <= 0 or
                type(record["bf16"]) is not bool):
            raise ValueError("Torch and nvidia-smi device properties differ")
        seen.add(uuid)
        mapped.append({"index": index, "physical_index": physical_index, "uuid": uuid,
                       "name": name, "memory_bytes": record["memory_bytes"],
                       "memory_mib": memory_mib, "bf16": record["bf16"]})
    return mapped


def collect_hardware_inventory(torch, smi_stdout, save_raw):
    """Retain unnormalized observations before any identity comparison."""
    raw = {"format": "irisx/nvarc-raw-hardware-v1", "smi_stdout": smi_stdout,
           "smi_rows": [[item.strip() for item in line.split(",")]
                        for line in smi_stdout.splitlines() if line.strip()],
           "torch_records": [], "torch_version": torch.__version__,
           "cuda_build": torch.version.cuda, "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES")}
    save_raw(raw)
    try:
        raw["torch_device_count"] = torch.cuda.device_count()
        save_raw(raw)
        for index in range(raw["torch_device_count"]):
            properties = torch.cuda.get_device_properties(index)
            value = properties.uuid
            record = {"index": index, "uuid": str(value), "uuid_repr": repr(value),
                      "uuid_type": type(value).__name__, "name": properties.name,
                      "memory_bytes": properties.total_memory, "bf16": None}
            raw["torch_records"].append(record)
            save_raw(raw)
            with torch.cuda.device(index):
                record["bf16"] = torch.cuda.is_bf16_supported()
            save_raw(raw)
        inventory = map_hardware_inventory(raw["torch_records"], raw["smi_rows"])
        raw["normalized_mapping"] = inventory
        save_raw(raw)
        return inventory
    except Exception as error:
        raw["error"] = {"type": type(error).__name__, "message": str(error)[:2000]}
        save_raw(raw)
        raise
