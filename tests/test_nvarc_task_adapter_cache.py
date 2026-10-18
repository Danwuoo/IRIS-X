"""Tiny genuine CPU snapshots; these tests are not full-model/GPU evidence."""
import copy
from dataclasses import FrozenInstanceError, replace
import errno
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.nvarc_competition_20261018 import task_adapter_cache as cache_module
from tests.platform_requirements import requires_linux

_HAS_ML = (importlib.util.find_spec("torch") is not None
           and importlib.util.find_spec("safetensors") is not None)
if _HAS_ML:
    import torch
    from tools.nvarc_competition_20261018.model import state_digest


BINDING = {"task_id": "synthetic_adapter", "task_index": 3,
           "inputs": {"train": [{"input": [[1]], "output": [[2]]}],
                      "test": [{"input": [[4]]}]},
           "config": {"seed": 17, "steps": 2, "lr": 0.0001}}


class PortableSchemaTests(unittest.TestCase):
    def test_canonical_plain_json_is_stable_and_does_not_mutate(self):
        binding = copy.deepcopy(BINDING)
        reordered = {key: binding[key] for key in reversed(binding)}
        self.assertEqual(cache_module._binding_bytes(binding), cache_module._binding_bytes(reordered))
        self.assertEqual(binding, BINDING)
        self.assertNotEqual(cache_module._binding_bytes({"index": True}),
                            cache_module._binding_bytes({"index": 1}))

    def test_invalid_binding_schema_is_portably_rejected(self):
        cyclic = {}
        cyclic["self"] = cyclic
        for binding in ({}, [], {1: "value"}, {"x": (1, 2)}, {"x": float("nan")},
                        {"x": float("inf")}, {"x": object()}, cyclic):
            with self.subTest(binding=str(binding)), self.assertRaises(ValueError):
                cache_module._binding_bytes(binding)

    def test_unsupported_filesystem_fails_before_any_disk_action(self):
        with patch.object(cache_module, "filesystem_supported", return_value=False), \
                patch.object(cache_module, "_safe_directory") as open_directory:
            with self.assertRaisesRegex(NotImplementedError, "Linux no-follow"):
                cache_module.TaskAdapterCache("unused", max_bytes=10000, min_free_bytes=0)
        open_directory.assert_not_called()

    def test_import_with_missing_posix_flags_is_safe_without_ml(self):
        script = ("import os, sys\n"
                  "for name in ('O_DIRECTORY', 'O_NOFOLLOW'):\n"
                  "    if hasattr(os, name): delattr(os, name)\n"
                  "from tools.nvarc_competition_20261018 import task_adapter_cache as cache\n"
                  "assert 'torch' not in sys.modules and 'safetensors' not in sys.modules\n"
                  "assert not cache.filesystem_supported()\n"
                  "try: cache.TaskAdapterCache('unused', max_bytes=10000, min_free_bytes=0)\n"
                  "except NotImplementedError: pass\n"
                  "else: raise AssertionError('unsupported filesystem accepted')\n")
        subprocess.run([sys.executable, "-c", script], check=True,
                       cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)


class _CacheTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)

    def cache(self, name="cache", **kwargs):
        return cache_module.TaskAdapterCache(self.parent / name,
            max_bytes=kwargs.get("max_bytes", 1024 * 1024),
            min_free_bytes=kwargs.get("min_free_bytes", 0))


