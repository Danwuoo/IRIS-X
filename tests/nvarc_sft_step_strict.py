"""Real two-rank FSDP accumulation against an independent all-sample gradient."""
import contextlib
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
from irisx.arc_nvarc_sft_step import source_optimizer, train_source_step
from tests import test_arc_nvarc_ml as ml_tests

ROOT = Path(__file__).resolve().parents[1]
ROWS = [{'input_ids': [14, 11, 1, 12, 2, 15], 'labels': [-100] * 4 + [2, 15]},
        {'input_ids': [14, 11, 3, 4, 10, 5, 12, 6, 15], 'labels': [-100] * 7 + [6, 15]},
        {'input_ids': [14, 11, 7, 12, 8, 9, 15], 'labels': [-100] * 4 + [8, 9, 15]}]


def worker(folder: Path, rank: int, port: int):
    from datetime import timedelta
    import torch.distributed as dist
    from torch.distributed.fsdp import FullyShardedDataParallel as FSDP
    from torch.distributed.fsdp.wrap import ModuleWrapPolicy
    from torch.distributed.checkpoint.state_dict import StateDictOptions, get_state_dict
    torch.set_num_threads(1)
    os.environ.update(MASTER_ADDR='127.0.0.1', MASTER_PORT=str(port), RANK=str(rank), WORLD_SIZE='2', USE_LIBUV='0')
    dist.init_process_group('gloo', timeout=timedelta(seconds=90))
    group = dist.new_group([0, 1], backend='gloo', timeout=timedelta(seconds=90))
    try:
        torch.manual_seed(24)
        base = ml_tests.NvarcMLTests()._tiny_qwen()
        base.resize_token_embeddings(16)
        wrapped = FSDP(base, auto_wrap_policy=ModuleWrapPolicy({type(base.model.language_model.layers[0])}),
            process_group=group, device_id=torch.device('cpu'), use_orig_params=True, backward_prefetch=None)
        optimizer, scheduler = source_optimizer(wrapped, RECIPE)
        reports = []
        for step in range(2):
            # Unequal rank sample/supervision counts force a zero-loss collective slot.
            reports.append(train_source_step(wrapped, optimizer, scheduler, ROWS[rank::2],
                device=torch.device('cpu'), recipe=RECIPE, capacity=32, length_multiple=4))
            print('optimizer-step-complete',step+1,flush=True)
        import torch.distributed.checkpoint as dcp
        model, optim = get_state_dict(wrapped, optimizer,
            options=StateDictOptions(full_state_dict=False, cpu_offload=True))
        dcp.save({'model':model,'optimizer':optim},checkpoint_id=folder/'checkpoint')
        if rank == 0:
            (folder/'reports.json').write_text(json.dumps(reports))
        dist.barrier()
    finally:
        dist.destroy_process_group(group)
        dist.destroy_process_group()


class SFTStepStrictTests(unittest.TestCase):
    def test_accumulated_shards_and_adam_moments_match_unpacked_global_token_mean(self):
        threads = torch.get_num_threads()
        torch.set_num_threads(1)
        try:
            torch.manual_seed(24)
            oracle = ml_tests.NvarcMLTests()._tiny_qwen()
            oracle.resize_token_embeddings(16)
            optimizer, scheduler = source_optimizer(oracle, RECIPE)
            for step in range(2):
                optimizer.zero_grad(set_to_none=True)
                count = sum(sum(y >= 0 for y in row['labels'][1:]) for row in ROWS)
                # Reverse placement order to make the reference independent of MFFD.
                for row in reversed(ROWS):
                    ids, labels = torch.tensor([row['input_ids']]),torch.tensor([row['labels']])
                    logits=oracle(input_ids=ids,use_cache=False).logits
                    loss=torch.nn.functional.cross_entropy(logits[:,:-1].float().reshape(-1,16),
                        labels[:,1:].reshape(-1),ignore_index=-100,reduction='sum')/count
                    loss.backward()
                torch.nn.utils.clip_grad_norm_(oracle.parameters(),RECIPE['clip_grad_norm'])
                optimizer.step();scheduler.step()
            retained = os.environ.get('NVARC_SFT_TEST_OUTPUT')
            if retained:
                Path(retained).mkdir(parents=True, exist_ok=True)
            with (contextlib.nullcontext(retained) if retained else tempfile.TemporaryDirectory()) as directory:
                folder=Path(directory)
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'OMP_NUM_THREADS':'1','PYTHONIOENCODING':'utf-8'}
                processes=[];streams=[]
                try:
                    for rank in range(2):
                        log=(folder/f'rank-{rank}.log').open('w',encoding='utf-8');streams.append(log)
                        command=[sys.executable,'-m','tests.nvarc_sft_step_strict','--worker',str(folder),str(rank),str(port)]
                        processes.append(subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT))
                    deadline=time.monotonic()+150
                    while any(p.poll() is None for p in processes):
                        if time.monotonic()>deadline or any(p.poll() not in {None,0} for p in processes):
                            self.fail('Worker exit codes: '+str([p.poll() for p in processes])+'\n'+
                                '\n'.join(p.read_text(errors='replace')[-9000:] for p in folder.glob('*.log')))
                        time.sleep(.2)
                    self.assertEqual([0,0],[p.returncode for p in processes],
                        '\n'.join(p.read_text(errors='replace')[-9000:] for p in folder.glob('*.log')))
                finally:
                    for p in processes:
                        if p.poll() is None:
                            if os.name == 'nt':
                                subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=10)
                            else:
                                p.kill()
                            p.wait(timeout=10)
                    for s in streams:s.close()
                from torch.distributed.checkpoint.format_utils import dcp_to_torch_save
                dcp_to_torch_save(folder/'checkpoint',folder/'distributed.pt')
                result=torch.load(folder/'distributed.pt',weights_only=True)
                result['reports']=json.loads((folder/'reports.json').read_text())
                for name,value in oracle.state_dict().items():
                    torch.testing.assert_close(value,result['model'][name],rtol=1e-5,atol=1e-7)
                from torch.distributed.checkpoint.state_dict import get_optimizer_state_dict
                expected=get_optimizer_state_dict(oracle,optimizer)
                for name,state in expected['state'].items():
                    for key,value in state.items():
                        torch.testing.assert_close(value,result['optimizer']['state'][name][key],rtol=2e-5,atol=1e-7)
                for index,report in enumerate(result['reports']):
                    self.assertEqual((3,22,7),(report['global_sequence_count'],report['global_input_tokens'],report['global_supervised_tokens']))
                    self.assertEqual((2,0,2),(report['real_forward_calls'],report['dummy_forward_calls'],report['collective_slots']))
                    self.assertEqual((1e-6,1.495e-6)[index],report['learning_rate'])
                    self.assertGreater(report['cpu_accumulation_bytes'],0)
        finally:
            torch.set_num_threads(threads)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':
        worker(Path(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]))
    else:
        unittest.main()
