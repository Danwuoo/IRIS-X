"""Source-only synthetic unit tests. No model or production execution evidence."""
from __future__ import annotations
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('assembly_under_test', HERE/'runtime_assembly.py')
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


class RuntimeAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-runtime-assembly-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root/'repository'
        self.repo.mkdir()
        self.output = self.root/'new-runtime'
        original = json.loads((HERE/'runtime-path-map.json').read_bytes())
        self.mapping = copy.deepcopy(original)
        self.raw = {}
        for name, row in self.mapping['files'].items():
            raw = ('Authored synthetic source-only fixture: '+name+'\n').encode()
            self.raw[name] = raw
            row.update(bytes=len(raw), sha256=a.sha(raw))
            path = self.repo/row['repository_path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o644)
        identity = {name: a.sha(raw) for name, raw in self.raw.items()}
        inner = {name: value for name, value in identity.items() if name not in a.INNER_EXCLUSIONS}
        self.freeze = {'format': 'irisx/qwen14b-portfolio-source-freeze-v1', 'runtime_member_count': a.FULL_COUNT,
                       'source_identity': identity, 'source_identity_sha256': a.digest(identity),
                       'total_expanded_bytes': sum(len(raw) for raw in self.raw.values()),
                       'files': {name: {'bytes': len(raw), 'sha256': a.sha(raw)} for name, raw in self.raw.items()}}
        self.publication = {'format': 'irisx/qwen14b-portfolio-publication-contract-v1',
                            'source_freeze_sha256': 'synthetic-freeze', 'source_identity_sha256': a.digest(identity),
                            'terminal_contract': {'inner_request_source_identity': {'mapping': inner, 'identity_sha256': a.digest(inner)}}}
        self.mapping.update(source_freeze_sha256='synthetic-freeze', source_identity_sha256=a.digest(identity),
                            inner_source_identity_sha256=a.digest(inner))

    def reject(self, code, fn, *args, **kwargs):
        with self.assertRaises(a.AssemblyError) as caught:
            fn(*args, **kwargs)
        self.assertEqual(str(caught.exception), code)

    def contract(self):
        return a._validate_structure(self.freeze, self.publication, self.mapping)

    def read(self):
        entries, _ = self.contract()
        with a.directory(self.repo) as fd:
            return a._read_sources(fd, entries)

    def assemble_synthetic_helpers(self):
        # Internal helpers only: no pinned-admission receipt or execution claim.
        entries, inner = self.contract()
        repo, output = a._check_locations(self.repo, self.output)
        with a.directory(repo) as fd, a.directory(output.parent) as parent_fd:
            a._require_absent(parent_fd, output.name)
            sources = a._read_sources(fd, entries)
            a._write_new_tree(parent_fd, output.name, sources, entries, inner)

    def ordinary_path(self):
        return next(self.repo/row['repository_path'] for name, row in self.mapping['files'].items()
                    if not name.startswith(a.MATERIAL_LOGICAL))

    def test_checked_real_path_map_hash(self):
        self.assertEqual(a.sha((HERE/'runtime-path-map.json').read_bytes()), a.PATH_MAP_SHA256)

    def test_safe_material_relocation_and_exact_157_output(self):
        self.assemble_synthetic_helpers()
        files = {p.relative_to(self.output).as_posix(): p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
        self.assertEqual(files, self.raw)
        self.assertEqual(len(files), a.FULL_COUNT)
        self.assertFalse((self.output/'research/qwen14b-materials').exists())
        for name in files: self.assertEqual((self.output/name).stat().st_mode & 0o7777, 0o644)

    def test_repository_history_tests_and_unmapped_extra_never_copied(self):
        extra = self.repo/'historical-tests/never-copy.txt'
        extra.parent.mkdir()
        extra.write_bytes(b'synthetic unrelated history')
        self.assemble_synthetic_helpers()
        self.assertFalse((self.output/'historical-tests').exists())
        self.assertEqual(extra.read_bytes(), b'synthetic unrelated history')

    def test_input_bytes_unchanged(self):
        before = {name: (self.repo/row['repository_path']).read_bytes() for name, row in self.mapping['files'].items()}
        self.assemble_synthetic_helpers()
        self.assertEqual(before, {name: (self.repo/row['repository_path']).read_bytes() for name, row in self.mapping['files'].items()})

    def test_missing_mapping_entry_rejected(self):
        self.mapping['files'].pop(next(iter(self.mapping['files'])))
        self.reject('closed_full_mapping', self.contract)

    def test_extra_mapping_entry_rejected(self):
        self.mapping['files']['extra.py'] = copy.deepcopy(next(iter(self.mapping['files'].values())))
        self.reject('closed_full_mapping', self.contract)

    def test_repository_mapping_cannot_redirect_any_member(self):
        next(iter(self.mapping['files'].values()))['repository_path'] = 'research/wrong-source.py'
        self.reject('closed_logical_path_mapping', self.contract)

    def test_missing_mapped_source_rejected_before_output(self):
        self.ordinary_path().unlink()
        self.reject('source_unavailable_or_link', self.assemble_synthetic_helpers)
        self.assertFalse(self.output.exists())

    def test_missing_material_rejected_before_output(self):
        row = next(row for name, row in self.mapping['files'].items() if name.startswith(a.MATERIAL_LOGICAL))
        (self.repo/row['repository_path']).unlink()
        self.reject('dedicated_materials_tree_not_closed', self.assemble_synthetic_helpers)
        self.assertFalse(self.output.exists())

    def test_extra_material_file_rejected_before_output(self):
        (self.repo/a.MATERIAL_REPOSITORY/'unexpected.txt').write_bytes(b'synthetic extra')
        self.reject('dedicated_materials_tree_not_closed', self.assemble_synthetic_helpers)
        self.assertFalse(self.output.exists())

    def test_extra_empty_material_directory_rejected(self):
        (self.repo/a.MATERIAL_REPOSITORY/'extra-empty').mkdir()
        self.reject('dedicated_materials_tree_not_closed', self.read)

    def test_source_hash_mismatch_rejected_before_output(self):
        path = self.ordinary_path()
        path.write_bytes(b'x'*path.stat().st_size)
        self.reject('source_bytes_mismatch', self.assemble_synthetic_helpers)
        self.assertFalse(self.output.exists())

    def test_source_size_mismatch_rejected(self):
        self.ordinary_path().write_bytes(b'short')
        self.reject('source_bytes_mismatch', self.read)

    def test_frozen_mapping_hash_or_size_mismatch_rejected(self):
        name = next(iter(self.mapping['files']))
        self.mapping['files'][name]['bytes'] += 1
        self.reject('frozen_entry_binding', self.contract)
        self.mapping['files'][name]['bytes'] -= 1
        self.mapping['files'][name]['sha256'] = '0'*64
        self.reject('frozen_entry_binding', self.contract)

    def test_full_identity_mismatch_rejected(self):
        self.freeze['source_identity_sha256'] = '0'*64
        self.reject('full_identity_binding', self.contract)

    def test_inner_identity_mismatch_rejected(self):
        self.mapping['inner_source_identity_sha256'] = '0'*64
        self.reject('inner_identity_binding', self.contract)

    def test_missing_inner_member_rejected(self):
        inner = self.publication['terminal_contract']['inner_request_source_identity']['mapping']
        inner.pop(next(iter(inner)))
        self.reject('complete_inner_subset', self.contract)

    def test_wrong_153_member_subset_rejected(self):
        inner = self.publication['terminal_contract']['inner_request_source_identity']['mapping']
        inner.pop(next(iter(inner)))
        extra = next(iter(a.INNER_EXCLUSIONS))
        inner[extra] = self.freeze['source_identity'][extra]
        self.reject('complete_inner_subset', self.contract)

    def test_source_mode_must_remain_100644(self):
        self.ordinary_path().chmod(0o755)
        self.reject('source_mode_must_be_100644', self.read)

    def test_mapping_mode_must_remain_100644(self):
        next(iter(self.mapping['files'].values()))['mode'] = '100755'
        self.reject('frozen_entry_binding', self.contract)

    def test_source_symlink_rejected(self):
        path = self.ordinary_path()
        actual = self.root/'link-target'
        path.rename(actual)
        path.symlink_to(actual)
        self.reject('source_unavailable_or_link', self.read)

    def test_source_hardlink_rejected(self):
        path = self.ordinary_path()
        os.link(path, self.root/'extra-hardlink')
        self.reject('regular_unlinked_file_required', self.read)

    def test_material_subtree_symlink_rejected(self):
        path = self.repo/a.MATERIAL_REPOSITORY
        target = self.root/'actual-materials'
        path.rename(target)
        path.symlink_to(target, target_is_directory=True)
        self.reject('source_unavailable_or_link', self.read)

    def test_material_extra_symlink_rejected(self):
        (self.repo/a.MATERIAL_REPOSITORY/'bad-link').symlink_to(self.root/'missing')
        self.reject('inventory_link_or_special_file', self.read)

    def test_source_ancestor_symlink_rejected(self):
        actual = self.root/'actual-repository'
        self.repo.rename(actual)
        self.repo.symlink_to(actual, target_is_directory=True)
        self.reject('directory_unavailable_or_link', self.read)

    def test_output_ancestor_symlink_rejected_before_write(self):
        actual = self.root/'actual-output-parent'
        actual.mkdir()
        link = self.root/'linked-output-parent'
        link.symlink_to(actual, target_is_directory=True)
        self.output = link/'runtime'
        self.reject('directory_unavailable_or_link', self.assemble_synthetic_helpers)
        self.assertFalse((actual/'runtime').exists())

    def test_output_symlink_rejected(self):
        self.output.symlink_to(self.root/'missing', target_is_directory=True)
        self.reject('output_must_be_new', self.assemble_synthetic_helpers)

    def test_output_must_be_new_even_if_empty(self):
        self.output.mkdir()
        self.reject('output_must_be_new', self.assemble_synthetic_helpers)

    def test_nonempty_output_rejected_and_preserved(self):
        self.output.mkdir()
        marker = self.output/'do-not-overwrite'
        marker.write_bytes(b'preserve')
        self.reject('output_must_be_new', self.assemble_synthetic_helpers)
        self.assertEqual(marker.read_bytes(), b'preserve')

    def test_source_output_overlap_in_both_directions_rejected(self):
        for output in (self.repo, self.repo/'inside', self.root):
            self.reject('source_output_overlap', a._check_locations, self.repo, output)

    def test_unsafe_relative_paths_rejected(self):
        for path in ('../x', '/tmp/x', 'a//b', 'a/./b', 'a/../b', 'a\\b', 'x:y', 'a\nb', ''):
            with self.subTest(path=path): self.reject('unsafe_relative_path', a.safe_name, path)

    def test_unsafe_absolute_locator_rejected(self):
        self.reject('unsafe_local_path', a.explicit_path, str(self.root)+'/../outside')
        for value in ('', ' ', None): self.reject('explicit_local_path_required', a.explicit_path, value)

    def test_public_api_rejects_synthetic_document_hash_without_output(self):
        path = self.root/'synthetic-freeze.json'
        path.write_text(json.dumps(self.freeze))
        self.reject('frozen_document_hash_mismatch', a.assemble_runtime,
                    repository_root=self.repo, output_root=self.output, source_freeze=path,
                    publication_manifest=path, path_map=HERE/'runtime-path-map.json')
        self.assertFalse(self.output.exists())

    def test_each_trust_anchor_document_hash_is_required(self):
        path = self.root/'altered-document.json'
        path.write_bytes(b'{}')
        for expected in (a.SOURCE_FREEZE_SHA256, a.PUBLICATION_MANIFEST_SHA256, a.PATH_MAP_SHA256):
            self.reject('frozen_document_hash_mismatch', a.read_document, path, expected)

    def verify_synthetic_tree(self):
        entries, inner = self.contract()
        with a.directory(self.output) as fd:
            return a._verify_tree(fd, entries, inner)

    def test_readonly_runtime_verifier_accepts_exact_synthetic_tree(self):
        self.assemble_synthetic_helpers()
        before = {name: (self.output/name).read_bytes() for name in self.raw}
        self.verify_synthetic_tree()
        self.assertEqual(before, {name: (self.output/name).read_bytes() for name in self.raw})

    def test_runtime_verifier_rejects_extra_file(self):
        self.assemble_synthetic_helpers()
        (self.output/'unexpected.txt').write_bytes(b'synthetic extra')
        self.reject('output_tree_not_closed', self.verify_synthetic_tree)

    def test_runtime_verifier_rejects_missing_file(self):
        self.assemble_synthetic_helpers()
        (self.output/next(iter(self.raw))).unlink()
        self.reject('output_tree_not_closed', self.verify_synthetic_tree)

    def test_runtime_verifier_rejects_hash_and_size_changes(self):
        self.assemble_synthetic_helpers()
        path = self.output/next(iter(self.raw))
        path.write_bytes(b'x'*path.stat().st_size)
        self.reject('output_bytes_mismatch', self.verify_synthetic_tree)
        path.write_bytes(b'short')
        self.reject('output_bytes_mismatch', self.verify_synthetic_tree)

    def test_runtime_verifier_rejects_symlink_and_mode_changes(self):
        self.assemble_synthetic_helpers()
        path = self.output/next(iter(self.raw))
        path.chmod(0o755)
        self.reject('source_mode_must_be_100644', self.verify_synthetic_tree)
        path.chmod(0o644)
        target = self.root/'actual-output-file'
        path.rename(target)
        path.symlink_to(target)
        self.reject('inventory_link_or_special_file', self.verify_synthetic_tree)

    def test_public_verifier_rejects_unpinned_documents(self):
        release = self.repo/'tools/arc_qwen_portfolio_deployment_20261012/release/portfolio-v1'
        release.mkdir(parents=True)
        (release/'SOURCE-FREEZE.json').write_text(json.dumps(self.freeze))
        self.reject('frozen_document_hash_mismatch', a.verify_runtime, self.output, self.repo)



if __name__ == '__main__':
    unittest.main()
