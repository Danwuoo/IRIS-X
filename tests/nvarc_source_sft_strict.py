"""Accumulated source SFT uninterrupted/resumed tensor equivalence and export."""
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
from irisx.arc_nvarc_gpu_preflight_v2 import RECIPE
from irisx.arc_nvarc_m2 import create_tiny_qwen_material
from irisx.arc_nvarc_source_sft import export
from irisx.canonical import canonical_bytes, digest_value
from tests import nvarc_sft_step_strict as accumulation_tests

ROOT=Path(__file__).resolve().parents[1]


class SourceSFTStrictTests(unittest.TestCase):
    def test_cursor_optimizer_rng_resume_and_every_export_tensor(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            model,base=create_tiny_qwen_material(root/'model');del model
            rows=accumulation_tests.ROWS*2
            plan={'format':'irisx/nvarc-source-sft-v1','run_id':'nvarc-overnight-cpu-fixture',
                'backend':'cpu','data_kind':'synthetic-fixture','source_recipe':RECIPE,'world_size':2,
                'base_material_digest':base,'data_digest':digest_value(rows),'global_batch_size':3,
                'maximum_optimizer_steps':2,'maximum_training_tokens':44,'scheduled_input_tokens':44,
                'maximum_sequence_length':9,'packing_execution':'isolated-segments','packing_capacity':256000,
                'packing_length_multiple':64,'checkpoint_steps':[1,2],'seed':24,
                'maximum_paid_usd':0,'maximum_generations':0,'maximum_teacher_calls':0}
            (root/'plan.json').write_bytes(canonical_bytes(plan,newline=True))
            (root/'rows.json').write_bytes(canonical_bytes(rows,newline=True))
            def launch(name,flags=()):
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                command=[sys.executable,'-m','irisx.arc_nvarc_source_sft','--plan',str(root/'plan.json'),
                    '--compact',str(root/'model'),'--data',str(root/'rows.json'),'--output',str(root/name),
                    '--scratch',str(root/(name+'-scratch')),*flags]
                processes=[];logs=[]
                try:
                    for rank in range(2):
                        log=(root/f'{name}-{rank}.log').open('w',encoding='utf-8');logs.append(log)
                        env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'MASTER_ADDR':'127.0.0.1','MASTER_PORT':str(port),
                            'WORLD_SIZE':'2','RANK':str(rank),'LOCAL_RANK':str(rank),'USE_LIBUV':'0',
                            'OMP_NUM_THREADS':'1','HF_HUB_OFFLINE':'1','PYTHONIOENCODING':'utf-8'}
                        processes.append(subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT))
                    deadline=time.monotonic()+180
                    while any(p.poll() is None for p in processes):
                        if any(p.poll() not in {None,0} for p in processes) or time.monotonic()>deadline:
                            self.fail(str([p.poll() for p in processes])+'\n'+
                                '\n'.join(p.read_text(errors='replace')[-10000:] for p in root.glob(name+'-*.log')))
                        time.sleep(.2)
                    self.assertEqual([0,0],[p.returncode for p in processes])
                finally:
                    for p in processes:
                        if p.poll() is None:
                            if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=10)
                            else:p.kill()
                            p.wait(timeout=10)
                    for log in logs:log.close()
            launch('continuous')
            launch('resumed',['--stop-after-step','1'])
            pause=json.loads((root/'resumed/pause-result.json').read_bytes())
            launch('resumed',['--resume'])
            from torch.distributed.checkpoint.format_utils import dcp_to_torch_save
            states=[]
            for name in ('continuous','resumed'):
                dcp_to_torch_save(root/(name+'-scratch')/'checkpoint-step-0002/dcp',root/(name+'.pt'))
                states.append(torch.load(root/(name+'.pt'),weights_only=True))
            def compare(a,b):
                if torch.is_tensor(a):torch.testing.assert_close(a,b,rtol=0,atol=0)
                elif isinstance(a,dict):
                    self.assertEqual(set(a),set(b))
                    for key in a:compare(a[key],b[key])
                elif isinstance(a,(tuple,list)):
                    self.assertEqual(len(a),len(b))
                    for x,y in zip(a,b):compare(x,y)
                else:self.assertEqual(a,b)
            compare(*states)
            for rank in range(2):
                a=torch.load(root/'continuous-scratch/checkpoint-step-0002'/f'rank-{rank}.pt',weights_only=True)
                b=torch.load(root/'resumed-scratch/checkpoint-step-0002'/f'rank-{rank}.pt',weights_only=True)
                compare(a,b)
            final=json.loads((root/'resumed/final-result.json').read_bytes())
            self.assertEqual((2,6,44,14),(final['step'],final['cursor'],final['input_tokens'],final['supervised_tokens']))
            self.assertEqual(pause['weight_fingerprint_after'],final['restored_fingerprint'])
            self.assertFalse(final['full_sft_completed'])
            self.assertFalse((root/'continuous-scratch/checkpoint-step-0001').exists())
            chain=export(root/'plan.json',root/'model',root/'rows.json',root/'resumed',root/'resumed-scratch',root/'export')
            self.assertTrue(chain['reload_tensor_bytes_identical'])
            self.assertGreater(len(chain['export_tensor_inventory']),10)


if __name__=='__main__':unittest.main()
