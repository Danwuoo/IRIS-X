"""Real Parquet static coverage and immutable prefix recovery, no exec."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import pyarrow as pa
import pyarrow.parquet as pq
from irisx.arc_nvarc_datasets import sha_file
from irisx.canonical import canonical_bytes
from tools import audit_nvarc_sdg_programs as analysis


class WholeStaticRecoveryTests(unittest.TestCase):
    def test_every_row_and_immutable_prefix_recovery_without_repeated_ast(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);space=root/'.irisx/nvarc-original'
            material=space/'materials/sdg-artifacts-20261002-resume-001';material.mkdir(parents=True)
            profile=space/'manifests/sdg-full-profile-20261002-001';profile.mkdir(parents=True)
            key={'mix_name':'mix','summary_name1':'one','summary_name2':'two',
                'puzzle_name1':'11111111','puzzle_name2':'22222222'}
            # A top-level exception must stay inert even in the complete pass.
            code="raise RuntimeError('never execute fixture')\ndef generate_puzzle_output(grid): return grid"
            values={'inputs':[{**key,'completion':'```python\ndef generate_puzzle_input(seed): return [[seed]]\n```'},
                              {**key,'completion':'missing Python fence'}],
                    'outputs':[{**key,'sid':0,'completion':'```python\n'+code+'\n```'},
                               {**key,'sid':1,'completion':'```python\ndef generate_puzzle_output(grid, shape): return grid\n```'}]}
            members=[]
            with zipfile.ZipFile(material/'nvarc-artifacts-puzzles.zip','w') as archive:
                for stage,rows in values.items():
                    path=material/(stage+'.parquet');pq.write_table(pa.Table.from_pylist(rows),path)
                    raw=path.read_bytes();name=stage+'/data-00000.parquet';archive.writestr(name,raw)
                    members.append({'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
            members += [{'path':f'summaries/fixture-{i:03d}','bytes':0,'sha256':hashlib.sha256(b'').hexdigest()} for i in range(190)]
            (material/'archive-inventory.json').write_bytes(canonical_bytes({'member_count':192,'members':members}))
            (material/'acquisition.json').write_bytes(canonical_bytes({'state':'verified-published-raw-artifacts',
                'inventory_sha256':sha_file(material/'archive-inventory.json')}))
            parent={'parent_ids':['11111111','22222222'],'exposure_tags':['evaluation','protected']}
            (profile/'parent-lineage.jsonl').write_bytes(canonical_bytes(parent,newline=True))
            (profile/'profile.json').write_bytes(canonical_bytes({'parent_lineage_sha256':sha_file(profile/'parent-lineage.jsonl'),
                'rows_by_stage':{'inputs':2,'outputs':2}}))
            manifest=root/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json';manifest.parent.mkdir(parents=True)
            manifest.write_bytes((analysis.ROOT/'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes())
            full=root/'full'
            with patch.object(analysis,'ROOT',root):analysis.audit(full)
            report=json.loads((full/'report.json').read_bytes())
            self.assertEqual(report['rows_by_stage'],{'inputs':2,'outputs':2})
            self.assertEqual(report['states_by_stage']['outputs'],{'one-argument-contract':1,'one-argument-rejected':1})
            frozen=root/'frozen';frozen.mkdir()
            for name in ('analysis-source.py','analysis-source-binding.json'):
                (frozen/name).write_bytes((full/name).read_bytes())
            prefix=(full/'programs.jsonl').read_bytes().splitlines(keepends=True)[:1]
            (frozen/'programs.jsonl').write_bytes(b''.join(prefix));(frozen/'members.jsonl').write_bytes(b'')
            ledger=json.loads((full/'ledger.json').read_bytes())
            ledger.update(state='incomplete-retained',program_rows_completed=1,members_reserved=1,members_completed=0)
            (frozen/'ledger.json').write_bytes(canonical_bytes(ledger))
            previous={p.name:sha_file(p) for p in frozen.iterdir()}
            resumed=root/'resumed'
            with patch.object(analysis,'ROOT',root),patch.object(analysis,'inspect_program',wraps=analysis.inspect_program) as inspect:
                analysis.audit(resumed,frozen)
                self.assertEqual(inspect.call_count,3)
            recovered=json.loads((resumed/'report.json').read_bytes())
            self.assertEqual((recovered['carried_static_diagnostics'],recovered['new_static_diagnostics']),(1,3))
            self.assertEqual((resumed/'programs.jsonl').read_bytes(),(full/'programs.jsonl').read_bytes())
            self.assertEqual(previous,{p.name:sha_file(p) for p in frozen.iterdir()})
            for key in ('states_by_stage','output_solution_count_histogram','exposure_response_counts'):
                self.assertEqual(recovered[key],report[key])
            self.assertEqual(recovered['generated_program_executions'],0)
            self.assertFalse(recovered['program_semantics_verified'])


if __name__=='__main__':unittest.main()
