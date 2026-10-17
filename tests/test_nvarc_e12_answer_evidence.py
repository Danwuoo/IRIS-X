"""Literal CPU E12 inference evidence; no GPU, provider, truth or outcome reuse.

The literal view/decoder fixtures test evidence boundaries, not native-source
qualification. Retained source integration may separately run the unchanged
formatter, inverse transforms and score_kgmon through verify_source_provenance.
"""
from tests.platform_requirements import requires_linux
import copy
import json
import math
import os
import re
import shutil
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import sys

from tools import nvarc_e12_answer_evidence as evidence
from tools import nvarc_e10_answer_evidence as frozen
from tools import nvarc_native_multitask as native
from tools import nvarc_native_solve_runtime as source
from tools.nvarc_public_eval import PhaseTelemetry
from tests.nvarc_e12_cpu_fixture import Array, FakeTensor, LiteralEngine, fixture


def _load_linux_runtime():
    global runtime
    from tools import nvarc_e12_runtime as runtime

@requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _load_linux_runtime()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plan = fixture(self.root)
        self.engine = LiteralEngine()
        self.directory = self.root/'workers/0/arms/ttt64'
        self.directory.mkdir(parents=True)
        self.addCleanup(self.tmp.cleanup)
        self.challenges = json.loads((self.root/'challenges.json').read_bytes())

    def solve(self, arm='ttt64', *, deadline=1000., observe=True, schedule='interleaved', directory=None,rank=0):
        directory = self.directory if directory is None else directory
        directory.mkdir(parents=True, exist_ok=True)
        with patch.object(evidence.time, 'time', side_effect=self.engine.now), \
             patch.object(native, 'test_views', side_effect=self.engine.views), \
             patch.object(native, 'verifier_rows', side_effect=self.engine.rows):
            return evidence.solve_task(self.engine,self.root,self.plan,rank,deadline,PhaseTelemetry(),
                observe_forwards=observe,schedule=schedule,arm_id=arm,directory=directory)

    def artifacts(self, directory=None):
        directory = self.directory if directory is None else directory
        record = json.loads((directory/'answer-checkpoint.json').read_bytes())
        allocations = json.loads((directory/'test-allocations.json').read_bytes())
        events = evidence.read_events(directory/'inference-events.jsonl',record['binding'])
        return record, events, allocations

    def replay(self, record=None, events=None, allocations=None):
        saved, rows, admissions = self.artifacts()
        return evidence.check_inference(rows if events is None else events,
            saved['tests'] if record is None else record['tests'],2,plan=self.plan,
            arm_id='ttt64',admitted_allocations=admissions if allocations is None else allocations)

    def provenance(self, record=None, events=None, allocations=None):
        saved, rows, admissions = self.artifacts()
        tokenizer = NS(encode=lambda _text:NS(ids=[10]),decode=lambda tokens,**_kw:'q')
        fake_module = NS(Tokenizer=NS(from_file=lambda _path:tokenizer))
        with patch.dict(sys.modules,{'tokenizers':fake_module,'numpy':NS(asarray=Array)}), \
             patch.object(source,'load_sources',return_value=(self.engine.loader,None,self.engine.decoder)), \
             patch.object(native,'test_views',side_effect=self.engine.views), \
             patch.object(native,'verifier_rows',side_effect=self.engine.rows):
            return evidence.verify_source_provenance(self.root,self.challenges,self.plan['task_order'][0],
                rows if events is None else events,saved['tests'] if record is None else record['tests'],
                plan=self.plan,arm_id='ttt64',admitted_allocations=admissions if allocations is None else allocations)

    def test_both_arms_use_original_p02_and_same_actual_first_prefill(self):
        calls=[]
        original=self.engine.solver.inference_turbo_dfs
        def observe(adapter,prefixes,length,max_score,deadline):
            calls.append(max_score)
            return original(adapter,prefixes,length,max_score,deadline)
        self.engine.solver.inference_turbo_dfs=observe
        left=self.solve()
        right_dir=self.directory.parent/'ttt128'
        right=self.solve('ttt128',directory=right_dir)
        self.assertEqual(calls,[-math.log(.2)]*16)
        self.assertEqual((left['binding']['training_updates'],right['binding']['training_updates']),(64,128))
        self.assertTrue(left['output_qualified'] and right['output_qualified'])
        starts=[];prefills=[]
        for directory in (self.directory,right_dir):
            record,events,allocations=self.artifacts(directory)
            self.assertEqual(record['accounting']['generation']['completed'],8)
            self.assertEqual(record['accounting']['verification']['completed'],16)
            self.assertTrue(all('verification_schedule' not in t for t in record['tests']))
            starts.append([{k:row[k] for k in ('test_index','base_key','source_views','source_input_digests')}
                for row in events if row['event']=='test_started'])
            prefills.append([row['input_ids_digest'] for row in events
                if row['event']=='forward_reserved' and row['phase']=='generation' and not row['cached']])
            self.assertEqual(len(prefills[-1]),8)
            for index,value in allocations.items():
                self.assertEqual(runtime.allocation_deadlines(value,record['binding'],int(index)),
                    (value['started_epoch']+120,value['started_epoch']+150))
        self.assertEqual(starts[0],starts[1]);self.assertEqual(prefills[0],prefills[1])
        self.assertEqual(self.replay(),left['accounting'])
        self.provenance()

    def test_four_tasks_preserve_six_cases_and_original_caps_for_each_arm(self):
        counts={arm:0 for arm in runtime.ARMS}
        for rank,key in enumerate(self.plan['task_order']):
            for arm in runtime.ARMS:
                directory=self.root/'full-matrix'/str(rank)/arm
                record=self.solve(arm,directory=directory,rank=rank)
                saved,events,allocations=self.artifacts(directory)
                count=self.plan['test_counts'][key]
                self.assertEqual(evidence.check_inference(events,record['tests'],count,plan=self.plan,
                    arm_id=arm,admitted_allocations=allocations),record['accounting'])
                self.assertEqual(len(record['tests']),count)
                self.assertEqual(record['accounting']['generation']['completed'],4*count)
                self.assertEqual(record['accounting']['verification']['completed'],8*count)
                counts[arm]+=count
        self.assertEqual(counts,{'ttt64':6,'ttt128':6})
        self.assertEqual(evidence.PER_TEST,{'generation':4096,'verification':128,'input_tokens':5242880})

    def test_wrapper_validates_every_arm_allocation_before_native_solver(self):
        bound=evidence.task_binding(self.plan,self.challenges,0,schedule='interleaved',arm_id='ttt64')
        allocation=runtime.paired_allocation(bound,0,100.,1000.)
        adapter=NS(generation_deadline=220.,verification_deadline=250.)
        args=(self.challenges,bound['task_id'],0,None,None,None,None,adapter)
        base=dict(maximum_candidates=64,emit=lambda *_args,**_kw:None,test_allocation=allocation,arm_id='ttt64')
        with patch.object(evidence,'native_solve_test',return_value='literal') as solve:
            self.assertEqual(evidence.solve_test(*args,**base),'literal')
            self.assertIsNone(solve.call_args.kwargs['dfs_arm'])
            self.assertEqual(solve.call_args.kwargs['verification_schedule'],'interleaved')
        cases=[dict(test_allocation=None),dict(arm_id=None),dict(arm_id='ttt128'),
            dict(verification_schedule='deferred'),dict(maximum_candidates=True),dict(maximum_candidates=63)]
        changed=copy.deepcopy(allocation);changed['generation_seconds']=119
        cases.append(dict(test_allocation=changed))
        for changes in cases:
            with self.subTest(changes=changes), patch.object(evidence,'native_solve_test') as solve:
                with self.assertRaises(RuntimeError):evidence.solve_test(*args,**dict(base,**changes))
                solve.assert_not_called()
        adapter.generation_deadline=221.
        with patch.object(evidence,'native_solve_test') as solve:
            with self.assertRaisesRegex(RuntimeError,'deadlines'):evidence.solve_test(*args,**base)
            solve.assert_not_called()

    def test_missing_arm_observer_and_deferred_reject_before_model(self):
        for kwargs in (dict(arm=None),dict(arm='p02'),dict(observe=False),dict(schedule='deferred')):
            with self.subTest(kwargs=kwargs),self.assertRaises(RuntimeError):self.solve(**kwargs)
        self.assertEqual(self.engine.model.calls,[])
        self.assertFalse((self.directory/'inference-events.jsonl').exists())

    def test_no_clipped_window_and_explicit_unexecuted_slots(self):
        result=self.solve(deadline=249.)
        self.assertEqual(self.engine.model.calls,[])
        self.assertFalse(result['output_qualified'])
        self.assertEqual([t['status'] for t in result['tests']],['not_executed']*2)
        self.assertEqual(self.artifacts()[2],{})
        self.assertEqual(self.replay(),result['accounting'])
        self.provenance()

    def test_beam_threshold_is_strict_before_parsing_and_in_replay(self):
        original=self.engine.solver.inference_turbo_dfs
        def bad_score(*args):
            original(*args)
            return [(0,[(-math.log(.2),[1,15])])]
        self.engine.solver.inference_turbo_dfs=bad_score
        with self.assertRaisesRegex(RuntimeError,'beam score'):self.solve()
        self.assertEqual(self.engine.verified,0)
        self.assertFalse(self.artifacts()[0]['output_qualified'])

    def test_exact_nll_inputs_and_eight_view_receipts_cannot_be_rehashed(self):
        self.solve();record,events,allocations=self.artifacts()
        for mutation in ('input','nll','missing-view','beam'):
            changed=copy.deepcopy(events)
            if mutation=='input':
                row=next(r for r in changed if r['event']=='forward_reserved' and r['phase']=='verification')
                row['input_ids_digest']=native.digest([[9,1,15]]*4)
            elif mutation=='nll':
                row=next(r for r in changed if r['event']=='verification_observed')
                row['rows'][0]['score']=-1.
            elif mutation=='missing-view':
                row=next(r for r in changed if r['event']=='verification_observed')
                row['rows'].pop()
            else:
                row=next(r for r in changed if r['event']=='candidate_parsed')
                row['beam_score']=-math.log(.2)
            with self.subTest(mutation=mutation),self.assertRaises(RuntimeError):self.replay(events=changed)

    def test_source_prefill_inverse_ranking_and_return_provenance_are_checked(self):
        self.solve();record,events,allocations=self.artifacts();self.provenance()
        for mutation in ('prefill','source','tokens','rank','verifier'):
            changed=copy.deepcopy(events);result=copy.deepcopy(record)
            if mutation=='prefill':
                row=next(r for r in changed if r['event']=='forward_reserved' and r['phase']=='generation')
                row['input_ids_digest']=native.digest([[9]]*4)
            elif mutation=='source':
                row=next(r for r in changed if r['event']=='test_started')
                row['source_input_digests'][row['source_views'][0]]=native.digest([9])
            elif mutation=='tokens':
                next(r for r in changed if r['event']=='candidate_parsed')['source_tokens']=[2,15]
            elif mutation=='rank':result['tests'][0]['ranked_grids'].reverse()
            else:
                next(r for r in changed if r['event']=='verification_observed')['rows'][0]['source_view']='foreign'
            with self.subTest(mutation=mutation),self.assertRaises(RuntimeError):
                self.provenance(record=result,events=changed)

    def test_foreign_arm_typed_binding_and_missing_allocations_fail(self):
        self.solve();record,events,allocations=self.artifacts()
        for key,value in [('arm_id','ttt128'),('training_updates',128),('rank',False),
                ('schedule','deferred'),('dfs_probability_floor',.1)]:
            changed=copy.deepcopy(allocations);changed['0']['binding'][key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):
                evidence.verify_task(self.root,self.plan,0,directory=self.directory,arm_id='ttt64',admitted_allocations=changed)
        for method in (evidence.verify_task,evidence.recover_completed_tests):
            with self.assertRaisesRegex(RuntimeError,'allocation map'):
                method(self.root,self.plan,0,directory=self.directory,arm_id='ttt64')
        with patch.object(source,'load_sources') as load:
            with self.assertRaisesRegex(RuntimeError,'allocation map'):
                evidence.verify_source_provenance(self.root,self.challenges,record['binding']['task_id'],events,
                    record['tests'],plan=self.plan,arm_id='ttt64')
            load.assert_not_called()
        mutated=copy.deepcopy(events);mutated[-1]['training_updates']=128
        with self.assertRaises(RuntimeError):self.replay(events=mutated)
        with self.assertRaises(RuntimeError):self.replay(allocations={})

    def test_full_verification_binds_host_observer_and_constructor(self):
        result=self.solve();allocations=self.artifacts()[2]
        with patch.object(evidence,'verify_source_provenance'):
            self.assertEqual(evidence.verify_task(self.root,self.plan,0,directory=self.directory,
                arm_id='ttt64',admitted_allocations=allocations),result)
        observed=json.loads((self.directory/'inference-forward-diagnostics.json').read_bytes())
        self.assertEqual(observed['observed_rows'],24)
        self.assertEqual(observed['added_tensor_readbacks'],0)
        observed['rows']=[]
        native.write(self.directory/'inference-forward-diagnostics.json',observed)
        with patch.object(evidence,'verify_source_provenance'):
            with self.assertRaisesRegex(RuntimeError,'observation'):
                evidence.verify_task(self.root,self.plan,0,directory=self.directory,
                    arm_id='ttt64',admitted_allocations=allocations)
        entry=json.loads((self.directory/'adapter-entry.json').read_bytes())
        self.assertEqual(entry['constructor'],'tools.nvarc_e12_answer_evidence.AnswerModel')
        self.assertEqual(entry['reserved'],{'generation':0,'verification':0,'control':0})

    def test_failed_later_test_recovers_only_committed_prefix(self):
        self.engine.model.fail_after=12
        with self.assertRaisesRegex(RuntimeError,'literal model failure'):self.solve()
        record,events,allocations=self.artifacts()
        with patch.object(evidence,'verify_source_provenance'):
            recovered=evidence.recover_completed_tests(self.root,self.plan,0,directory=self.directory,
                arm_id='ttt64',admitted_allocations=allocations)
        self.assertEqual(recovered['tests'][0],record['tests'][0])
        self.assertEqual(recovered['tests'][1]['status'],'not_executed')
        self.assertFalse(recovered['output_qualified'])
        self.assertFalse(recovered['training_and_reset_qualified'])
        self.assertGreater(len(events),next(r['sequence'] for r in events if r['event']=='test_committed')+1)

    def test_frozen_historical_profile_does_not_admit_e12(self):
        with self.assertRaises(RuntimeError):frozen.for_plan(self.plan)
        self.assertEqual(frozen.PER_TEST,evidence.PER_TEST)


