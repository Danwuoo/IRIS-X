import contextlib
import io
import tempfile
from pathlib import Path
import os
import unittest
from tools import stage_arc_next_notebook as s
class NotebookTests(unittest.TestCase):
    def test_all_defaults_inert(self):
        nb=s.notebook({'source_digest':'0'*64,'source_commit':'0'*40},{'tools/__init__.py':b''})
        before=os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                values={}
                with contextlib.redirect_stdout(io.StringIO()):
                    for cell in nb['cells']:
                        if cell['cell_type']=='code':exec(compile(''.join(cell['source']),'notebook','exec'),values)
                self.assertTrue(all(values[x] is False for x in s.FLAGS))
                self.assertEqual(list(Path(d).iterdir()),[])
            finally:os.chdir(before)
    def test_flags_are_distinct_and_scoring_separate(self):
        self.assertIn('SCORE_DEVELOPMENT',s.FLAGS)
        self.assertEqual(len(s.FLAGS),len(set(s.FLAGS)))
if __name__=='__main__':unittest.main()
