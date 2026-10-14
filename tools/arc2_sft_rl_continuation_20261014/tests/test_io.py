"""Synthetic local I/O and collector-link tests; no evaluator/provider fixtures."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import stat
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).absolute().parents[2]))
from arc2_sft_rl_continuation_20261014 import io as local_io
from arc2_sft_rl_continuation_20261014.io import (
    InputError, MAX_JSON_BYTES, read_json, report_links, write_new_json,
)


try:
    local_io._platform(write=True)
except InputError:
    SAFE_IO_AVAILABLE = False
else:
    SAFE_IO_AVAILABLE = True


class PlatformTests(unittest.TestCase):
    def test_unsupported_platform_fails_closed(self):
        for attribute, value in (("name", "nt"), ("supports_dir_fd", set()),
                                 ("supports_follow_symlinks", set())):
            with self.subTest(attribute=attribute), mock.patch.object(local_io.os, attribute, value):
                with self.assertRaisesRegex(InputError, "unsupported_safe_io_platform"):
                    read_json("unused.json", "0" * 64)
                with self.assertRaisesRegex(InputError, "unsupported_safe_io_platform"):
                    write_new_json("unused.json", {})


@unittest.skipUnless(SAFE_IO_AVAILABLE, "POSIX no-follow descriptor I/O required")
class LocalIOTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def save(self, raw):
        path = self.root / "report.json"
        path.write_bytes(raw)
        return path, hashlib.sha256(raw).hexdigest()

    def test_read_round_trip(self):
        path, sha = self.save(b'{"status":"STOPPED_INCOMPLETE"}')
        value, descriptor = read_json(path, sha)
        self.assertEqual(value, {"status": "STOPPED_INCOMPLETE"})
        self.assertEqual(descriptor, {"bytes": path.stat().st_size, "sha256": sha})

    def test_changed_hash(self):
        path, sha = self.save(b"{}")
        path.write_bytes(b'{"changed":true}')
        with self.assertRaisesRegex(InputError, "input_hash"):
            read_json(path, sha)

    def test_strict_json(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}', b'[]', b'\xff', b'{'):
            with self.subTest(raw=raw):
                path, sha = self.save(raw)
                with self.assertRaises(InputError):
                    read_json(path, sha)

    def test_bad_hash(self):
        path, _ = self.save(b"{}")
        for sha in (None, True, "A" * 64, "short"):
            with self.assertRaises(InputError):
                read_json(path, sha)

    def test_symlink_and_parent_symlink(self):
        path, sha = self.save(b"{}")
        alias = self.root / "alias.json"
        alias.symlink_to(path)
        with self.assertRaisesRegex(InputError, "symlink_path"):
            read_json(alias, sha)
        linked = self.root / "linked"
        linked.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(InputError, "symlink_path"):
            read_json(linked / path.name, sha)

    def test_hardlink_and_fifo_rejected(self):
        path, sha = self.save(b"{}")
        os.link(path, self.root / "hardlink.json")
        with self.assertRaisesRegex(InputError, "regular_single_link_input"):
            read_json(path, sha)
        if hasattr(os, "mkfifo"):
            fifo = self.root / "fifo"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(InputError, "regular_single_link_input"):
                read_json(fifo, sha)

    def test_oversized_input_rejected_before_read(self):
        path = self.root / "oversized.json"
        with path.open("wb") as stream:
            stream.truncate(MAX_JSON_BYTES + 1)
        with self.assertRaisesRegex(InputError, "input_size"):
            read_json(path, "0" * 64)

    def test_no_traversal(self):
        path, sha = self.save(b"{}")
        with self.assertRaisesRegex(InputError, "path_traversal"):
            read_json(self.root / ".." / self.root.name / path.name, sha)

    def test_atomic_write_refuses_overwrite(self):
        path = self.root / "output.json"
        descriptor = write_new_json(path, {"offline": True})
        before = path.read_bytes()
        self.assertEqual(hashlib.sha256(before).hexdigest(), descriptor["sha256"])
        with self.assertRaisesRegex(InputError, "output_exists"):
            write_new_json(path, {"replacement": True})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.root.glob(".arc2-report-*")), [])

    def test_publication_failure_cleans_temporary(self):
        with mock.patch("arc2_sft_rl_continuation_20261014.io.os.link", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                write_new_json(self.root / "output.json", {"offline": True})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_output_parent_must_exist_and_be_regular_path(self):
        with self.assertRaisesRegex(InputError, "output_parent_missing"):
            write_new_json(self.root / "absent" / "output.json", {})
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(InputError, "symlink_path"):
            write_new_json(alias / "output.json", {})

    @contextmanager
    def tracked_fds(self):
        opened = set()
        real_open, real_dup, real_close = os.open, os.dup, os.close

        def track_open(*args, **kwargs):
            fd = real_open(*args, **kwargs)
            opened.add(fd)
            return fd

        def track_dup(*args, **kwargs):
            fd = real_dup(*args, **kwargs)
            opened.add(fd)
            return fd

        def track_close(fd):
            real_close(fd)
            opened.discard(fd)

        with mock.patch.object(local_io.os, "open", side_effect=track_open), \
                mock.patch.object(local_io.os, "dup", side_effect=track_dup), \
                mock.patch.object(local_io.os, "close", side_effect=track_close):
            try:
                yield
            finally:
                self.assertEqual(opened, set(), "owned descriptors leaked")

    def ancestor_tree(self, raw=b"{}"):
        ancestor = self.root / "ancestor"
        ancestor.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (ancestor / "report.json").write_bytes(raw)
        (outside / "report.json").write_bytes(b'{"foreign":true}')
        return ancestor, outside, self.root / "moved"

    def test_success_closes_every_descriptor(self):
        path, sha = self.save(b"{}")
        with self.tracked_fds():
            read_json(path, sha)
            write_new_json(self.root / "output.json", {"complete": True})

    def test_empty_input(self):
        path, sha = self.save(b"")
        with self.tracked_fds(), self.assertRaisesRegex(InputError, "input_size"):
            read_json(path, sha)

    def test_path_bounds_and_root_rejected_before_open(self):
        for path in ("/", "/" + "/".join(["x"] * local_io.MAX_PATH_PARTS), "/" + "x" * local_io.MAX_PATH_BYTES):
            with self.subTest(path_length=len(path)), mock.patch.object(local_io.os, "open") as opened:
                with self.assertRaisesRegex(InputError, "invalid_path"):
                    read_json(path, "0" * 64)
                opened.assert_not_called()

    def test_ancestor_replaced_between_stat_and_open(self):
        ancestor, outside, moved = self.ancestor_tree()
        real_open = os.open

        def replace(name, flags, *args, **kwargs):
            if name == "ancestor":
                ancestor.rename(moved)
                ancestor.mkdir()
                (ancestor / "report.json").write_bytes(b"{}")
            return real_open(name, flags, *args, **kwargs)

        with self.tracked_fds():
            # Use the tracking wrapper as the underlying open, so the rejected
            # replacement directory descriptor is counted as well.
            real_open = os.open
            with mock.patch.object(local_io.os, "open", side_effect=replace):
                with self.assertRaisesRegex(InputError, "path_changed"):
                    read_json(ancestor / "report.json", hashlib.sha256(b"{}").hexdigest())
        self.assertEqual((outside / "report.json").read_bytes(), b'{"foreign":true}')

    def test_input_ancestor_swap_at_file_open_is_contained(self):
        ancestor, outside, moved = self.ancestor_tree()
        original_inode = (ancestor / "report.json").stat().st_ino
        real_open = os.open
        seen = []

        def replace(name, flags, *args, **kwargs):
            if name == "report.json":
                ancestor.rename(moved)
                ancestor.symlink_to(outside, target_is_directory=True)
            fd = real_open(name, flags, *args, **kwargs)
            if name == "report.json":
                seen.append(os.fstat(fd).st_ino)
            return fd

        with self.tracked_fds():
            real_open = os.open
            with mock.patch.object(local_io.os, "open", side_effect=replace), \
                    self.assertRaisesRegex(InputError, "path_changed"):
                read_json(ancestor / "report.json", hashlib.sha256(b"{}").hexdigest())
        self.assertEqual(seen, [original_inode])

    def test_input_ancestor_swap_during_read_is_rejected(self):
        ancestor, outside, moved = self.ancestor_tree()
        real_read = os.read
        switched = False

        def replace(fd, count):
            nonlocal switched
            raw = real_read(fd, count)
            if not switched:
                switched = True
                ancestor.rename(moved)
                ancestor.symlink_to(outside, target_is_directory=True)
            return raw

        with self.tracked_fds(), mock.patch.object(local_io.os, "read", side_effect=replace), \
                self.assertRaisesRegex(InputError, "path_changed"):
            read_json(ancestor / "report.json", hashlib.sha256(b"{}").hexdigest())

    def test_input_replaced_between_stat_and_open(self):
        path, sha = self.save(b"{}")
        replacement = self.root / "replacement.json"
        replacement.write_bytes(b"{}")
        real_open = os.open

        def replace(name, flags, *args, **kwargs):
            if name == path.name:
                replacement.replace(path)
            return real_open(name, flags, *args, **kwargs)

        with self.tracked_fds():
            real_open = os.open
            with mock.patch.object(local_io.os, "open", side_effect=replace), \
                    self.assertRaisesRegex(InputError, "input_replaced"):
                read_json(path, sha)

    def test_input_replaced_by_fifo_at_open_never_blocks(self):
        path, sha = self.save(b"{}")
        real_open = os.open

        def replace(name, flags, *args, **kwargs):
            if name == path.name:
                path.unlink()
                os.mkfifo(path)
                self.assertTrue(flags & os.O_NONBLOCK)
            return real_open(name, flags, *args, **kwargs)

        with self.tracked_fds():
            real_open = os.open
            with mock.patch.object(local_io.os, "open", side_effect=replace), \
                    self.assertRaisesRegex(InputError, "input_replaced"):
                read_json(path, sha)

    def test_input_hardlink_added_during_read(self):
        path, sha = self.save(b"{}")
        real_read = os.read
        switched = False

        def replace(fd, count):
            nonlocal switched
            raw = real_read(fd, count)
            if not switched:
                switched = True
                os.link(path, self.root / "hardlink.json")
            return raw

        with self.tracked_fds(), mock.patch.object(local_io.os, "read", side_effect=replace), \
                self.assertRaisesRegex(InputError, "input_changed"):
            read_json(path, sha)

    def test_input_name_replaced_after_read(self):
        path, sha = self.save(b"{}")
        replacement = self.root / "replacement.json"
        replacement.write_bytes(b"{}")
        real_read = os.read
        switched = False

        def replace(fd, count):
            nonlocal switched
            raw = real_read(fd, count)
            if not switched:
                switched = True
                replacement.replace(path)
            return raw

        with self.tracked_fds(), mock.patch.object(local_io.os, "read", side_effect=replace), \
                self.assertRaisesRegex(InputError, "input_changed"):
            read_json(path, sha)

    def test_input_growth_is_bounded(self):
        path, sha = self.save(b"{}")
        real_read = os.read
        counts = []

        def grow(fd, count):
            if not counts:
                path.write_bytes(b" " * 1024)
            result = real_read(fd, count)
            counts.append(len(result))
            return result

        with self.tracked_fds(), mock.patch.object(local_io, "MAX_JSON_BYTES", 32), \
                mock.patch.object(local_io.os, "read", side_effect=grow), \
                self.assertRaisesRegex(InputError, "input_changed"):
            read_json(path, sha)
        self.assertLessEqual(sum(counts), 33)

    def test_read_failure_and_interrupt_close_descriptors(self):
        path, sha = self.save(b"{}")
        for failure in (OSError("read failed"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__), self.tracked_fds(), \
                    mock.patch.object(local_io.os, "read", side_effect=failure), \
                    self.assertRaises(type(failure)):
                read_json(path, sha)

    def test_huge_integer_parse_error_has_fixed_code(self):
        if not hasattr(sys, "get_int_max_str_digits") or not sys.get_int_max_str_digits():
            self.skipTest("interpreter has no active integer conversion limit")
        path, sha = self.save(b'{"private":' + b"9" * (sys.get_int_max_str_digits() + 1) + b"}")
        with self.assertRaisesRegex(InputError, "^invalid_json$"):
            read_json(path, sha)

    def test_existing_output_kinds_are_preserved(self):
        path, _ = self.save(b"{}")
        alias = self.root / "alias.json"
        alias.symlink_to(path)
        dangling = self.root / "dangling.json"
        dangling.symlink_to(self.root / "absent.json")
        directory = self.root / "directory"
        directory.mkdir()
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        hardlink = self.root / "hardlink.json"
        os.link(path, hardlink)
        for output in (path, alias, dangling, directory, fifo, hardlink):
            identity = output.lstat()
            with self.subTest(name=output.name), self.tracked_fds(), \
                    self.assertRaisesRegex(InputError, "output_exists"):
                write_new_json(output, {"replacement": True})
            self.assertEqual(output.lstat().st_ino, identity.st_ino)
        self.assertEqual(path.read_bytes(), b"{}")

    def test_short_writes_are_completed(self):
        path = self.root / "output.json"
        real_write = os.write

        def short(fd, raw):
            return real_write(fd, raw[:3])

        with self.tracked_fds(), mock.patch.object(local_io.os, "write", side_effect=short):
            descriptor = write_new_json(path, {"complete": "yes" * 20})
        raw = path.read_bytes()
        self.assertEqual(descriptor, {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)
        self.assertEqual(path.stat().st_nlink, 1)

    def test_zero_write_rejected_and_cleaned(self):
        with self.tracked_fds(), mock.patch.object(local_io.os, "write", return_value=0), \
                self.assertRaisesRegex(InputError, "output_write"):
            write_new_json(self.root / "output.json", {})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_write_failures_and_interrupts_clean_stage_and_fds(self):
        for call in ("write", "fsync", "link", "dup"):
            for failure in (OSError("synthetic failure"), KeyboardInterrupt()):
                with self.subTest(call=call, failure=type(failure).__name__), self.tracked_fds(), \
                        mock.patch.object(local_io.os, call, side_effect=failure), \
                        self.assertRaises(type(failure)):
                    write_new_json(self.root / "output.json", {})
                self.assertEqual(list(self.root.glob(".arc2-report-*")), [])
                output = self.root / "output.json"
                if call == "dup":
                    self.assertEqual(json.loads(output.read_bytes()), {})
                    output.unlink()
                else:
                    self.assertFalse(output.exists())

    def test_invalid_output_does_not_touch_filesystem(self):
        cyclic = {}
        cyclic["self"] = cyclic
        for value in ({"a": float("nan")}, {"a": float("inf")}, {"a": object()}, cyclic):
            with self.subTest(kind=type(value["a"]).__name__ if "a" in value else "cycle"), \
                    mock.patch.object(local_io.os, "open") as opened, \
                    self.assertRaisesRegex(InputError, "invalid_output_json"):
                write_new_json(self.root / "output.json", value)
            opened.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_output_size_rejected_before_open(self):
        with mock.patch.object(local_io, "MAX_JSON_BYTES", 32), \
                mock.patch.object(local_io.os, "open") as opened, \
                self.assertRaisesRegex(InputError, "output_size"):
            write_new_json(self.root / "output.json", {"a": "x" * 40})
        opened.assert_not_called()

    def test_output_ancestor_swap_after_stage_is_cleaned_in_original_parent(self):
        ancestor, outside, moved = self.ancestor_tree()
        real_write = os.write
        switched = False

        def replace(fd, raw):
            nonlocal switched
            if not switched:
                switched = True
                ancestor.rename(moved)
                ancestor.symlink_to(outside, target_is_directory=True)
            return real_write(fd, raw)

        with self.tracked_fds(), mock.patch.object(local_io.os, "write", side_effect=replace), \
                self.assertRaisesRegex(InputError, "path_changed"):
            write_new_json(ancestor / "output.json", {"complete": True})
        self.assertEqual(sorted(p.name for p in moved.iterdir()), ["report.json"])
        self.assertEqual(sorted(p.name for p in outside.iterdir()), ["report.json"])

    def test_output_ancestor_swap_at_publication_is_contained_and_rejected(self):
        ancestor, outside, moved = self.ancestor_tree()
        real_link = os.link

        def replace(source, destination, **kwargs):
            self.assertIn("src_dir_fd", kwargs)
            self.assertIn("dst_dir_fd", kwargs)
            ancestor.rename(moved)
            ancestor.symlink_to(outside, target_is_directory=True)
            return real_link(source, destination, **kwargs)

        with self.tracked_fds(), mock.patch.object(local_io.os, "link", side_effect=replace), \
                self.assertRaisesRegex(InputError, "path_changed"):
            write_new_json(ancestor / "output.json", {"complete": True})
        self.assertEqual(json.loads((moved / "output.json").read_bytes()), {"complete": True})
        self.assertEqual(list(moved.glob(".arc2-report-*")), [])
        self.assertEqual(sorted(p.name for p in outside.iterdir()), ["report.json"])

    def test_competing_output_at_link_is_never_overwritten(self):
        output = self.root / "output.json"
        real_link = os.link

        def compete(source, destination, **kwargs):
            output.write_bytes(b'{"competitor":true}')
            return real_link(source, destination, **kwargs)

        with self.tracked_fds(), mock.patch.object(local_io.os, "link", side_effect=compete), \
                self.assertRaisesRegex(InputError, "output_exists"):
            write_new_json(output, {"complete": True})
        self.assertEqual(output.read_bytes(), b'{"competitor":true}')
        self.assertEqual(list(self.root.glob(".arc2-report-*")), [])

    def test_output_replacement_after_link_is_preserved_and_rejected(self):
        output = self.root / "output.json"
        real_link = os.link

        def compete(source, destination, **kwargs):
            result = real_link(source, destination, **kwargs)
            output.unlink()
            output.write_bytes(b'{"competitor":true}')
            return result

        with self.tracked_fds(), mock.patch.object(local_io.os, "link", side_effect=compete), \
                self.assertRaisesRegex(InputError, "output_changed"):
            write_new_json(output, {"complete": True})
        self.assertEqual(output.read_bytes(), b'{"competitor":true}')
        self.assertEqual(list(self.root.glob(".arc2-report-*")), [])

    def test_source_name_substitution_never_returns_another_inode_descriptor(self):
        output = self.root / "output.json"
        real_link = os.link

        def substitute(source, destination, **kwargs):
            fd = kwargs["src_dir_fd"]
            os.rename(source, "original.json", src_dir_fd=fd, dst_dir_fd=fd)
            foreign = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
            try:
                os.write(foreign, b'{"foreign":true}')
            finally:
                os.close(foreign)
            return real_link(source, destination, **kwargs)

        with self.tracked_fds(), mock.patch.object(local_io.os, "link", side_effect=substitute), \
                self.assertRaisesRegex(InputError, "output_temporary_changed"):
            write_new_json(output, {"complete": True})
        # A deliberately hostile same-UID mutation is detected. Do not delete
        # its foreign entries while attempting cleanup, or return their hash.
        self.assertEqual(output.read_bytes(), b'{"foreign":true}')
        stage, = self.root.glob(".arc2-report-*")
        self.assertEqual((stage / "payload.json").read_bytes(), b'{"foreign":true}')
        self.assertEqual(json.loads((stage / "original.json").read_bytes()), {"complete": True})

    def test_output_content_mutation_at_link_is_rejected(self):
        output = self.root / "output.json"
        real_link = os.link

        def mutate(source, destination, **kwargs):
            result = real_link(source, destination, **kwargs)
            output.write_bytes(b'{"mutated":true}')
            return result

        with self.tracked_fds(), mock.patch.object(local_io.os, "link", side_effect=mutate), \
                self.assertRaisesRegex(InputError, "output_changed"):
            write_new_json(output, {"complete": True})
        self.assertEqual(list(self.root.glob(".arc2-report-*")), [])

    def test_stage_collisions_are_bounded_and_preserved(self):
        stage = self.root / ".arc2-report-fixed"
        stage.mkdir()
        with self.tracked_fds(), mock.patch.object(local_io.secrets, "token_hex", return_value="fixed") as token, \
                self.assertRaisesRegex(InputError, "output_temporary_collision"):
            write_new_json(self.root / "output.json", {})
        self.assertEqual(token.call_count, local_io._STAGE_ATTEMPTS)
        self.assertEqual(list(self.root.iterdir()), [stage])

    def test_unbound_stage_identity_failure_preserves_uncertain_entries(self):
        real_stat = os.stat
        for foreign in (False, True):
            for failure in (OSError("identity unavailable"), KeyboardInterrupt()):
                root = self.root / (str(foreign) + type(failure).__name__)
                root.mkdir()
                intercepted = False

                def fail(name, *args, **kwargs):
                    nonlocal intercepted
                    if not intercepted and isinstance(name, str) and name.startswith(".arc2-report-"):
                        intercepted = True
                        if foreign:
                            directory = kwargs["dir_fd"]
                            os.rename(name, "original-empty", src_dir_fd=directory, dst_dir_fd=directory)
                            os.mkdir(name, 0o700, dir_fd=directory)
                            replacement = os.open(name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=directory)
                            try:
                                sentinel = os.open("foreign", os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                                                   0o600, dir_fd=replacement)
                                os.close(sentinel)
                            finally:
                                os.close(replacement)
                        raise failure
                    return real_stat(name, *args, **kwargs)

                with self.subTest(foreign=foreign, failure=type(failure).__name__), self.tracked_fds(), \
                        mock.patch.object(local_io.os, "stat", side_effect=fail), \
                        self.assertRaises(type(failure)):
                    write_new_json(root / "output.json", {})
                self.assertTrue(intercepted)
                self.assertFalse((root / "output.json").exists())
                uncertain, = root.glob(".arc2-report-*")
                self.assertEqual(sorted(p.name for p in uncertain.iterdir()), ["foreign"] if foreign else [])
                if foreign:
                    self.assertTrue((root / "original-empty").is_dir())

    def test_stage_directory_open_failure_removes_directory_and_closes_handles(self):
        real_open = os.open

        def fail(name, *args, **kwargs):
            if isinstance(name, str) and name.startswith(".arc2-report-"):
                raise OSError("synthetic stage open failure")
            return real_open(name, *args, **kwargs)

        with self.tracked_fds():
            real_open = os.open
            with mock.patch.object(local_io.os, "open", side_effect=fail), self.assertRaises(OSError):
                write_new_json(self.root / "output.json", {})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_stage_payload_open_failure_closes_handles_and_removes_directory(self):
        real_open = os.open

        def fail(name, *args, **kwargs):
            if name == "payload.json":
                raise OSError("synthetic payload open failure")
            return real_open(name, *args, **kwargs)

        with self.tracked_fds():
            real_open = os.open
            with mock.patch.object(local_io.os, "open", side_effect=fail), self.assertRaises(OSError):
                write_new_json(self.root / "output.json", {})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cleanup_failure_closes_every_descriptor_and_does_not_claim_success(self):
        for call in ("unlink", "rmdir"):
            with self.subTest(call=call), self.tracked_fds(), \
                    mock.patch.object(local_io.os, call, side_effect=OSError("cleanup failure")), \
                    self.assertRaises(OSError):
                write_new_json(self.root / (call + ".json"), {})



class LinkTests(unittest.TestCase):
    def setUp(self):
        self.descriptor = {"bytes": 200, "sha256": "a" * 64}
        self.retrieval_descriptor = {"bytes": 300, "sha256": "b" * 64}
        self.checkpoint_descriptor = {"bytes": 400, "sha256": "c" * 64}
        self.report = {"provider_status": "ERROR"}
        for key in ("operational_success", "comparison_complete", "compute_matched", "comparison_eligible",
                    "public_benchmark_evidence_eligible", "goal_met", "public_goal_met"):
            self.report[key] = False
        self.checkpoint = {
            **self.report, "status": "TERMINAL_EVIDENCE_VERIFIED", "automatic_retry": False,
            "validation": {**self.descriptor, "path": "/never-open-this-private-reference"},
            "retrieval": self.retrieval_descriptor,
        }
        self.retrieval = {"format": "irisx/rlvr-selected-retrieval-v1", "numeric_output_version": 999,
                          "before": {"status": "ERROR"}, "after": {"status": "ERROR"},
                          "inventory_scope": "selected_outputs_only", "whole_provider_inventory_verified": False}

    def linked(self):
        return report_links(self.report, self.descriptor, checkpoint=self.checkpoint,
                            checkpoint_descriptor=self.checkpoint_descriptor, retrieval=self.retrieval,
                            retrieval_descriptor=self.retrieval_descriptor)

    def test_explicit_links_are_not_authentication(self):
        with mock.patch("builtins.open", side_effect=AssertionError("must not follow descriptor")):
            result = self.linked()
        self.assertIs(result["local_descriptor_links_consistent"], True)
        self.assertIs(result["external_collection_authenticated"], False)
        self.assertEqual(result["recorded_numeric_output_version"], 999)
        self.assertNotIn("private-reference", json.dumps(result))

    def test_report_alone_does_not_invent_collection(self):
        result = report_links(self.report, self.descriptor)
        self.assertIsNone(result["local_descriptor_links_consistent"])
        self.assertIsNone(result["recorded_numeric_output_version"])

    def test_changed_validation_binding(self):
        self.checkpoint["validation"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(InputError, "checkpoint_validation_link"):
            self.linked()

    def test_inconsistent_boolean_and_status(self):
        for key, value in (("comparison_complete", 0), ("provider_status", "COMPLETE")):
            original = self.checkpoint[key]
            self.checkpoint[key] = value
            with self.assertRaises(InputError):
                self.linked()
            self.checkpoint[key] = original

    def test_partial_retrieval_or_different_bracket_rejected(self):
        with self.assertRaisesRegex(InputError, "retrieval_requires_checkpoint"):
            report_links(self.report, self.descriptor, retrieval=self.retrieval, retrieval_descriptor=self.retrieval_descriptor)
        self.retrieval["after"]["status"] = "RUNNING"
        with self.assertRaisesRegex(InputError, "retrieval_bracket"):
            self.linked()

    def test_numeric_version_bool_rejected(self):
        self.retrieval["numeric_output_version"] = True
        with self.assertRaisesRegex(InputError, "retrieval_version"):
            self.linked()


if __name__ == "__main__":
    unittest.main()
