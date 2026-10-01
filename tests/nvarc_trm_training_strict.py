"""Actual pinned TRM train_batch/EMA oracle and persistent-carry resume."""
import copy,json,hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import torch

from irisx.arc_nvarc_m3_trm import _batch,_initial_carry_on_device,_model_config
from irisx.arc_nvarc_trm_runtime import build_runtime_bundle,runtime_classes,construct_source_model
from irisx.arc_nvarc_trm_training import build_training_reference,reference_functions,SourceTRMTrainer,tensor_tree_inventory,pack_tree,verify_trm_export
from irisx.canonical import digest_value,canonical_bytes
from irisx.errors import ValidationError

ROOT=Path(__file__).resolve().parents[1]


class SourceTRMTrainingStrictTests(unittest.TestCase):
    def test_source_normalization_schedule_ema_carry_and_exact_resume(self):
        threads=torch.get_num_threads();torch.set_num_threads(1)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);source=ROOT/'.irisx/arc-agi-2/qwen35-nvarc/source/NVARC'
                binding=build_runtime_bundle(source/'external/TinyRecursiveModels',root/'bundle')
                build_training_reference(source,root/'reference');reference=reference_functions(root/'reference')
                cfg={'global_batch_size':2,'lr':.0003,'lr_min_ratio':1.,'lr_warmup_steps':2000,
                    'beta1':.9,'beta2':.95,'weight_decay':.1,'puzzle_emb_weight_decay':.1,
                    'puzzle_emb_lr':.01,'ema_rate':.999,'total_steps':2}
                mc=_model_config({'num_puzzle_identifiers':3});mc.update(batch_size=2,halt_max_steps=16,halt_exploration_prob=.1)
                batch=_batch([[1,2],[3,4]],[[4,3],[2,1]],identifier=1)
                second=_batch([[1,2,3],[4,5,6]],[[6,5,4],[3,2,1]],identifier=2)
                batch={key:torch.cat([value,second[key]]) for key,value in batch.items()}
                identity=digest_value({'config':cfg,'model':mc,'fixture':'actual public-demo training only'})
                with runtime_classes(root/'bundle',binding['bundle_digest']) as classes:
                    torch.manual_seed(0);trainer=SourceTRMTrainer(classes,mc,cfg,reference,identity)
                    control=construct_source_model(classes,mc,'cpu');control.load_state_dict(trainer.model.state_dict())
                    _,_,sparse,adam=classes
                    control_opts=[sparse(control.model.puzzle_emb.buffers(),world_size=1,lr=0.,weight_decay=.1),
                        adam(control.parameters(),lr=.001,weight_decay=.1,betas=(.9,.95))]
                    control_ema=reference['EMAHelper'](mu=.999);control_ema.register(control)
                    state=SimpleNamespace(step=0,total_steps=2,carry=_initial_carry_on_device(control,batch),
                        model=control,optimizers=control_opts,optimizer_lrs=[.01,.0003])
                    control.train()
                    for index in range(2):
                        before=torch.get_rng_state();observation=trainer.train(batch);after=torch.get_rng_state()
                        torch.set_rng_state(before)
                        # The unchanged CUDA-only reference is CPU-replayed by
                        # making only Tensor.cuda an identity. Its already
                        # initialized CPU carry avoids a CUDA factory context.
                        with patch.object(torch.Tensor,'cuda',lambda value,*args,**kwargs:value):
                            metrics=reference['train_batch'](SimpleNamespace(**cfg),state,batch,2,0,1)
                        control_ema.update(control)
                        self.assertTrue(torch.equal(after,torch.get_rng_state()))
                        actual={'model':trainer.model.state_dict(),'optimizers':[o.state_dict() for o in trainer.optimizers],
                            'ema':trainer.ema.state_dict(),'carry':trainer.carry}
                        expected={'model':control.state_dict(),'optimizers':[o.state_dict() for o in control_opts],
                            'ema':control_ema.state_dict(),'carry':state.carry}
                        self.assertEqual(tensor_tree_inventory(actual),tensor_tree_inventory(expected))
                        self.assertGreater(observation['nonzero_gradient_tensors'],0)
                        self.assertEqual(observation['learning_rates'][-1],metrics['train/lr'])
                        if index==0:trainer.save(root/'checkpoint-1.pt')
                    final=tensor_tree_inventory(trainer.state())
                    resumed=SourceTRMTrainer(classes,mc,cfg,reference,identity)
                    resumed.restore(root/'checkpoint-1.pt',batch)
                    self.assertEqual(1,resumed.step)
                    resumed.train(batch)
                    self.assertEqual(final,tensor_tree_inventory(resumed.state()))
                    wrong=SourceTRMTrainer(classes,mc,cfg,reference,digest_value({'wrong':'identity'}))
                    with self.assertRaisesRegex(ValidationError,'identity/config'):
                        wrong.restore(root/'checkpoint-1.pt',batch)
                    resumed.ema.ema(resumed.model)
                    export=root/'export';export.mkdir();torch.save(pack_tree(resumed.model.state_dict()),export/'trm-ema.pt')
                    material={'training_identity_digest':identity,'tensor_inventory':tensor_tree_inventory(resumed.model.state_dict()),
                        'checkpoint_sha256':hashlib.sha256((export/'trm-ema.pt').read_bytes()).hexdigest()}
                    (export/'material.json').write_bytes(canonical_bytes(material,newline=True))
                    self.assertEqual(material,verify_trm_export(export,digest_value(material)))
                    with (export/'trm-ema.pt').open('ab') as stream:stream.write(b'tamper')
                    with self.assertRaisesRegex(ValidationError,'checkpoint bytes'):
                        verify_trm_export(export,digest_value(material))
        finally:torch.set_num_threads(threads)


if __name__=='__main__':unittest.main()
