"""Finite CPU mailbox faults; real OS termination remains in the E00 fixture."""
import errno
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tools import nvarc_public_eval as core
from tools import nvarc_public_eval_parent as parent
from tools import nvarc_public_eval_runtime as runtime
from tools.nvarc_native_multitask import write
from tests.test_nvarc_public_eval import fixture, record


def denied():
    # Windows CRT read_bytes loses winerror; both an ACL and sharing lock can
    # present as this exact EACCES. Only finite probation can distinguish them.
    return PermissionError(errno.EACCES, 'injected Windows mailbox access denial')


class Clock:
    def __init__(self): self.value = 0
    def __call__(self): return self.value
    def advance(self, value): self.value += value


class Child:
    def __init__(self, rank): self.pid = 90000+rank; self.code = None; self.polls = 0
    def poll(self): self.polls += 1; return self.code


class ParentFixture:
    """Deterministic mailbox IO, with process control separately OS-tested."""
    def __init__(self, root, fault=None, *, clock_step=.2, exit_after_denial=None, plan_change=None):
        self.root = root; self.plan, self.data = fixture(); self.clock = Clock()
        if plan_change: self.plan.update(plan_change)
        self.children = []; self.stops = []; self.dispatched = {}; self.fault = fault
        self.clock_step, self.exit_after_denial = clock_step, exit_after_denial
        self.denials = 0; self.reads = []; self.store = core.ResultStore(root, self.plan, self.data, allow_fixture=True)

    def launch(self, command, **_kwargs):
        rank = int(command[command.index('--rank')+1]); child = Child(rank); self.children.append(child)
        write(self.root/'workers'/str(rank)/'ready.json', {'rank': rank, 'uuid': 'fake-'+str(rank),
            'model_material_digest': self.plan['model_material_digest']})
        return child

    def stop(self, child):
        self.stops.append((child.pid, self.clock()))
        if child.code is None: child.code = -9

    def read(self, path):
        self.reads.append((path.as_posix(), self.clock()))
        if self.fault:
            outcome = self.fault(path, self)
            if isinstance(outcome, BaseException):
                self.denials += 1; raise outcome
            if outcome is not None: return outcome
        return path.read_bytes()

    def pause(self, _seconds):
        self.clock.advance(self.clock_step)
        if self.exit_after_denial is not None and self.denials:
            self.children[0].code = self.exit_after_denial
        for rank, child in enumerate(self.children):
            job = self.root/'workers'/str(rank)/'job.json'
            if not job.is_file() or child.code is not None: continue
            value = json.loads(job.read_bytes())
            if 'task_id' not in value or value['sequence'] in self.dispatched: continue
            key = value['task_id']; self.dispatched[value['sequence']] = key
            directory = self.root/'tasks'/key; directory.mkdir(exist_ok=True)
            write(directory/'checkpoint.json', record(self.plan, self.data, key, [[2]] if key == 'a' else None))
            write(self.root/'workers'/str(rank)/'done.json', {'sequence': value['sequence'], 'task_id': key,
                'outcome': 'partial', 'retired': False})

    def run(self):
        factory = lambda **kw: core.MailboxReader(read_bytes=self.read, windows=True, **kw)
        with patch.object(parent, 'MailboxReader', factory), patch.object(parent, 'stop_process', self.stop), redirect_stdout(io.StringIO()):
            return parent.run_workers(self.root, self.plan, self.data, self.root, self.root,
                [{'uuid': 'fake-'+str(i)} for i in range(4)], self.store, 0,
                launch=self.launch, worker_command=['unused-cpu-fake'], now=self.clock, pause=self.pause)


