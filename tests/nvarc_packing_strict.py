"""Independent NeMo placement and real hybrid attention/state differential."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import random
import unittest

import torch
from irisx.arc_nvarc_packing import (REFERENCE, pack_sequences, modified_first_fit_decreasing,
    iter_isolated_forwards, isolated_pack_loss)
from tests import test_arc_nvarc_ml as ml_tests

ROOT = Path(__file__).resolve().parents[1]


class PackingStrictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.threads)

    def test_placement_matches_independent_pinned_nemo_on_503_inputs(self):
        path = ROOT / '.irisx/nvarc-original/materials/nemo-packing-reference-20261002/nemo_rl/data/packing/algorithms.py'
        self.assertEqual(REFERENCE['algorithm_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        spec = importlib.util.spec_from_file_location('pinned_nemo_packing', path)
        upstream = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upstream)
        randomizer = random.Random(24)
        cases = [(100, []), (100, [51, 49, 34, 33, 17, 16, 1]), (128, [64] * 32)]
        cases += [(capacity, [randomizer.randint(1, capacity) for _ in range(randomizer.randint(1, 256))])
                  for capacity in (32, 64, 100, 256, 256000) for _ in range(100)]
        for capacity, lengths in cases:
            self.assertEqual(upstream.ModifiedFirstFitDecreasingPacker(capacity).pack(lengths),
                             modified_first_fit_decreasing(lengths, capacity))

    def test_hybrid_logits_loss_and_gradients_match_independent_samples_without_leakage(self):
        torch.manual_seed(24)
        model = ml_tests.NvarcMLTests()._tiny_qwen()
        model.resize_token_embeddings(16)
        model.eval()
        independent = copy.deepcopy(model)
        rows = [{'input_ids': [14, 11, 1, 12, 2, 15], 'labels': [-100] * 4 + [2, 15]},
                {'input_ids': [14, 11, 3, 4, 10, 5, 12, 6, 15],
                 'labels': [-100] * 7 + [6, 15]},
                {'input_ids': [14, 11, 7, 12, 8, 9, 15], 'labels': [-100] * 4 + [8, 9, 15]}]
        packs = pack_sequences(rows, capacity=32, length_multiple=4)
        expected, loss_sum, count = {}, 0, 0
        for index, row in enumerate(rows):
            ids = torch.tensor([row['input_ids']])
            labels = torch.tensor([row['labels']])
            logits = independent(input_ids=ids, use_cache=False).logits
            expected[index] = logits.detach()
            loss_sum = loss_sum + torch.nn.functional.cross_entropy(logits[:, :-1].float().reshape(-1, 16),
                labels[:, 1:].reshape(-1), ignore_index=-100, reduction='sum')
            count += sum(y >= 0 for y in row['labels'][1:])
        packed_sum = 0
        for pack in packs:
            for item in iter_isolated_forwards(model, pack, torch.device('cpu')):
                torch.testing.assert_close(item['logits'], expected[item['segment']['row_index']], rtol=0, atol=0)
                packed_sum = packed_sum + item['loss_sum']
        torch.testing.assert_close(packed_sum / count, loss_sum / count)
        (packed_sum / count).backward()
        (loss_sum / count).backward()
        for actual, reference in zip(model.parameters(), independent.parameters()):
            if actual.grad is not None:
                torch.testing.assert_close(actual.grad, reference.grad, rtol=1e-5, atol=1e-7)
        changed = copy.deepcopy(rows)
        changed[0]['input_ids'][2] = 9
        changed[0]['input_ids'][4] = changed[0]['labels'][4] = 3
        with torch.no_grad():
            for pack in pack_sequences(changed, capacity=32, length_multiple=4):
                for item in iter_isolated_forwards(model, pack, torch.device('cpu')):
                    index = item['segment']['row_index']
                    if index != 0:
                        torch.testing.assert_close(item['logits'], expected[index], rtol=0, atol=0)
            # Show this architecture is sensitive to the unsafe concatenation.
            prefix = rows[0]['input_ids'] + rows[1]['input_ids']
            joined = model(input_ids=torch.tensor([prefix]), use_cache=False).logits[:, len(rows[0]['input_ids']):]
            self.assertFalse(torch.allclose(joined, expected[1], rtol=1e-4, atol=1e-6))


if __name__ == '__main__':
    unittest.main()
