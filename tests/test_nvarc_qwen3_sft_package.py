"""Offline storage accounting and rendered parent gate; fixtures only."""
import base64
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
import zlib

from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError
from tools.stage_nvarc_qwen3_sft import render,storage_bound


class OriginalSFTPackageTests(unittest.TestCase):
    def test_full_fp32_model_two_adam_moments_and_commit_overlap_are_counted(self):
        elements=3_640_000_000
        two=storage_bound(elements)
        self.assertEqual(elements*12,two['checkpoint_bytes_per_transaction'])
        self.assertEqual(elements*26+4*1024**3,two['minimum_free_working_bytes'])
        sustained=storage_bound(elements,12716)
        self.assertEqual(elements*38+4*1024**3,sustained['minimum_free_working_bytes'])
        for invalid in (True,0,-1,1.5):
            with self.assertRaises(ValidationError):storage_bound(invalid)

    def test_rendered_insufficient_retained_disk_stops_before_dependencies_or_model(self):
        run='nvarc-original-qwen3-sft-901'
        plan={'run_id':run,'format':'irisx/nvarc-original-qwen3-source-sft-v1','owner_decision':'Decision 0054',
            'approved':True,'maximum_optimizer_steps':2,'global_batch_size':256,'checkpoint_storage':'durable-retained',
            'maximum_paid_usd':0,'maximum_generations':0,'maximum_teacher_calls':0,
            'datasets':{'base':'fixture/base','wheels':'fixture/wheels'},'competition_sources':['arc-prize-2026-arc-agi-2'],
            'checkpoint_storage_bound':storage_bound(3_640_000_000),'minimum_host_available_bytes':64*1024**3}
        raw={'plan':canonical_bytes(plan),'samples':b'[]','runtime_wheel':b'fixture only','wheel_manifest':b'{}'}
        payloads={key:base64.b64encode(zlib.compress(value)).decode() for key,value in raw.items()}
        hashes={key:hashlib.sha256(value).hexdigest() for key,value in raw.items()}
        source=render(run,payloads,hashes)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for suffix in ('working','temp','input/datasets/fixture/base','input/datasets/fixture/wheels',
                    'input/competitions/arc-prize-2026-arc-agi-2'):
                (root/'kaggle'/suffix).mkdir(parents=True)
            (root/'kaggle/input/datasets/fixture/base/material-manifest.json').write_text('{}')
            (root/'kaggle/input/datasets/fixture/wheels/transformers-5.8.1-py3-none-any.whl').write_bytes(b'fixture')
            (root/'meminfo').write_text('MemAvailable: 83886080 kB\nMemTotal: 104857600 kB\n')
            def local_path(value):
                if str(value).startswith('/kaggle/'):return root/'kaggle'/str(value)[8:]
                if str(value)=='/proc/meminfo':return root/'meminfo'
                return Path(value)
            uuids=[f'00000000-0000-0000-0000-{i:012d}' for i in range(4)]
            fake=SimpleNamespace(__version__='fixture',version=SimpleNamespace(cuda='fixture'),
                cuda=SimpleNamespace(device_count=lambda:4,device=lambda index:nullcontext(),is_bf16_supported=lambda:True,
                    get_device_properties=lambda index:SimpleNamespace(uuid=uuids[index],name='NVIDIA L4',total_memory=24*1024**3)))
            smi='\n'.join(f'{i}, NVIDIA L4, 24000, GPU-{uuid}' for i,uuid in enumerate(uuids))
            with patch.dict(sys.modules,{'torch':fake}),patch('pathlib.Path',side_effect=local_path),patch(
                    'subprocess.run',return_value=SimpleNamespace(stdout=smi)) as process,patch(
                    'shutil.disk_usage',return_value=SimpleNamespace(free=20*1024**3)):
                with self.assertRaisesRegex(RuntimeError,'complete retained FP32 model/Adam'):
                    exec(compile(source,'artificial-original-sft-storage-gate','exec'),{})
                self.assertEqual(1,process.call_count)
                self.assertEqual('nvidia-smi',process.call_args.args[0][0])
            work=root/'kaggle/working'/run
            terminal=json.loads((work/'terminal.json').read_bytes())
            self.assertEqual('retained-storage-gate',terminal['phase'])
            self.assertEqual(0,terminal['generation_calls'])
            self.assertFalse((work/'worker').exists())
            with zipfile.ZipFile(work.parent/'gpu-preflight-result.zip') as archive:
                self.assertEqual([],json.loads(archive.read('checkpoint-inventory.json')))
                self.assertEqual('failed',json.loads(archive.read('terminal.json'))['outcome'])


if __name__=='__main__':unittest.main()
