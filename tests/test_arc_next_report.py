from pathlib import Path
import tempfile
import unittest
import json
import zipfile
from tools.arc_next_report import metrics,ranked_prefix,export_report
class ReportTests(unittest.TestCase):
    def candidate(self,g,call,tok,sec):return {'outputs':[g],'call_id':call,'digest':str(g),'usage_at_admission':{'prompt_tokens':tok,'generated_tokens':0},'admitted_at_seconds':sec}
    def test_frontier_does_not_use_future_votes(self):
        a=self.candidate([[1]],0,10,1);b=self.candidate([[2]],1,20,2);c=self.candidate([[2]],2,30,3)
        self.assertEqual(ranked_prefix([a,b,c],max_tokens=20)[0]['outputs'],[[[1]]])
        self.assertEqual(ranked_prefix([a,b,c])[0]['outputs'],[[[2]]])
        self.assertEqual(metrics([],[[[0]]])['top2'],0)
    def test_export_no_weights_or_solutions(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'run';p.mkdir();(p/'preflight.json').write_text('{}');(p/'watchdog-result.json').write_text(json.dumps({'cleanup':{'worker_alive_after_cleanup':False,'group_still_observable_after_kill':False}}));(p/'adapter').mkdir();(p/'adapter/x.safetensors').write_bytes(b'x')
            result=export_report(p)
            with zipfile.ZipFile(result['archive']) as z:self.assertNotIn('adapter/x.safetensors',z.namelist())
            with self.assertRaises(ValueError):export_report(p)
    def test_unconfirmed_worker_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'preflight.json').write_text('{}');(p/'watchdog-result.json').write_text(json.dumps({'cleanup':{'worker_alive_after_cleanup':True}}))
            with self.assertRaises(ValueError):export_report(p)
    def test_unknown_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):export_report(d)
if __name__=='__main__':unittest.main()