class MailboxIOTests(unittest.TestCase):
    def test_one_attempt_per_poll_and_recovery_has_no_internal_wait(self):
        values = iter([denied(), b'{"ok":1}']); events = []
        def read(_path):
            value = next(values)
            if isinstance(value, BaseException): raise value
            return value
        reader = core.MailboxReader(read_bytes=read, windows=True, observe=lambda kind, **kw: events.append(kind))
        self.assertIsNone(reader.read('ready.json'))
        self.assertEqual(reader.read('ready.json'), b'{"ok":1}')
        self.assertEqual(events, ['mailbox-read-deferred', 'mailbox-read-recovered'])
        self.assertEqual(reader.recovered_paths, 1)

    def test_persistent_windows_denial_is_five_attempts_and_other_errors_immediate(self):
        calls = []
        def read(_path): calls.append(1); raise denied()
        reader = core.MailboxReader(read_bytes=read, windows=True)
        for _ in range(4): self.assertIsNone(reader.read('ready.json'))
        with self.assertRaises(PermissionError): reader.read('ready.json')
        with self.assertRaises(PermissionError): reader.read('ready.json')
        self.assertEqual(len(calls), 5)
        for windows, error in ((False, denied()), (True, OSError(errno.EIO, 'disk IO fault')),
                               (True, PermissionError(errno.EPERM, 'permanent policy denial'))):
            with self.subTest(windows=windows, error=error):
                reader = core.MailboxReader(read_bytes=lambda _: (_ for _ in ()).throw(error), windows=windows)
                with self.assertRaises(type(error)): reader.read('ready.json')
                self.assertEqual(reader.deferred_reads, 0)

    def test_final_read_is_bounded_after_producer_stop_and_required_missing_fails(self):
        for error in (denied(), FileNotFoundError(errno.ENOENT, 'missing required checkpoint')):
            waits = []; calls = []
            def read(_path): calls.append(1); raise error
            reader = core.MailboxReader(read_bytes=read, windows=True)
            with self.assertRaises(type(error)): reader.final_read('checkpoint.json', required=True, pause=waits.append)
            self.assertEqual(len(calls), 5); self.assertEqual(waits, [.2]*4)
        reader = core.MailboxReader(read_bytes=lambda _: (_ for _ in ()).throw(FileNotFoundError()), windows=True)
        self.assertIsNone(reader.final_read('optional.json', pause=lambda _: self.fail('optional absence must not wait')))

    def test_real_windows_exclusive_handle_denial_recovers_after_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'ready.json'; write(path, {'version': 1})
            before = path.read_bytes()
            if os.name == 'nt':
                import ctypes
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                create = kernel.CreateFileW
                create.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                   ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p)
                create.restype = ctypes.c_void_p
                close = kernel.CloseHandle; close.argtypes = (ctypes.c_void_p,); close.restype = ctypes.c_int
                handle = create(str(path), 0x80000000, 0, None, 3, 0x80, None)
                self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
                reader = core.MailboxReader()
                try:
                    with self.assertRaises(PermissionError): path.read_bytes()
                    self.assertIsNone(reader.read(path))
                finally: self.assertTrue(close(handle))
                self.assertEqual(reader.read(path), before)
                self.assertEqual(reader.recovered_paths, 1)
            else:
                self.assertEqual(core.MailboxReader().read(path), before)

    def test_ready_done_and_checkpoint_short_denials_recover_with_single_dispatch(self):
        targets = {'ready.json', 'done.json', 'checkpoint.json'}; hit = set()
        def fault(path, f):
            if path.name in targets and path.is_file() and path not in hit:
                hit.add(path); return denied()
        with tempfile.TemporaryDirectory() as tmp:
            f = ParentFixture(Path(tmp), fault); result = f.run()
            self.assertEqual((result['dispatched_tasks'], result['finished_tasks']), (2, 2))
            self.assertEqual(result['worker_failures'], [])
            self.assertEqual(sorted(f.dispatched.values()), ['a', 'b'])
            self.assertTrue(all(c.code is not None for c in f.children))
            self.assertEqual(f.store.records['a']['tests'][0]['ranked_grids'], [[[2]]])
            events = [json.loads(r) for r in (f.root/'progress.jsonl').read_bytes().splitlines()]
            self.assertEqual(len([r for r in events if r['event'] == 'task-dispatch-reserved']), 2)
            self.assertEqual(len([r for r in events if r['event'] == 'mailbox-read-recovered']), 8)

    def test_persistent_ready_denial_has_bounded_stop_and_no_dispatch(self):
        def fault(path, _f):
            if path.name == 'ready.json': return denied()
        with tempfile.TemporaryDirectory() as tmp:
            f = ParentFixture(Path(tmp), fault)
            with self.assertRaises(PermissionError): f.run()
            self.assertEqual(f.denials, 17)  # four rounds, then rank zero's fifth denial
            self.assertEqual(len(f.stops), 4); self.assertEqual(f.dispatched, {})

    def test_persistent_done_or_checkpoint_denial_preserves_prior_commit_and_stops(self):
        for target in ('done.json', 'checkpoint.json'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                first_checkpoint = set(); first_done = set()
                def fault(path, _f):
                    if not path.is_file(): return None
                    if target == 'checkpoint.json' and path.name == 'done.json' and path not in first_done:
                        first_done.add(path); return FileNotFoundError(errno.ENOENT, 'not published yet')
                    if path.name != target: return None
                    if target == 'checkpoint.json' and path not in first_checkpoint:
                        first_checkpoint.add(path); return None
                    return denied()
                f = ParentFixture(Path(tmp), fault)
                with self.assertRaises(PermissionError): f.run()
                self.assertEqual(f.store.records['a']['tests'][0]['ranked_grids'], [[[2]]])
                self.assertTrue(all(c.code is not None for c in f.children))
                self.assertEqual(sorted(f.dispatched.values()), ['a', 'b'])
                self.assertEqual(json.loads((f.root/'coverage.json').read_bytes())['tests'], 3)

    def test_read_deferral_does_not_bypass_startup_session_exit_or_task_watchdog(self):
        def ready_fault(path, _f):
            if path.name == 'ready.json': return denied()
        for step in (901, 3301):
            with self.subTest(clock_step=step), tempfile.TemporaryDirectory() as tmp:
                f = ParentFixture(Path(tmp), ready_fault, clock_step=step)
                if step == 901:
                    with self.assertRaisesRegex(RuntimeError, 'startup exceeded'): f.run()
                else:
                    result = f.run(); self.assertEqual(result['dispatched_tasks'], 0)
                self.assertEqual(len(f.stops), 4); self.assertLess(f.denials, 17)
        with tempfile.TemporaryDirectory() as tmp:
            f = ParentFixture(Path(tmp), ready_fault, exit_after_denial=17)
            with self.assertRaisesRegex(RuntimeError, 'startup worker failure'): f.run()
            self.assertEqual(f.children[0].code, 17); self.assertLess(f.denials, 17)
        def done_fault(path, _f):
            if path.name == 'done.json': return denied()
        with tempfile.TemporaryDirectory() as tmp:
            f = ParentFixture(Path(tmp), done_fault, clock_step=.2)
            advance = f.pause
            def pause(seconds):
                advance(seconds); f.clock_step = 181
            f.pause = pause
            result = f.run()
            timed = [r for r in result['worker_failures'] if r['parent_hard_watchdog']]
            self.assertEqual(len(timed), 2)
            self.assertTrue(all(abs(t-181.2) < 1e-8 for _, t in f.stops[:2]))
            self.assertEqual(f.denials, 2)
            self.assertEqual(result['dispatched_tasks'], 2)
            self.assertEqual(set(f.store.records), {'a', 'b'})

    def test_invalid_json_foreign_ready_done_and_checkpoint_fail_closed(self):
        for name, body, error in (
            ('ready.json', b'{"rank":0,"rank":0}', ValueError),
            ('ready.json', b'{"rank":0,"uuid":"foreign","model_material_digest":"wrong"}', RuntimeError),
            ('done.json', b'{"sequence":1,"task_id":"foreign","outcome":"complete","retired":false}', RuntimeError),
            ('done.json', b'{"sequence":999}', RuntimeError),
            ('checkpoint.json', b'{"binding":{"task_id":"foreign"}}', RuntimeError),
            ('checkpoint.json', b'{"binding":NaN}', ValueError)):
            with self.subTest(name=name, body=body), tempfile.TemporaryDirectory() as tmp:
                def fault(path, _f):
                    if path.name == name and path.is_file(): return body
                f = ParentFixture(Path(tmp), fault)
                with self.assertRaises(error): f.run()
                self.assertTrue(all(c.code is not None for c in f.children))
                self.assertEqual(f.denials, 0)
                self.assertNotIn('foreign', f.store.records)

    def test_worker_job_denial_keeps_deadline_and_invalid_messages_fail_closed(self):
        for mode in ('recover', 'persistent', 'deadline', 'invalid', 'foreign'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); plan, data = fixture(); write(root/'plan.json', plan); write(root/'challenges.json', data)
                (root/'workers/0').mkdir(parents=True); clock = Clock(); calls = []; reads = []
                def read(_path):
                    reads.append(1)
                    if mode in ('recover', 'persistent', 'deadline') and (mode != 'recover' or len(reads) == 1): raise denied()
                    if mode == 'invalid': return b'{"sequence":1,"sequence":1}'
                    if mode == 'foreign': return b'{"sequence":1,"task_id":"foreign"}'
                    return b'{"sequence":1,"task_id":"a"}' if not calls else b'{"stop":true}'
                def run(*args, **kw): calls.append(1); return record(plan, data, 'a'), False
                factory = lambda: core.MailboxReader(read_bytes=read, windows=True)
                with patch.object(runtime, 'MailboxReader', factory), patch.object(runtime, 'NativeEngine', return_value=object()), \
                     patch.object(runtime, 'install_owner_guard'), patch.object(runtime, 'run_one_task', run), \
                     patch.object(runtime.signal, 'SIGKILL', 9, create=True), \
                     patch.object(runtime.time, 'time', clock), patch.object(runtime.time, 'sleep', lambda _: clock.advance(.1)), \
                     redirect_stdout(io.StringIO()):
                    if mode == 'persistent':
                        with self.assertRaises(PermissionError): runtime.worker(root, root, root, 0, 1, 1)
                    elif mode == 'invalid':
                        with self.assertRaises(ValueError): runtime.worker(root, root, root, 0, 1, 1)
                    elif mode == 'foreign':
                        with self.assertRaisesRegex(RuntimeError, 'job identity'): runtime.worker(root, root, root, 0, 1, 1)
                    else:
                        runtime.worker(root, root, root, 0, .05 if mode == 'deadline' else 1, 1)
                self.assertEqual(len(calls), int(mode == 'recover'))
                self.assertEqual(len(reads), {'recover': 3, 'persistent': 5, 'deadline': 1, 'invalid': 1, 'foreign': 1}[mode])


if __name__ == '__main__': unittest.main()
