"""Public-byte deployment regression; no authentic candidate or launch receipt."""
import ast
import copy
import hashlib
import json
import io
import zipfile
from pathlib import Path
import unittest
from unittest.mock import patch
from tools.arc_qwen_rlvr004_20261013.admission_run008 import assemble as a


def consumed_runtime():
    # Public source-only reconstruction. This is not a private material candidate.
    builder = a.s.dependency(a.TOOL / 'prepare_successor_release.py', a.s.ASSEMBLER_SHA,
                             'test_public_runtime_archive')
    source = a.p.frozen_runtime(a.p.Snapshot(a.TOOL.parents[1]), builder)
    for name in ('environment_v2', 'parent_scoring', 'runner', 'worker'):
        source['owned_runtime/' + name + '.py'] = (a.TOOL / 'loader_repair_run008/overlays/owned_runtime' / (name + '.py')).read_bytes()
    source[a.p.INSTALLER_TARGET] = (a.TOOL / 'installer_logging_repair/bootstrap.py').read_bytes()
    environment = json.loads((a.TOOL / 'release/consumer-release/environment.json').read_bytes())
    for key in ('contract_path', 'environment_lock_path', 'tokenizer_path'):
        environment['model_config'][key] = a.SOURCE + '/runtime/' + environment['model_config'][key].split('/runtime/', 1)[1]
    environment = a.encoded(environment)
    source, _ = a.s.runtime_bytes(source, {}, environment)
    if a.sha(a.canonical(sorted((n, a.sha(b)) for n, b in source.items()))) != a.ORIGINAL_SOURCE_SHA:
        raise ValueError('exact public v41 source reconstruction')
    if a.sha(builder.zip_blobs(source, stored=True)) != a.ORIGINAL_ARCHIVE_SHA:
        raise ValueError('exact public v41 archive reconstruction')
    return source, environment


def consumed_deployment():
    files = {}
    old = a.TOOL / 'preparation_diagnostics_repair'
    for name in a.PREPARATION_ORIGINAL:
        raw = (old / name).read_bytes().replace(
            b'/tmp/irisx-qwen14b-rlvr-20261012-environment005', a.ENV.encode())
        if name == 'prepare_entry.py':
            raw = raw.replace(b'/kaggle/working/irisx-qwen14b-rlvr-20261012-run005', a.RUN.encode())
        else:
            raw = raw.replace(b'exact run005/source005 paths required',
                              b'exact fresh successor run/source paths required')
        if hashlib.sha256(raw).hexdigest() != a.PREPARATION_ORIGINAL[name]:
            raise ValueError('public consumed deployment bytes mismatch')
        files[name] = raw
    for name in ('source_loader.py', 'parent_entry.py', 'notebook_builder.py'):
        files[name] = (a.TOOL / 'support/deployment' / name).read_bytes()
    return files


