"""Actual-call guards and independently rehashed numerical evidence, offline."""
from array import array
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from irisx.arc_nvarc_qwen3_packing_diagnostic import FORMAT,TINY,ForwardBudget,schedule,ordered_rows,changed_rows
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.verify_nvarc_qwen3_packing_diagnostic import verify,measurements


class FakeTensor:
    def __init__(self,ids): self.ids=ids
    def tolist(self): return [self.ids]


class PackingDiagnosticTests(unittest.TestCase):
    def rows(self):
        return [{'input_ids':[14,11,10,i,15,14,12,10,2,15], 'labels':[-100]*8+[2,15],
            'parent_ids':['public-'+str(i)],'exposure':['training2']} for i in range(8)]

    def plan(self,rows):
        allowed=schedule(rows)
        return {'format':FORMAT,'owner_decision':'Decision 0054','run_id':'nvarc-original-qwen3-probe-002',
            'data_digest':digest_value(rows),'forward_schedule':allowed,'atol':0.25,'rtol':0.03,
            'maximum_outer_forwards':len(allowed),'maximum_input_tokens':sum(x['input_tokens'] for x in allowed),
            'maximum_worker_wall_seconds':1200,'maximum_optimizer_steps':0,'maximum_generations':0,
            'maximum_teacher_calls':0,'maximum_paid_usd':0}

    def test_actual_guard_reserves_before_call_and_blocks_constructor_wrong_extra(self):
        rows=self.rows(); plan=self.plan(rows); stored=[]; called=[]
        budget=ForwardBudget(rows,plan,lambda name,value:stored.append(copy.deepcopy(value)))
        model=type('Qwen3ForCausalLM',(),{})()
        def actual(module,*args,**kwargs):
            self.assertIs(stored[-1][-1]['completed'],False)
            self.assertEqual(stored[-1][-1]['cumulative_forwards'],len(called)+1)
            called.append(kwargs['input_ids'].tolist()); return 'logits'
        def invoke(ids):return budget.guard_call(model,(),{'input_ids':FakeTensor(ids)},actual)
        with self.assertRaises(ValidationError):invoke(TINY[0]['input_ids'])
        with self.assertRaises(ValidationError):budget.perform('tiny-independent-gradients',lambda:invoke([1,2]))
        self.assertEqual(called,[]);self.assertEqual(stored,[])
        self.assertEqual(budget.perform('tiny-independent-gradients',lambda:invoke(TINY[0]['input_ids'])),'logits')
        self.assertIs(stored[-1][-1]['completed'],True)
        with self.assertRaises(ValidationError):budget.perform('actual-packed-varlen',lambda:invoke(TINY[1]['input_ids']))
        self.assertEqual(len(called),1)
        budget.events=[{**x,'completed':True} for x in budget.allowed]
        with self.assertRaises(ValidationError):budget.perform('actual-packed-isolation',lambda:invoke([14,15]))
        self.assertEqual(len(called),1)

    def test_failed_real_entry_keeps_reserved_incomplete_prefix(self):
        rows=self.rows();stored=[];budget=ForwardBudget(rows,self.plan(rows),lambda name,value:stored.append(copy.deepcopy(value)))
        model=type('Qwen3ForCausalLM',(),{})()
        def fail(*args,**kwargs):raise RuntimeError('device failure')
        with self.assertRaises(RuntimeError):budget.perform('tiny-independent-gradients',lambda:
            budget.guard_call(model,(),{'input_ids':FakeTensor(TINY[0]['input_ids'])},fail))
        self.assertEqual(len(stored),1);self.assertIs(stored[0][0]['completed'],False)
        self.assertIsNone(budget.active)

    def fixture(self,root):
        rows=self.rows();plan=self.plan(rows);package=root/'package';package.mkdir()
        for name,value in [('plan.json',plan),('samples.json',rows),('stage-summary.json',{'payload_sha256':{'runtime':'fixture'}})]:
            (package/name).write_text(json.dumps(value),encoding='utf-8')
        calls=tokens=0;ledger=[]
        for row in schedule(rows):
            calls+=1;tokens+=row['input_tokens'];ledger.append({**row,'cumulative_forwards':calls,
                'cumulative_input_tokens':tokens,'completed':True})
        _,ordered=ordered_rows(rows);offsets=[0]
        for row in ordered:offsets.append(offsets[-1]+len(row['input_ids']))
        baseline=array('f',[0.0]*(offsets[-1]*16));single=array('f',baseline);packed=array('f',baseline)
        # A genuine gate rejection survives a digest-valid failed archive.
        packed[offsets[1]*16]=8.125
        altered=array('f',packed);altered[0]=1.0
        arrays={'independent-flash-sdpa':baseline,'single-varlen':single,'packed-varlen':packed,'isolation':altered}
        values={'plan.json':plan,'payload-bindings.json':{'runtime':'fixture'},
            'terminal.json':{'run_id':plan['run_id'],'outcome':'failed','phase':'model-probe',
                'error_type':'ValidationError','error_message':'fixed gate rejected','contains_evaluator_truth':False},
            'worker/worker-ledger.json':ledger,'worker/vectors.json':{
                name+'-logits':{'path':name+'-logits.f32le','shape':[1,offsets[-1],16],'dtype':'float32-le'} for name in arrays},
            'worker/actual-weight-differential.json':{'atol':0.25,'rtol':0.03,'offsets':offsets,
                'packed_token_mean_loss':1.0,'timings':[{'mode':mode,'seconds':1.0} for mode in list(arrays)[:3]],
                'all_logits_retained':True,'comparisons':{
                    rhs+'-vs-'+lhs:measurements(arrays[lhs],arrays[rhs],offsets) for lhs,rhs in
                    [('independent-flash-sdpa','single-varlen'),('single-varlen','packed-varlen'),('independent-flash-sdpa','packed-varlen')]}},
            'worker/isolation.json':{'unchanged_later_samples_bitwise_equal':True,'original_prefix_digest':digest_value(rows),
                'changed_prefix_digest':digest_value(changed_rows(rows))}}
        binary={'worker/'+name+'-logits.f32le':value.tobytes() for name,value in arrays.items()}
        def archive():
            raw={name:json.dumps(value).encode() for name,value in values.items()};raw.update(binary)
            manifest={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'members':[
                {'path':name,'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()} for name,value in raw.items()]}
            target=root/'result.zip'
            with zipfile.ZipFile(target,'w') as stream:
                stream.writestr('manifest.json',json.dumps(manifest))
                for name,value in raw.items():stream.writestr(name,value)
            return target
        return package,values,binary,archive

    def test_failed_archive_recounts_full_logits_and_rejects_rehashed_numeric_lie(self):
        with tempfile.TemporaryDirectory() as directory:
            package,values,binary,archive=self.fixture(Path(directory))
            proof=verify(archive(),package)
            self.assertIs(proof['fixed_numerical_gate_passed'],False)
            self.assertIs(proof['independently_recomputed_packed_isolation'],True)
            self.assertEqual(proof['completed_outer_forwards'],21)
            self.assertEqual(proof['independently_recomputed_logit_comparisons'][
                'packed-varlen-vs-independent-flash-sdpa'][1]['max_absolute_error'],8.125)
            values['worker/actual-weight-differential.json']['comparisons'][
                'packed-varlen-vs-independent-flash-sdpa'][1]['outside_tolerance']=0
            with self.assertRaises(ValidationError):verify(archive(),package)

    def test_rehashed_cost_boolean_nonfinite_shape_and_isolation_lies_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            package,values,binary,archive=self.fixture(Path(directory));original=copy.deepcopy(values)
            for key,value in [('input_ids_digest','foreign'),('cumulative_forwards',True),('completed',1)]:
                values.clear();values.update(copy.deepcopy(original));values['worker/worker-ledger.json'][0][key]=value
                with self.subTest(key=key),self.assertRaises(ValidationError):verify(archive(),package)
            values.clear();values.update(copy.deepcopy(original));values['worker/vectors.json']['packed-varlen-logits']['shape'][1]-=1
            with self.assertRaises(ValidationError):verify(archive(),package)
            values.clear();values.update(copy.deepcopy(original));values['worker/isolation.json']['unchanged_later_samples_bitwise_equal']=False
            with self.assertRaises(ValidationError):verify(archive(),package)
            values.clear();values.update(copy.deepcopy(original));key='worker/single-varlen-logits.f32le'
            raw=array('f');raw.frombytes(binary[key]);raw[0]=float('nan');binary[key]=raw.tobytes()
            with self.assertRaises(ValidationError):verify(archive(),package)


if __name__=='__main__':unittest.main()
