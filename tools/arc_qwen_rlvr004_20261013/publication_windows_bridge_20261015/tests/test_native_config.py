"""Pure schema negatives, not a native Windows/credential admission test."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, patch

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


def recovery_document():
    d=document();d['format']=m.RECOVERY_FORMAT
    d['sources']['recovery_boot_probe.py']={'bytes':1,'sha256':'e'*64}
    d['recovery']={'capability_sha256':'1'*64,'reservation_sha256':'2'*64,
      'challenge':'3'*64,'host_install_sha256':'4'*64,
      'last_boot_utc':'2026-10-15T08:00:00.000000Z','expires_epoch':time.time()+600,
      'allowed_operations':['open','dataset','kernel','status','close']}
    return d


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


class RecoveryConfigTests(unittest.TestCase):
    def test_distinct_format_exact_eight_sources(self):
        d=recovery_document();self.assertIs(m.validate_document(d),d)
        self.assertEqual(len(d['sources']),8)
        self.assertEqual(len(m.SOURCE_NAMES),7)
        for field in ('format','recovery','sources'):
            bad=copy.deepcopy(d)
            if field=='format':bad['format']=m.FORMAT
            elif field=='recovery':del bad['recovery']
            else:del bad['sources']['recovery_boot_probe.py']
            with self.subTest(field=field),self.assertRaises(ValueError):m.validate_document(bad)
    def test_no_unknown_mode_or_legacy_recovery_source(self):
        for value in ('recovery','',None,True):
            d=document();d['format']=value
            with self.subTest(value=value),self.assertRaises(ValueError):m.validate_document(d)
        d=document();d['sources']['recovery_boot_probe.py']={'bytes':1,'sha256':'e'*64}
        with self.assertRaises(ValueError):m.validate_document(d)
    def test_closed_recovery_fields_and_exact_operations(self):
        for key in recovery_document()['recovery']:
            d=recovery_document();del d['recovery'][key]
            with self.subTest(key=key),self.assertRaises(ValueError):m.validate_document(d)
        for change in ({'mode':'ignore_unknown'},{'allowed_operations':['open','dataset','kernel','status','close','save']},
                       {'allowed_operations':['close','status','kernel','dataset','open']},
                       {'allowed_operations':('open','dataset','kernel','status','close')},
                       {'challenge':'raw-host-id'},{'capability_sha256':True},{'reservation_sha256':'A'*64}):
            d=recovery_document();d['recovery'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):m.validate_document(d)
    def test_expiry_and_boot_time_are_finite_canonical(self):
        for value in (True,0,-1,1e11+1,float('inf'),float('nan'),'123'):
            d=recovery_document();d['recovery']['expires_epoch']=value
            with self.subTest(value=value),self.assertRaises(ValueError):m.validate_document(d)
        for value in ('2026-10-15T08:00:00Z','2026-10-15T08:00:00.000000+00:00',
                      '2026-99-15T08:00:00.000000Z','2100-10-15T08:00:00.000000Z'):
            d=recovery_document();d['recovery']['last_boot_utc']=value
            with self.subTest(value=value),self.assertRaises(ValueError):m.validate_document(d)
    def test_expired_configuration_fails_before_native_or_credentials(self):
        d=recovery_document();d['recovery']['expires_epoch']=time.time()-1
        runtime=m.NativeRuntime(d,'unused','a'*64,None)
        with self.assertRaisesRegex(ValueError,'native_recovery_expired'):runtime.verify_runtime()
    def runtime_probe(self, updates=None):
        d=recovery_document()
        # This synthetic pinned module makes no native query; the production
        # observer has its own tests. Here we verify caller binding and freshness.
        source=('from datetime import datetime, timezone\nimport json\n'
          'def observe_boot(challenge, *, expected_source_sha256, expected_runtime_sha256, timeout_seconds):\n'
          '    value={"challenge":challenge,"host_install_sha256":'+repr('4'*64)+',\n'
          '        "last_boot_utc":"2026-10-15T08:00:00.000000Z",\n'
          '        "source_sha256":expected_source_sha256,"runtime_sha256":expected_runtime_sha256,\n'
          '        "observed_utc":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}\n'
          '    value.update('+repr(updates or {})+')\n'
          '    return value\n'
          'def canonical_bytes(value): return json.dumps(value).encode()\n'
          'def validate_observation(value, **kwargs): return json.loads(value.decode())\n').encode()
        d['sources']['recovery_boot_probe.py']={'bytes':len(source),'sha256':hashlib.sha256(source).hexdigest()}
        runtime=m.NativeRuntime(d,'unused','a'*64,None)
        runtime.verify_runtime=Mock()
        runtime.read_source=Mock(return_value=source)
        return runtime
    def observe(self,runtime,**overrides):
        kwargs={'deadline_epoch':time.time()+100,'max_seconds':100,'monotonic_deadline':time.monotonic()+100}
        kwargs.update(overrides)
        return runtime.verify_recovery_boot(**kwargs)
    def test_fresh_probe_source_loaded_and_checked_each_time(self):
        runtime=self.runtime_probe()
        self.observe(runtime);self.observe(runtime)
        self.assertEqual(runtime.read_source.call_count,2)
        self.assertEqual(runtime.verify_runtime.call_count,4)
    def test_real_observer_validator_contract_with_synthetic_observe_only(self):
        source=P.with_name('recovery_boot_probe.py').read_bytes()
        source+=b'''
def observe_boot(challenge, *, expected_source_sha256, expected_runtime_sha256, timeout_seconds=15):
    now=datetime.now(timezone.utc)
    boot='2026-10-15T08:00:00.000000Z'
    return {'format':FORMAT,'ok':True,'challenge':challenge,'host_install_sha256':'4'*64,
        'observed_utc':now.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),'last_boot_utc':boot,
        'tick_count64_ms':int((now-_timestamp(boot)).total_seconds()*1000),
        'windows_version':'10.0.26100','windows_build':'26100',
        'source_sha256':expected_source_sha256,'runtime_sha256':expected_runtime_sha256,
        'native_process_closure_verified':True,'closure':dict(CLOSURE),**SAFE_FACTS}
'''
        runtime=self.runtime_probe()
        runtime.document['sources']['recovery_boot_probe.py']={'bytes':len(source),'sha256':hashlib.sha256(source).hexdigest()}
        runtime.read_source.return_value=source
        self.assertTrue(self.observe(runtime)['native_process_closure_verified'])
    def test_probe_bytes_bound_before_execution(self):
        runtime=self.runtime_probe();runtime.read_source.return_value+=b'\n'
        with self.assertRaisesRegex(ValueError,'native_recovery_probe_source'):self.observe(runtime)
    def test_cached_wrong_host_boot_challenge_and_source_fail(self):
        for change in ({'observed_utc':'2026-10-15T08:01:00.000000Z'},
                       {'host_install_sha256':'5'*64},{'last_boot_utc':'2026-10-15T08:02:00.000000Z'},
                       {'challenge':'6'*64},{'source_sha256':{}},{'runtime_sha256':{}}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.observe(self.runtime_probe(change))
    def test_original_lease_cannot_be_extended_or_nonfinite(self):
        runtime=self.runtime_probe()
        for change in ({'deadline_epoch':runtime.recovery['expires_epoch']+1},
                       {'deadline_epoch':time.time()-1},{'deadline_epoch':float('nan')},
                       {'max_seconds':float('inf')},{'max_seconds':True},
                       {'monotonic_deadline':time.monotonic()-1},{'monotonic_deadline':float('nan')}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.observe(runtime,**change)

if __name__=='__main__':unittest.main()
