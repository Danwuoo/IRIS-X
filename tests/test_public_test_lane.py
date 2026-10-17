"""The public lane must not turn absent evidence or unrelated failures into passes."""

import io
import unittest

from tools import run_public_tests as lane


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


if __name__ == "__main__":
    unittest.main()
