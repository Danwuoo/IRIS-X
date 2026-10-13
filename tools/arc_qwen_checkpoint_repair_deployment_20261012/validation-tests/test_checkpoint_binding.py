"""Source-exact checkpoint identity subchecks, plus explicit authored mutations.

Uses actual retained tiny native checkpoints at production/global0/64/256 and
local0/8/16. It never relabels their historical source as final-source execution,
never loads tensors, and never runs a model, provider or public scorer.
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
VALIDATION=Path(__file__).resolve().parents[1]/'validation';ROOT=VALIDATION.parent
sys.path.insert(0,str(VALIDATION))
import validate_transfer_outputs as v

class NativeCheckpointBinding(unittest.TestCase):
    control_path='evidence/native-production-schedule-002'
    source_path='evidence/native002-source'
    @classmethod
    def setUpClass(cls):
        cls.control=ROOT/cls.control_path
        cls.source_root=ROOT/cls.source_path
        if not (cls.control/'receipt.json').is_file() or not (cls.source_root/v.PACKAGE/'protocol.py').is_file():
            raise unittest.SkipTest('retained actual native002 checkpoint/source fixture unavailable')
        receipt=v.json_file(cls.control/'receipt.json')
        if receipt['status']!='passed':raise unittest.SkipTest('actual native002 control incomplete')
        cls.source=v.SourceSnapshot(cls.source_root,v.source_identity(cls.source_root))
        cls.records={'global':v.json_file(cls.control/'global-records.json'),'ttt':v.json_file(cls.control/'task-records.json')}
        cls.fixtures={}
        for key,kind in (('results','global'),('task_results','ttt')):
            for row in receipt[key]:
                path=Path(row['saved']['path']);manifest=v.json_file(path/'manifest.json')
                cls.fixtures[kind,row['update']]={'manifest':manifest,'saved':row['saved'],
                    'resume':v.json_file(path/'resume/state.json'),
                    'inference':v.json_file(path/'inference/adapter_model.safetensors.index.json')}
    @classmethod
    def tearDownClass(cls):cls.source.close()
    def validate(self,kind='global',update=64,mutate=None):
        manifest=deepcopy(self.fixtures[kind,update]['manifest']);original=self.fixtures[kind,update]['manifest']['binding']
        if mutate:mutate(manifest['binding'])
        return v.validate_checkpoint_binding(manifest['binding'],self.source,kind=kind,update=update,
            records=self.records[kind],config=original['config'],provenance=original['provenance'],
            model_identity=original['model']['native_identity'])
    def rejected(self,fn,kind='global',update=64):
        with self.assertRaises(ValueError):self.validate(kind,update,fn)
    def test_all_actual_global0_64_256(self):
        for update in (0,64,256):self.assertEqual(self.validate(update=update)['allowed_updates'],[0,64,256])
    def test_all_actual_task0_8_16(self):
        for update in (0,8,16):self.assertEqual(self.validate('ttt',update)['allowed_updates'],[0,8,16])
    def test_global64_not_task_schedule(self):self.rejected(lambda b:b.__setitem__('checkpoint_schedule',v.checkpoint_contract(self.source,'ttt')))
    def test_task16_not_global_schedule(self):self.rejected(lambda b:b.__setitem__('checkpoint_schedule',v.checkpoint_contract(self.source,'global')),'ttt',16)
    def test_missing_schedule(self):self.rejected(lambda b:b.pop('checkpoint_schedule'))
    def test_inherited16_ceiling(self):self.rejected(lambda b:b['checkpoint_schedule'].__setitem__('allowed_updates',[0,8,16]))
    def test_arbitrary_huge_global_schedule(self):self.rejected(lambda b:b['checkpoint_schedule'].__setitem__('allowed_updates',[0,64,999999]))
    def test_bool_allowed_update(self):self.rejected(lambda b:b['checkpoint_schedule'].__setitem__('allowed_updates',[False,64,256]))
    def test_float_allowed_update(self):self.rejected(lambda b:b['checkpoint_schedule'].__setitem__('allowed_updates',[0,64.0,256]))
    def test_fixture_flag_type(self):self.rejected(lambda b:b['checkpoint_schedule'].__setitem__('fixture_only',0))
    def test_global_branch_changed(self):self.rejected(lambda b:b.__setitem__('branch_id','representative_ttt'))
    def test_source_policy_hash_changed(self):self.rejected(lambda b:b['checkpoint_schedule']['source_sha256'].__setitem__('checkpoint_policy.py','a'*64))
    def test_source_protocol_hash_changed(self):self.rejected(lambda b:b['checkpoint_schedule'].__setitem__('protocol_sha256','a'*64))
    def test_source_subset_no_longer_accepted(self):self.rejected(lambda b:b.__setitem__('source',{v.PACKAGE+'protocol.py':self.source.mapping[v.PACKAGE+'protocol.py']}))
    def test_source_unknown_extra(self):self.rejected(lambda b:b['source'].__setitem__('tools/foreign.py','a'*64))
    def test_config_learning_rate_changed(self):self.rejected(lambda b:b['config'].__setitem__('learning_rate',.9))
    def test_config_schedule_changed(self):self.rejected(lambda b:b['config'].__setitem__('schedule_steps',16))
    def test_config_unknown_extra(self):self.rejected(lambda b:b['config'].__setitem__('unapproved',True))
    def test_config_boolean_type(self):self.rejected(lambda b:b['config'].__setitem__('gradient_checkpointing',1))
    def test_config_removed_seed(self):self.rejected(lambda b:b['config'].pop('seed'))
    def test_record_digest_changed(self):self.rejected(lambda b:b.__setitem__('records_sha256','a'*64))
    def test_record_ids_reordered(self):self.rejected(lambda b:b['record_ids'].reverse())
    def test_record_ids_missing(self):self.rejected(lambda b:b['record_ids'].pop())
    def test_record_count_changed(self):self.rejected(lambda b:b.__setitem__('records_count',1))
    def test_record_count_boolean(self):self.rejected(lambda b:b.__setitem__('records_count',True))
    def test_provenance_changed(self):self.rejected(lambda b:b['provenance'].__setitem__('query_targets_used',True))
    def test_model_identity_changed(self):self.rejected(lambda b:b['model']['native_identity'].__setitem__('model_key','foreign'))
    def test_parameter_names_duplicate(self):self.rejected(lambda b:b['parameter_names'].append(b['parameter_names'][0]))
    def test_precision_changed(self):self.rejected(lambda b:b.__setitem__('precision','fp8'))
    def test_arbitrary_update_type(self):
        binding=self.fixtures['global',0]['manifest']['binding']
        for update in (False,0.,8,16,257,1000000):
            with self.subTest(update=update),self.assertRaises(ValueError):
                v.validate_checkpoint_binding(binding,self.source,kind='global',update=update,records=self.records['global'],
                    config=binding['config'],provenance=binding['provenance'])
    def test_actual_inference_full_state_metadata_identity(self):
        for (kind,update),f in self.fixtures.items():
            with self.subTest(kind=kind,update=update):
                m=f['manifest'];r=f['resume'];i=f['inference'];binding=m['binding']
                v.validate_checkpoint_projection(m,r,i,f['saved'])
                self.assertEqual(i['binding'],binding);self.assertEqual(i['update'],update)
                self.assertEqual(i['adapter_sha256'],m['adapter_sha256']);self.assertFalse(i['resume_capable'])
                self.assertEqual(r['handle']['state_sha256'],m['state_sha256'])
                self.assertEqual(r['handle']['identity_sha256'],v.native_digest({k:binding[k] for k in ('model','config','source')}))
                self.assertEqual(v.file_sha(Path(f['saved']['path'])/'manifest.json'),f['saved']['manifest_sha256'])
                self.assertEqual(v.file_sha(Path(f['saved']['path'])/'inference/adapter_model.safetensors.index.json'),f['saved']['inference_manifest_sha256'])
    def test_native002_is_never_final_source_relabelled(self):
        final=ROOT/'final-source-freeze-001'
        if not final.is_dir():self.skipTest('final source absent')
        self.assertNotEqual(self.source.mapping,v.source_identity(final))

class BaselineNativeCheckpointBinding(NativeCheckpointBinding):
    control_path='evidence/native-production-schedule-final'
    source_path='final-source-freeze-001'
    def test_native002_is_never_final_source_relabelled(self):
        old=v.source_identity(ROOT/'evidence/native002-source')
        self.assertNotEqual(self.source.mapping,old)
        self.assertEqual(self.source.mapping,v.source_identity(ROOT/'final-source-freeze-001'))
    def mutate_projection(self,fn):
        value=deepcopy(self.fixtures['global',64]);fn(value)
        with self.assertRaises(ValueError):v.validate_checkpoint_projection(value['manifest'],value['resume'],value['inference'],value['saved'])
    def test_manifest_update_cannot_impersonate_receipt(self):self.mutate_projection(lambda f:f['manifest'].__setitem__('update',16))
    def test_manifest_update_float_rejected(self):self.mutate_projection(lambda f:f['manifest'].__setitem__('update',64.))
    def test_inference_update_rejected(self):self.mutate_projection(lambda f:f['inference'].__setitem__('update',16))
    def test_resume_identity_rejected(self):self.mutate_projection(lambda f:f['resume']['handle'].__setitem__('identity_sha256','a'*64))
    def test_resume_counter_rejected(self):
        def edit(f):
            run=v.checkpoint_tree_node(f['resume']['tree'],'run_state')
            v.checkpoint_tree_node(run,'steps')['v']=16
        self.mutate_projection(edit)
    def test_resume_scheduler_counter_rejected(self):
        def edit(f):
            scheduler=v.checkpoint_tree_node(f['resume']['tree'],'scheduler')
            v.checkpoint_tree_node(scheduler,'last_epoch')['v']=16
        self.mutate_projection(edit)
    def test_resume_record_identity_rejected(self):
        def edit(f):
            run=v.checkpoint_tree_node(f['resume']['tree'],'run_state');identity=v.checkpoint_tree_node(run,'identity')
            v.checkpoint_tree_node(identity,'data_sha256')['v']='a'*64
        self.mutate_projection(edit)
    def test_resume_scope_rejected(self):
        self.mutate_projection(lambda f:v.checkpoint_tree_node(f['resume']['tree'],'task_id').__setitem__('v','synthetic-task'))


class FinalNativeCheckpointBinding(BaselineNativeCheckpointBinding):
    control_path='evidence/native-production-schedule-final002'
    source_path='final-source-freeze-002'
    def test_native002_is_never_final_source_relabelled(self):
        self.assertEqual(self.source.mapping,v.source_identity(ROOT/'final-source-freeze-002'))
        self.assertNotEqual(self.source.mapping,v.source_identity(ROOT/'final-source-freeze-001'))


class RunSchedules(unittest.TestCase):
    def test_exact_production(self):self.assertEqual(v.checkpoint_run_kind({'config':{}}),'global')
    def test_exact_tiny_global(self):self.assertEqual(v.checkpoint_run_kind({'config':{'tiny_cpu':True,'test_checkpoint_updates':[64,256]}}),'global')
    def test_explicit_fixture(self):self.assertEqual(v.checkpoint_run_kind({'config':{'tiny_cpu':True,'test_fixture_dataset':True}}),'fixture')
    def test_fixture_requires_both_flags(self):
        for config in ({'tiny_cpu':True},{'test_checkpoint_updates':[1,2]},{'tiny_cpu':False,'test_fixture_dataset':True,'test_checkpoint_updates':[1,2]}):
            with self.subTest(config=config),self.assertRaises(ValueError):v.checkpoint_run_kind({'config':config})
    def test_closed_strict_schedule(self):
        for values in ([0,64,256],[8,16],[64.,256],[True,2],[64,999999],['64',256],None):
            with self.subTest(values=values),self.assertRaises(ValueError):v.checkpoint_run_kind({'config':{'tiny_cpu':True,'test_fixture_dataset':True,'test_checkpoint_updates':values}})


class RepresentativeCheckpointRequirement(unittest.TestCase):
    def setUp(self):
        self.case={'case_id':'dev:authored','parent_id':'authored'}
        self.dataset={'cases':[self.case],'plan':{'representative_ttt_parent':'authored'}}
    def check(self,rows):
        class Archive:
            members={'experiment/ttt-predictions-sealed.json'}
            def json(self,name):return {'rows':rows}
        return v.validate_representative_checkpoints(Archive(),{},None,{},None,None,{},self.dataset)
    def test_completed_representative_requires_checkpoint(self):
        with self.assertRaisesRegex(ValueError,'omitted'):self.check([{'case_id':'dev:authored','complete':True,'representative_checkpoint':None}])
    def test_incomplete_representative_can_retain_abstention(self):
        self.assertEqual(self.check([{'case_id':'dev:authored','complete':False}]),0)

if __name__=='__main__':unittest.main()