class PreparationAssemblyTests(unittest.TestCase):
    def test_exact_consumed_two_callers_and_pinned_successors(self):
        original = consumed_deployment()
        repaired = a.repaired_preparation(original)
        self.assertEqual(set(repaired), set(original))
        self.assertEqual({name for name in original if original[name] != repaired[name]},
                         {'launch_notebook.py', 'prepare_entry.py'})
        self.assertEqual(a.repaired_preparation(original), repaired)
        self.assertEqual(original, consumed_deployment())
        for name, digest in a.PREPARATION_REPAIRS.items():
            self.assertEqual(a.sha((a.TOOL / 'preparation_environment_repair' / name).read_bytes()), digest)
            compile(repaired[name], name, 'exec')
            self.assertNotIn(b'20261012-environment005', repaired[name])
            self.assertIn(a.ENV.encode(), repaired[name])
        self.assertIn(a.RUN.encode(), repaired['prepare_entry.py'])

    def test_missing_or_tampered_consumed_caller_rejected(self):
        for name in a.PREPARATION_ORIGINAL:
            for missing in (False, True):
                with self.subTest(name=name, missing=missing):
                    files = consumed_deployment()
                    if missing: del files[name]
                    else: files[name] += b'\n# tamper\n'
                    with self.assertRaises(ValueError): a.repaired_preparation(files)

    def test_stale_successor_pin_rejected(self):
        for name in a.PREPARATION_REPAIRS:
            pins = dict(a.PREPARATION_REPAIRS); pins[name] = '0' * 64
            with self.subTest(name=name), patch.object(a, 'PREPARATION_REPAIRS', pins):
                with self.assertRaises(ValueError): a.repaired_preparation(consumed_deployment())

    def test_namespace_substitution_is_mandatory(self):
        original = a.pinned
        def wrong(path, digest):
            return original(path, digest).replace(b'20261012-environment005', b'20261012-environmentBAD')
        with patch.object(a, 'pinned', side_effect=wrong):
            with self.assertRaises(ValueError): a.repaired_preparation(consumed_deployment())

    def test_deployment_inventory_and_review_binding_follow_repaired_bytes(self):
        # The real assembler computes descriptors after replacement; assert the
        # order and exact inventory expression rather than fabricate its inputs.
        tree = ast.parse(Path(a.__file__).read_bytes())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'assemble')
        repair = [n for n in function.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                  and isinstance(n.value.func, ast.Name) and n.value.func.id == 'repaired_preparation']
        self.assertEqual(len(repair), 1)
        proposal = next(n for n in function.body if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'proposal' for t in n.targets))
        self.assertLess(repair[0].lineno, proposal.lineno)
        inventory = next(value for key, value in zip(proposal.value.keys, proposal.value.values)
                         if isinstance(key, ast.Constant) and key.value == 'deployment_inventory')
        expected = ast.parse('{n: desc(b) for n, b in sorted(deployment.items())}', mode='eval').body
        self.assertEqual(ast.dump(inventory), ast.dump(expected))
        self.assertIn('deployment_inventory', a.BINDING_KEYS)
        self.assertIn('assembler_source_sha256', a.BINDING_KEYS)
        self.assertIn('collector_sha256', a.BINDING_KEYS)

    def test_exact_runtime_successor_and_every_unchanged_body(self):
        old, environment = consumed_runtime()
        source, archive, normalized = a.repaired_runtime(old, environment)
        self.assertEqual(set(source), set(old))
        self.assertEqual({n for n in old if old[n] != source[n]},
                         {'owned_runtime/parent_scoring.py', 'owned_runtime/release.py'})
        self.assertEqual(sum(old[n] == source[n] for n in old), 257)
        self.assertTrue(all(old[n] == source[n] for n in old if n.startswith('baseline/')))
        self.assertEqual(a.sha(a.canonical(sorted((n, a.sha(b)) for n, b in source.items()))), a.SOURCE_SHA)
        self.assertEqual(a.sha(archive), a.ARCHIVE_SHA)
        self.assertNotEqual(a.SOURCE_SHA, a.ORIGINAL_SOURCE_SHA)
        self.assertNotEqual(a.ARCHIVE_SHA, a.ORIGINAL_ARCHIVE_SHA)
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.assertEqual(set(z.namelist()), set(source))
            self.assertTrue(all(z.read(n) == b for n, b in source.items()))
        self.assertIn(normalized.encode(), source['owned_runtime/release.py'])
        wire = ast.parse((a.TOOL / 'publication_windows_bridge_20261015/verify_active_wire.py').read_bytes())
        constants = {t.id: ast.literal_eval(n.value) for n in wire.body if isinstance(n, ast.Assign)
                     for t in n.targets if isinstance(t, ast.Name) and t.id in ('SOURCE', 'ARCHIVE')}
        self.assertEqual(constants, {'SOURCE': a.SOURCE_SHA, 'ARCHIVE': a.ARCHIVE_SHA})

    def test_runtime_changed_input_pin_and_environment_reject(self):
        old, environment = consumed_runtime()
        bad = dict(old); bad['owned_runtime/parent_scoring.py'] += b'\n'
        with self.assertRaises(ValueError): a.repaired_runtime(bad, environment)
        with patch.object(a, 'GUARDED_PARENT_SHA', '0' * 64):
            with self.assertRaises(ValueError): a.repaired_runtime(old, environment)
        with self.assertRaises(ValueError): a.repaired_runtime(old, environment + b' ')

    def test_release_and_consumer_use_successor_identities(self):
        function = next(n for n in ast.parse(Path(a.__file__).read_bytes()).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'assemble')
        for owner in ('release', 'operator'):
            update = next(n for n in ast.walk(function) if isinstance(n, ast.Call)
                          and isinstance(n.func, ast.Attribute) and n.func.attr == 'update'
                          and isinstance(n.func.value, ast.Name) and n.func.value.id == owner)
            keywords = {n.arg: ast.dump(n.value) for n in update.keywords}
            for key, name in (('source_sha256', 'SOURCE_SHA'), ('source_archive_sha256', 'ARCHIVE_SHA')):
                self.assertEqual(keywords[key], ast.dump(ast.Name(id=name, ctx=ast.Load())))
        text = ast.get_source_segment(Path(a.__file__).read_text(), function)
        self.assertIn("'source.zip': archive", text)
        self.assertNotIn("'source.zip': original['code-payload/source.zip']", text)

    def test_original_identities_and_existing_protocol_are_unchanged(self):
        self.assertEqual(a.ORIGINAL_SOURCE_SHA, 'c61025e67354272099e40941cadcd77202964846d9a4c42c51a1817f77bb661b')
        self.assertEqual(a.ORIGINAL_ARCHIVE_SHA, '4d8b414bd35ca79a2eaaec7042880966879ed13bdeaf96762eaee7932ee1de4c')
        self.assertEqual(a.PREPARE_SHA, '302c61282ce6abc19254cf22d2f16104f0cbd523af28b8431a52a70a683510c2')
        self.assertEqual(a.PROPOSAL_INVENTORY_SHA, 'fc32f98bef4188761fd51275bb05dd26c6fbd237afb8b8403b492f61442055cd')


if __name__ == '__main__': unittest.main()
