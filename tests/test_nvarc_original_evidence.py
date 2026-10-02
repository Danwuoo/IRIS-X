"""Rehashed hostile evidence and source grid-contract controls, offline."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.reconcile_nvarc_published_yield import inspect_pairs
from tools.verify_nvarc_qwen3_probe import verify,check_architecture
from tools.audit_nvarc_sdg_programs import inspect_program


class OriginalEvidenceTests(unittest.TestCase):
    def test_legacy_and_modern_rotary_config_require_same_original_value(self):
        config={'model_type':'qwen3','vocab_size':16,'num_hidden_layers':36,'hidden_size':2560,
            'num_attention_heads':32,'num_key_value_heads':8,'head_dim':128,'intermediate_size':9728,
            'tie_word_embeddings':True,'attention_dropout':0}
        check_architecture({**config,'rope_theta':5000000})
        check_architecture({**config,'rope_parameters':{'rope_theta':5000000,'rope_type':'default'}})
        for params in ({'rope_theta':1000000,'rope_type':'default'},{'rope_theta':5000000,'rope_type':'dynamic'}):
            with self.assertRaises(ValidationError):check_architecture({**config,'rope_parameters':params})

    def test_static_source_entry_contract_never_executes_host_code(self):
        code="raise RuntimeError('must never run on host')\ndef generate_puzzle_output(grid):\n return grid"
        self.assertEqual(inspect_program(code,'generate_puzzle_output')['state'],'one-argument-contract')
        wrong='def generate_puzzle_output(grid,shape):\n return grid'
        self.assertEqual(inspect_program(wrong,'generate_puzzle_output')['state'],'one-argument-rejected')
        self.assertEqual(inspect_program('def broken(', 'generate_puzzle_output')['state'],'python-syntax-rejected')
        self.assertEqual(inspect_program('async def generate_puzzle_output(grid):\n return grid',
            'generate_puzzle_output')['state'],'async-entry')

    def test_source_pair_contract_rejects_boolean_ragged_and_short_data(self):
        pairs=[{'input':[[i%10,(i+1)%10]],'output':[[(i+2)%10,(i+3)%10]]} for i in range(12)]
        # Independent predicate accepts variety, making schema/color checks
        # independently observable instead of duplicating source validation.
        self.assertEqual(inspect_pairs(pairs,lambda grids:True)['issues'],[])
        for grid in ([[True,1]],[[1,2],[3]]):
            changed=[{**row,'input':grid} for row in pairs]
            self.assertIn('input-grid-contract',inspect_pairs(changed,lambda grids:True)['issues'])
        self.assertIn('below-source-minimum-twelve-pairs',inspect_pairs(pairs[:11],lambda grids:True)['issues'])
        self.assertEqual(inspect_pairs({'input':[[0]]},lambda grids:True)['issues'],['pair-schema'])

    def test_closed_failure_evidence_and_rehashed_cost_attack(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);package=root/'package';package.mkdir()
            plan={'run_id':'nvarc-original-qwen3-probe-001','maximum_outer_forwards':13,
                'maximum_input_tokens':344,'actual_model_input_tokens_per_pass':100}
            for name,value in [('plan.json',plan),('samples.json',[]),('stage-summary.json',{'payload_sha256':{'runtime':'abc'}})]:
                (package/name).write_text(json.dumps(value),encoding='utf-8')
            values={'plan.json':plan,'payload-bindings.json':{'runtime':'abc'},
                'terminal.json':{'run_id':plan['run_id'],'outcome':'failed','phase':'model-probe',
                    'error_type':'RuntimeError','error_message':'native backend unavailable','contains_evaluator_truth':False},
                'worker/worker-ledger.json':[{'stage':'tiny-independent-gradients','reserved_forwards':2,
                    'reserved_input_tokens':22,'cumulative_forwards':2,'cumulative_input_tokens':22}]}
            def write():
                raw={name:json.dumps(value).encode() for name,value in values.items()}
                manifest={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'members':[
                    {'path':name,'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()} for name,value in raw.items()]}
                path=root/'result.zip'
                with zipfile.ZipFile(path,'w') as archive:
                    archive.writestr('manifest.json',json.dumps(manifest))
                    for name,value in raw.items():archive.writestr(name,value)
                return path
            proof=verify(write(),package)
            self.assertEqual(proof['reserved_outer_forwards'],2)
            self.assertEqual(proof['outcome'],'failed')
            # The attacker recomputes every ZIP digest, so rejection must come
            # from the independently reconstructed cost prefix.
            values['worker/worker-ledger.json'][0]['cumulative_forwards']=1
            with self.assertRaises(ValidationError):verify(write(),package)
            values['worker/worker-ledger.json'][0]['cumulative_forwards']=2
            values['payload-bindings.json']['runtime']='foreign'
            with self.assertRaises(ValidationError):verify(write(),package)


if __name__=='__main__':unittest.main()
