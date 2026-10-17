"""Portable synthetic WinAPI protocol tests, not native Windows ownership proof.

The real job lifecycle closure runs against a literal in-memory kernel double.
The existing real-process Windows regressions remain the operating-system proof.
No process is created or signalled by these interface tests.
"""

from contextlib import ExitStack
import ctypes
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from irisx import arc_nvarc_combined as runtime
from irisx.errors import ValidationError


class KernelFunction:
    """A callable that accepts the ctypes signature declarations unchanged."""

    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


class Process:
    pid = 4101
    _handle = 17

    def __init__(self, returncode=0):
        # A successful leader exit must not be mistaken for descendant cleanup.
        self.returncode = returncode
        self.kills = 0
        self.waits = []

    def poll(self):
        return self.returncode

    def kill(self):
        self.kills += 1
        self.returncode = 1

    def wait(self, timeout):
        self.waits.append(timeout)
        if self.returncode is None:
            raise runtime.subprocess.TimeoutExpired("synthetic owned worker", timeout)
        return self.returncode


class Kernel:
    handle = 23

    def __init__(self):
        self.members = [4101, 4102]
        self.active = len(self.members)
        self.calls = []
        self.closed = False
        self.fail_stop = False
        self.fail_close = False
        self.remain_active = False
        self.CreateJobObjectW = KernelFunction(self.create)
        self.SetInformationJobObject = KernelFunction(self.configure)
        self.AssignProcessToJobObject = KernelFunction(self.assign)
        self.QueryInformationJobObject = KernelFunction(self.query)
        self.TerminateJobObject = KernelFunction(self.stop)
        self.CloseHandle = KernelFunction(self.close)

    @staticmethod
    def check(condition):
        if not condition:
            raise AssertionError("unexpected synthetic kernel interface call")

    def create(self, security, name):
        self.check(security is None and name is None)
        return self.handle

    def configure(self, handle, kind, pointer, size):
        self.check(handle == self.handle and kind == 9)
        self.check(pointer._obj.BasicLimitInformation.LimitFlags == 0x2000)
        self.check(size == ctypes.sizeof(pointer._obj))
        return 1

    def assign(self, handle, process_handle):
        self.check(handle == self.handle and process_handle.value == Process._handle)
        return 1

    def query(self, handle, kind, pointer, size, returned):
        self.check(handle == self.handle and not self.closed)
        self.check(size == ctypes.sizeof(pointer._obj) and returned is None)
        self.calls.append(("query", kind))
        if kind == 3:
            pointer._obj.assigned = len(self.members)
            pointer._obj.listed = len(self.members)
            for index, pid in enumerate(self.members):
                pointer._obj.pids[index] = pid
        elif kind == 1:
            pointer._obj.ActiveProcesses = self.active
        else:
            raise AssertionError("unexpected job information class")
        return 1

    def stop(self, handle, code):
        self.check(handle == self.handle and not self.closed and code == 1)
        self.calls.append(("stop",))
        if self.fail_stop:
            return 0
        if not self.remain_active:
            self.members = []
            self.active = 0
        return 1

    def close(self, handle):
        self.check(handle == self.handle and not self.closed)
        self.calls.append(("close",))
        if self.fail_close:
            return 0
        self.closed = True
        return 1


class WindowsJobLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.kernel = Kernel()
        self.context = ExitStack()
        self.addCleanup(self.context.close)
        # Replace only the runtime's OS interface, never global os.name or any
        # real process/signalling operation. This deliberately selects WinAPI
        # protocol code on every host without claiming that host is Windows.
        self.context.enter_context(patch.object(runtime, "os", SimpleNamespace(name="nt")))
        self.context.enter_context(patch.object(ctypes, "WinDLL", return_value=self.kernel, create=True))
        self.context.enter_context(patch.object(ctypes, "get_last_error", return_value=5, create=True))
        self.context.enter_context(patch.object(ctypes, "WinError",
            side_effect=lambda code: OSError(code, "synthetic kernel failure"), create=True))

    def test_deferred_force_reap_retains_handle_until_measured_reap(self):
        process = Process()
        job = runtime._windows_job(process)
        errors = runtime._force_reap(process, job, 0, defer_job_close=True)
        self.assertEqual(errors, [])
        self.assertFalse(self.kernel.closed)
        self.assertEqual(self.kernel.calls, [("query", 3), ("stop",)])
        self.assertEqual(process.waits, [0])

        observation = runtime._reap(process, job, .1, .1)
        self.assertEqual(observation, {"kind": "owned-windows-job",
            "initial_process_ids": [4101, 4102], "active_processes_after_termination": 0})
        self.assertEqual(self.kernel.calls,
            [("query", 3), ("stop",), ("stop",), ("query", 1), ("close",)])
        self.assertTrue(self.kernel.closed)
        self.assertEqual(process.waits, [0, .1])

    def test_first_descendant_membership_survives_repeated_stop_requests(self):
        job = runtime._windows_job(Process())
        job.request_termination()
        self.assertEqual(self.kernel.members, [])
        job.request_termination()
        self.assertFalse(self.kernel.closed)
        self.assertNotIn(("query", 1), self.kernel.calls)

        observation = job.terminate(.1)
        self.assertEqual(observation["initial_process_ids"], [4101, 4102])
        self.assertEqual(observation["active_processes_after_termination"], 0)
        self.assertEqual(self.kernel.calls.count(("query", 3)), 1)
        self.assertEqual(self.kernel.calls.count(("close",)), 1)

    def test_failed_stop_closes_fail_closed_and_cannot_fabricate_cleanup_proof(self):
        process = Process(returncode=None)
        job = runtime._windows_job(process)
        self.kernel.fail_stop = True
        errors = runtime._force_reap(process, job, .1, defer_job_close=True)
        self.assertEqual(len(errors), 1)
        self.assertIn("synthetic kernel failure", errors[0])
        self.assertTrue(self.kernel.closed)
        self.assertEqual(process.kills, 1)
        self.assertEqual(process.waits, [.1])
        with self.assertRaisesRegex(ValidationError, "closed before cleanup observation"):
            runtime._reap(process, job, .1, .1)
        self.assertNotIn(("query", 1), self.kernel.calls)
        self.assertEqual(self.kernel.calls.count(("close",)), 1)

    def test_failed_stop_and_close_retain_errors_and_still_reap_leader(self):
        process = Process(returncode=None)
        job = runtime._windows_job(process)
        self.kernel.fail_stop = self.kernel.fail_close = True
        errors = runtime._force_reap(process, job, .1, defer_job_close=True)
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("synthetic kernel failure" in error for error in errors))
        self.assertEqual(process.kills, 1)
        self.assertEqual(process.waits, [.1])
        self.assertNotIn(("query", 1), self.kernel.calls)
        # This is a synthetic handle, but explicitly release it once the
        # injected failure is removed so the lifecycle under test is complete.
        self.kernel.fail_close = False
        job()
        self.assertTrue(self.kernel.closed)

    def test_without_deferral_force_reap_closes_immediately(self):
        process = Process(returncode=None)
        job = runtime._windows_job(process)
        self.assertEqual(runtime._force_reap(process, job, .1), [])
        self.assertEqual(self.kernel.calls, [("close",)])
        self.assertTrue(self.kernel.closed)
        self.assertEqual(process.kills, 1)
        self.assertEqual(process.waits, [.1])

    def test_active_descendants_cannot_be_reported_as_measured_cleanup(self):
        job = runtime._windows_job(Process())
        self.kernel.remain_active = True
        job.request_termination()
        with self.assertRaisesRegex(TimeoutError, "descendants did not terminate"):
            job.terminate(0)
        self.assertTrue(self.kernel.closed)
        self.assertEqual(self.kernel.calls.count(("query", 3)), 1)
        self.assertEqual(self.kernel.calls[-2:], [("query", 1), ("close",)])


if __name__ == "__main__":
    unittest.main()
