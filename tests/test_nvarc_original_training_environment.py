"""Distribution metadata controls, without importing the source packages."""
import unittest
from irisx.errors import ValidationError
from tools.audit_nvarc_original_training_environment import metadata_version
from tools.replay_nvarc_original_training_edges import source_snapshot


class OriginalTrainingEnvironmentTests(unittest.TestCase):
    def test_normalized_distribution_name_requires_exact_version(self):
        raw=b'Name: cut-cross-entropy\nVersion: 25.1.1\n\n'
        self.assertEqual(metadata_version(raw,'cut_cross_entropy','25.1.1')['version'],'25.1.1')
        for name,version in [('foreign','25.1.1'),('cut_cross_entropy','25.1.0')]:
            with self.subTest(name=name,version=version),self.assertRaises(ValidationError):metadata_version(raw,name,version)
        with self.assertRaises(ValidationError):metadata_version(b'Version: 25.1.1\n','cut_cross_entropy','25.1.1')

    def test_exact_worker_clone_survives_source_mutation_and_rejects_missing_clone(self):
        class TensorFixture:
            def __init__(self,value):self.value=value;self.detached=False
            def clone(self):return TensorFixture(self.value)
            def detach(self):self.detached=True;return self
        raw={'adapter':TensorFixture(7)}
        source='def worker():\n    default_weights = {k: v.clone().detach() for k, v in default_weights.items()}\n'
        baseline=source_snapshot(raw,source);raw['adapter'].value=9
        self.assertEqual(baseline.copy()['adapter'].value,7)
        self.assertTrue(baseline['adapter'].detached)
        self.assertIsNot(baseline['adapter'],raw['adapter'])
        for replacement in ('v.detach()','v.clone()','v'):
            with self.subTest(replacement=replacement),self.assertRaises(ValidationError):
                source_snapshot(raw,source.replace('v.clone().detach()',replacement))


if __name__=='__main__':unittest.main()
