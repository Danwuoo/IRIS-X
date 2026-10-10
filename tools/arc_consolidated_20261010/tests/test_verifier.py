"""Portable contract checks plus real Linux-only OS isolation acceptance."""
import copy
import hashlib
from pathlib import Path
import subprocess
import unittest
from unittest import mock

from tools.arc_consolidated_20261010 import verifier as v
from tools.arc_consolidated_20261010.tests.support import TemporaryDirectory


IDENTITY = "def transform(grid):\n    return grid\n"


def task(grid=None, output=None):
    grid = [[1, 2], [3, 4]] if grid is None else grid
    return {"task_id": "demo-only", "demos": [{"input": copy.deepcopy(grid),
                                                "output": copy.deepcopy(grid if output is None else output)}]}


def fit_receipt(request):
    result = v._result("fit", "all demos fit", request)
    result.update(worker_wall_seconds=0.01, worker_cpu_seconds=0.01)
    for index, pair in enumerate(request["task"]["demos"]):
        row = v._empty_demo(index, pair)
        row.update(status="match", match=True, actual_shape=row["expected_shape"],
                   mismatch_count=0, gas=7, reason="demo fit")
        result["demos"].append(row)
    result["gas"] = 7 * len(result["demos"])
    return result


class FakeProcess:
    pid = 7654321

    def __init__(self, args, *, stdin, stdout, stderr, cwd, start_new_session,
                 close_fds, transform=None, raw=None, timeout=False, returncode=0):
        self.args, self.timeout, self.waits, self.returncode = args, timeout, 0, returncode
        self.request = v._strict_json(stdin.read())
        value = fit_receipt(self.request)
        if transform is not None:
            transform(value)
        stdout.write(raw if raw is not None else v._canonical(value))
        stdout.flush()
        assert start_new_session is True and close_fds is True

    def wait(self, timeout=None):
        self.waits += 1
        if self.timeout and self.waits == 1:
            raise subprocess.TimeoutExpired(self.args, timeout)
        return self.returncode


