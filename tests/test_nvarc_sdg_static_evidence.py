"""Independent static recount retains ancestors and rejects altered bindings."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError
from tools.verify_nvarc_sdg_static import recount


class StaticEvidenceTests(unittest.TestCase):
    def test_every_retained_member_row_parent_and_counter_without_execution(self):
        parent={'parent_ids':['11111111','22222222'],'exposure_tags':['evaluation','protected'],
            'records_by_stage':{'inputs':1,'outputs':2}}
        join={'mix_name':'mix','summary_name1':'one','summary_name2':'two',
            'puzzle_name1':'11111111','puzzle_name2':'22222222'}
        base={'join_key':join,'parent_ids':parent['parent_ids'],'exposure_tags':parent['exposure_tags'],
            'completion_sha256':'a'*64,'code_sha256':'b'*64,'filtered':False,'program_semantics_verified':False}
        diagnosed={**base,'state':'one-argument-contract','imports':['numpy'],'positional_parameters':['grid'],
            'required_positional_parameters':1,'has_varargs':False,'accepts_one_positional_argument':True,'function_count':1}
        rows=[{**diagnosed,'member':'inputs/data-00000.parquet','stage':'inputs','row':0,'sid':None},
            {**diagnosed,'member':'outputs/data-00000.parquet','stage':'outputs','row':0,'sid':0},
            {**base,'member':'outputs/data-00000.parquet','stage':'outputs','row':1,
                'state':'python-syntax-rejected','sid':1}]
        members=[{'path':'inputs/data-00000.parquet','rows_verified':1},
            {'path':'outputs/data-00000.parquet','rows_verified':2}]
        parents={tuple(parent['parent_ids']):parent}
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            def write(values):
                raw=b''.join(canonical_bytes(row,newline=True) for row in values)
                (folder/'programs.jsonl').write_bytes(raw);return raw
            raw=write(rows);result=recount(folder,members,parents)
            self.assertEqual(result['program_rows_sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(result['rows_by_stage'],{'inputs':1,'outputs':2})
            self.assertEqual(result['output_solution_count_histogram'],{'2':1})
            self.assertEqual(result['exposure_response_counts'],{'evaluation':3,'protected':3})
            self.assertEqual(result['states_by_stage']['outputs'],{'one-argument-contract':1,'python-syntax-rejected':1})
            for key,value in (('exposure_tags',[]),('row',1),('state','dynamic-success'),
                    ('program_semantics_verified',True),('filtered',True),('code_sha256',None),('unexpected_plaintext','foreign')):
                changed=copy.deepcopy(rows);changed[0][key]=value;write(changed)
                with self.subTest(key=key),self.assertRaises(ValidationError):recount(folder,members,parents)
            write(rows[:-1])
            with self.assertRaises(ValidationError):recount(folder,members,parents)
            write(rows[::-1])
            with self.assertRaises(ValidationError):recount(folder,members,parents)


if __name__=='__main__':unittest.main()
