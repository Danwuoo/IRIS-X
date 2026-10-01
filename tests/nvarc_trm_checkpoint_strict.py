"""Actual source TRM state loading versus the pinned embedding reset rule."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import torch

from irisx.arc_nvarc_m3_trm import _source_classes,_model_config
from irisx.arc_nvarc_trm_checkpoint import load_published_state,PUZZLE_EMBEDDING
from irisx.arc_nvarc_upstream import SOURCE
from irisx.errors import ValidationError


class PublishedTRMCheckpointTests(unittest.TestCase):
    def test_source_mean_reset_and_closed_tensor_load(self):
        model_cls,loss_cls,_,_=_source_classes(SOURCE/'NVARC/external/TinyRecursiveModels')
        config=_model_config({'num_puzzle_identifiers':5})
        torch.manual_seed(47);source=loss_cls(model_cls(config),loss_type='stablemax_cross_entropy')
        with torch.no_grad():source.state_dict()[PUZZLE_EMBEDDING].copy_(torch.arange(5*32).reshape(5,32))
        raw={'_orig_mod.'+name:value for name,value in source.state_dict().items()}
        target=loss_cls(model_cls({**config,'num_puzzle_identifiers':1}),loss_type='stablemax_cross_entropy')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'checkpoint';torch.save(raw,path)
            sha=hashlib.sha256(path.read_bytes()).hexdigest()
            report=load_published_state(target,path,sha)
            self.assertTrue(report['source_mean_reset_applied'])
            self.assertEqual([5,32],report['source_puzzle_embedding_shape'])
            for name,value in target.state_dict().items():
                expected=source.state_dict()[name].mean(0,keepdim=True) if name==PUZZLE_EMBEDDING else source.state_dict()[name]
                self.assertTrue(torch.equal(value,expected))
            with self.assertRaisesRegex(ValidationError,'digest'):
                load_published_state(target,path,'0'*64)
            raw['_orig_mod.unexpected.weight']=torch.ones(1);torch.save(raw,path)
            with self.assertRaisesRegex(ValidationError,'closed state names'):
                load_published_state(target,path,hashlib.sha256(path.read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
