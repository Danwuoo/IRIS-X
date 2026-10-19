"""Torch-free policy/dtype regressions, with synthetic artifacts only.

The fusion admission fixture deliberately stops at the next protocol gate. It
does not recover historical closure, load official weights, or claim efficacy.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tests.platform_requirements import requires_linux
from tools.arc2_goal_sprint_20261017.data import canonical
from tools.nvarc_posttrain_20261017 import matched_controller as mc
from tools.nvarc_posttrain_20261017.precision_contract import (
    LEGACY_POLICY, FP32_HEAD_POLICY, FP32_BACKBONE_POLICY, full_precision_execution_contract,
)

POLICY_DTYPES = ((LEGACY_POLICY, 'torch.bfloat16'),
                 (FP32_HEAD_POLICY, 'torch.bfloat16'),
                 (FP32_BACKBONE_POLICY, 'torch.float32'))
TENSORS = {'synthetic.cpu.weight': {'shape': [2], 'dtype': 'torch.float32'}}


def producer_contract(tensors, policy, frozen_dtype):
    """Independent fixture metadata; never derives dtype from the consumer."""
    result = {'tensors': copy.deepcopy(tensors), 'tensor_count': len(tensors),
        'parameter_count': sum(math.prod(row['shape']) for row in tensors.values()),
        'frozen_dtype': frozen_dtype, 'trainable_dtype': 'torch.float32',
        'rank': 64, 'alpha': 16, 'use_rslora': True,
        'target_modules': ['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
        'modules_to_save': ['embed_tokens', 'lm_head']}
    if policy != LEGACY_POLICY:
        result['probability_policy'] = policy
    return result


def tensor_fixture(root, policy, frozen_dtype, values=(1., 2.)):
    name = next(iter(TENSORS)); raw = struct.pack('<ff', *values)
    header = canonical({name: {'dtype': 'F32', 'shape': [2], 'data_offsets': [0, 8]}})
    header += b' ' * (-len(header) % 8)
    path = root / 'trainable_state.safetensors'
    path.write_bytes(struct.pack('<Q', len(header)) + header + raw)
    manifest = {'trainable_contract': producer_contract(TENSORS, policy, frozen_dtype),
        'trainable_tensors': {name: {**TENSORS[name], 'sha256': hashlib.sha256(raw).hexdigest()}},
        'state_sha256': hashlib.sha256(name.encode() + b'(2,)' + raw).hexdigest()}
    return path, manifest


class OfficialTrainableContractTests(unittest.TestCase):
    def test_all_admitted_policies_preserve_exact_official_geometry(self):
        tensors = mc._official_tensor_contract()
        for policy, dtype in POLICY_DTYPES:
            with self.subTest(policy=policy):
                actual = mc._official_trainable_contract(policy)
                self.assertEqual(actual, producer_contract(tensors, policy, dtype))
                self.assertEqual(actual['tensor_count'], 394)
                self.assertEqual(actual['parameter_count'], 69795840)
                self.assertTrue(all(row['dtype'] == 'torch.float32' for row in actual['tensors'].values()))

    def test_legacy_and_head_only_contract_bytes_are_unchanged(self):
        pins = {LEGACY_POLICY: '01b7d0d59052d008389683fd2316620bdf0a52bf4ce4de0a86b14c90037bba27',
                FP32_HEAD_POLICY: '31226f28f3d58f7a8bfe1a1d8fce7530f755dd63b93e0f98f217beefa5f30544'}
        for policy, expected in pins.items():
            with self.subTest(policy=policy):
                self.assertEqual(hashlib.sha256(canonical(mc._official_trainable_contract(policy))).hexdigest(), expected)
        self.assertEqual(mc._official_trainable_contract(), mc._official_trainable_contract(LEGACY_POLICY))
        self.assertNotIn('probability_policy', mc._official_trainable_contract())

    def test_unknown_policy_is_rejected_before_building_tensor_inventory(self):
        with patch.object(mc, '_official_tensor_contract') as tensors:
            for policy in ('unknown', '', None, True, [], {}):
                with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, 'admitted compact probability policy'):
                    mc._official_trainable_contract(policy)
            tensors.assert_not_called()


class TensorContractPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tensor_patch = patch.object(mc, '_official_tensor_contract', return_value=TENSORS)
        self.tensor_patch.start(); self.addCleanup(self.tensor_patch.stop)

    def test_each_policy_accepts_only_its_expected_resident_dtype(self):
        for policy, dtype in POLICY_DTYPES:
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as temp:
                path, manifest = tensor_fixture(Path(temp), policy, dtype)
                mc._verify_tensor_file(path, manifest, policy)
                manifest['trainable_contract']['frozen_dtype'] = (
                    'torch.bfloat16' if dtype == 'torch.float32' else 'torch.float32')
                with self.assertRaisesRegex(ValueError, 'exact official2B named trainables'):
                    mc._verify_tensor_file(path, manifest, policy)

    def test_relabelled_or_missing_policy_is_not_accepted(self):
        for policy in (LEGACY_POLICY, FP32_HEAD_POLICY, 'unknown', None):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as temp:
                path, manifest = tensor_fixture(Path(temp), FP32_BACKBONE_POLICY, 'torch.float32')
                if policy is None:
                    manifest['trainable_contract'].pop('probability_policy')
                else:
                    manifest['trainable_contract']['probability_policy'] = policy
                with self.assertRaisesRegex(ValueError, 'exact official2B named trainables'):
                    mc._verify_tensor_file(path, manifest, FP32_BACKBONE_POLICY)

    def test_unknown_expected_policy_cannot_be_matched_by_a_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            path, manifest = tensor_fixture(Path(temp), 'unknown', 'torch.float32')
            with self.assertRaisesRegex(ValueError, 'admitted compact probability policy'):
                mc._verify_tensor_file(path, manifest, 'unknown')

    def test_fp32_acceptance_keeps_tensor_hash_state_and_finiteness_checks(self):
        for mutation, message in (('tensor_hash', 'tensor SHA'), ('state_hash', 'full state SHA'),
                                  ('nonfinite', 'nonfinite checkpoint'), ('shape', 'shape/offsets')):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                values = (float('nan'), 2.) if mutation == 'nonfinite' else (1., 2.)
                path, manifest = tensor_fixture(Path(temp), FP32_BACKBONE_POLICY, 'torch.float32', values)
                if mutation == 'tensor_hash':
                    manifest['trainable_tensors'][next(iter(TENSORS))]['sha256'] = '0' * 64
                elif mutation == 'state_hash':
                    manifest['state_sha256'] = '0' * 64
                elif mutation == 'shape':
                    # Same byte length, but incompatible safetensors geometry.
                    path.write_bytes(path.read_bytes().replace(b'"shape":[2]', b'"shape":[1]'))
                with self.assertRaisesRegex(ValueError, message):
                    mc._verify_tensor_file(path, manifest, FP32_BACKBONE_POLICY)


@requires_linux('The production fusion controller imports Linux owned-process guards')
class FusionProductionAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_nvarc_efficient_fusion_panels import corpus
        from tools.nvarc_efficient_fusion_20261018 import controller, panels
        cls.controller = controller
        cls.temp = tempfile.TemporaryDirectory()
        args = corpus(Path(cls.temp.name))
        cls.prepared = panels.prepare_panels(*args[:4], **args[4])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def validate_until_next_gate(self, root, changes=None):
        ctl = self.controller
        protocol = {'version': ctl.PROTOCOL, 'source_identity': 'a' * 64,
            'panel_pins': self.prepared['pins'], 'config': ctl.DEFAULT_CONFIG,
            'arms': []}  # Intentionally incomplete: never a valid closure fixture.
        report = {'format': 'irisx/efficient-fusion-workflow-v1', 'source_identity': 'a' * 64,
            'protocol_sha256': ctl.sha(protocol), 'engine_contract': mc._official_model_contract(),
            'trainable_contract': producer_contract(mc._official_tensor_contract(), FP32_BACKBONE_POLICY, 'torch.float32'),
            'tokenizer_admission': mc._official_tokenizer_admission(),
            'base_identity': {'synthetic_fixture': True},
            'probability_execution': full_precision_execution_contract()}
        if changes:
            changes(report)
        for name, value in (('report.json', report), ('protocol.json', protocol), ('prepared-panels.json', self.prepared)):
            (root / name).write_bytes(canonical(value) + b'\n')
        # No fixture_contracts override: exercise the actual official consumer.
        ctl.validate_result(root, expected_source='a' * 64, expected_prepared=self.prepared,
                            model_identity={'synthetic_fixture': True})

    def test_fp32_report_passes_arithmetic_admission_but_not_later_protocol_gate(self):
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(ValueError, 'fixed loss/evaluation/selection declaration'):
            self.validate_until_next_gate(Path(temp))

    def test_wrong_dtype_policy_model_and_probability_are_still_rejected(self):
        changes = [lambda r: r['trainable_contract'].update(frozen_dtype='torch.bfloat16'),
            lambda r: r['trainable_contract'].update(probability_policy=FP32_HEAD_POLICY),
            lambda r: r['trainable_contract'].update(probability_policy='unknown'),
            lambda r: r['engine_contract'].update(hidden_size=4096),
            lambda r: r['probability_execution'].update(autocast_enabled=True),
            lambda r: r['tokenizer_admission'].update(vocab_size=17),
            lambda r: r.update(base_identity={'synthetic_fixture': False})]
        for index, change in enumerate(changes):
            with self.subTest(case=index), tempfile.TemporaryDirectory() as temp, \
                    self.assertRaisesRegex(ValueError, 'exact admitted model/arithmetic contract differs'):
                self.validate_until_next_gate(Path(temp), change)


if __name__ == '__main__':
    unittest.main()
