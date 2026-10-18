"""Explicit public-checkout test lane; never substitutes private run evidence.

Ordinary unittest discovery and repository_check --all remain strict. The public
lane excludes only the exact retained integrations below. The separately named
portable subset also reports explicit Linux-capability annotations as unverified.
Missing public fixtures, import failures and unclassified failures still fail.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tests.platform_requirements import linux_requirement


RETAINED_TESTS = {
    "test_repository_check.RepositoryCheckTests.test_retained_archive_objects_are_valid":
        "original annotated archive/pre-product-transition-2026-09-17 tag (not published on the public remote) and its exact recovery objects",
    "test_nvarc_abc.ABCBoundaryTests.test_retained_plan_and_save_projection":
        ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/ retained SFT evidence and ABC001 package",
    "test_nvarc_abc.ABCBoundaryTests.test_public_shape_and_palette_fail_closed_without_truth":
        ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-001-submission/visible.json",
    "test_nvarc_abc.ABCBoundaryTests.test_exact_package_preflight_and_save_guard":
        ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-001-submission/",
    "test_nvarc_abc.ABCBoundaryTests.test_notebook_guard_accepts_exact_plan_and_rejects_rehashed_bytes_before_setup":
        ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-001-submission/kernel/kaggle-notebook.ipynb",
    "test_nvarc_abc_002.ABCRepairTests.test_retained_plan_and_save_projection":
        ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/ retained SFT evidence and ABC002 package",
    "test_nvarc_abc_003.ABCTuningBoundaries.test_retained_plan_and_save_projection":
        ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/ retained SFT evidence and ABC003 package",
    "test_nvarc_abc_004.ABCBeamBoundaries.test_retained_plan_and_save_projection":
        ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/ retained SFT evidence and ABC004 package",
    "test_nvarc_abc_004.ABCBeamBoundaries.test_003_analysis_uses_all_five_approved_arms":
        ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-003-result.zip",
    "test_nvarc_abc_005.ABCPairedBoundaries.test_retained_plan_and_save_projection":
        ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/ retained SFT evidence and ABC005 package",
    "test_nvarc_abc_005.ABCPairedBoundaries.test_004_predecessor_analysis_has_three_approved_arms":
        ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-004-result.zip",
    "test_nvarc_native_export.NativeExportProcessTests.test_mixed_seed_parent_exports_real_tiny_cpu_evidence_in_fresh_child":
        ".irisx/nvarc-original/materials/ retained tokenizer/native sources (the model under test is tiny CPU only)",
    "test_nvarc_native_export.NativeExportProcessTests.test_legacy_review_bytes_stay_frozen_and_new_export_proposal_is_inert":
        ".irisx/nvarc-original/runs/nvarc-original-qwen3-native-ttt-008/package-l4/ and retained native materials",
    "test_nvarc_native_save_v4.NativeSaveV4Tests.test_exact_review_allows_save_with_unknown_facts_and_preserves_v3":
        ".irisx/control-review-c2079c9-caadb179/acceptance.json and retained native007/native009 packages",
}

# All these methods construct the real native package in setUpClass before
# exercising the fake provider transport. Enumerate methods rather than hiding
# an entire module: newly added tests must be classified deliberately.
for _method in (
    "test_inert_review_builds_real_sdk_wire_without_credentials",
    "test_acceptance_is_one_save_receipt_and_runtime_unobserved",
    "test_all_failures_unknowns_and_interrupts_consume_identity",
    "test_crash_claim_blocks_reinitialization_even_without_receipt",
    "test_tampered_package_or_wire_is_rejected_before_credentials",
    "test_mounts_privacy_and_execution_fields_fail_closed",
    "test_fixed_path_and_single_init_are_enforced",
    "test_v2_admission_binds_review_and_real_resource_fields",
    "test_admission_derivation_changes_only_plan_payload",
    "test_acceptance_command_diagnostics_never_imply_gpu_gate",
    "test_retained_identity_cannot_be_staged_in_another_directory",
    "test_actual_offline_admitted_stage_preflight_init_roundtrip",
    "test_credential_failure_is_reserved_without_provider_send_or_retry",
    "test_save_only_exception_roundtrip_preserves_unknowns_and_payloads",
):
    RETAINED_TESTS["test_nvarc_native_editor_transport.NativeEditorTransportTests." + _method] = (
        ".irisx/nvarc-original/runs/nvarc-original-qwen3-native-ttt-008/package-l4/, "
        "retained native materials and official Kaggle SDK"
    )


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


class RetainedEvidenceNotRun(unittest.TestCase):
    """Visible skip with the original identity, never a successful assertion."""

    def __init__(self, test_id, requirement):
        super().__init__()
        self.test_id = test_id
        self.requirement = requirement

    def id(self):
        return self.test_id

    def __str__(self):
        return self.test_id

    def runTest(self):
        self.skipTest("UNVERIFIED retained-evidence integration: " + self.requirement)


class LinuxCapabilityNotRun(RetainedEvidenceNotRun):
    def runTest(self):
        self.skipTest("UNVERIFIED Linux-only capability in public-portable lane: " + self.requirement)


def select_suite(suite, *, retained_only=False, portable=False, manifest=None):
    if retained_only and portable:
        raise ValueError("retained acceptance cannot be combined with a portable subset")
    manifest = RETAINED_TESTS if manifest is None else manifest
    discovered = list(cases(suite))
    missing = set(manifest) - {test.id() for test in discovered}
    if missing:
        raise ValueError("retained-test manifest does not match discovery: " + ", ".join(sorted(missing)))
    selected = unittest.TestSuite()
    for test in discovered:
        requirement = manifest.get(test.id())
        if retained_only:
            if requirement is not None:
                selected.addTest(test)
        else:
            if requirement is not None:
                selected.addTest(RetainedEvidenceNotRun(test.id(), requirement))
            elif portable and (capability := linux_requirement(test)):
                selected.addTest(LinuxCapabilityNotRun(test.id(), capability))
            else:
                selected.addTest(test)
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--portable", action="store_true", help="explicit Windows-portable subset; Linux capability checks remain unverified")
    mode.add_argument("--retained", action="store_true", help="run the actual retained-evidence tests, fail if evidence is absent")
    args = parser.parse_args(argv)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    suite = select_suite(suite, retained_only=args.retained, portable=args.portable)
    if args.retained:
        print("Retained-evidence integration: genuine local inputs required; no replacement fixtures.", flush=True)
    else:
        print("Public-portable subset: Linux capability checks are explicitly UNVERIFIED." if args.portable else "Complete Linux public lane; no Linux capability exclusions.", flush=True)
        if args.portable:
            count = sum(isinstance(test, LinuxCapabilityNotRun) for test in cases(suite))
            print(f"Linux-capability tests explicitly UNVERIFIED: {count}.", flush=True)
        print(f"Public-checkout lane: {len(RETAINED_TESTS)} retained-evidence tests explicitly UNVERIFIED.", flush=True)
        print("This is not full Stage 4, GPU, model-quality or historical acceptance.", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