class PortableVerifierTests(unittest.TestCase):
    def run_fake(self, **kwargs):
        children = []

        def launch(*args, **kw):
            child = FakeProcess(*args, **kw, **kwargs)
            children.append(child)
            return child

        with mock.patch.object(v, "capability", return_value={"available": True}), \
                mock.patch.object(v, "_check_assets", return_value={}), \
                mock.patch.object(v.tempfile, "TemporaryDirectory", TemporaryDirectory), \
                mock.patch.object(v.subprocess, "Popen", side_effect=launch), \
                mock.patch.object(v.signal, "SIGKILL", 9, create=True), \
                mock.patch.object(v.os, "killpg", create=True) as kill:
            result = v.verify(IDENTITY, task())
        return result, children, kill

    def test_schema_accepts_boundary_and_copies(self):
        original = task([[9 for _ in range(30)] for _ in range(30)])
        checked = v.validate_task(original)
        checked["demos"][0]["input"][0][0] = 1
        self.assertEqual(original["demos"][0]["input"][0][0], 9)

    def test_schema_allows_shared_grid_objects_but_copies_them(self):
        grid = [[1]]
        checked = v.validate_task({"task_id": "x", "demos": [{"input": grid, "output": grid}]})
        self.assertIsNot(checked["demos"][0]["input"], checked["demos"][0]["output"])

    def test_schema_rejects_forbidden_fields_at_every_level(self):
        for key in ("test", "query", "gold", "solutions", "GOLD"):
            for level in (0, 1, 2):
                value = task()
                if level == 0:
                    value[key] = []
                elif level == 1:
                    value["demos"][0][key] = []
                else:
                    value["demos"][0]["input"] = [[{key: []}]]
                with self.subTest(key=key, level=level), self.assertRaises(v.AdmissionError):
                    v.validate_task(value)

    def test_schema_rejects_extra_keys_and_types(self):
        cases = [None, [], {"task_id": "x", "demos": [], "metadata": {}},
                 {"task_id": "x", "demos": []}, {"task_id": 1, "demos": task()["demos"]}]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(v.AdmissionError):
                v.validate_task(value)

    def test_schema_rejects_noninteger_and_oversized_grids(self):
        for grid in ([[True]], [[1.0]], [[10]], [[-1]], [], [[]], [[1], [1, 2]],
                     [[1] * 31], [[1] for _ in range(31)], ((1,),)):
            with self.subTest(grid=grid), self.assertRaises(v.AdmissionError):
                v.validate_task(task(grid))

    def test_cycles_and_excess_depth_rejected(self):
        value = task()
        value["demos"].append(value)
        with self.assertRaises(v.AdmissionError):
            v.validate_task(value)

    def test_nonlinux_fails_closed_before_asset_load_or_dispatch(self):
        with mock.patch.object(v.sys, "platform", "win32"), \
                mock.patch.object(v, "_check_assets") as assets, \
                mock.patch.object(v.subprocess, "Popen") as popen:
            result = v.verify(IDENTITY, task())
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["dispatched"])
        self.assertTrue(result["owned_descendants_stopped"])
        self.assertEqual(result["gas_charged"], 0)
        assets.assert_not_called()
        popen.assert_not_called()

    def test_envelope_limits_cannot_be_raised(self):
        for kwargs in ({"timeout": 3.01}, {"timeout": True}, {"timeout": float("nan")},
                       {"timeout": float("inf")}, {"timeout": 0}, {"max_steps": 200001},
                       {"max_steps": True}, {"max_steps": 0}):
            with self.subTest(kwargs=kwargs), mock.patch.object(v.subprocess, "Popen") as popen:
                result = v.verify(IDENTITY, task(), **kwargs)
                self.assertEqual(result["status"], "admission_rejected")
                popen.assert_not_called()

    def test_source_byte_limit_and_invalid_unicode(self):
        for source in ("x" * 32769, "\ud800", "", None):
            with self.subTest(source_type=type(source)), mock.patch.object(v.subprocess, "Popen") as popen:
                self.assertEqual(v.verify(source, task())["status"], "admission_rejected")
                popen.assert_not_called()

    def test_both_assets_checked_against_exact_pins(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pins = {}
            for filename in v.ASSET_PINS:
                data = filename.encode()
                (root / filename).write_bytes(data)
                pins[filename] = hashlib.sha256(data).hexdigest()
            with mock.patch.object(v, "ASSET_DIRECTORY", root), mock.patch.object(v, "ASSET_PINS", pins):
                self.assertEqual(set(v._check_assets()), set(pins))
                (root / "arc_typed_ir.py").write_bytes(b"changed")
                with self.assertRaises(v.AdmissionError):
                    v._check_assets()

    def test_asset_tamper_refuses_dispatch(self):
        with mock.patch.object(v, "capability", return_value={"available": True}), \
                mock.patch.object(v, "_check_assets", side_effect=v.AdmissionError("hash mismatch")), \
                mock.patch.object(v.subprocess, "Popen") as popen:
            result = v.verify(IDENTITY, task())
        self.assertEqual(result["status"], "admission_rejected")
        popen.assert_not_called()

    def test_valid_bound_receipt_uses_isolated_child_and_observed_gas(self):
        result, children, _ = self.run_fake()
        self.assertEqual(result["status"], "fit")
        self.assertTrue(result["known"])
        self.assertEqual(result["gas_charged"], 7)
        self.assertEqual(result["gas_reserved"], 200000)
        self.assertTrue(result["owned_descendants_stopped"])
        self.assertEqual(children[0].args[1], "-I")
        self.assertNotIn(IDENTITY, children[0].args)
        self.assertEqual(set(children[0].request["task"]), {"task_id", "demos"})

    def test_timeout_kills_reaps_and_charges_full_reservation(self):
        result, children, kill = self.run_fake(timeout=True)
        self.assertEqual(result["status"], "unknown")
        self.assertFalse(result["known"])
        self.assertIsNone(result["gas"])
        self.assertEqual(result["gas_charged"], 200000)
        self.assertEqual(children[0].waits, 2)
        self.assertTrue(result["owned_descendants_stopped"])
        kill.assert_called_once_with(children[0].pid, 9)

    def test_nonzero_process_exit_is_unknown_even_with_plausible_response(self):
        result, _, _ = self.run_fake(returncode=-9)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["gas_charged"], 200000)

    def test_wrong_hashes_cannot_become_scientific_evidence(self):
        for key in ("source_sha256", "task_sha256", "request_sha256"):
            with self.subTest(key=key):
                result, _, _ = self.run_fake(transform=lambda row: row.update({key: "0" * 64}))
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(result["gas_charged"], 200000)

    def test_boolean_counters_and_inconsistent_receipts_rejected(self):
        changes = [lambda r: r.update(gas=True), lambda r: r.update(all_demos_fit=1),
                   lambda r: r["demos"][0].update(gas=True),
                   lambda r: r["demos"][0].update(index=False),
                   lambda r: r["demos"][0].update(mismatch_count=False),
                   lambda r: r["demos"][0].update(expected_shape=[True, 2]),
                   lambda r: r.update(gas=8), lambda r: r.update(status="mismatch"),
                   lambda r: r.update(demos=[]), lambda r: r.update(worker_cpu_seconds=True),
                   lambda r: r.update(status=[]), lambda r: r["demos"][0].update(status={}),
                   lambda r: r.update(worker_wall_seconds=10**1000)]
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(self.run_fake(transform=change)[0]["status"], "unknown")

    def test_partial_duplicate_nonfinite_and_oversized_ipc_fail_closed(self):
        for raw in (b"{", b'{"schema":1,"schema":2}', b'{"x":NaN}',
                    b"x" * (v.MAX_RESPONSE_BYTES + 1)):
            with self.subTest(size=len(raw)):
                self.assertEqual(self.run_fake(raw=raw)[0]["status"], "unknown")

    def test_feedback_bounded_and_counts_missing_cells(self):
        count, samples = v._feedback([[1] * 30 for _ in range(30)], [[2]])
        self.assertEqual(count, 900)
        self.assertEqual(len(samples), 8)
        self.assertEqual(samples[0], {"row": 0, "column": 0, "expected": 2, "actual": 1})

    def test_shared_gas_receipt_requires_sum_and_caps(self):
        request = v._validate_request(IDENTITY, task(), 3, 100)
        value = fit_receipt(request)
        value["gas"] = 101
        with self.assertRaises(ValueError):
            v._validate_receipt(value, request)

    def test_actual_asset_pins(self):
        self.assertEqual(set(v._check_assets()), set(v.ASSET_PINS))


