"""Reject vote-only acceptance without consistent programs or source bounds."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from irisx.arc_nvarc_combined import atomic,sha
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.replay_nvarc_published_outputs import CANARY
from tools.verify_nvarc_published_outputs import majority_pairs,verify


class PublishedOutputDiagnosticTests(unittest.TestCase):
    def votes(self,exclusions):
        inputs=[[[0,i%2]] for i in range(12)]
        rows=[]
        for i in range(12):
            rows.extend({'result':None if sid in exclusions[i%len(exclusions)] else [[2,3+i%2]]}
                for sid in range(10))
        return inputs,rows

    def test_majorities_require_four_globally_consistent_programs(self):
        inputs,rows=self.votes([{8,9}])
        pairs,counts,sids=majority_pairs(inputs,rows)
        self.assertEqual((len(pairs),counts,sids),(12,[8]*12,list(range(8))))
        inputs,rows=self.votes([{0,1},{2,3},{4,5},{6,7}])
        pairs,counts,sids=majority_pairs(inputs,rows)
        self.assertEqual(pairs,[])
        self.assertTrue(all(count==8 for count in counts))
        self.assertEqual(sids,[8,9])

    def test_identity_and_uniform_output_do_not_pass_source_filter(self):
        inputs,rows=self.votes([{8,9}])
        for i,row in enumerate(rows):row['result']=inputs[i//10]
        self.assertEqual(majority_pairs(inputs,rows)[0],[])
        for row in rows:row['result']=[[2]]
        self.assertEqual(majority_pairs(inputs,rows)[0],[])

    def failure(self,folder):
        import hashlib
        programs=['unused diagnostic text '+str(i) for i in range(10)]
        pairs=[{'input':[[0,i%2]],'output':[[2,3+i%2]]} for i in range(30)]
        binding={'path':'nvarc_full/0934a4d8/0934a4d8_00576224.json'}
        for name,value in [('programs.json',programs),('published-pairs.json',pairs),
            ('selection.json',{'binding':binding}),('raw-responses.json',[]),('material-verification.json',{})]:
            atomic(folder/name,value)
        (folder/'replay-source.py').write_text('# deliberately never executed\n')
        wanted=[{'stage':'trusted-isolation-canary','gid':None,'sid':None,'input_digest':digest_value([[0]]),
            'code_sha256':hashlib.sha256(CANARY.encode()).hexdigest()}]
        wanted.extend({'stage':'published-output-diagnostic','gid':gid,'sid':sid,
            'input_digest':digest_value(pair['input']),'code_sha256':hashlib.sha256(code.encode()).hexdigest()}
            for gid,pair in enumerate(pairs) for sid,code in enumerate(programs))
        plan={'format':'irisx/nvarc-published-output-diagnostic-v1','owner_decision':'Decision 0054',
            'run_id':folder.name,'maximum_program_attempts':301,'maximum_wall_seconds':1800,
            'maximum_execution_seconds':1200,'maximum_teacher_calls':0,'maximum_model_calls':0,
            'maximum_paid_usd':0,'source_minimum_output_programs':20,'retained_output_programs':10,
            'source_twenty_program_precondition_passed':False,'input_generation_replayed':False,
            'helper_removal_replayed':False,'accepted_source_pairs':0,'arc_correctness_scored':False,
            'source_filter':{'minimum_majority':8,'minimum_pairs':12,'minimum_correct_solutions':4},
            'material_inventory':{p.name:sha(p) for p in folder.iterdir()},'selection':binding,
            'replay_source_sha256':sha(folder/'replay-source.py'),'forward_schedule':wanted}
        atomic(folder/'plan.json',plan)
        event={**wanted[0],'attempt':1,'completed':False}
        (folder/'invocations.jsonl').write_text(json.dumps(event)+'\n')
        (folder/'program-results.jsonl').write_text('')
        terminal={'outcome':'failed','wall_seconds':1,'teacher_calls':0,'model_calls':0,'paid_usd':0,
            'accepted_source_pairs':0,'program_attempts_reserved':1,'returned_observations':0}
        atomic(folder/'terminal.json',terminal)
        return plan,terminal

    def test_failed_prefix_cannot_hide_attempts_relax_gates_or_expand_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);plan,terminal=self.failure(folder)
            self.assertEqual(verify(folder)['program_attempts_reserved'],1)
            for key,value in [('program_attempts_reserved',0),('returned_observations',1)]:
                changed={**terminal,key:value};atomic(folder/'terminal.json',changed)
                with self.assertRaises(ValidationError):verify(folder)
            atomic(folder/'terminal.json',terminal)
            for key,value in [('maximum_teacher_calls',1),('source_filter',{'minimum_majority':7,
                'minimum_pairs':12,'minimum_correct_solutions':4}),('maximum_execution_seconds',1201)]:
                changed={**plan,key:value};atomic(folder/'plan.json',changed)
                with self.assertRaises(ValidationError):verify(folder)
            changed=copy.deepcopy(plan);changed['material_inventory']['../outside.json']='0'*64
            atomic(folder/'plan.json',changed)
            with self.assertRaises(ValidationError):verify(folder)


if __name__=='__main__':unittest.main()
