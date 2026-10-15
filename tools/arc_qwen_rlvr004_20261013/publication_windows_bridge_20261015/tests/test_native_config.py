"""Pure schema negatives, not a native Windows/credential admission test."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

P=Path(__file__).parents[1]/'native_config.py'
spec=importlib.util.spec_from_file_location('native_config_schema_test',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def document():
    return {'format':m.FORMAT,'account':'danielwuu',
      'identity':{'sid':'S-1-5-21-111-222-333-1001','profile':r'C:\Users\Synthetic'},
      'runtime':{'executable':{'path':r'C:\Work\venv\Scripts\python.exe','sha256':'a'*64},
        'base_executable':{'path':r'C:\Python312\python.exe','sha256':'b'*64},
        'pyvenv_cfg_sha256':'c'*64,'venv_prefix':r'C:\Work\venv',
        'sdk_root':r'C:\Work\venv\Lib\site-packages','python_version':[3,12,10]},
      'source_root':r'C:\Work\bridge','sources':{n:{'bytes':1,'sha256':'d'*64} for n in m.SOURCE_NAMES},
      'versions':{'code_predecessor':20,'code':21,'inactive_predecessor':39,'inactive':40,'active':41},
      'network_environment_sha256':{},'requests_ca_bundle':None}


class NativeConfigSchema(unittest.TestCase):
    def test_closed_valid_schema(self):
        d=document();self.assertIs(m.validate_document(d),d)
    def test_json_duplicate_nonfinite_and_scalar(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}',b'[]'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):m.strict_json(raw)
    def test_size_type(self):
        for raw in ('{}',b'',b' '*(1024**2+1)):
            with self.assertRaises(ValueError):m.strict_json(raw)
    def test_no_extra_top_fields(self):
        d=document();d['credentials']='forbidden'
        with self.assertRaises(ValueError):m.validate_document(d)
    def test_account_and_sid(self):
        for key,value in [('account','other'),('sid','S-1-5-18')]:
            d=document()
            if key=='sid':d['identity'][key]=value
            else:d[key]=value
            with self.assertRaises(ValueError):m.validate_document(d)
    def test_exact_runtime_version_and_bool(self):
        for version in ([3,13,0],[3,12,True],[3,12],['3',12,10]):
            d=document();d['runtime']['python_version']=version
            with self.assertRaises(ValueError):m.validate_document(d)
    def test_base_runtime_required(self):
        for key in ('base_executable','pyvenv_cfg_sha256'):
            d=document();del d['runtime'][key]
            with self.assertRaises(ValueError):m.validate_document(d)
    def test_executable_must_be_in_bound_venv(self):
        d=document();d['runtime']['executable']['path']=r'C:\Other\python.exe'
        with self.assertRaises(ValueError):m.validate_document(d)
    def test_sdk_root_exact(self):
        d=document();d['runtime']['sdk_root']=r'C:\Other\site-packages'
        with self.assertRaises(ValueError):m.validate_document(d)
    def test_paths_reject_unc_ads_dot_relative_control(self):
        for value in (r'\\server\share\x',r'C:\x:stream',r'C:\a\..\b','x',r'C:\x\a.',r'C:\x\a?','C:\\x\x00'):
            with self.subTest(value=value),self.assertRaises(ValueError):m.native_path(value)
    def test_source_exact_closure(self):
        for add in (True,False):
            d=document()
            if add:d['sources']['unknown.py']={'bytes':1,'sha256':'a'*64}
            else:del d['sources']['sdk-lock.json']
            with self.assertRaises(ValueError):m.validate_document(d)
    def test_source_size_hash(self):
        for key,value in [('bytes',True),('bytes',0),('bytes',1024**2+1),('sha256','a'*63)]:
            d=document();d['sources']['protocol.py'][key]=value
            with self.assertRaises(ValueError):m.validate_document(d)
    def test_versions_exact_successors_not_bool(self):
        for key,value in [('active',42),('code',True),('code',2**31)]:
            d=document();d['versions'][key]=value
            with self.assertRaises(ValueError):m.validate_document(d)
    def test_environment_records_only_hashes_of_allowed_keys(self):
        for env in ({'KAGGLE_API_TOKEN':'a'*64},{'HTTPS_PROXY':'raw value'},{'HOME':'a'*64}):
            d=document();d['network_environment_sha256']=env
            with self.assertRaises(ValueError):m.validate_document(d)
    def test_reviewed_ca_requires_absolute_path_and_hash(self):
        for ca in ({'path':'relative.pem','sha256':'a'*64},{'path':r'C:\CA\bundle.pem','sha256':'bad'}):
            d=document();d['requests_ca_bundle']=ca
            with self.assertRaises(ValueError):m.validate_document(d)
    def test_schema_does_not_touch_auth_environment_or_import_sdk(self):
        import sys
        before={x for x in sys.modules if x.split('.')[0] in ('kaggle','kagglesdk')}
        m.validate_document(document())
        self.assertEqual(before,{x for x in sys.modules if x.split('.')[0] in ('kaggle','kagglesdk')})

if __name__=='__main__':unittest.main()
