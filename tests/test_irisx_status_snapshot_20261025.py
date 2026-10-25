"""Static publication integrity only; no original datasets or provider access."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/'research/irisx-status-20261025'


class Snapshot(unittest.TestCase):
    def load(self, name):
        return json.loads((SNAP/name).read_text())

    def test_published_source_pins(self):
        for item in self.load('SOURCE-PROVENANCE.json')['source_files']:
            path=ROOT/item['repository_path']
            body=path.read_bytes()
            self.assertLess(len(body),1024*1024)
            self.assertEqual(hashlib.sha256(body).hexdigest(),item['sha256'])
            self.assertEqual(len(body),item['bytes'])

    def test_plan_is_disabled_and_not_a_quality_result(self):
        p=self.load('postsft/TPU-MATRIX.json')
        self.assertEqual(p['model_calls'],0)
        self.assertEqual(p['provider_calls'],0)
        self.assertFalse(p['cost']['gpu_run_authorized'])
        self.assertEqual(p['go_no_go']['formal_training'],'NO_GO')
        k=self.load('postsft/K1-RESULT.json')
        self.assertEqual(k['method_optimizer_updates_total'],4)
        self.assertFalse(k['quality_gain_observed'])
        self.assertFalse(k['native_checkpoint_restore_pass'])
        self.assertFalse(k['clean_holdout'])

    def test_no_token_or_answer_bodies_in_discovery_metadata(self):
        p=self.load('postsft/DISCOVERY-PANEL.json')
        self.assertFalse(p['execution_authorized'])
        self.assertEqual(len(p['rows']),16)
        self.assertEqual(len({r['parent_id'] for r in p['rows']}),16)
        for r in p['rows']:
            self.assertFalse({'prompt','ids','target_ids','answer','gold','query_targets_sha256'} & set(r))

    def test_aggregate_counts_not_new_parents(self):
        p=self.load('postsft/OFFICIAL800-LENGTH-SUMMARY.json')
        self.assertEqual(p['parents'],800)
        self.assertEqual(p['views'],2573)
        self.assertEqual(p['new_parents'],0)
        self.assertFalse(p['native_or_model_test'])
        self.assertEqual(p['generation_caps']['512']['parents_any_view'],743)
        self.assertEqual(p['generation_caps']['512']['views_both_conditions'],2380)


if __name__=='__main__':
    unittest.main()
