"""Explicit synthetic metadata-only phase-boundary omission fixtures."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'validation'))
import validate_transfer_outputs as v

class PhaseArchive:
    synthetic=True
    def __init__(self,stage='native-load'):
        self.members={'active-stage.json':{'stage':stage,'status':'closed'}}
    def json(self,name):
        v.need(name in self.members,'missing evidence member: '+name)
        return self.members[name]
    def admitted(self):
        self.members['active-stage.json']['stage']='true-arc-main-then-conditional-public-then-ttt'
        for n in ('model-admission.json','calibration/calibration.json','feasibility.json','dataset/frozen-plan.json','dataset/solver-dataset.json','decoder-policy.json'):self.members[n]={}
        return self

class PhaseBoundaries(unittest.TestCase):
    def test_actual_retained_before_load_failure_phase_and_closure(self):
        root=ROOT/'runtime-delta-evidence-20261012-1251/owned-preload-failure'
        if not root.exists():self.skipTest('retained actual before-load failure absent')
        terminal=v.json_file(root/'terminal-receipt.json');self.assertEqual(terminal['status'],'TRANSFER_FAILED')
        archive=v.ClosedArchive(root/'evidence.zip')
        try:
            v.owned_tree(archive,'owned-tree/',terminal['closure_proof'])
            self.assertFalse(v.validate_phase_artifacts(archive,terminal)['admitted_phase'])
        finally:archive.close()
    def test_closed_before_load_failure_needs_no_forecast(self):
        result=v.validate_phase_artifacts(PhaseArchive(),{'status':'TRANSFER_FAILED','child':{}})
        self.assertFalse(result['admitted_phase']);self.assertFalse(result['performed_main'])
    def test_failed_training_artifact_needs_admission_despite_early_marker(self):
        a=PhaseArchive();a.members['experiment/train-64.json']={}
        with self.assertRaisesRegex(v.ValidationError,'feasibility'):v.validate_phase_artifacts(a,{'status':'TRANSFER_FAILED','child':{}})
    def test_failed_after_admission_may_not_omit_forecast(self):
        a=PhaseArchive().admitted();a.members.pop('feasibility.json')
        with self.assertRaisesRegex(v.ValidationError,'feasibility'):v.validate_phase_artifacts(a,{'status':'TRANSFER_FAILED','child':{}})
    def test_partial_may_not_omit_admission_files(self):
        with self.assertRaisesRegex(v.ValidationError,'feasibility'):v.validate_phase_artifacts(PhaseArchive(),{'status':'TRANSFER_PARTIAL','child':{}})
    def test_not_admitted_may_not_omit_decision(self):
        with self.assertRaisesRegex(v.ValidationError,'feasibility'):v.validate_phase_artifacts(PhaseArchive(),{'status':'TRANSFER_NOT_ADMITTED','child':{}})
    def test_dispatched_public_may_not_omit_forecast(self):
        a=PhaseArchive().admitted();a.members['experiment/public/native/example.json']={}
        with self.assertRaisesRegex(v.ValidationError,'public/forecast'):v.validate_phase_artifacts(a,{'status':'TRANSFER_FAILED','child':{}})
    def test_sealed_public_may_not_omit_forecast(self):
        with self.assertRaisesRegex(v.ValidationError,'public/forecast'):v.validate_phase_artifacts(PhaseArchive(),{'status':'TRANSFER_FAILED','child':{'public_branch':{'status':'PUBLIC_PREDICTIONS_SEALED'}}})
    def test_dispatched_public_needs_admitted_decision(self):
        a=PhaseArchive().admitted();a.members['experiment/public/native/example.json']={};a.members['experiment/public/forecast.json']={'admitted':False}
        with self.assertRaisesRegex(v.ValidationError,'not admitted'):v.validate_phase_artifacts(a,{'status':'TRANSFER_FAILED','child':{}})
    def test_dispatched_ttt_may_not_omit_phase_receipt(self):
        a=PhaseArchive().admitted();a.members['experiment/ttt/example/train.json']={}
        with self.assertRaisesRegex(v.ValidationError,'ttt-predictions'):v.validate_phase_artifacts(a,{'status':'TRANSFER_FAILED','child':{}})
    def test_dispatched_ttt_may_not_omit_forecast(self):
        a=PhaseArchive().admitted();a.members['experiment/ttt/example/train.json']={};a.members['experiment/ttt-predictions-sealed.json']={'status':'TTT_PARTIAL','rows':[]}
        with self.assertRaisesRegex(v.ValidationError,'omitted admission'):v.validate_phase_artifacts(a,{'status':'TRANSFER_FAILED','child':{}})
    def test_dispatched_ttt_needs_admitted_decision(self):
        a=PhaseArchive().admitted();a.members['experiment/ttt-predictions-sealed.json']={'status':'TTT_PARTIAL','rows':[],'forecast':{'admitted':False}}
        with self.assertRaisesRegex(v.ValidationError,'not admitted'):v.validate_phase_artifacts(a,{'status':'TRANSFER_FAILED','child':{}})

if __name__=='__main__':unittest.main()
