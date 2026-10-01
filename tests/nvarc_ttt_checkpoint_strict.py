"""Full 128-view source epoch matches with nonreentrant checkpointing."""
import copy
import unittest
import torch
from irisx.arc_nvarc_training import TaskLocalAdapter
from tests import nvarc_method_strict as method_tests
from tests import test_arc_nvarc_ml as ml_tests


class TTTCheckpointStrictTests(unittest.TestCase):
    def test_checkpointed_rank256_epoch_matches_losses_adapter_and_reset(self):
        from peft import get_peft_model_state_dict
        threads=torch.get_num_threads();torch.set_num_threads(1)
        try:
            torch.manual_seed(24)
            model=ml_tests.NvarcMLTests()._tiny_qwen();model.resize_token_embeddings(16)
            other=copy.deepcopy(model);offloaded=copy.deepcopy(model)
            config={'rank':256,'alpha':32,'seed':42,'use_rslora':True,
                'training_schedule':'source-one-epoch','source_qwen':True,'augmentation_count':16,
                'source_augmentation_seed':1,'max_sequence_length':8192,'learning_rate':5e-5,
                'warmup_ratio':.1,'maximum_optimizer_steps':128,'maximum_training_tokens':1048576}
            adapters=[TaskLocalAdapter(model,config),TaskLocalAdapter(other,{**config,'gradient_checkpointing':True}),
                TaskLocalAdapter(offloaded,{**config,'gradient_checkpointing':True,'optimizer_state_device':'cpu'})]
            states=[]
            for index,adapter in enumerate(adapters):
                adapter.adapt(method_tests.TASK)
                observation=adapter.last_observation
                self.assertEqual(128,observation['steps'])
                self.assertTrue(observation['complete_epoch'])
                self.assertEqual(bool(index),observation['gradient_checkpointing'])
                states.append({name:value.detach().clone() for name,value in get_peft_model_state_dict(adapter.model).items()})
                adapter.reset(clear_observation=False)
                self.assertTrue(all(torch.equal(value.cpu(),adapter.initial[name])
                    for name,value in get_peft_model_state_dict(adapter.model).items()))
            for name in states[0]:torch.testing.assert_close(states[0][name],states[1][name],rtol=0,atol=0)
            self.assertEqual(adapters[0].last_observation['losses_by_step'],adapters[1].last_observation['losses_by_step'])
            self.assertEqual(adapters[0].last_observation['learning_rates_by_step'],adapters[1].last_observation['learning_rates_by_step'])
            for name in states[0]:torch.testing.assert_close(states[0][name],states[2][name],rtol=0,atol=0)
            self.assertEqual(adapters[0].last_observation['losses_by_step'],adapters[2].last_observation['losses_by_step'])
            self.assertEqual(adapters[0].last_observation['learning_rates_by_step'],adapters[2].last_observation['learning_rates_by_step'])
            self.assertEqual('cpu',adapters[2].last_observation['optimizer_state_device'])
        finally:torch.set_num_threads(threads)


if __name__=='__main__':unittest.main()
