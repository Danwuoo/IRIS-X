"""Keep original ordered parents, SIDs and defaults separate from semantics."""
from collections import defaultdict
import unittest
from tools.audit_nvarc_sdg_published_groups import update_group,bind_member,summarize
from irisx.arc_nvarc_sdg_artifacts import KEYS
from irisx.errors import ValidationError


class PublishedGroupJoinTests(unittest.TestCase):
    def response(self,stage,sid=None,reverse=False,mix='mix1'):
        parents=['00000001','00000002']
        if reverse:parents.reverse()
        return {'stage':stage,'sid':sid,'join_key':dict(zip(KEYS,[mix,'summary1','summary1',*parents])),
            'parent_ids':sorted(parents),'exposure_tags':['public-training-only'],
            'filtered':False,'program_semantics_verified':False}

    def test_direction_and_multiple_mix_candidates_remain_explicit_unknowns(self):
        groups={};by_order=defaultdict(list)
        for reverse,mix,count in ((False,'mix1',10),(False,'mix2',20),(True,'mix1',20)):
            update_group(groups,self.response('inputs',reverse=reverse,mix=mix))
            for sid in range(count):update_group(groups,self.response('outputs',sid,reverse,mix))
        for key in groups:by_order[key[-2:]].append(key)
        member={'path':'nvarc_training/00000001/00000001_00000002.json','sha256':'a'*64,'pair_count':30,
            'ordered_parent_ids':['00000001','00000002'],'parent_ids':['00000001','00000002'],
            'exposure_tags':['public-training-only'],'filtered':False,'program_semantics_verified':False}
        bound=bind_member(member,groups,by_order)
        self.assertEqual([row['output_responses'] for row in bound['same_order_groups']],[10,20])
        self.assertEqual(bound['reversed_order_group_count'],1)
        self.assertTrue(bound['selection_of_historical_mix_unknown'])
        self.assertFalse(bound['historical_generation_cli_known'])
        report=summarize([bound],20)
        self.assertEqual(report['default_minimum_output_response_coverage'],{'has_group_at_source_default':1})
        self.assertFalse(report['program_semantics_verified'])
        self.assertFalse(report['source_8_12_4_filter_replayed'])

    def test_duplicate_or_bool_sid_exposure_and_duplicate_input_rejected(self):
        import copy
        groups={};update_group(groups,self.response('inputs'));update_group(groups,self.response('outputs',0))
        before=copy.deepcopy(groups)
        for row in (self.response('outputs',0),self.response('outputs',True),self.response('inputs')):
            with self.assertRaises(ValidationError):update_group(groups,row)
            self.assertEqual(groups,before)
        row=self.response('outputs',1);row['exposure_tags']=[]
        with self.assertRaises(ValidationError):update_group(groups,row)

    def test_ten_program_group_cannot_be_called_default_twenty_or_semantic_pass(self):
        bound={'path':'nvarc_full/a/a_b.json','pair_count':12,'same_order_groups':[{'output_responses':10}]}
        report=summarize([bound],20)
        self.assertEqual(report['default_minimum_output_response_coverage'],{'no_group_at_source_default':1})
        self.assertEqual(report['published_pair_count'],12)
        self.assertFalse(report['historical_generation_cli_known'])
        self.assertEqual(report['generated_program_executions'],0)


if __name__=='__main__':unittest.main()
