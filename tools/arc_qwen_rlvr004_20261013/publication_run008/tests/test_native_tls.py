"""CPU-only inherited-CA regression; every HTTP send is mocked, never disabled."""
import ast
from pathlib import Path
import os
import tempfile
import types
import unittest
from unittest import mock
from test_native_transport import HERE,load

class NativeTlsTests(unittest.TestCase):
    def setUp(self):
        self.launch=load('native_tls_launch_'+self._testMethodName,HERE/'launch.py')
        self.common=load('native_tls_common_'+self._testMethodName,HERE/'operator_common.py')
        self.ca=os.environ.get('REQUESTS_CA_BUNDLE')
        self.assertIsNotNone(self.ca,'test requires the existing runtime CA selector')

    def environment(self,**extra):
        parent={'REQUESTS_CA_BUNDLE':self.ca,'SSL_CERT_FILE':self.ca,'HTTPS_PROXY':'http://proxy.invalid:8443','NO_PROXY':'localhost,127.0.0.1',**extra}
        with mock.patch.dict(os.environ,parent,clear=True):
            return self.launch.plan(['publish','--help'])[2]

    def test_requests_ca_and_nonsecret_proxy_selection_propagate_exactly(self):
        import requests
        environment=self.environment(CURL_CA_BUNDLE='/unreviewed/fallback.pem',REQUESTS_CLIENT_CERT='/unreviewed/client.pem',PYTHONHTTPSVERIFY='0')
        self.assertEqual(environment['REQUESTS_CA_BUNDLE'],self.ca)
        self.assertEqual(environment['SSL_CERT_FILE'],self.ca)
        self.assertEqual(environment['HTTPS_PROXY'],'http://proxy.invalid:8443')
        self.assertEqual(environment['NO_PROXY'],'localhost,127.0.0.1')
        self.assertNotIn('CURL_CA_BUNDLE',environment);self.assertNotIn('REQUESTS_CLIENT_CERT',environment)
        self.assertNotIn('PYTHONHTTPSVERIFY',environment)
        with mock.patch.dict(os.environ,environment,clear=True),requests.Session() as session:
            settings=session.merge_environment_settings('https://api.kaggle.com/v1/kernels.KernelsApiService/GetKernel',{},None,None,None)
            self.assertEqual(settings['verify'],self.ca);self.assertIsNone(settings['cert'])
            self.assertEqual(settings['proxies']['https'],'http://proxy.invalid:8443')
            self.assertEqual(session.merge_environment_settings('https://localhost/test',{},None,None,None)['proxies'],{})

    def test_false_missing_changed_and_linked_ca_are_rejected(self):
        for bad in ('False','false','0','','/no/such/ca.pem'):
            with self.subTest(value=bad),mock.patch.dict(os.environ,{'REQUESTS_CA_BUNDLE':bad},clear=True),self.assertRaises((ValueError,OSError)):
                self.launch.plan(['publish','--help'])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'synthetic-not-certificate';p.write_text('synthetic invalid certificate')
            with self.assertRaisesRegex(ValueError,'bytes_changed'):self.launch.existing_requests_ca({'REQUESTS_CA_BUNDLE':str(p)})
            link=Path(d)/'link';link.symlink_to(self.ca)
            with self.assertRaisesRegex(ValueError,'linked_existing'):self.launch.existing_requests_ca({'REQUESTS_CA_BUNDLE':str(link)})

    def test_absent_selector_preserves_requests_default_verification(self):
        import requests
        with mock.patch.dict(os.environ,{},clear=True):environment=self.launch.plan(['publish','--help'])[2]
        self.assertNotIn('REQUESTS_CA_BUNDLE',environment)
        with mock.patch.dict(os.environ,environment,clear=True),requests.Session() as session:
            self.assertIs(session.merge_environment_settings('https://api.kaggle.com/',{},None,None,None)['verify'],True)

    def test_sdk_and_storage_sends_use_verified_existing_bundle(self):
        import requests
        environment=self.environment();calls=[]
        def response(body):
            r=mock.Mock(headers={'Content-Type':'application/octet-stream','Content-Length':str(len(body))},status_code=200)
            r.iter_content.return_value=iter([body]);return r
        def send(_session,request,**kw):
            calls.append((request,kw))
            self.assertEqual(kw['verify'],self.ca)
            self.assertIsNot(kw['verify'],False)
            self.assertFalse(kw['allow_redirects'])
            return response(b'abc')
        with tempfile.TemporaryDirectory() as tmp,mock.patch.dict(os.environ,environment,clear=True),mock.patch.object(requests.Session,'send',autospec=True,side_effect=send):
            with requests.Session() as session:
                client=types.SimpleNamespace(http_client=lambda:types.SimpleNamespace(_session=session))
                self.common.bound_sdk_client(client,{})
                req=requests.Request('POST','https://api.kaggle.com/v1/kernels.KernelsApiService/GetKernel').prepare()
                kw=session.merge_environment_settings(req.url,{},None,None,None);session.send(req,**kw)
            path=Path(tmp)/'synthetic.zip';path.write_bytes(b'abc')
            self.common.upload_once('https://storage.googleapis.com/synthetic/test.zip',path)
            redirect=mock.Mock(headers={'Location':'https://storage.googleapis.com/synthetic/test.zip'})
            self.common.binary_get(redirect,Path(tmp)/'download.zip',3,expected_size=3)
            redirect=mock.Mock(headers={'Location':'https://storage.googleapis.com/synthetic/test.zip'})
            self.common.binary_metadata(redirect,3,3)
        self.assertEqual(len(calls),4)

    def test_reviewed_surface_forbids_verification_disable(self):
        # No supported argument exposes a Requests verification override. Fail
        # regression if any reviewed transport adds verify=False/session.verify=False.
        for filename in ('launch.py','native_auth.py','operator_common.py','rl_transport.py','rl_collect.py'):
            tree=ast.parse((HERE/filename).read_bytes())
            for node in ast.walk(tree):
                if isinstance(node,ast.keyword) and node.arg=='verify':
                    self.assertFalse(isinstance(node.value,ast.Constant) and node.value.value is False,filename)
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='verify' for t in node.targets):
                    self.assertFalse(isinstance(node.value,ast.Constant) and node.value.value is False,filename)
        # Authentication and provider origins stay in their unchanged reviewed files.
        self.assertEqual(self.launch.ENTRY_SHA256['rl_transport.py'],'a4da4850d7a2e44af2d85d4be65e55913a746ddeb66a26238500457911261bac')
        self.assertEqual(self.launch.ENTRY_SHA256['rl_collect.py'],'71603a1eb47b1b7656f2ca6a8f2b2eb6faa99469a27aef63d4f0446828ef3a78')

if __name__=='__main__':unittest.main(verbosity=2)
