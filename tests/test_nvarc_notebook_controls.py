"""Offline standalone archive/CLI controls; no native imports or provider actions."""
import ast
import builtins
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import struct
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch
import zipfile
import zlib

from tools.nvarc_native_multitask import canonical
from tools import nvarc_notebook_controls as controls
from tools import stage_nvarc_stage4_candidate as candidate
from tools import stage_nvarc_e10_probe as probe
from tools import stage_nvarc_e10_screen as screen
from tests.test_nvarc_e10_screen import fixture
from tests.test_nvarc_e10_probe import probe_fixture


class DownloadCellTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.root=Path(self.directory.name)
        self.plan={'screen_id':'stage4-e10-probe-download-fixture','maximum_archive_uncompressed_bytes':4096,
            'approved_for_runtime':False,'promotion':False}
        self.path=self.root/(self.plan['screen_id']+'.zip')
        self.links=[];self.imports=[]
    def tearDown(self):self.directory.cleanup()
    def archive(self,*,plan=None,extra=None,path=None):
        with zipfile.ZipFile(path or self.path,'w',compression=zipfile.ZIP_STORED) as out:
            out.writestr('screen.json',canonical(self.plan if plan is None else plan))
            out.writestr('terminal.json',canonical({'outcome':'failed','promotion':False,'errors':['fixture']}))
            for name,body in extra or []:out.writestr(name,body)
    def execute(self,*,path=None,plan=None):
        cell=controls.render_download_cell(self.plan if plan is None else plan)
        source=''.join(cell['source']).replace("Path('/kaggle/working')/(DOWNLOAD_RUN_ID+'.zip')",repr(str(path or self.path)))
        source=source.replace('DOWNLOAD_PATH='+repr(str(path or self.path)), 'DOWNLOAD_PATH=Path('+repr(str(path or self.path))+')')
        ui=ModuleType('IPython.display');ui.FileLink=lambda value:value;ui.display=self.links.append
        def guarded(name,*args,**kwargs):
            self.imports.append(name)
            if name not in {'hashlib','json','os','stat','struct','zipfile','pathlib','IPython.display'}:
                raise AssertionError('unexpected cell import: '+name)
            return builtins.__import__(name,*args,**kwargs)
        namespace={'__builtins__':dict(vars(builtins),__import__=guarded)}
        with patch.dict(sys.modules,{'IPython':ModuleType('IPython'),'IPython.display':ui}),contextlib.redirect_stdout(io.StringIO()):
            exec(compile(source,'independent-download-cell','exec'),namespace)
        return namespace
    def test_failed_run_download_is_independent_readonly_and_stdlib_until_ui(self):
        self.archive();before=self.path.read_bytes();found=self.execute()
        self.assertEqual(self.links,[str(self.path)]);self.assertEqual(before,self.path.read_bytes())
        self.assertNotIn('screen',found);self.assertNotIn('work',found);self.assertNotIn('PACKED',found)
        self.assertEqual(self.imports[-1],'IPython.display')
    def test_missing_temp_truncated_corrupt_crc_and_wrong_identity_refuse_before_ui(self):
        for kind in ('missing','temp','truncated','crc','wrong-run','wrong-plan','trailing'):
            with self.subTest(kind=kind):
                if self.path.exists():self.path.unlink()
                if kind!='missing':self.archive()
                target=self.path
                if kind=='temp':target=self.path.with_suffix('.zip.tmp');self.path.rename(target)
                if kind=='truncated':self.path.write_bytes(self.path.read_bytes()[:-3])
                if kind=='crc':
                    raw=self.path.read_bytes();self.path.write_bytes(raw.replace(b'fixture',b'fixturE',1))
                if kind in ('wrong-run','wrong-plan'):
                    changed={**self.plan,('screen_id' if kind=='wrong-run' else 'promotion'):('stage4-e10-probe-other' if kind=='wrong-run' else True)}
                    self.archive(plan=changed)
                if kind=='trailing':self.path.write_bytes(self.path.read_bytes()+b'tail')
                with self.assertRaises((OSError,RuntimeError,zipfile.BadZipFile,struct.error)):self.execute(path=target)
                self.assertFalse(self.links);self.assertNotIn('IPython.display',self.imports);self.imports=[]
    def test_unsafe_member_metadata_and_duplicate_identity_refuse(self):
        names=['../escape','/absolute','bad\\name','bad:name','folder//entry','folder/./entry','bad\x01name','screen.json']
        for name in names:
            with self.subTest(name=name):
                with contextlib.redirect_stderr(io.StringIO()):self.archive(extra=[(name,b'unsafe')])
                with self.assertRaises(RuntimeError):self.execute()
                self.assertFalse(self.links)
        for mode in (stat.S_IFLNK|0o777,stat.S_IFIFO|0o600,stat.S_IFDIR|0o700):
            info=zipfile.ZipInfo('unsafe');info.create_system=3;info.external_attr=mode<<16
            self.archive(extra=[(info,b'unsafe')])
            with self.assertRaises(RuntimeError):self.execute()
            self.assertFalse(self.links)
    def test_archive_symlink_parent_symlink_and_fifo_refuse_without_read_hang(self):
        self.archive();link=self.root/'other.zip';link.symlink_to(self.path)
        # Keep the expected final name while resolving through a symlink parent.
        parent=self.root/'alias';parent.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(RuntimeError):self.execute(path=parent/self.path.name)
        original=self.root/'original.zip';self.path.rename(original);self.path.symlink_to(original)
        with self.assertRaises(OSError):self.execute()
        self.path.unlink();os.mkfifo(self.path)
        with self.assertRaises(RuntimeError):self.execute()
        self.assertFalse(self.links)
    def test_member_and_central_directory_bounds_refuse_before_ui(self):
        self.archive(extra=[('large',b'x'*4096)])
        with self.assertRaisesRegex(RuntimeError,'uncompressed'):self.execute()
        self.archive();body=bytearray(self.path.read_bytes());struct.pack_into('<L',body,len(body)-10,17*1024**2);self.path.write_bytes(body)
        with self.assertRaisesRegex(RuntimeError,'directory'):self.execute()
        self.assertFalse(self.links)
    def test_zip64_end_records_are_supported_without_large_fixture(self):
        self.archive();body=self.path.read_bytes();end=struct.unpack('<4s4H2LH',body[-22:]);offset=len(body)-22
        large=struct.pack('<4sQ2H2L4Q',b'PK\x06\x06',44,45,45,0,0,end[4],end[4],end[5],end[6])
        locator=struct.pack('<4sLQL',b'PK\x06\x07',0,offset,1)
        final=struct.pack('<4s4H2LH',b'PK\x05\x06',0,0,65535,65535,0xffffffff,0xffffffff,0)
        for closed_end in (final,body[-22:]):
            self.path.write_bytes(body[:-22]+large+locator+closed_end);self.execute()
        self.assertEqual(len(self.links),2)
    def test_output_complete_deflate_without_compressed_eof_is_refused(self):
        self.archive()
        with zipfile.ZipFile(self.path,'a',compression=zipfile.ZIP_DEFLATED) as archive:archive.writestr('diagnostic',b'abc')
        body=bytearray(self.path.read_bytes())
        with zipfile.ZipFile(self.path) as archive:info=archive.getinfo('diagnostic')
        start=info.header_offset;name_len,extra_len=struct.unpack_from('<2H',body,start+26)
        data_start=start+30+name_len+extra_len;end=data_start+info.compress_size
        damaged=bytes(body[data_start:end-1]);decoder=zlib.decompressobj(-15)
        self.assertEqual(decoder.decompress(damaged),b'abc');self.assertFalse(decoder.eof)
        del body[end-1];struct.pack_into('<L',body,start+18,info.compress_size-1)
        central=bytes(body).index(b'PK\x01\x02')
        while True:
            name_len,extra_len,comment_len=struct.unpack_from('<3H',body,central+28)
            if body[central+46:central+46+name_len]==b'diagnostic':
                struct.pack_into('<L',body,central+20,info.compress_size-1);break
            central+=46+name_len+extra_len+comment_len
        old_offset=struct.unpack_from('<L',body,len(body)-6)[0];struct.pack_into('<L',body,len(body)-6,old_offset-1)
        self.path.write_bytes(body)
        with zipfile.ZipFile(self.path) as archive:self.assertEqual(archive.read('diagnostic'),b'abc')
        with self.assertRaisesRegex(RuntimeError,'compressed'):self.execute()
        self.assertFalse(self.links)
    def test_stored_member_with_unread_trailing_byte_is_refused(self):
        self.archive(extra=[('diagnostic',b'abc')]);body=bytearray(self.path.read_bytes())
        with zipfile.ZipFile(self.path) as archive:info=archive.getinfo('diagnostic')
        start=info.header_offset;name_len,extra_len=struct.unpack_from('<2H',body,start+26)
        end=start+30+name_len+extra_len+info.compress_size
        body[end:end]=b'x';struct.pack_into('<L',body,start+18,info.compress_size+1)
        central=bytes(body).index(b'PK\x01\x02')
        while True:
            name_len,extra_len,comment_len=struct.unpack_from('<3H',body,central+28)
            if body[central+46:central+46+name_len]==b'diagnostic':
                struct.pack_into('<L',body,central+20,info.compress_size+1);break
            central+=46+name_len+extra_len+comment_len
        old_offset=struct.unpack_from('<L',body,len(body)-6)[0];struct.pack_into('<L',body,len(body)-6,old_offset+1)
        self.path.write_bytes(body)
        with zipfile.ZipFile(self.path) as archive:self.assertEqual(archive.read('diagnostic'),b'abc')
        with self.assertRaisesRegex(RuntimeError,'regular archive members'):self.execute()
        self.assertFalse(self.links)
    def test_cell_has_no_scientific_or_mutating_capabilities(self):
        source=''.join(controls.render_download_cell(self.plan)['source']);tree=ast.parse(source)
        imports={node.module if isinstance(node,ast.ImportFrom) else alias.name
            for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom))
            for alias in (node.names if isinstance(node,ast.Import) else [None])}
        self.assertEqual(imports,{'hashlib','json','os','stat','struct','zipfile','pathlib','IPython.display'})
        for token in ('rglob','walk(','extract','mkdir','write_bytes','subprocess','PACKED','supervise','torch','recover'):
            self.assertNotIn(token,ast.unparse(tree))


