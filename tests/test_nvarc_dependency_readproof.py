"""Independent tiny opaque fixtures only; never imports dependency/model code."""
from tests.platform_requirements import requires_linux
import copy
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import nvarc_dependency_readproof as gate
from tools import stage_nvarc_e10_probe as stage
from tools.nvarc_native_multitask import canonical, digest, write
from tools.nvarc_runtime_archive import validate_members
from tests.test_nvarc_e10_probe import probe_fixture


def tiny_proof(directory):
    rows = {}
    for index, name in enumerate(sorted(gate.SELECTED_PATHS)):
        # Looks executable but is only read by the test's gate.
        body = ('raise RuntimeError("dependency byte execution forbidden '+str(index)+'")\n').encode()
        path = Path(directory)/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        rows[name] = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
    return {'format': gate.FORMAT, 'dependency_ref': gate.DEPENDENCY_REF, 'version_number': 2,
        'script_version_id': 272622465, 'selected_files': rows,
        'evidence_sha256': {key: str(i)*64 for i,key in enumerate(
            ('minimal_manifest','native_manifest','installer_source','installer_log'))},
        'read_limits': {'maximum_wall_seconds': 30, 'maximum_total_read_bytes': sum(v['bytes'] for v in rows.values())+5,
            'maximum_chunk_bytes': 7, 'minimum_free_working_bytes': 1}, 'limitations': dict(gate.LIMITATIONS)}


class ReadProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)/'root'; self.root.mkdir()
        self.dependency = Path(self.tmp.name)/'dependency'; self.dependency.mkdir()
        self.proof = tiny_proof(self.dependency); self.receipt = self.root/gate.RECEIPT_FILE
    def tearDown(self): self.tmp.cleanup()
    def verify(self, **kwargs):
        self.receipt.unlink(missing_ok=True)
        return gate.verify_selected(self.dependency, self.proof, receipt_path=self.receipt,
            plan_digest='sha256:'+'4'*64, deadline=kwargs.pop('deadline',time.monotonic()+30),
            working_root=self.root, **kwargs)
    @requires_linux('Selected-byte readproof uses POSIX descriptor identity, disk accounting and resource-bound native runtime')
    def test_streaming_exact_five_files_and_no_discovery(self):
        original = os.read; sizes = []
        def read(fd,size): sizes.append(size); return original(fd,size)
        with patch.object(gate.os,'read',side_effect=read), \
             patch.object(Path,'rglob',side_effect=AssertionError('discovery forbidden')):
            value = self.verify()
        self.assertEqual(value['outcome'],'verified-selected-bytes')
        self.assertEqual(value['selected_files'],self.proof['selected_files']); self.assertLessEqual(max(sizes),7)
        self.assertEqual(value['file_bytes_read'],sum(v['bytes'] for v in self.proof['selected_files'].values()))
        self.assertEqual(value['limitations'],gate.LIMITATIONS); self.assertEqual(value['discovered_code_executions'],0)
    @requires_linux('Selected-byte readproof uses POSIX descriptor identity, disk accounting and resource-bound native runtime')
    def test_mismatch_or_missing_retains_failed_receipt(self):
        path = self.dependency/'qwen3.patch'; body = path.read_bytes()
        for mutation in (body[:-1],b'x'+body[1:],None):
            if mutation is None:path.unlink()
            else:path.write_bytes(mutation)
            with self.assertRaises((RuntimeError,FileNotFoundError)):self.verify()
            value = json.loads(self.receipt.read_bytes()); self.assertEqual(value['outcome'],'failed')
            self.assertIsNotNone(value['error']); path.write_bytes(body)
    @requires_linux('Selected-byte readproof uses POSIX descriptor identity, disk accounting and resource-bound native runtime')
    def test_symlink_parent_file_root_hardlink_and_fifo_rejected(self):
        path = self.dependency/'qwen3.patch'; body = path.read_bytes()
        target = Path(self.tmp.name)/'opaque'; target.write_bytes(body)
        path.unlink(); path.symlink_to(target)
        with self.assertRaises(OSError):self.verify()
        path.unlink(); os.link(target,path)
        with self.assertRaisesRegex(RuntimeError,'single-linked'):self.verify()
        path.unlink(); os.mkfifo(path)
        with self.assertRaisesRegex(RuntimeError,'regular'):self.verify()
        path.unlink(); path.write_bytes(body)
        parent = self.dependency/'unsloth/models'; parent.rename(self.dependency/'opaque-models')
        parent.symlink_to(self.dependency/'opaque-models',target_is_directory=True)
        with self.assertRaises(OSError):self.verify()
        parent.unlink(); (self.dependency/'opaque-models').rename(parent)
        linked = Path(self.tmp.name)/'linked'; linked.symlink_to(self.dependency,target_is_directory=True)
        self.receipt.unlink()
        with self.assertRaises(OSError):gate.verify_selected(linked,self.proof,receipt_path=self.receipt,
            plan_digest='sha256:'+'4'*64,deadline=time.monotonic()+30,working_root=self.root)
        self.assertEqual(json.loads(self.receipt.read_bytes())['outcome'],'failed')
    @requires_linux('Selected-byte readproof uses POSIX descriptor identity, disk accounting and resource-bound native runtime')
    def test_deadline_disk_and_invalid_caps_retain_failure(self):
        for deadline in (0,float('nan'),float('inf'),time.monotonic()-1):
            with self.assertRaisesRegex(RuntimeError,'deadline'):self.verify(deadline=deadline)
            self.assertEqual(json.loads(self.receipt.read_bytes())['outcome'],'failed')
        with self.assertRaisesRegex(RuntimeError,'disk'):self.verify(disk_free=lambda _:0)
        for field,bad in [('maximum_wall_seconds',float('nan')),('maximum_wall_seconds',float('inf')),
            ('maximum_wall_seconds',0),('maximum_chunk_bytes',0),('maximum_total_read_bytes',1),
            ('minimum_free_working_bytes',False)]:
            original = self.proof['read_limits'][field]; self.proof['read_limits'][field]=bad
            with self.assertRaisesRegex(RuntimeError,'caps'):self.verify()
            self.assertEqual(json.loads(self.receipt.read_bytes())['outcome'],'failed')
            self.proof['read_limits'][field]=original
    @requires_linux('Selected-byte readproof uses POSIX descriptor identity, disk accounting and resource-bound native runtime')
    def test_deadline_during_chunk_read_and_changed_file_rejected(self):
        original = os.read; clock = [100.]
        def read(fd,size):
            result = original(fd,size); clock[0] += 2; return result
        with patch.object(gate.os,'read',side_effect=read),self.assertRaisesRegex(RuntimeError,'deadline'):
            self.verify(deadline=101.,now=lambda:clock[0])
        self.assertEqual(json.loads(self.receipt.read_bytes())['outcome'],'failed')
        changed = [False]
        def mutate(fd,size):
            result = original(fd,size)
            if not changed[0]:
                os.utime(self.dependency/sorted(gate.SELECTED_PATHS)[0],ns=(1,1)); changed[0]=True
            return result
        with patch.object(gate.os,'read',side_effect=mutate),self.assertRaisesRegex(RuntimeError,'changed'):
            self.verify()
    @requires_linux('Selected-byte readproof uses POSIX descriptor identity, disk accounting and resource-bound native runtime')
    def test_expired_post_read_deadline_counts_returned_chunk_bytes(self):
        original=os.read;clock=[100.];self.proof['read_limits']['maximum_chunk_bytes']=11
        def read(fd,size):
            body=original(fd,size);self.assertEqual(len(body),11);clock[0]=102.;return body
        with patch.object(gate.os,'read',side_effect=read),self.assertRaisesRegex(RuntimeError,'deadline'):
            self.verify(deadline=101.,now=lambda:clock[0])
        receipt=json.loads(self.receipt.read_bytes())
        self.assertEqual(receipt['outcome'],'failed');self.assertEqual(receipt['selected_files'],{})
        self.assertEqual(receipt['file_bytes_read'],11);self.assertEqual(receipt['read_bytes_including_eof_checks'],11)
    @requires_linux('Selected-byte readproof uses POSIX descriptor identity, disk accounting and resource-bound native runtime')
    def test_expired_post_eof_read_deadline_counts_returned_extra_byte(self):
        original=os.read;clock=[100.];name=sorted(gate.SELECTED_PATHS)[0]
        expected=self.proof['selected_files'][name]['bytes'];path=self.dependency/name
        def read(fd,size):
            if size==1 and os.lseek(fd,0,os.SEEK_CUR)==expected:
                with path.open('ab') as stream:stream.write(b'X')
                extra=original(fd,size);self.assertEqual(extra,b'X');clock[0]=102.;return extra
            return original(fd,size)
        with patch.object(gate.os,'read',side_effect=read),self.assertRaisesRegex(RuntimeError,'deadline'):
            self.verify(deadline=101.,now=lambda:clock[0])
        receipt=json.loads(self.receipt.read_bytes())
        self.assertEqual(receipt['outcome'],'failed');self.assertEqual(receipt['selected_files'],{})
        self.assertEqual(receipt['file_bytes_read'],expected)
        self.assertEqual(receipt['read_bytes_including_eof_checks'],expected+1)
    def test_exact_closed_paths_and_inventory_preservation(self):
        inventory = {'qwen3.patch':dict(self.proof['selected_files']['qwen3.patch']),'unselected':{'opaque':'untouched'}}
        before = copy.deepcopy(inventory); gate.bind_contract(self.proof,inventory); self.assertEqual(inventory,before)
        inventory['qwen3.patch']['sha256']='f'*64
        with self.assertRaisesRegex(RuntimeError,'contradicts'):gate.bind_contract(self.proof,inventory)
        for path in ('../qwen3.patch','/qwen3.patch','unselected'):
            bad = copy.deepcopy(self.proof); bad['selected_files'][path]=bad['selected_files'].pop('qwen3.patch')
            with self.assertRaisesRegex(RuntimeError,'five selected'):gate.validate_contract(bad)
    @requires_linux('Selected-byte readproof uses POSIX descriptor identity, disk accounting and resource-bound native runtime')
    def test_failed_receipt_cannot_be_overwritten_by_retry(self):
        path=self.dependency/'qwen3.patch'; body=path.read_bytes(); path.write_bytes(b'x'*len(body))
        with self.assertRaises(RuntimeError):self.verify()
        retained=self.receipt.read_bytes(); path.write_bytes(body)
        with self.assertRaisesRegex(RuntimeError,'new immutable'):gate.verify_selected(self.dependency,self.proof,
            receipt_path=self.receipt,plan_digest='sha256:'+'4'*64,deadline=time.monotonic()+30,working_root=self.root)
        self.assertEqual(self.receipt.read_bytes(),retained)
    def plan(self):
        plan, raw = probe_fixture(); plan['dependency_readproof_digest']=digest(self.proof)
        raw[gate.PROOF_FILE]=canonical(self.proof)
        plan['payload_sha256'][gate.PROOF_FILE]=hashlib.sha256(raw[gate.PROOF_FILE]).hexdigest()
        raw['plan.json']=raw['screen.json']=canonical(plan)
        for name,body in raw.items():
            path=self.root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(body)
        return plan
    @requires_linux('Selected-byte readproof uses POSIX descriptor identity, disk accounting and resource-bound native runtime')
    def test_real_gate_prevents_prepare_and_retains_archivable_failure(self):
        from tools import nvarc_e10_probe as probe
        plan = self.plan(); path = self.dependency/'qwen3.patch'; path.write_bytes(b'x'*path.stat().st_size)
        with patch.object(stage,'verify_runtime',return_value=plan),patch.object(probe,'prepare') as prepare, \
             patch.object(probe,'verify_mount') as mount,patch.object(probe.subprocess,'Popen') as launch, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.execute(self.root,self.dependency,time.monotonic()),1)
        prepare.assert_not_called(); mount.assert_not_called(); launch.assert_not_called()
        self.assertEqual(json.loads(self.receipt.read_bytes())['outcome'],'failed')
        names={path.relative_to(self.root).as_posix() for path in validate_members(self.root)}
        self.assertIn(gate.PROOF_FILE,names); self.assertIn(gate.RECEIPT_FILE,names)
        self.assertNotIn('flash_attn_2_cuda.cpython-311-x86_64-linux-gnu.so',names)
    @requires_linux('Selected-byte readproof uses POSIX descriptor identity, disk accounting and resource-bound native runtime')
    def test_gate_success_reaches_only_injected_preparation_sentinel(self):
        from tools import nvarc_e10_probe as probe
        plan = self.plan()
        with patch.object(stage,'verify_runtime',return_value=plan), \
             patch.object(probe,'verify_mount',return_value={'competition_files_opened':0}), \
             patch.object(probe,'prepare',side_effect=RuntimeError('independent-preparation-sentinel')) as prepare, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.execute(self.root,self.dependency,time.monotonic()),1)
        prepare.assert_called_once(); self.assertEqual(json.loads(self.receipt.read_bytes())['outcome'],'verified-selected-bytes')
        self.assertIn('independent-preparation-sentinel',json.loads((self.root/'terminal.json').read_bytes())['errors'][0]['message'])
    @requires_linux('Selected-byte readproof uses POSIX descriptor identity, disk accounting and resource-bound native runtime')
    def test_worker_requires_hash_bound_gate_receipt_before_engine(self):
        from tools import nvarc_e10_probe as probe
        plan = self.plan(); value = gate.verify_before_prepare(self.root,plan,self.dependency,time.monotonic())
        pin = hashlib.sha256(self.receipt.read_bytes()).hexdigest()
        self.assertEqual(gate.require_worker_receipt(self.root,plan,self.dependency,pin),value)
        write(self.receipt,{**value,'outcome':'failed'})
        with self.assertRaisesRegex(RuntimeError,'verification'):gate.require_worker_receipt(self.root,plan,self.dependency,pin)
        (self.root/'workers/0').mkdir(parents=True)
        with patch.object(probe,'NativeEngine') as engine,patch.object(probe,'install_owner_guard'):
            self.assertEqual(probe.worker(self.root,self.dependency,Path('never-read-model'),0,time.time()+30,os.getpid(),pin),1)
        engine.assert_not_called()
        result=json.loads((self.root/'workers/0/result.json').read_bytes())
        self.assertEqual(result['accounting']['reserved_forwards'],0)
    def test_admitted_nonfixture_probe_cannot_omit_proof(self):
        plan,raw=probe_fixture(); config={key:plan[key] for key in __import__(
            'tools.stage_nvarc_e10_screen',fromlist=['CONFIG_FIELDS']).CONFIG_FIELDS}
        external={'source-inventory.json':b'{}'}
        with patch.object(stage,'validate_baseline'),patch.object(stage,'native_notice_closure',return_value=True), \
             self.assertRaisesRegex(RuntimeError,'separately supplied'):
            stage.construct('stage4-e10-probe-no-proof','0'*40,external,config,
                {'source_provenance':'synthetic'},resource_admission={'not':'admitted'})
    def test_additive_proof_source_closure_and_versioned_metadata(self):
        plan,raw=probe_fixture()
        from tools.stage_nvarc_e10_screen import CONFIG_FIELDS,EXTERNAL_FILES
        config={key:plan[key] for key in CONFIG_FIELDS}
        config.update(native_source_learning_rates=plan['native_source_learning_rates'],dependency_script_version_id=272622465)
        external={name:raw[name] for name in EXTERNAL_FILES};external['verified-tokenizer.json']=b'{}'
        original=external['source-inventory.json']
        plan,payload=stage.construct('stage4-e10-probe-tiny-readproof','0'*40,external,config,
            json.loads(raw['material-contract.json']),fixture=True,dependency_readproof=self.proof)
        self.assertEqual(payload['source-inventory.json'],original)
        self.assertEqual(plan['dependency_readproof_digest'],digest(self.proof))
        self.assertIn('tools/nvarc_dependency_readproof.py',plan['payload_sha256'])
        self.assertIn(gate.PROOF_FILE,plan['payload_sha256']);self.assertFalse(set(gate.SELECTED_PATHS)&set(payload))
        package=Path(self.tmp.name)/'fixture-package';stage.stage(package,plan,payload)
        metadata=json.loads((package/'kernel/kernel-metadata.json').read_bytes())
        self.assertEqual(metadata['kernel_sources'],[gate.VERSIONED_REF])
        self.assertFalse(stage.preflight(package)['approved_for_runtime'])


if __name__=='__main__':unittest.main()
