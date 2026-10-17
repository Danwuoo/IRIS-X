"""Literal, non-executed cache fixtures for the probe-002 archive failure."""
from tests.platform_requirements import requires_linux
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import nvarc_runtime_archive as members
from tools.nvarc_e10_screen import archive
from tools.nvarc_native_multitask import write


class WorkerCacheArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.root=Path(self.temporary.name)/'runtime';self.root.mkdir()
        self.output=Path(self.temporary.name)/'result.zip'
        write(self.root/'screen.json',{'payload_sha256':{},'worker_ids':['0','1','2','3']})
        self.evidence={
            'terminal.json':b'{"outcome":"complete","correctness_scored":false}',
            'workers/0/ready.json':b'{"rank":0}',
            'workers/0/result.json':b'{"outcome":"complete"}',
            'workers/0/events.jsonl':b'{"event":"literal-cpu-fixture"}\n',
            'workers/0/stdout.log':b'literal retained stdout\n',
            'workers/0/stderr.log':b'literal retained stderr\n',
        }
        for name,body in self.evidence.items():self.put(name,body)

    def tearDown(self):self.temporary.cleanup()

    def put(self,name,body=b'raise AssertionError("cache fixture must never execute")\n'):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        return path

    def test_observed_cache_is_excluded_without_reading_and_all_evidence_is_retained(self):
        observed=self.put('workers/0/unsloth_compiled_cache/UnslothAlignPropTrainer.py')
        for rank in range(4):
            self.put(f'workers/{rank}/unsloth_compiled_cache/nested/__pycache__/generated.pyc')
        original=Path.read_bytes
        def read(path):
            if 'unsloth_compiled_cache' in path.parts:raise AssertionError('generated cache content read')
            return original(path)
        with patch.object(Path,'read_bytes',read):
            files=members.validate_members(self.root)
            self.assertNotIn(observed,files)
            archive(self.root,self.output,10000)
        with zipfile.ZipFile(self.output) as stream:
            self.assertEqual(set(stream.namelist()),{'screen.json',*self.evidence})
            for name,body in self.evidence.items():self.assertEqual(stream.read(name),body)

    def test_only_exact_declared_worker_cache_placement_is_excluded(self):
        for relative in ('workers/0/unknown.py',
                'workers/0/unsloth_compiled_cach/UnslothAlignPropTrainer.py',
                'workers/4/unsloth_compiled_cache/UnslothAlignPropTrainer.py',
                'workers/4/unsloth_compiled_cache/__pycache__/generated.pyc',
                'workers/00/unsloth_compiled_cache/UnslothAlignPropTrainer.py',
                'unsloth_compiled_cache/UnslothAlignPropTrainer.py',
                'unsloth_compiled_cache/triton-cache/generated.py',
                'workers/0/neighbor/unsloth_compiled_cache/UnslothAlignPropTrainer.py',
                'workers/0/__pycache__/unsloth_compiled_cache/generated.py',
                'workers/0/triton-cache/unsloth_compiled_cache/generated.py',
                'workers/0/unsloth_compiled_cache.py',
                'workers/0/unsloth_compiled_cache'):
            with self.subTest(relative=relative):
                path=self.put(relative)
                with self.assertRaisesRegex(RuntimeError,'unrecognized runtime archive member'):
                    members.validate_members(self.root)
                path.unlink()

    def test_symlinks_inside_excluded_cache_and_legacy_cache_are_never_pruned(self):
        outside=Path(self.temporary.name)/'outside';outside.mkdir()
        (outside/'foreign.py').write_text('literal outside content')
        for relative,target in (
                ('workers/0/unsloth_compiled_cache',outside),
                ('workers/0/unsloth_compiled_cache/nested/escape',outside),
                ('workers/0/unsloth_compiled_cache/nested/file.py',outside/'foreign.py'),
                ('workers/0/unsloth_compiled_cache/nested/broken.py',outside/'missing.py'),
                ('workers/0/triton-cache/nested/escape',outside),
                ('workers/0/__pycache__/nested/escape',outside)):
            with self.subTest(relative=relative):
                path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.symlink_to(target)
                with self.assertRaisesRegex(RuntimeError,'cannot follow symlinks'):
                    members.validate_members(self.root)
                path.unlink()

    def test_root_and_screen_symlinks_are_rejected_before_manifest_read(self):
        alias=Path(self.temporary.name)/'alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError,'cannot follow symlinks'):members.validate_members(alias)
        screen=self.root/'screen.json';body=screen.read_bytes();screen.unlink()
        external=Path(self.temporary.name)/'screen.json';external.write_bytes(body);screen.symlink_to(external)
        with self.assertRaisesRegex(RuntimeError,'cannot follow symlinks'):members.validate_members(self.root)

    @unittest.skipUnless(hasattr(os,'mkfifo'),'requires POSIX FIFO')
    def test_excluded_cache_fifo_fails_without_opening_it(self):
        path=self.root/'workers/0/unsloth_compiled_cache/pipe';path.parent.mkdir(parents=True)
        os.mkfifo(path)
        with self.assertRaisesRegex(RuntimeError,'regular files and directories'):members.validate_members(self.root)

    def test_cache_bytes_do_not_consume_archive_cap_but_retained_bytes_still_do(self):
        cap=sum(path.stat().st_size for path in members.validate_members(self.root))
        huge=self.put('workers/0/unsloth_compiled_cache/UnslothAlignPropTrainer.py',b'')
        with huge.open('wb') as stream:stream.truncate(1024**3)
        archive(self.root,self.output,cap)
        with zipfile.ZipFile(self.output) as stream:
            self.assertEqual(sum(info.file_size for info in stream.infolist()),cap)
        self.output.unlink()
        with self.assertRaisesRegex(RuntimeError,'declared byte cap'):archive(self.root,self.output,cap-1)
        self.assertFalse(self.output.exists())

    def test_cache_entries_and_depth_still_count_toward_bounded_walk(self):
        cache=self.root/'workers/0/unsloth_compiled_cache';cache.mkdir(parents=True)
        for index in range(20):self.put(f'workers/0/unsloth_compiled_cache/{index}.py')
        with patch.object(members,'MAX_TREE_ENTRIES',20),\
                self.assertRaisesRegex(RuntimeError,'tree entry cap'):members.validate_members(self.root)
        with patch.object(members,'MAX_TREE_DEPTH',3),\
                self.assertRaisesRegex(RuntimeError,'safe runtime archive path'):members.validate_members(self.root)
        with patch.object(members,'MAX_PATH_CHARACTERS',30),\
                self.assertRaisesRegex(RuntimeError,'safe runtime archive path'):members.validate_members(self.root)

    @requires_linux('POSIX filenames with backslash, colon and newline cannot be represented equivalently on Windows')
    def test_cache_paths_remain_safe(self):
        for name in ('bad\\name.py','bad:name.py','bad\nname.py'):
            with self.subTest(name=name):
                path=self.put('workers/0/unsloth_compiled_cache/'+name)
                with self.assertRaisesRegex(RuntimeError,'safe runtime archive path'):members.validate_members(self.root)
                path.unlink()

    def test_cache_cannot_hide_a_pinned_static_member_or_mutated_source(self):
        source=self.put('tools/literal.py',b'literal frozen source')
        screen=json.loads((self.root/'screen.json').read_bytes())
        screen['payload_sha256']={'tools/literal.py':hashlib.sha256(source.read_bytes()).hexdigest()}
        write(self.root/'screen.json',screen);members.validate_members(self.root)
        self.put('workers/0/unsloth_compiled_cache/UnslothAlignPropTrainer.py')
        source.write_bytes(b'mutated source')
        with self.assertRaisesRegex(RuntimeError,'source/input differs'):members.validate_members(self.root)
        source.write_bytes(b'literal frozen source')
        screen['payload_sha256']['workers/0/unsloth_compiled_cache/UnslothAlignPropTrainer.py']='0'*64
        write(self.root/'screen.json',screen)
        with self.assertRaisesRegex(RuntimeError,'cannot replace a static runtime payload'):
            members.validate_members(self.root)


if __name__=='__main__':unittest.main()
