"""Reuse historical synthetic interfaces against successor functions, unmodified inputs.

These are parser/model-metadata/archive/TTT/public-bridge checks, not successor
execution or provider evidence. Historical content is never relabeled.
"""
import importlib.util
from pathlib import Path
import sys
import unittest
VALIDATION=Path(__file__).resolve().parents[1]
OLD=VALIDATION.parents[1]/'portfolio63-next-20261012'
sys.path.insert(0,str(VALIDATION))
import validate_transfer_outputs as v

def load_tests(loader,tests,pattern):
    if not (OLD/'validation-tests').is_dir():
        def omitted():raise unittest.SkipTest('67 historical sibling interface tests require the preserved historical package')
        tests.addTest(unittest.FunctionTestCase(omitted));return tests
    for name,classes in [('test_validation',['StaticFixtures']),('test_model_material',['MaterialMetadata']),('test_phase_boundaries',['PhaseBoundaries']),('test_public_content',['PublicContent'])]:
        path=OLD/'validation-tests'/(name+'.py');spec=importlib.util.spec_from_file_location('_inherited_'+name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        if module.v is not v:raise AssertionError('inherited fixture used wrong validator')
        for cls in classes:tests.addTests(loader.loadTestsFromTestCase(getattr(module,cls)))
    return tests
