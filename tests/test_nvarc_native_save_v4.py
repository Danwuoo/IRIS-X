"""Exact owner save approval never upgrades unknown resource/session facts."""
import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import save_nvarc_native_multitask as save
from tools import stage_nvarc_native_multitask as stage
from tools.nvarc_native_multitask import canonical


def admission():
    value={
        'format':save.EXPORT_SAVE_ADMISSION_FORMAT,'run_id':save.EXPORT_SAVE_RUN,
        'reviewed_run_id':save.EXPORT_REVIEW_RUN,'reviewed_plan_digest':save.EXPORT_REVIEW_PLAN,
        'reviewed_notebook_sha256':save.EXPORT_REVIEW_NOTEBOOK,'source_commit':save.EXPORT_SOURCE_COMMIT,
        'control_review_sha256':save.REVIEW_SHA,'maximum_paid_usd':0,'local_resource_admission':False,
        'ui_operator':'user','private':True,'internet':False,
        'owner_clearance_ref':'Decision 0058; owner instruction: 提交',
        'quick_save_authorized':True,'maximum_quick_saves':1,'agent_execution_authorized':False,
        'resource_information_status':'unavailable',
        'resource_information_unavailable':list(save.UNAVAILABLE_EXPORT_FACTS),
        'owner_resource_exception_ref':save.EXPORT_SAVE_REF,
        'owner_resource_exception_sha256':save.sha(save.ROOT/save.EXPORT_SAVE_REF),
    }
    value.update({key:None for key in save.UNAVAILABLE_EXPORT_FACTS})
    return value


class NativeSaveV4Tests(unittest.TestCase):
    def test_exact_review_allows_save_with_unknown_facts_and_preserves_v3(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'admission.json';value=admission();path.write_bytes(canonical(value))
            self.assertEqual(stage.admission_for(path,save.EXPORT_SAVE_RUN),value)
            self.assertFalse(value['local_resource_admission'])
            self.assertTrue(all(value[k] is None for k in save.UNAVAILABLE_EXPORT_FACTS))
        old=save.paths(save.RESOURCE_EXCEPTION_RUN)[1]/'controller-admission.json'
        self.assertEqual(save.validate_admission(old,save.RESOURCE_EXCEPTION_RUN)['format'],
                         save.SAVE_ONLY_ADMISSION_FORMAT)

    def test_scope_bindings_and_fabricated_resource_facts_rejected(self):
        # Unit-check invalid fields without asserting retained review provenance.
        real_sha = save.sha
        with patch.object(save, 'sha', side_effect=lambda path:
                save.REVIEW_SHA if path == save.REVIEW_FILE else real_sha(path)), \
             patch.object(stage, 'preflight', side_effect=AssertionError(
                 'invalid admission must fail before retained-package preflight')):
            base=admission()
            changes={
                'run_id':'nvarc-original-qwen3-native-multitask-011','reviewed_run_id':save.RESOURCE_EXCEPTION_REVIEW_RUN,
                'reviewed_plan_digest':'sha256:'+'0'*64,'reviewed_notebook_sha256':'0'*64,
                'source_commit':save.REVIEW_COMMIT,'control_review_sha256':'0'*64,
                'maximum_paid_usd':1,'local_resource_admission':True,'private':False,'internet':True,
                'quick_save_authorized':False,'maximum_quick_saves':2,'agent_execution_authorized':True,
                'owner_clearance_ref':'older approval','resource_information_status':'available',
                'resource_information_unavailable':list(save.UNAVAILABLE_QUOTA_FIELDS),
                'owner_resource_exception_ref':save.RESOURCE_EXCEPTION_REF,
                'owner_resource_exception_sha256':'0'*64,
                'reserved_quota_hours':2.5,'quota_observed_at':'2026-10-04T23:00:00+08:00',
                'l4_quota_multiplier':2,'quota_reservation_id':'invented',
                'prior_sessions_reconciled':True,'owner_editor_sessions_closed':True,
            }
            for key,value in changes.items():
                with self.subTest(key=key):
                    changed=copy.deepcopy(base);changed[key]=value
                    with self.assertRaisesRegex(RuntimeError, 'only exact owner-authorized'):save.validate_export_save_admission(changed,save.EXPORT_SAVE_RUN)
            with self.assertRaises(RuntimeError):save.validate_export_save_admission(base,'nvarc-original-qwen3-native-multitask-011')

    def test_format_field_closure_and_unavailable_list_order_required(self):
        # Unit-check invalid fields without asserting retained review provenance.
        real_sha = save.sha
        with patch.object(save, 'sha', side_effect=lambda path:
                save.REVIEW_SHA if path == save.REVIEW_FILE else real_sha(path)), \
             patch.object(stage, 'preflight', side_effect=AssertionError(
                 'invalid admission must fail before retained-package preflight')):
            for change in ('extra','missing','format','order'):
                value=admission()
                if change=='extra':value['resource_sufficient']=True
                elif change=='missing':del value['owner_editor_sessions_closed']
                elif change=='format':value['format']=save.SAVE_ONLY_ADMISSION_FORMAT
                else:value['resource_information_unavailable'].reverse()
                with self.subTest(change=change),self.assertRaisesRegex(RuntimeError, 'only exact owner-authorized'):
                    save.validate_export_save_admission(value,save.EXPORT_SAVE_RUN)


if __name__=='__main__':unittest.main()
