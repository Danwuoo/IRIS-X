"""Offline fixtures executing the generated notebook's exact hardware segment."""

import ast
import base64
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from irisx.arc_nvarc_combined import atomic, read, select_devices
from irisx.errors import ValidationError

UUIDS = [letter * 8 + "-" + letter * 4 + "-" + letter * 4 + "-" + letter * 4 + "-" + letter * 12
         for letter in "abcd"]


def records(uuids=None):
    return [{"uuid": value, "name": "NVIDIA L4", "memory_bytes": 23659151360, "bf16": True}
            for value in (UUIDS if uuids is None else uuids)]


def rows():
    # CUDA logical order and SMI row order/physical ordinals deliberately differ.
    return [[str(index), "NVIDIA L4", "23034", "GPU-" + UUIDS[position]]
            for index, position in ((2, 1), (0, 3), (3, 0), (1, 2))]


def fake_torch(values):
    class CUDA:
        active = 0
        def device_count(self):
            return len(values)
        def get_device_properties(self, index):
            value = values[index]
            return SimpleNamespace(uuid=value["uuid"], name=value["name"], total_memory=value["memory_bytes"])
        @contextmanager
        def device(self, index):
            previous, self.active = self.active, index
            try:
                yield
            finally:
                self.active = previous
        def is_bf16_supported(self):
            return values[self.active]["bf16"]
    module = ModuleType("torch")
    module.cuda = CUDA()
    module.version = SimpleNamespace(cuda="controlled-fixture")
    module.__version__ = "controlled-fixture-no-CUDA"
    return module


def hardware_segment(source):
    tree = ast.parse(source)
    block = next(node for node in tree.body if isinstance(node, ast.Try))
    def phase(node, value):
        return (isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == "phase" and
                isinstance(node.value, ast.Constant) and node.value.value == value)
    start = next(i for i, node in enumerate(block.body) if phase(node, "hardware-inventory"))
    end = next(i for i, node in enumerate(block.body) if phase(node, "mount-resolution"))
    definitions = [node for node in tree.body if isinstance(node, (ast.Import, ast.FunctionDef)) and
                   (isinstance(node, ast.FunctionDef) and node.name in
                    {"normalize_gpu_uuid", "map_hardware_inventory", "collect_hardware_inventory"} or
                    isinstance(node, ast.Import) and all(alias.name in {"os", "re"} for alias in node.names))]
    assert len([node for node in definitions if isinstance(node, ast.FunctionDef)]) == 3
    selection = next(node for node in block.body if isinstance(node, ast.Assign) and
                     ast.unparse(node.targets[0]) == "hardware")
    payloads = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and
                    ast.unparse(node.targets[0]) == "PAYLOADS")
    return (compile(ast.Module(body=definitions + block.body[start:end] + [selection], type_ignores=[]),
                    "exact-generated-hardware-segment", "exec"), json.loads(base64.b64decode(payloads["plan"])))


def execute_hardware(source, values, smi_rows, output):
    code, plan = hardware_segment(source)
    calls = []
    def smi(command, **kwargs):
        assert command[0] == "nvidia-smi" and command[1] == "--query-gpu=index,name,memory.total,uuid"
        assert kwargs["timeout"] <= 30 and kwargs["check"] is True
        calls.append(command)
        return SimpleNamespace(stdout="\n".join(", ".join(row) for row in smi_rows))
    import subprocess
    namespace = {"emit": lambda *args, **kwargs: None, "remaining": lambda *args: 30,
                 "save": lambda name, value: atomic(output / name, value), "setup_deadline": 300,
                 "select_devices": select_devices, "plan": plan, "subprocess": subprocess}
    with patch.dict("sys.modules", {"torch": fake_torch(values)}), patch("subprocess.run", side_effect=smi):
        exec(code, namespace)
    assert len(calls) == 1
    return namespace["hardware"]


def probe_hardware(source):
    """Simulated inventory evidence, explicitly distinct from actual GPU acceptance."""
    count = 0
    with tempfile.TemporaryDirectory(prefix="nvarc-hardware-fixture-") as temp:
        root = Path(temp)
        for values in (records(), records(["GPU-" + value.upper() for value in UUIDS])):
            hardware = execute_hardware(source, values, rows(), root)
            assert [hardware["assignments"][b]["physical_index"] for b in ("m2", "m3")] == [3, 2]
            assert [hardware["assignments"][b]["uuid"] for b in ("m2", "m3")] == ["GPU-" + v for v in UUIDS[:2]]
            count += 1
        bad = []
        wrong = records(); wrong[0]["uuid"] = "99999999-9999-9999-9999-999999999999"
        bad.append((wrong, rows(), "Torch UUID missing"))
        partial = records(); partial[0]["uuid"] = UUIDS[0][:8]; bad.append((partial, rows(), "full GPU UUID"))
        duplicate = records(); duplicate[1]["uuid"] = UUIDS[0]; bad.append((duplicate, rows(), "duplicated"))
        duplicate_smi = rows(); duplicate_smi[1][3] = duplicate_smi[0][3].removeprefix("GPU-")
        bad.append((records(), duplicate_smi, "duplicate/invalid"))
        duplicate_index = rows(); duplicate_index[1][0] = duplicate_index[0][0]
        bad.append((records(), duplicate_index, "duplicate/invalid"))
        malformed = rows(); malformed[0] = malformed[0][:3]; bad.append((records(), malformed, "malformed"))
        for key, value in (("bf16", False), ("memory_bytes", 16 * 10**9)):
            limited = records(); limited[0][key] = value; bad.append((limited, rows(), "two BF16 L4"))
        small_smi = rows(); small_smi[2][2] = "16000"; bad.append((records(), small_smi, "two BF16 L4"))
        t4 = records(); t4[0]["name"] = "Tesla T4"
        smi_t4 = rows(); smi_t4[2][1] = "Tesla T4"; bad.append((t4, smi_t4, "two BF16 L4"))
        for values, smi_rows, expected in bad:
            try:
                execute_hardware(source, values, smi_rows, root)
            except (ValueError, ValidationError) as error:
                assert expected in str(error), (expected, str(error))
                # Preserve the raw observations even when a later L4 gate fails.
                raw = read(root / "hardware-raw.json")
                assert raw["smi_rows"] == smi_rows
                assert raw["torch_records"][0]["uuid"] == values[0]["uuid"]
                count += 1
            else:
                raise AssertionError("invalid hardware fixture was accepted")
    return {"kind": "controlled-Torch-and-SMI-fixtures", "cases_passed": count,
            "generated_hardware_path_executed": True, "raw_diagnostics_on_rejection": True,
            "actual_cuda_devices": False, "model_calls": 0, "external_calls": 0}
