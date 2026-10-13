"""Exact production-labelled notebook15-field config in explicit synthetic envelopes."""
from copy import deepcopy
from pathlib import Path
import os,sys,tempfile,unittest
VALIDATION=Path(__file__).resolve().parents[1]/'validation';ROOT=VALIDATION.parent
sys.path[:0]=[str(VALIDATION),str(Path(__file__).parent)]
import validate_transfer_outputs as v
from successor_fixture_helpers import make_final_source_collector_fixture,release_path,source_for_release
class ExactOuterConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release=release_path()
        if not (cls.release/'publication-manifest.json').is_file():raise unittest.SkipTest('checkpoint release fixture unavailable')
        try:cls.fixture_source=source_for_release(cls.release)
        except ValueError as exc:
            if str(exc)=='no exact immutable source fixture matches mapping':raise unittest.SkipTest('exact release present but matching immutable source fixture omitted') from exc
            raise
        cls.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        cls.args=make_final_source_collector_fixture(Path(cls.temp.name)/'authored-failure',synthetic=True,
            template_release=cls.release,source_root=cls.fixture_source)
        m,msha=v.document(cls.args['manifest']);f,_=v.document(cls.args['finalization']);j,_=v.document(cls.args['launch_journal']);l,_=v.document(cls.args['launch_receipt'])
        cls.spec,cls.constants=v.validate_launch(m,msha,f,j,l,cls.args['finalized_notebook'],cls.release.absolute(),allow_synthetic=True)
        cls.finalization=f
        d=v.Downloads(cls.args['download_root'],cls.args['retrieval_receipt'],l,cls.spec,msha)
        cls.data={n:d.raw(n) for n in d.files};cls.prefix=Path(cls.spec['output_root']).name+'-launcher/'
        cls.terminal=d.json(Path(cls.spec['output_root']).name+'/terminal-receipt.json')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def check(self,edit=None,status=None):
        raw=deepcopy(self.data);prefix=self.prefix;terminal=deepcopy(self.terminal)
        request=v.strict_json(raw[prefix+'request.json'])
        if edit:edit(request)
        raw[prefix+'request.json']=v.canonical(request)
        launch=v.strict_json(raw[prefix+'owned-tree/launch.json']);launch['worker_argv'][-1]=v.raw_sha(raw[prefix+'request.json'])
        raw[prefix+'owned-tree/launch.json']=v.canonical(launch)
        if status:
            terminal['status']=status;terminal['science_complete']=status=='TRANSFER_COMPLETE'
            raw[prefix+'result.json']=v.canonical(terminal)
        class Downloads:
            def raw(self,name):return raw[name]
            def json(self,name):return v.strict_json(raw[name])
        return v.validate_outer(Downloads(),self.spec,self.constants,self.finalization,terminal)
    def test_exact_fifteen_fields(self):
        req=v.strict_json(self.data[self.prefix+'request.json']);self.assertEqual(len(req['config']),15);self.check()
    def test_exact_three_clock_cutoffs(self):
        cfg=v.strict_json(self.data[self.prefix+'request.json'])['config']
        self.assertEqual([cfg[k] for k in ('execution_cutoff_seconds','outer_cutoff_seconds','provider_runtime_seconds')],[42000,42180,42300])
    def test_production_label_synthetic_complete_partial_failure_outer_envelopes(self):
        # Outer-only authored status controls. This never claims the fictional
        # before-load archive completed training or passed content validation.
        for status in ('TRANSFER_COMPLETE','TRANSFER_PARTIAL','TRANSFER_FAILED'):
            with self.subTest(status=status):self.check(status=status)
    def test_missing_any_of_fifteen_fields(self):
        fields=v.strict_json(self.data[self.prefix+'request.json'])['config']
        for key in fields:
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(lambda r:r['config'].pop(key))
    def test_extra_field(self):
        with self.assertRaises(ValueError):self.check(lambda r:r['config'].__setitem__('extra',True))
    def test_every_cutoff_mutation(self):
        for key in ('execution_cutoff_seconds','outer_cutoff_seconds','provider_runtime_seconds'):
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(lambda r:r['config'].__setitem__(key,r['config'][key]+1))
    def test_float_cannot_impersonate_integer_cutoff(self):
        with self.assertRaises(ValueError):self.check(lambda r:r['config'].__setitem__('execution_cutoff_seconds',42000.))
    def test_int_cannot_impersonate_boolean(self):
        with self.assertRaises(ValueError):self.check(lambda r:r['config'].__setitem__('manual_start',1))
    def test_changed_output_root(self):
        with self.assertRaises(ValueError):self.check(lambda r:r['config'].__setitem__('output_root','/kaggle/working/irisx-qwen14b-transfer-20261012-run002'))
    def test_clock_origin_cannot_reset(self):
        with self.assertRaises(ValueError):self.check(lambda r:r.__setitem__('started_epoch',r['started_epoch']+1))
    def test_actual_source_parent_not_old_source(self):
        self.assertEqual(self.constants['SOURCE_PARENT'],'/kaggle/working/irisx-qwen14b-transfer-20261012-source003')
    def test_exact_byte_original_predecessor_files_preserved(self):
        predecessor=ROOT.parent/'portfolio63-transfer-repair-20261012/validation'
        self.assertEqual(v.file_sha(predecessor/'validate_transfer_outputs.py'),'416d7f93e1b123efd9aaef7948c7350dab524cfb33afa14ea8077e1cd076c98b')
        for name in ('budget_checks.py','generation_checks.py','selector_replay.py','frozen-panel-plan.json'):
            self.assertEqual(v.file_sha(predecessor/name),v.file_sha(VALIDATION/name))
if __name__=='__main__':unittest.main()