@requires_linux("cache ownership requires Linux no-follow, dir_fd, uid, inode and fsync semantics")
@unittest.skipUnless(cache_module.filesystem_supported(), "Linux descriptor filesystem required")
class OwnershipTests(_CacheTestCase):
    def test_manifest_is_counted_and_fresh_root_is_required(self):
        cache = self.cache()
        self.assertEqual(cache.used_bytes, (cache.root / "owner.json").stat().st_size)
        with self.assertRaises(FileExistsError):
            self.cache()
        self.assertEqual(len(list(cache.root.iterdir())), 1)

    def test_limits_are_strict_and_manifest_cannot_exceed_bound(self):
        for limit, reserve in [(True, 0), (1.5, 0), (-1, 0), (10000, True),
                               (10000, -1), (0, 0), (1, 0)]:
            with self.subTest(limit=limit, reserve=reserve), self.assertRaises(ValueError):
                self.cache(max_bytes=limit, min_free_bytes=reserve)
        self.assertFalse((self.parent / "cache").exists())

    def test_unowned_existing_empty_directory_is_rejected(self):
        (self.parent / "cache").mkdir()
        with self.assertRaises(FileExistsError):
            self.cache()

    def test_symlink_root_and_parent_and_traversal_are_rejected(self):
        real = self.parent / "real"
        real.mkdir()
        (self.parent / "link").symlink_to(real, target_is_directory=True)
        for path in (self.parent / "link", self.parent / "link" / "child",
                     real / ".." / "child"):
            with self.subTest(path=path), self.assertRaises((OSError, ValueError)):
                cache_module.TaskAdapterCache(path, max_bytes=10000, min_free_bytes=0)
        self.assertEqual(list(real.iterdir()), [])

    def test_root_replacement_rejected_without_touching_replacement(self):
        cache = self.cache()
        moved = self.parent / "original"
        cache.root.rename(moved)
        cache.root.mkdir()
        sentinel = cache.root / "keep.txt"
        sentinel.write_text("untouched")
        with self.assertRaises(cache_module.CacheIntegrityError):
            _ = cache.used_bytes
        self.assertEqual(sentinel.read_text(), "untouched")

    def test_owner_manifest_content_and_inode_replacement_rejected(self):
        cache = self.cache()
        manifest = cache.root / "owner.json"
        original = manifest.read_bytes()
        manifest.write_bytes(original.replace(b"session-local", b"foreign-local"))
        with self.assertRaises(cache_module.CacheIntegrityError):
            _ = cache.used_bytes
        manifest.write_bytes(original)
        self.assertGreater(cache.used_bytes, 0)
        replacement = self.parent / "replacement"
        replacement.write_bytes(original)
        replacement.replace(manifest)
        with self.assertRaises(cache_module.CacheIntegrityError):
            _ = cache.used_bytes

    def test_unowned_root_file_is_not_removed(self):
        cache = self.cache()
        extra = cache.root / "keep.txt"
        extra.write_text("do not delete")
        with self.assertRaises(cache_module.CacheIntegrityError):
            _ = cache.used_bytes
        self.assertEqual(extra.read_text(), "do not delete")

    def test_constructor_disk_reserve_failure_leaves_no_root(self):
        with patch.object(cache_module, "_space_available", return_value=False):
            with self.assertRaises(OSError) as raised:
                self.cache()
        self.assertEqual(raised.exception.errno, errno.ENOSPC)
        self.assertFalse((self.parent / "cache").exists())

    def test_failed_manifest_write_cleans_only_owned_new_root(self):
        with patch.object(cache_module.os, "fsync", side_effect=OSError(errno.EIO, "synthetic")):
            with self.assertRaises(OSError):
                self.cache()
        self.assertFalse((self.parent / "cache").exists())

    def test_failed_directory_open_cleans_only_new_empty_root(self):
        actual_open = cache_module.os.open
        def fail_cache_open(path, *args, **kwargs):
            if path == "cache":
                raise OSError(errno.EIO, "synthetic open failure")
            return actual_open(path, *args, **kwargs)
        with patch.object(cache_module, "filesystem_supported", return_value=True), \
                patch.object(cache_module.os, "open", side_effect=fail_cache_open):
            with self.assertRaises(OSError):
                self.cache()
        self.assertFalse((self.parent / "cache").exists())

    def test_space_admission_keeps_reserve_and_block_rounding(self):
        info = type("Disk", (), {"f_bavail": 7, "f_frsize": 4096, "f_bsize": 4096})()
        with patch.object(cache_module.os, "fstatvfs", return_value=info):
            self.assertTrue(cache_module._space_available(0, 4096, [1, 1]))
            self.assertFalse(cache_module._space_available(0, 4097, [1, 1]))