class CompactTokens:
    """Literal compact token alphabet for frozen-source CPU tests only.

    This is a labeled tokenizer substitute. Production replay uses tokenizers
    against the retained verified-tokenizer.json and never uses this fixture.
    """
    words={str(i):i for i in range(10)} | {'\n':10,'user':11,'assistant':12,
        '<|endoftext|>':13,'<|im_start|>':14,'<|im_end|>':15}
    pattern=re.compile('|'.join(re.escape(k) for k in sorted(words,key=len,reverse=True)))
    def encode(self,text):
        parts=self.pattern.findall(text)
        if ''.join(parts)!=text:raise AssertionError('literal compact token grammar differs')
        return [self.words[p] for p in parts]
    def decode(self,values,**_kwargs):
        inverse={v:k for k,v in self.words.items()}
        return ''.join(inverse[v] for v in values)


@unittest.skipUnless(os.environ.get('IRISX_E12_NATIVE_FIXTURE'),
    'set IRISX_E12_NATIVE_FIXTURE to retained hash-bound source/tokenizer directory')
@requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
class FrozenSourceReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _load_linux_runtime()

    def test_original_formatter_inverse_and_ranker_with_synthetic_model(self):
        """Frozen source is real; model/DFS/tokenizer substitutes are explicit."""
        import numpy as np
        material=Path(os.environ['IRISX_E12_NATIVE_FIXTURE'])
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for name in (*source.SOURCE_HASHES,'verified-tokenizer.json'):
                shutil.copyfile(material/name,root/name)
            plan=fixture(root)
            engine=LiteralEngine();engine.tokenizer=CompactTokens()
            engine.loader,_,engine.decoder=source.load_sources(root,NS(no_grad=lambda:lambda f:f),np)
            def generate(adapter,prefixes,length,max_score,deadline):
                self.assertEqual(max_score,-math.log(.2))
                adapter(input_ids=FakeTensor(prefixes),use_cache=True)
                engine.clock+=1
                return [(0,[(.1,[1,15])])]
            def verify(queries,answers,tokenizer,adapter):
                rows=[tokenizer.encode(q)+tokenizer.encode(a) for q,a in zip(queries,answers)]
                width=max(map(len,rows))
                adapter(input_ids=FakeTensor([r+[13]*(width-len(r)) for r in rows]),use_cache=False)
                engine.clock+=.5
                # The literal model emits 16 equal logits, so every token's
                # negative log probability is log(16), not a native-model score.
                return [len(tokenizer.encode(a))*math.log(16.) for a in answers]
            engine.solver=NS(inference_turbo_dfs=generate,calc_scores=verify,turbo_dfs=None)
            token_adapter=NS(encode=lambda text:NS(ids=engine.tokenizer.encode(text)),decode=engine.tokenizer.decode)
            tokenizer_module=NS(Tokenizer=NS(from_file=lambda _path:token_adapter))
            first=[]
            with patch.object(evidence.time,'time',side_effect=engine.now), \
                 patch.dict(sys.modules,{'tokenizers':tokenizer_module}):
                for arm in runtime.ARMS:
                    directory=root/'workers/0/arms'/arm;directory.mkdir(parents=True)
                    result=evidence.solve_task(engine,root,plan,0,1000.,PhaseTelemetry(),
                        arm_id=arm,directory=directory,observe_forwards=True)
                    allocations=json.loads((directory/'test-allocations.json').read_bytes())
                    self.assertEqual(evidence.verify_task(root,plan,0,arm_id=arm,directory=directory,
                        admitted_allocations=allocations),result)
                    self.assertTrue(all(t['native_complete'] for t in result['tests']))
                    events=evidence.read_events(directory/'inference-events.jsonl',result['binding'])
                    first.append([r['input_ids_digest'] for r in events if r['event']=='forward_reserved'
                        and r['phase']=='generation' and r['cached'] is False])
                    corrupted=copy.deepcopy(events)
                    next(r for r in corrupted if r['event']=='candidate_parsed')['candidate_grid']=[[9,9]]
                    with self.assertRaisesRegex(RuntimeError,'parse/inverse'):
                        evidence.verify_source_provenance(root,json.loads((root/'challenges.json').read_bytes()),
                            plan['task_order'][0],corrupted,result['tests'],plan=plan,arm_id=arm,
                            admitted_allocations=allocations)
            self.assertEqual(len(first[0]),8)
            self.assertEqual(first[0],first[1])


if __name__=='__main__':unittest.main()
