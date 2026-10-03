"""Actual original Qwen3/FSDP restart, full Adam state and export differentials."""
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

import torch
from transformers import Qwen3Config, Qwen3ForCausalLM
from irisx.arc_nvarc_qwen3_sft import FORMAT, encode_source_pair, export, file_inventory
from irisx.arc_nvarc_source_sft import tensor_inventory
from irisx.arc_nvarc_sft_step import source_optimizer
from irisx.arc_nvarc_gpu_preflight_v2 import RECIPE
from irisx.canonical import canonical_bytes, digest_value

ROOT = Path(__file__).resolve().parents[1]
ROWS = [
    {'input_ids':[14,11,10,1,2,15,14,12,10,3,4,15], 'labels':[-100]*9+[3,4,15]},
    {'input_ids':[14,11,10,8,15,14,12,10,7,15], 'labels':[-100]*8+[7,15]},
    {'input_ids':[14,11,10,0,2,1,15,14,12,10,1,2,0,15], 'labels':[-100]*10+[1,2,0,15]}]


class OriginalSFTStrictTests(unittest.TestCase):
    def test_original_tokenizer_pair_matches_actual_wordlevel_and_source_mask(self):
        from tokenizers import Tokenizer
        source = ROOT/'.irisx/arc-agi-2/qwen35-nvarc/source/NVARC/ARChitects/qwen3_configs/tokenizer.json'
        tokenizer = Tokenizer.from_file(str(source))
        pair = [{'role':'user','content':'12\n34'}, {'role':'assistant','content':'56\n78'}]
        tokens, labels = encode_source_pair(pair)
        user = '<|im_start|>user\n12\n34<|im_end|>'
        assistant = '<|im_start|>assistant\n56\n78<|im_end|>'
        self.assertEqual(tokenizer.encode(user+assistant).ids, tokens)
        self.assertEqual([-100]*(len(tokenizer.encode(user).ids)+3)+tokenizer.encode('56\n78<|im_end|>').ids, labels)

    def test_three_steps_restart_failure_retains_all_model_moments_rng_and_export(self):
        torch.set_num_threads(2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            torch.manual_seed(731)
            config = Qwen3Config(vocab_size=16,hidden_size=64,intermediate_size=128,num_hidden_layers=2,
                num_attention_heads=4,num_key_value_heads=2,head_dim=16,max_position_embeddings=262144,
                rope_theta=5000000,attention_dropout=0.,tie_word_embeddings=True,pad_token_id=13,bos_token_id=13,eos_token_id=15)
            config._attn_implementation = 'sdpa'
            model = Qwen3ForCausalLM(config).float()
            oracle = copy.deepcopy(model)
            model.save_pretrained(root/'model',safe_serialization=True)
            del model
            inventory = file_inventory(root/'model')
            rows = ROWS*3
            plan = {'format':FORMAT,'model_family':'qwen3','run_id':'nvarc-original-qwen3-sft-901',
                'backend':'cpu','data_kind':'synthetic-fixture','source_recipe':RECIPE,'world_size':2,
                'model_inventory':inventory,'base_material_digest':digest_value(inventory),'data_digest':digest_value(rows),
                'global_batch_size':3,'maximum_optimizer_steps':3,'maximum_training_tokens':108,'maximum_input_tokens':114,
                'scheduled_input_tokens':108,'maximum_sequence_length':14,'maximum_physical_input_tokens':16,
                'packing_execution':'segmented-gemm-whole-sample-packing','packing_capacity':256000,'packing_length_multiple':64,
                'checkpoint_steps':[1,2,3],'checkpoint_storage':'durable-retained','checkpoint_keep_last':2,'seed':24,
                'maximum_outer_forwards':12,'maximum_worker_wall_seconds':180,
                'maximum_paid_usd':0,'maximum_generations':0,'maximum_teacher_calls':0}
            (root/'plan.json').write_bytes(canonical_bytes(plan,newline=True))
            (root/'rows.json').write_bytes(canonical_bytes(rows,newline=True))

            def launch(name, flags=(), fail=False):
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
                command = [sys.executable,'-m','irisx.arc_nvarc_qwen3_sft','--plan',str(root/'plan.json'),
                    '--compact',str(root/'model'),'--data',str(root/'rows.json'),'--output',str(root/name),
                    '--checkpoints',str(root/(name+'-checkpoints')),*flags]
                processes, logs = [], []
                try:
                    for rank in range(2):
                        log = (root/f'{name}-{rank}.log').open('w',encoding='utf-8'); logs.append(log)
                        env = {**os.environ,'PYTHONPATH':str(ROOT/'src'),'MASTER_ADDR':'127.0.0.1','MASTER_PORT':str(port),
                            'WORLD_SIZE':'2','RANK':str(rank),'LOCAL_RANK':str(rank),'USE_LIBUV':'0','OMP_NUM_THREADS':'1',
                            'HF_HUB_OFFLINE':'1','PYTHONIOENCODING':'utf-8'}
                        processes.append(subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT))
                    deadline = time.monotonic()+180
                    while any(p.poll() is None for p in processes):
                        if any(p.poll() not in {None,0} for p in processes):
                            if fail:
                                break
                            self.fail('\n'.join(p.read_text(errors='replace')[-10000:] for p in root.glob(name+'-*.log')))
                        if time.monotonic()>deadline:
                            self.fail('original restart timeout')
                        time.sleep(.2)
                    self.assertEqual(fail, any(p.returncode for p in processes),
                        '\n'.join(p.read_text(errors='replace')[-10000:] for p in root.glob(name+'-*.log')))
                finally:
                    for p in processes:
                        if p.poll() is None:
                            if os.name=='nt': subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=10)
                            else: p.kill()
                            p.wait(timeout=10)
                    for log in logs: log.close()
            launch('continuous')
            launch('resumed',['--stop-after-step','1'])
            checkpoint_root = root/'resumed-checkpoints'
            committed = (checkpoint_root/'latest.json').read_bytes()
            reference = json.loads(committed)
            # A crash after restore must preserve the only committed checkpoint.
            launch('resumed',['--resume','--fault-before-step','1'],fail=True)
            self.assertEqual(committed,(checkpoint_root/'latest.json').read_bytes())
            self.assertTrue((checkpoint_root/reference['path']/'manifest.json').is_file())
            # A previous incomplete transaction for step 2 cannot be overwritten.
            incomplete = checkpoint_root/'checkpoint-step-0002-attempt-0001'
            incomplete.mkdir(); (incomplete/'partial.txt').write_text('retained interrupted transaction')
            launch('resumed',['--resume'])
            self.assertEqual('retained interrupted transaction',(incomplete/'partial.txt').read_text())
            self.assertTrue((checkpoint_root/'checkpoint-step-0002-attempt-0002/manifest.json').is_file())
            from torch.distributed.checkpoint.format_utils import dcp_to_torch_save
            states = []
            for name in ('continuous','resumed'):
                cp = root/(name+'-checkpoints')
                latest = json.loads((cp/'latest.json').read_bytes())
                dcp_to_torch_save(cp/latest['path']/'dcp',root/(name+'.pt'))
                states.append(torch.load(root/(name+'.pt'),weights_only=True))
            def compare(a,b):
                if torch.is_tensor(a): torch.testing.assert_close(a,b,rtol=0,atol=0)
                elif isinstance(a,dict):
                    self.assertEqual(set(a),set(b))
                    for key in a: compare(a[key],b[key])
                elif isinstance(a,(list,tuple)):
                    self.assertEqual(len(a),len(b))
                    for x,y in zip(a,b): compare(x,y)
                else: self.assertEqual(a,b)
            compare(*states)
            for rank in range(2):
                compare(torch.load(root/'continuous-checkpoints/checkpoint-step-0003-attempt-0001'/f'rank-{rank}.pt',weights_only=True),
                        torch.load(root/'resumed-checkpoints/checkpoint-step-0003-attempt-0001'/f'rank-{rank}.pt',weights_only=True))
            final = json.loads((root/'resumed/final-result.json').read_bytes())
            self.assertEqual((3,9,108,27),(final['step'],final['cursor'],final['input_tokens'],final['supervised_tokens']))
            self.assertEqual('qwen3',final['model_family'])
            self.assertFalse(final['full_sft_completed'])
            # Independent unpacked global token-mean loss/Adam, without shared
            # packing, accumulation, FSDP or checkpoint helper implementations.
            optimizer,scheduler = source_optimizer(oracle,RECIPE)
            import torch.nn.functional as F
            for _ in range(3):
                optimizer.zero_grad(set_to_none=True)
                for row in ROWS:
                    logits = oracle(torch.tensor([row['input_ids']]),use_cache=False).logits
                    loss = F.cross_entropy(logits[:,:-1].float().reshape(-1,16),
                        torch.tensor(row['labels'][1:]),ignore_index=-100,reduction='sum') / 9
                    loss.backward()
                torch.nn.utils.clip_grad_norm_(oracle.parameters(),.5)
                optimizer.step(); scheduler.step()
            for name,value in oracle.state_dict().items():
                torch.testing.assert_close(value,states[0]['model'][name],atol=1e-7,rtol=2e-5)
            for name,parameter in oracle.named_parameters():
                for key in ('exp_avg','exp_avg_sq'):
                    torch.testing.assert_close(optimizer.state[parameter][key],states[0]['optimizer']['state'][name][key],atol=1e-7,rtol=4e-5)
            chain = export(root/'plan.json',root/'model',root/'rows.json',root/'resumed',checkpoint_root,root/'export')
            self.assertTrue(chain['reload_tensor_bytes_identical'])
            self.assertTrue(chain['optimizer_checkpoint_retained'])
            print(json.dumps({'original_qwen3_three_steps':True,'actual_calls_including_dummy':12,
                'source_input_tokens':108,'actual_input_tokens_including_dummy':114,'all_model_adam_rng_scheduler_resume_exact':True,
                'unpacked_oracle_matches_every_weight_and_moment':True,'prior_checkpoint_retained_after_failure':True,
                'incomplete_transaction_preserved':True,'export_tensors':len(chain['export_tensor_inventory']),
                'gpu_evidence':False,'full_sft_completed':False}),flush=True)


if __name__=='__main__': unittest.main()