@requires_linux("adapter cache snapshots require Linux no-follow descriptor ownership semantics")
@unittest.skipUnless(cache_module.filesystem_supported(), "Linux descriptor filesystem required")
@unittest.skipUnless(_HAS_ML, "genuine Torch and safetensors CPU environment required")
class SnapshotTests(_CacheTestCase):
    def state(self):
        return {"layer.lora_A.weight": torch.arange(6, dtype=torch.float32).reshape(2, 3),
                "layer.lora_B.weight": torch.tensor([[0.25], [-0.5]], dtype=torch.bfloat16)}

    def put(self, cache=None, binding=None, state=None):
        cache = self.cache() if cache is None else cache
        binding = copy.deepcopy(BINDING) if binding is None else binding
        state = self.state() if state is None else state
        receipt = cache.put(binding, state)
        self.assertIsNotNone(receipt)
        return cache, binding, state, receipt

    def actual_bytes(self, cache):
        return sum(path.stat().st_size for path in cache.root.rglob("*") if path.is_file())

    def test_roundtrip_exact_digest_inventory_and_independent_state(self):
        cache, binding, original, receipt = self.put()
        self.assertEqual(receipt.adapter_sha256, state_digest(original))
        restored = cache.load(binding, receipt)
        self.assertEqual(state_digest(restored), state_digest(original))
        for name in original:
            self.assertTrue(torch.equal(restored[name], original[name]))
            self.assertEqual(restored[name].dtype, original[name].dtype)
            self.assertEqual(restored[name].shape, original[name].shape)
            self.assertEqual(restored[name].device.type, "cpu")
            self.assertTrue(restored[name].is_contiguous())
            self.assertFalse(restored[name].requires_grad)
            self.assertNotEqual(restored[name].data_ptr(), original[name].data_ptr())
        original["layer.lora_A.weight"].add_(100)
        restored["layer.lora_A.weight"].add_(200)
        self.assertEqual(state_digest(cache.load(binding, receipt)), receipt.adapter_sha256)
        self.assertEqual(cache.used_bytes, self.actual_bytes(cache))
        self.assertEqual(receipt.size_bytes, receipt.state_bytes + receipt.metadata_bytes)
        with self.assertRaises(FrozenInstanceError):
            receipt.adapter_sha256 = "0" * 64

    def test_canonical_binding_order_and_complete_input_config_identity(self):
        cache, binding, _, receipt = self.put()
        reordered = {key: binding[key] for key in reversed(binding)}
        self.assertEqual(state_digest(cache.load(reordered, receipt)), receipt.adapter_sha256)
        for key, value in [("task_id", "another"), ("task_index", 4),
                           ("inputs", {"changed": True}), ("config", {"steps": 3})]:
            wrong = copy.deepcopy(binding)
            wrong[key] = value
            with self.subTest(key=key):
                for method in (cache.load, cache.release):
                    with self.assertRaises(cache_module.CacheIntegrityError):
                        method(wrong, receipt)
        self.assertEqual(state_digest(cache.load(binding, receipt)), receipt.adapter_sha256)

    def test_caller_restores_real_tiny_model_and_checks_target_digest(self):
        from tools.nvarc_competition_20261018.model import adapter_state, restore_state
        model = torch.nn.Linear(3, 2)
        original = adapter_state(model)
        cache, binding, _, receipt = self.put(state=original)
        with torch.no_grad():
            model.weight.add_(1)
        changed = state_digest(adapter_state(model))
        self.assertNotEqual(changed, receipt.adapter_sha256)
        recovered = cache.load(binding, receipt)
        # Loading a CPU snapshot alone makes no live-model restoration claim.
        self.assertEqual(state_digest(adapter_state(model)), changed)
        restore_state(model, recovered)
        self.assertEqual(state_digest(adapter_state(model)), receipt.adapter_sha256)

    def test_non_plain_or_nonfinite_json_binding_rejected(self):
        cache = self.cache()
        cyclic = {}
        cyclic["self"] = cyclic
        for binding in ({}, [], {1: "value"}, {"x": (1, 2)}, {"x": float("nan")},
                        {"x": float("inf")}, {"x": object()}, cyclic):
            with self.subTest(binding=str(binding)), self.assertRaises(ValueError):
                cache.put(binding, self.state())
        self.assertEqual(len(list(cache.root.iterdir())), 1)

    def test_invalid_state_rejected_without_writes(self):
        cache = self.cache()
        invalid = [{}, {"x": [1.]}, {1: torch.ones(1)}, {"": torch.ones(1)},
                   {"a\x00b": torch.ones(1)}, {"__metadata__": torch.ones(1)},
                   {"x": torch.tensor([float("nan")])}, {"x": torch.tensor([float("inf")])},
                   {"x": torch.tensor([1], dtype=torch.int64)}, {"x": torch.tensor(1.)},
                   {"x": torch.ones(2, device="meta")},
                   {"x": torch.ones(2, 2).to_sparse()}]
        for state in invalid:
            with self.subTest(state=repr(state)), self.assertRaises(ValueError):
                cache.put(BINDING, state)
        self.assertEqual(len(list(cache.root.iterdir())), 1)

    def test_noncontiguous_cpu_input_is_copied_to_contiguous_snapshot(self):
        state = {"weight": torch.arange(12, dtype=torch.float64).reshape(3, 4).T}
        self.assertFalse(state["weight"].is_contiguous())
        cache, binding, _, receipt = self.put(state=state)
        loaded = cache.load(binding, receipt)
        self.assertTrue(loaded["weight"].is_contiguous())
        self.assertEqual(state_digest(loaded), state_digest(state))

    def test_equal_binding_puts_have_independent_release_rights(self):
        cache, binding, state, first = self.put()
        second = cache.put(binding, state)
        self.assertNotEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(first.adapter_sha256, second.adapter_sha256)
        before = cache.used_bytes
        cache.release(binding, first)
        self.assertEqual(cache.used_bytes, before - first.size_bytes)
        self.assertEqual(state_digest(cache.load(binding, second)), second.adapter_sha256)
        for method in (cache.load, cache.release):
            with self.assertRaises(cache_module.CacheIntegrityError):
                method(binding, first)
        cache.release(binding, second)
        self.assertEqual(cache.used_bytes, self.actual_bytes(cache))
        self.assertEqual(len(list(cache.root.iterdir())), 1)

    def test_bound_counts_state_and_all_metadata_with_no_eviction(self):
        probe, binding, state, receipt = self.put()
        # The bound is itself included in owner.json; solve its digit-width
        # effect instead of changing a cache's configuration after creation.
        exact_size = probe.used_bytes
        base = exact_size - len(str(probe.max_bytes))
        while exact_size != base + len(str(exact_size)):
            exact_size = base + len(str(exact_size))
        full = self.cache("full", max_bytes=exact_size)
        accepted = full.put(binding, state)
        self.assertIsNotNone(accepted)
        self.assertEqual(full.used_bytes, full.max_bytes)
        self.assertIsNone(full.put(binding, state))
        self.assertEqual(full.used_bytes, self.actual_bytes(full))
        self.assertEqual(state_digest(full.load(binding, accepted)), accepted.adapter_sha256)
        full.release(binding, accepted)
        self.assertIsNotNone(full.put(binding, state))

    def test_payload_alone_fits_but_metadata_does_not(self):
        probe, binding, state, receipt = self.put()
        limit = probe.used_bytes - receipt.metadata_bytes
        base = limit - len(str(probe.max_bytes))
        while limit != base + len(str(limit)):
            limit = base + len(str(limit))
        limited = self.cache("limited", max_bytes=limit)
        self.assertIsNone(limited.put(binding, state))
        self.assertEqual(limited.used_bytes, self.actual_bytes(limited))
        self.assertEqual(len(list(limited.root.iterdir())), 1)

    def test_disk_reserve_admission_declines_without_writes(self):
        cache = self.cache()
        with patch.object(cache_module, "_space_available", return_value=False):
            self.assertIsNone(cache.put(BINDING, self.state()))
        self.assertEqual(len(list(cache.root.iterdir())), 1)

    def test_disk_free_is_rechecked_before_commit(self):
        cache = self.cache(min_free_bytes=1)
        info = os.statvfs(cache.root)
        exhausted = type("Disk", (), {"f_bavail": 0, "f_frsize": info.f_frsize})()
        with patch.object(cache_module, "_space_available", return_value=True), \
                patch.object(cache_module.os, "fstatvfs", return_value=exhausted):
            self.assertIsNone(cache.put(BINDING, self.state()))
        self.assertEqual(len(list(cache.root.iterdir())), 1)

    def test_modified_state_bytes_or_truncation_rejected(self):
        cache, binding, _, receipt = self.put()
        path = cache.root / receipt.snapshot_id / "state.safetensors"
        original = path.read_bytes()
        corrupted = bytearray(original)
        corrupted[-1] ^= 1
        path.write_bytes(corrupted)
        with self.assertRaisesRegex(cache_module.CacheIntegrityError, "byte digest"):
            cache.load(binding, receipt)
        path.write_bytes(original[:-1])
        with self.assertRaises(cache_module.CacheIntegrityError):
            cache.load(binding, receipt)

    def test_modified_metadata_inventory_adapter_digest_and_receipt_rejected(self):
        cache, binding, _, receipt = self.put()
        path = cache.root / receipt.snapshot_id / "snapshot.json"
        original = path.read_bytes()
        for key, changed in [("adapter_sha256", "0" * 64), ("state_sha256", "1" * 64),
                             ("tensor_inventory", {"wrong": {"shape": [6]}})]:
            value = json.loads(original)
            value[key] = changed
            path.write_bytes(cache_module._canonical(value))
            with self.subTest(key=key), self.assertRaises(cache_module.CacheIntegrityError):
                cache.load(binding, receipt)
        path.write_bytes(original)
        for changed in (replace(receipt, adapter_sha256="0" * 64),
                        replace(receipt, metadata_sha256="0" * 64),
                        replace(receipt, state_sha256="0" * 64),
                        replace(receipt, state_bytes=receipt.state_bytes + 1)):
            with self.assertRaises(cache_module.CacheIntegrityError):
                cache.load(binding, changed)

    def test_loaded_tensor_inventory_and_exact_model_digest_are_verified(self):
        cache, binding, state, receipt = self.put()
        variants = [{"wrong.name": torch.ones(2)},
                    {**state, "layer.lora_A.weight": state["layer.lora_A.weight"].reshape(3, 2)},
                    {**state, "layer.lora_A.weight": state["layer.lora_A.weight"].to(torch.float64)},
                    {**state, "layer.lora_A.weight": state["layer.lora_A.weight"] + 1}]
        for changed in variants:
            with patch("safetensors.torch.load", return_value=changed):
                with self.assertRaisesRegex(cache_module.CacheIntegrityError, "inventory"):
                    cache.load(binding, receipt)
        with patch("tools.nvarc_competition_20261018.model.state_digest", return_value="0" * 64):
            with self.assertRaisesRegex(cache_module.CacheIntegrityError, "adapter digest"):
                cache.load(binding, receipt)

    def test_deserializer_failure_and_nonfinite_decode_are_rejected(self):
        from safetensors import SafetensorError
        cache, binding, _, receipt = self.put()
        with patch("safetensors.torch.load", side_effect=SafetensorError("synthetic")):
            with self.assertRaisesRegex(cache_module.CacheIntegrityError, "invalid safetensors"):
                cache.load(binding, receipt)
        with patch("safetensors.torch.load", return_value={"x": torch.tensor([float("inf")])}):
            with self.assertRaisesRegex(cache_module.CacheIntegrityError, "invalid safetensors"):
                cache.load(binding, receipt)

    def test_receipt_does_not_alias_authoritative_record(self):
        cache, binding, _, receipt = self.put()
        # Even bypassing the convenience frozen-dataclass guard cannot alter
        # the cache's private recorded expectations or its release accounting.
        object.__setattr__(receipt, "size_bytes", 0)
        with self.assertRaises(cache_module.CacheIntegrityError):
            cache.release(binding, receipt)

    def test_foreign_and_path_traversal_receipts_cannot_read_or_release(self):
        cache, binding, _, receipt = self.put()
        other = self.cache("other")
        outside = self.parent / "do-not-touch"
        outside.write_text("private")
        for invalid in (replace(receipt, snapshot_id="../../do-not-touch"),
                        replace(receipt, snapshot_id=str(outside)),
                        replace(receipt, cache_id=other.cache_id),
                        {"snapshot_id": str(outside)}):
            for method in (cache.load, cache.release):
                with self.assertRaises(cache_module.CacheIntegrityError):
                    method(binding, invalid)
        with self.assertRaises(cache_module.CacheIntegrityError):
            other.load(binding, receipt)
        self.assertEqual(outside.read_text(), "private")

    def test_symlink_snapshot_file_rejected_and_external_target_not_deleted(self):
        cache, binding, _, receipt = self.put()
        path = cache.root / receipt.snapshot_id / "state.safetensors"
        outside = self.parent / "external-state"
        path.rename(outside)
        path.symlink_to(outside)
        for method in (cache.load, cache.release):
            with self.assertRaises((OSError, cache_module.CacheIntegrityError)):
                method(binding, receipt)
        self.assertTrue(outside.is_file())
        self.assertTrue(path.is_symlink())

    def test_symlink_snapshot_directory_rejected(self):
        cache, binding, _, receipt = self.put()
        path = cache.root / receipt.snapshot_id
        outside = self.parent / "moved-snapshot"
        path.rename(outside)
        path.symlink_to(outside, target_is_directory=True)
        for method in (cache.load, cache.release):
            with self.assertRaises((OSError, cache_module.CacheIntegrityError)):
                method(binding, receipt)
        self.assertEqual(len(list(outside.iterdir())), 2)

    def test_hardlink_or_same_bytes_replaced_inode_rejected(self):
        cache, binding, _, receipt = self.put()
        path = cache.root / receipt.snapshot_id / "state.safetensors"
        alias = self.parent / "alias"
        os.link(path, alias)
        with self.assertRaises(cache_module.CacheIntegrityError):
            cache.load(binding, receipt)
        alias.unlink()
        alias.write_bytes(path.read_bytes())
        alias.replace(path)
        with self.assertRaises(cache_module.CacheIntegrityError):
            cache.release(binding, receipt)

    def test_release_refuses_unowned_file_inside_snapshot(self):
        cache, binding, _, receipt = self.put()
        foreign = cache.root / receipt.snapshot_id / "foreign.txt"
        foreign.write_text("preserve me")
        with self.assertRaises(cache_module.CacheIntegrityError):
            cache.release(binding, receipt)
        self.assertEqual(foreign.read_text(), "preserve me")
        self.assertTrue((foreign.parent / "state.safetensors").is_file())

    def test_failed_write_cleanup_refuses_to_delete_unowned_file(self):
        cache = self.cache()
        actual_write = cache_module._write_file
        def inject_foreign_file(fd, name, data, files):
            actual_write(fd, name, data, files)
            extra = os.open("foreign.txt", os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                            0o600, dir_fd=fd)
            os.close(extra)
            raise OSError(errno.ENOSPC, "synthetic disk exhaustion")
        with patch.object(cache_module, "_write_file", side_effect=inject_foreign_file):
            with self.assertRaisesRegex(cache_module.CacheIntegrityError, "unowned/replaced"):
                cache.put(BINDING, self.state())
        pending = list(cache.root.glob(".pending-*"))
        self.assertEqual(len(pending), 1)
        self.assertTrue((pending[0] / "foreign.txt").is_file())
        self.assertTrue((pending[0] / "state.safetensors").is_file())

    def test_failed_snapshot_write_cleans_temporary_and_preserves_prior_snapshot(self):
        cache, binding, state, receipt = self.put()
        before = cache.used_bytes
        actual_write = cache_module._write_file
        def fail_after_first_file(fd, name, data, files):
            actual_write(fd, name, data, files)
            if name == "state.safetensors":
                raise OSError(errno.ENOSPC, "synthetic disk exhaustion")
        with patch.object(cache_module, "_write_file", side_effect=fail_after_first_file):
            self.assertIsNone(cache.put(binding, state))
        self.assertEqual(cache.used_bytes, before)
        self.assertEqual(self.actual_bytes(cache), before)
        self.assertEqual(state_digest(cache.load(binding, receipt)), receipt.adapter_sha256)

    def test_failed_fsync_and_rename_leave_no_unrecorded_snapshot(self):
        for operation in ("fsync", "rename"):
            cache = self.cache(operation)
            with patch.object(cache_module.os, operation, side_effect=OSError(errno.EIO, "synthetic")):
                with self.assertRaises(OSError):
                    cache.put(BINDING, self.state())
            self.assertEqual(len(list(cache.root.iterdir())), 1)
            self.assertEqual(cache.used_bytes, self.actual_bytes(cache))

    def test_failed_temporary_directory_open_is_cleaned(self):
        cache = self.cache()
        actual_open = cache_module.os.open
        def fail_pending_open(path, *args, **kwargs):
            if str(path).startswith(".pending-"):
                raise OSError(errno.EIO, "synthetic open failure")
            return actual_open(path, *args, **kwargs)
        with patch.object(cache_module.os, "open", side_effect=fail_pending_open):
            with self.assertRaises(OSError):
                cache.put(BINDING, self.state())
        self.assertEqual(len(list(cache.root.iterdir())), 1)
        self.assertEqual(cache.used_bytes, self.actual_bytes(cache))

    def test_fsync_failure_after_directory_publish_is_cleaned(self):
        cache = self.cache()
        actual_fsync = cache_module.os.fsync
        count = 0
        def fail_final_fsync(fd):
            nonlocal count
            count += 1
            if count == 4:  # two files, temporary directory, published root
                raise OSError(errno.EIO, "synthetic post-rename sync failure")
            return actual_fsync(fd)
        with patch.object(cache_module.os, "fsync", side_effect=fail_final_fsync):
            with self.assertRaises(OSError):
                cache.put(BINDING, self.state())
        self.assertEqual(len(list(cache.root.iterdir())), 1)
        self.assertEqual(cache.used_bytes, self.actual_bytes(cache))

    def test_atomic_directory_commit_has_complete_fsynced_files(self):
        cache = self.cache()
        real_rename = cache_module.os.rename
        observed = []
        def check_rename(source, destination, **kwargs):
            directory = cache.root / source
            observed.append(set(path.name for path in directory.iterdir()))
            self.assertTrue(source.startswith(".pending-"))
            self.assertTrue(destination.startswith("snapshot-"))
            return real_rename(source, destination, **kwargs)
        with patch.object(cache_module.os, "rename", side_effect=check_rename):
            _, binding, _, receipt = self.put(cache=cache)
        self.assertEqual(observed, [{"snapshot.json", "state.safetensors"}])
        self.assertEqual(state_digest(cache.load(binding, receipt)), receipt.adapter_sha256)


if __name__ == "__main__":
    unittest.main()
