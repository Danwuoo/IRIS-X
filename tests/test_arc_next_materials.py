import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from tools import arc_next_materials as m

class MaterialsTests(unittest.TestCase):
    def inventory(self):
        return {'commit': m.ARC_COMMIT, 'evaluation_paths_included': False,
                'files': [{'path': f'data/training/{n:08x}.json', 'git_blob_sha1': '0'*40, 'bytes': 1} for n in range(1000)]}
    def test_group_split_is_complete_disjoint_deterministic(self):
        s = m.groups(self.inventory())
        self.assertEqual(s, m.groups(self.inventory()))
        names = ['training_ids','development_ids','unused_training_ids','unused_development_ids']
        all_ids = [x for name in names for x in s[name]]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(len(all_ids), 1000)
        self.assertEqual(len(s['training_ids']), 32)
        self.assertEqual(len(s['development_ids']), 4)
    def test_evaluation_paths_rejected(self):
        inv = self.inventory(); inv['files'][0]['path']='data/evaluation/00000000.json'
        with self.assertRaises(ValueError): m.groups(inv)
    def test_no_default_network_or_files(self):
        def forbidden(*args): raise AssertionError('network')
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(m.materialize_training({},Path(d)/'new',fetch=forbidden)['status'],'disabled')
            self.assertEqual(m.materialize_model('bad',Path(d)/'new')['status'],'disabled')
            self.assertFalse((Path(d)/'new').exists())
    def test_sanitize_ignores_all_test_contents(self):
        task={'train':[{'input':[[1]],'output':[[2]]},{'input':[[3]],'output':[[4]]}],
              'test':{'unread': 'sentinel-do-not-carry-test-truth'}}
        body=json.dumps(task).encode(); blob=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
        task,receipt=m.sanitize_source(body,{'bytes':len(body),'git_blob_sha1':blob})
        self.assertEqual(set(task),{'train'}); self.assertFalse(receipt['original_test_fields_retained'])
        with self.assertRaises(ValueError): m.sanitize_source(body+b' ',{'bytes':len(body),'git_blob_sha1':blob})
    def test_grid_types(self):
        for value in ([[True]], [[10]], [[1],[1,2]], []):
            with self.assertRaises(ValueError): m.grid(value)
if __name__=='__main__':unittest.main()
