"""Requests trust regression with synthetic CA identity and mocked HTTP sends."""
import os
from pathlib import Path
import types
import unittest
from unittest import mock
import test_portable_transport as fixtures


class PortableTlsTests(unittest.TestCase):
    setUp = fixtures.PortableTransportTests.setUp
    rewrite_config = fixtures.PortableTransportTests.rewrite_config

    def launch_environment(self):
        launcher = fixtures.load('portable_tls_' + self._testMethodName, fixtures.HERE / 'launch.py')
        return launcher.plan(['publish', 'validate', '--local-config', str(self.config_path),
                              '--local-config-sha', fixtures.sha(self.config_path)])[2]

    def ca_fixture(self):
        ca = self.root / 'synthetic-ca.pem'
        ca.write_bytes(b'SYNTHETIC IDENTITY ONLY; NO TLS HANDSHAKE\n')
        self.config['runtime']['requests_ca_bundle'] = {'path': str(ca), 'sha256': fixtures.sha(ca)}
        self.rewrite_config(self.config)
        return ca

    def test_default_requests_verification_remains_enabled(self):
        import requests
        environment = self.launch_environment()
        self.assertNotIn('REQUESTS_CA_BUNDLE', environment)
        with mock.patch.dict(os.environ, environment, clear=True), requests.Session() as session:
            settings = session.merge_environment_settings('https://api.kaggle.com/', {}, None, None, None)
            self.assertIs(settings['verify'], True)
            self.assertIsNone(settings['cert'])

    def test_existing_bundle_and_proxy_are_preserved_without_fallback(self):
        import requests
        ca = self.ca_fixture()
        with mock.patch.dict(os.environ, {'REQUESTS_CA_BUNDLE': str(ca), 'HTTPS_PROXY': 'http://proxy.invalid:8443',
                                          'https_proxy': 'http://proxy.invalid:8443',
                                          'NO_PROXY': 'localhost,127.0.0.1', 'no_proxy': 'localhost,127.0.0.1'}):
            environment = self.launch_environment()
        self.assertEqual(environment['REQUESTS_CA_BUNDLE'], str(ca))
        with mock.patch.dict(os.environ, environment, clear=True), requests.Session() as session:
            settings = session.merge_environment_settings('https://api.kaggle.com/', {}, None, None, None)
            self.assertEqual(settings['verify'], str(ca))
            self.assertEqual(settings['proxies']['https'], 'http://proxy.invalid:8443')
            self.assertIsNone(settings['cert'])
            self.assertEqual(session.merge_environment_settings('https://localhost/', {}, None, None, None)['proxies'], {})

    def test_bundle_selection_change_and_insecure_overrides_rejected(self):
        ca = self.ca_fixture()
        for environment in ({}, {'REQUESTS_CA_BUNDLE': 'False'}, {'REQUESTS_CA_BUNDLE': str(ca), 'PYTHONHTTPSVERIFY': '0'},
                            {'REQUESTS_CA_BUNDLE': str(ca), 'CURL_CA_BUNDLE': str(ca)},
                            {'REQUESTS_CA_BUNDLE': str(ca), 'REQUESTS_CLIENT_CERT': '/synthetic/key'}):
            with self.subTest(environment=sorted(environment)), mock.patch.dict(os.environ, {'HOME': str(self.home), **environment}, clear=True):
                with self.assertRaises(ValueError):
                    self.launch_environment()
        ca.write_bytes(b'changed synthetic bytes')
        with mock.patch.dict(os.environ, {'REQUESTS_CA_BUNDLE': str(ca)}), self.assertRaisesRegex(ValueError, 'bytes'):
            self.launch_environment()

    def test_all_four_sdk_and_storage_send_paths_keep_verification(self):
        import requests
        ca = self.ca_fixture()
        with mock.patch.dict(os.environ, {'REQUESTS_CA_BUNDLE': str(ca)}):
            environment = self.launch_environment()
        calls = []
        def send(_session, request, **kw):
            calls.append(request)
            self.assertEqual(kw['verify'], str(ca))
            self.assertFalse(kw['allow_redirects'])
            response = mock.Mock(headers={'Content-Type': 'application/octet-stream', 'Content-Length': '3'}, status_code=200)
            response.iter_content.return_value = iter([b'abc'])
            return response
        common = self.t._common
        with mock.patch.dict(os.environ, environment, clear=True), mock.patch.object(requests.Session, 'send', autospec=True, side_effect=send):
            with requests.Session() as session:
                common.bound_sdk_client(types.SimpleNamespace(http_client=lambda: types.SimpleNamespace(_session=session)), {})
                request = requests.Request('POST', 'https://api.kaggle.com/v1/kernels.KernelsApiService/GetKernel').prepare()
                session.send(request, **session.merge_environment_settings(request.url, {}, None, None, None))
            payload = self.root / 'synthetic.zip'; payload.write_bytes(b'abc')
            common.upload_once('https://storage.googleapis.com/synthetic/test.zip', payload)
            redirect = mock.Mock(headers={'Location': 'https://storage.googleapis.com/synthetic/test.zip'})
            common.binary_get(redirect, self.root / 'download.zip', 3, expected_size=3)
            redirect = mock.Mock(headers={'Location': 'https://storage.googleapis.com/synthetic/test.zip'})
            common.binary_metadata(redirect, 3, 3)
        self.assertEqual(len(calls), 4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
