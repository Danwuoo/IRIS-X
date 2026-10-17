"""The public lane must not turn absent evidence or unrelated failures into passes."""

import io
import unittest

from tools import run_public_tests as lane
from tests.platform_requirements import requires_linux


class PublicTestLaneTests(unittest.TestCase):
    def example(self, *, fail_public=False):
        seen = []

        class Example(unittest.TestCase):
            def test_public(self):
                seen.append("public")
                if fail_public:
                    self.fail("genuine public regression")

            def test_retained(self):
                seen.append("retained")
                raise FileNotFoundError("genuine private evidence absent")

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Example)
        retained_id = Example("test_retained").id()
        return suite, {retained_id: "private test evidence"}, seen

    def run_suite(self, suite):
        return unittest.TextTestRunner(stream=io.StringIO()).run(suite)

    def test_public_reports_retained_as_skipped_not_passed(self):
        suite, manifest, seen = self.example()
        result = self.run_suite(lane.select_suite(suite, manifest=manifest))
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(seen, ["public"])
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(len(result.skipped), 1)
        self.assertIn("UNVERIFIED", result.skipped[0][1])
        self.assertEqual(result.skipped[0][0].id(), next(iter(manifest)))

    def test_unclassified_failures_remain_failures(self):
        suite, manifest, _ = self.example(fail_public=True)
        result = self.run_suite(lane.select_suite(suite, manifest=manifest))
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.failures), 1)

    def test_retained_lane_runs_real_check_and_fails_without_evidence(self):
        suite, manifest, seen = self.example()
        result = self.run_suite(lane.select_suite(suite, manifest=manifest, retained_only=True))
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(seen, ["retained"])
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.skipped, [])

    def test_stale_or_mistyped_manifest_fails_closed(self):
        suite, manifest, _ = self.example()
        manifest["unknown.test"] = "missing integration"
        with self.assertRaisesRegex(ValueError, "does not match discovery"):
            lane.select_suite(suite, manifest=manifest)

    def test_default_discovery_is_not_mutated(self):
        suite, manifest, _ = self.example()
        lane.select_suite(suite, manifest=manifest)
        result = self.run_suite(suite)
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.errors), 1)

    def capability_example(self):
        seen = []

        class Example(unittest.TestCase):
            @requires_linux("literal POSIX fixture requirement")
            def test_linux(self):
                seen.append("linux")

            def test_portable(self):
                seen.append("portable")

        return unittest.defaultTestLoader.loadTestsFromTestCase(Example), seen

    def test_platform_metadata_does_not_skip_complete_public_lane(self):
        suite, seen = self.capability_example()
        result = self.run_suite(lane.select_suite(suite, manifest={}))
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(seen, ["linux", "portable"])
        self.assertEqual(result.skipped, [])

    def test_portable_lane_reports_annotated_body_unverified(self):
        suite, seen = self.capability_example()
        result = self.run_suite(lane.select_suite(suite, portable=True, manifest={}))
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(seen, ["portable"])
        self.assertEqual(len(result.skipped), 1)
        self.assertIn("UNVERIFIED Linux-only capability", result.skipped[0][1])

    def test_strict_discovery_ignores_platform_metadata(self):
        suite, seen = self.capability_example()
        result = self.run_suite(suite)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(seen, ["linux", "portable"])
        self.assertEqual(result.skipped, [])

    def test_portable_lane_keeps_unclassified_regression(self):
        suite, manifest, _ = self.example(fail_public=True)
        result = self.run_suite(lane.select_suite(suite, portable=True, manifest=manifest))
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.failures), 1)

    def test_portable_lane_does_not_swallow_module_import_failure(self):
        suite = unittest.defaultTestLoader.loadTestsFromName("deliberately_absent_public_test_module")
        result = self.run_suite(lane.select_suite(suite, portable=True, manifest={}))
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.skipped, [])

    def test_retained_mode_cannot_be_changed_into_portable_subset(self):
        suite, manifest, _ = self.example()
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            lane.select_suite(suite, manifest=manifest, portable=True, retained_only=True)

    def test_capability_annotation_requires_specific_reason(self):
        for reason in (None, "", "   "):
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                requires_linux(reason)

    def test_class_annotation_preserves_all_strict_test_bodies(self):
        @requires_linux("class setup requires POSIX descriptor storage")
        class Example(unittest.TestCase):
            def test_body(self):
                raise RuntimeError("original body executed")

        strict = self.run_suite(lane.select_suite(
            unittest.defaultTestLoader.loadTestsFromTestCase(Example), manifest={}))
        portable = self.run_suite(lane.select_suite(
            unittest.defaultTestLoader.loadTestsFromTestCase(Example), manifest={}, portable=True))
        self.assertEqual(len(strict.errors), 1)
        self.assertEqual(len(portable.skipped), 1)
        self.assertTrue(portable.wasSuccessful())


if __name__ == "__main__":
    unittest.main()