class ArrangementReconstructionTests(unittest.TestCase):
    def test_exact_caps_are_inert_seconds_and_machine_shape_is_unchanged(self):
        for seconds in (1800,10800,18000,42600):
            fields=controls.provider_cap_fields({'maximum_notebook_wall_seconds':seconds})
            self.assertEqual(fields['kernel_push_argv'],['kaggle','kernels','push','-p','kernel','-t',str(seconds)])
            self.assertEqual(fields['provider_session_timeout_seconds'],seconds)
            self.assertEqual(fields['provider_timeout_unit'],'seconds');self.assertFalse(fields['provider_timeout_enforcement_observed'])
            self.assertNotIn('--accelerator',fields['kernel_push_argv'])
        for value in (True,0,-1,1.5,'1800'):
            with self.assertRaises(RuntimeError):controls.provider_cap_fields({'maximum_notebook_wall_seconds':value})
    def test_probe_screen_cells_and_new_handoffs_reconstruct_exactly(self):
        p,raw=probe_fixture();s,plans,payload=fixture()
        for builder,plan,data,subplans in ((probe,p,raw,None),(screen,s,payload,plans)):
            with self.subTest(builder=builder.__name__),tempfile.TemporaryDirectory() as temp:
                package=Path(temp)/'package'
                if subplans is None:builder.stage(package,plan,data)
                else:builder.stage(package,plan,subplans,data)
                notebook=json.loads((package/'kernel/notebook.ipynb').read_bytes())
                self.assertEqual(len(notebook['cells']),4);self.assertEqual(notebook['cells'][3],controls.render_download_cell(plan))
                handoff=json.loads((package/'cli-handoff.json').read_bytes());self.assertFalse(handoff['execute_commands'])
                self.assertEqual(handoff['kernel_push_argv'][-2:],['-t',str(plan['maximum_notebook_wall_seconds'])])
                # Rehashing a modified transport or download cell cannot bypass exact reconstruction.
                for target in ('cli-handoff.json','kernel/notebook.ipynb','extra-file'):
                    path=package/target;old=path.read_bytes() if path.exists() else None
                    if target=='cli-handoff.json':changed=json.loads(old);changed['kernel_push_argv'][-1]='99';path.write_bytes(canonical(changed))
                    elif target=='kernel/notebook.ipynb':changed=json.loads(old);changed['cells'][3]['source'].append('print("tamper")\n');path.write_bytes(canonical(changed))
                    else:path.write_bytes(b'extra')
                    manifest_path=package/'package-manifest.json';original=manifest_path.read_bytes();manifest=json.loads(original)
                    manifest['files_sha256']={f.relative_to(package).as_posix():builder.sha(f) for f in package.rglob('*') if f.is_file() and f!=manifest_path}
                    manifest_path.write_bytes(canonical(manifest))
                    kwargs={} if subplans is None else {'allow_fixture':True}
                    with self.assertRaisesRegex(RuntimeError,'differs'):builder.preflight(package,**kwargs)
                    if old is None:path.unlink()
                    else:path.write_bytes(old)
                    manifest_path.write_bytes(original)
    def test_candidate_keeps_no_zip_producer_and_shared_import_closure(self):
        self.assertIn('tools/nvarc_notebook_controls.py',screen.LOCAL_FILES)
        self.assertIn('tools/nvarc_notebook_controls.py',probe.FILES)
        self.assertIn('tools/nvarc_notebook_controls.py',candidate.LOCAL_FILES)
        notebook=candidate.render({'run_id':'stage4-full-input-download-note'}, {})
        self.assertEqual(len(notebook['cells']),2)
        self.assertIn('no finalized ZIP producer',''.join(notebook['cells'][0]['source']))
        self.assertNotIn('zipfile',''.join(notebook['cells'][1]['source']))
        # Fresh isolated import cannot borrow a missing shared helper from the checkout.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in candidate.LOCAL_FILES:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((candidate.ROOT/name).read_bytes())
            (root/'tools/__init__.py').write_bytes(b'')
            command=[sys.executable,'-I','-B','-c',
                'import runpy; value=runpy.run_path('+repr(str(root/'tools/stage_nvarc_stage4_candidate.py'))+',run_name="snapshot_import"); '
                'assert "tools/nvarc_notebook_controls.py" in value["LOCAL_FILES"]; '
                'assert value["cli_handoff"]({"run_id":"fixture","kernel_id":"owner/fixture","maximum_notebook_wall_seconds":42600})["kernel_push_argv"][-1]=="42600"']
            subprocess.run(command,cwd=root,capture_output=True,check=True,timeout=10)


if __name__=='__main__':unittest.main()
