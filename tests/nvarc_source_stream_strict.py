"""Real Arrow/HF lazy stream conserves the source shuffle and exposure."""
import tempfile
from pathlib import Path
import unittest

import numpy as np
from irisx.arc_nvarc_datasets import sha_file
from irisx.arc_nvarc_source_stream import OriginalSequenceStream
from irisx.errors import ValidationError
from tests import nvarc_original_corpus_strict as corpus_tests


class SourceStreamStrictTests(unittest.TestCase):
    def test_full_shuffle_partition_whole_long_sample_and_validation_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = corpus_tests.OriginalCorpusStrictTests()._fixture(Path(directory))
            with OriginalSequenceStream(root, sha_file(root/'manifest.json')) as stream:
                self.assertEqual(list(stream.order), list(np.random.default_rng(24).permutation(7)))
                rows = [stream[index] for index in range(len(stream))]
                self.assertEqual(set(corpus_tests.SOURCES), {row['source_id'] for row in rows})
                long = next(row for row in rows if len(row['input_ids']) > 8192)
                self.assertEqual(17000, len(long['input_ids']))
                mixed = next(row for row in rows if row['source_id']=='nvarc_full')
                self.assertEqual(['22222222','33333333'], mixed['parent_ids'])
                self.assertIn('locked_holdout-ancestor',mixed['exposure_tags'])
                shards=[stream.batch(0,7,rank=rank,world=3) for rank in range(3)]
                self.assertEqual(list(range(7)),sorted(row['shuffle_position'] for shard in shards for row in shard))
                for bad in ((6,2),(7,1),(-1,1)):
                    with self.assertRaises(ValidationError):stream.batch(*bad)
            with OriginalSequenceStream(root,sha_file(root/'manifest.json'),split='validation') as validation:
                self.assertEqual(corpus_tests.VALIDATION,validation[0]['source_id'])
                with self.assertRaises(ValidationError):validation.batch(0,1)


if __name__=='__main__':unittest.main()
