"""Pin-only source rebind checks; no private evidence, provider, or model calls."""
from pathlib import Path
import tempfile
import unittest

from tools.arc_qwen_rlvr004_20261013.publication_local import rebind_local_consumer as rebind


ROOT = rebind.REPO / "tools/arc_qwen_rlvr004_20261013"
DELIVERY = rebind.REPO / ".irisx/imports/rlvr004-code17-20261013/release"
COLLECTOR = ROOT / "publication_local/rl_collect.py"


class ConsumerPinRebind(unittest.TestCase):
    def test_actual_current_code17_pins_match_original_consumer(self):
        old = ROOT / "release/terminal-consumer"
        files, helpers = rebind.consumer_files(old)
        self.assertEqual(len(files), 24)
        self.assertEqual(len(helpers), 21)
        self.assertEqual(rebind.sha(files["reviewed_entry.py"]), rebind.OLD_ENTRY_SHA256)
        self.assertEqual(rebind.sha(files["CONSUMER-OPERATOR.json"]), rebind.OLD_OPERATOR_SHA256)

    def test_literal_rebind_changes_only_two_files(self):
        files, helpers = rebind.consumer_files(ROOT / "release/terminal-consumer")
        changed = rebind.successor_files(files, "a" * 64)
        self.assertEqual({name for name in files if files[name] != changed[name]},
                         {"reviewed_entry.py", "CONSUMER-OPERATOR.json"})
        self.assertTrue(all(files[name] == changed[name] for name in helpers))
        before = rebind.document(files["CONSUMER-OPERATOR.json"])
        after = rebind.document(changed["CONSUMER-OPERATOR.json"])
        self.assertEqual(after.pop("collector_entry_sha256"), "a" * 64)
        before.pop("collector_entry_sha256")
        self.assertEqual(before, after)
        self.assertIn(rebind.sha(changed["CONSUMER-OPERATOR.json"]).encode(), changed["reviewed_entry.py"])

    def test_changed_entry_literal_is_rejected(self):
        files, _ = rebind.consumer_files(ROOT / "release/terminal-consumer")
        files["reviewed_entry.py"] = files["reviewed_entry.py"].replace(rebind.OLD_OPERATOR_SHA256.encode(), b"0" * 64)
        with self.assertRaisesRegex(rebind.BindingError, "one exact"):
            rebind.successor_files(files, "a" * 64)

    def test_wrong_source_operator_binding_rejected(self):
        files, _ = rebind.consumer_files(ROOT / "release/terminal-consumer")
        operator = rebind.document(files["CONSUMER-OPERATOR.json"])
        operator["source_sha256"] = "0" * 64
        files["CONSUMER-OPERATOR.json"] = rebind.encoded(operator)
        with self.assertRaisesRegex(rebind.BindingError, "content binding"):
            rebind.successor_files(files, "a" * 64)

    def test_invalid_collector_digest_rejected(self):
        files, _ = rebind.consumer_files(ROOT / "release/terminal-consumer")
        for digest in (None, "short", "z" * 64, "a" * 65):
            with self.subTest(digest=digest), self.assertRaises(rebind.BindingError):
                rebind.successor_files(files, digest)

    def test_existing_output_and_producer_overlap_rejected(self):
        with tempfile.TemporaryDirectory(prefix="consumer-rebind-guards-", dir=rebind.REPO / ".irisx") as temporary:
            base = Path(temporary)
            args = dict(old_root=base / "old", release_root=base / "release",
                        source_inventory=base / "candidate/SOURCE-INVENTORY.json",
                        source_archive=base / "candidate/code-payload/source.zip", collector=COLLECTOR)
            with self.assertRaisesRegex(rebind.BindingError, "fresh successor"):
                rebind.bind_consumer(**args, output_root=base)
            with self.assertRaisesRegex(rebind.BindingError, "outside original"):
                rebind.bind_consumer(**args, output_root=base / "candidate/consumer")

    @unittest.skipUnless(DELIVERY.is_dir() and COLLECTOR.is_file(), "local source delivery/collector unavailable")
    def test_actual_complete_source_binding_and_roundtrip(self):
        with tempfile.TemporaryDirectory(prefix="consumer-rebind-acceptance-", dir=rebind.REPO / ".irisx") as temporary:
            output = Path(temporary) / "consumer"
            result = rebind.bind_consumer(old_root=DELIVERY / "terminal-consumer",
                                         release_root=DELIVERY / "consumer-release",
                                         source_inventory=DELIVERY / "SOURCE-INVENTORY.json",
                                         source_archive=DELIVERY / "code-payload/source.zip",
                                         collector=COLLECTOR, output_root=output)
            self.assertEqual(result["status"], "LOCAL_CONSUMER_PINS_BOUND")
            self.assertTrue(result["all_21_helpers_and_inventory_unchanged"])
            self.assertEqual(result["collector_sha256"], rebind.sha(COLLECTOR.read_bytes()))
            self.assertEqual(len(result["files"]), 24)
            for name, digest in result["files"].items():
                self.assertEqual(rebind.sha((output / name).read_bytes()), digest)
            self.assertFalse(result["production_admission"])
            self.assertEqual(result["evaluator_body_reads"], 0)


if __name__ == "__main__":
    unittest.main()