@unittest.skipUnless(v.capability()["available"], "real verifier requires Linux AS/CPU/FSIZE rlimits; no fallback")
class LinuxVerifierAcceptanceTests(unittest.TestCase):
    def test_identity_boundary_and_input_immutable(self):
        value = task([[1] * 30 for _ in range(30)])
        before = copy.deepcopy(value)
        result = v.verify(IDENTITY, value)
        self.assertEqual(result["status"], "fit", result)
        self.assertEqual(value, before)
        self.assertGreater(result["gas"], 0)
        self.assertGreater(result["worker_cpu_seconds"], 0)

    def test_model_source_is_ast_data_not_host_python(self):
        for source in ("import os\ndef transform(grid):\n return grid\n",
                       "def transform(grid):\n return open('forbidden')\n",
                       "def transform(grid):\n return grid.__class__\n"):
            with self.subTest(source=source):
                result = v.verify(source, task())
                self.assertIn(result["status"], {"admission_rejected", "out_of_domain"}, result)

    def test_real_demo_mismatch_retains_bounded_feedback(self):
        result = v.verify(IDENTITY, task([[1] * 30 for _ in range(30)], [[2] * 30 for _ in range(30)]))
        self.assertEqual(result["status"], "mismatch", result)
        self.assertEqual(result["demos"][0]["mismatch_count"], 900)
        self.assertEqual(len(result["demos"][0]["mismatch_samples"]), 8)

    def test_shared_candidate_gas_not_reset_between_demos(self):
        single = v.verify(IDENTITY, task([[1]]))
        self.assertEqual(single["status"], "fit", single)
        value = task([[1]])
        value["demos"].append(copy.deepcopy(value["demos"][0]))
        result = v.verify(IDENTITY, value, max_steps=single["gas"])
        self.assertEqual(result["status"], "out_of_domain", result)
        self.assertEqual(result["demos"][0]["status"], "match")
        self.assertEqual(result["demos"][1]["status"], "not_evaluated")
        self.assertEqual(result["gas"], single["gas"])

    def test_infinite_loop_ends_at_gas_limit(self):
        result = v.verify("def transform(grid):\n while True:\n  pass\n", task(), max_steps=200)
        self.assertEqual(result["status"], "out_of_domain", result)
        self.assertEqual(result["gas"], 200)
        self.assertTrue(result["known"])

    def test_invalid_grid_output_is_out_of_domain(self):
        result = v.verify("def transform(grid):\n return []\n", task())
        self.assertEqual(result["status"], "out_of_domain", result)


if __name__ == "__main__":
    unittest.main()
