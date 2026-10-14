"""Offline auth lifecycle tests. All clients/credentials are synthetic objects."""
from datetime import datetime,timezone,timedelta
import contextlib
from pathlib import Path
import sys
import time
import types
import unittest
from unittest import mock
import test_native_transport as fixtures
from test_native_transport import load,HERE,sha

# Reuse fixture setup only; avoid re-running inherited tests.
class NativeAuthTests(unittest.TestCase):
    setUp=fixtures.NativeTransportTests.setUp
    bind=fixtures.NativeTransportTests.bind

    @contextlib.contextmanager
    def opened(self):
        import requests
        self.bind();c=self.t._common;auth=load('native_auth_lifecycle_'+self._testMethodName,HERE/'native_auth.py')
        clients=[]
        class Client:
            def __init__(self):
                self.session=requests.Session();self.closed=False
                self.http=types.SimpleNamespace(_session=self.session,_prepare_response=lambda kind,response:response)
                clients.append(self)
            def __enter__(self):return self
            def __exit__(self,*args):self.session.close();self.closed=True
            def http_client(self):return self.http
        class Credentials:
            refreshes=0;fail=False
            def __init__(self):self._access_token_expiration=datetime.now(timezone.utc)-timedelta(seconds=1)
            def get_username(self):return 'danielwuu'
            def access_token_has_expired(self):return False
            def refresh_access_token(self):
                type(self).refreshes+=1
                if type(self).fail:raise RuntimeError('synthetic renewal timeout')
                self._access_token_expiration=datetime.now(timezone.utc)+timedelta(hours=12)
            def delete(self,*args,**kwargs):raise AssertionError('delete must never be invoked')
        creds=Credentials()
        class Api:
            def get_config_value(self,name):return {'username':'danielwuu','auth_method':'OAUTH'}.get(name)
            def build_kaggle_client(self):return Client()
            def _authenticate_with_oauth_creds(self):
                if creds.access_token_has_expired():creds.refresh_access_token()
                return True
        class Redirect:pass
        modules={'kagglesdk':types.SimpleNamespace(KaggleClient=Client,KaggleCredentials=Credentials),'kaggle':types.SimpleNamespace(api=Api()),'kagglesdk.common.types.http_redirect':types.SimpleNamespace(HttpRedirect=Redirect)}
        original_enter=Client.__enter__;original_expired=Credentials.access_token_has_expired;original_bound=c.bound_sdk_client
        session=auth.OfficialSession(None,vars(c))
        try:
            with mock.patch.dict(sys.modules,modules),mock.patch.object(auth,'verify_sdk',return_value=(self.root,{})),mock.patch.object(c,'credential_guard'):
                session.open();yield session,creds,Credentials,clients,c
        finally:
            session.close()
            self.assertIs(Client.__enter__,original_enter);self.assertIs(Credentials.access_token_has_expired,original_expired)
            self.assertIs(c.bound_sdk_client,original_bound)
            self.assertTrue(all(client.closed for client in clients))
            self.assertFalse(any(isinstance(f,auth.ReviewedSdkFinder) for f in sys.meta_path))

    def test_preexpiry_renewal_journal_and_resource_counters_preserved(self):
        with self.opened() as (session,creds,cls,clients,c):
            creds._access_token_expiration=datetime.now(timezone.utc)+timedelta(seconds=200)
            self.assertTrue(creds.access_token_has_expired())
            session.mutations['SaveKernel']=1;session.next_renew=0;session.renew_if_due()
            self.assertEqual(cls.refreshes,1);self.assertEqual(session.mutations['SaveKernel'],1)
            self.assertTrue(clients[0].closed);self.assertFalse(clients[-1].closed)
            claims=list(c.STATE.glob('native-auth-refresh-*.claim.json'));self.assertEqual(len(claims),1)
            journal=c.obj(c.STATE/(claims[0].name[:-len('.claim.json')]+'-journal.json'))
            self.assertEqual(journal['stage'],'refresh_accepted');self.assertEqual(journal['claim_sha256'],sha(claims[0]))
            self.assertFalse(journal['new_grant_created']);self.assertGreater(journal['new_expiration_epoch'],time.time()+300)
            session.next_renew=0;session.renew_if_due();self.assertEqual(cls.refreshes,1)

    def test_unknown_refresh_is_durable_and_never_retried(self):
        with self.opened() as (session,creds,cls,clients,c):
            cls.fail=True;session.next_renew=0
            with self.assertRaises(c.AuthRefreshUncertain):session.renew_if_due()
            self.assertEqual(cls.refreshes,1)
            with self.assertRaisesRegex(ValueError,'unknown_reconcile_only'):session.renew_if_due()
            self.assertEqual(cls.refreshes,1)

    def test_unclaimed_refresh_and_delete_blocked(self):
        import requests
        with self.opened() as (session,creds,cls,clients,c):
            request=requests.Request('POST','https://api.kaggle.com/v1/users.AccountService/GenerateAccessToken').prepare()
            with self.assertRaisesRegex(ValueError,'unclaimed_auth_refresh'):session.client.session.send(request)
            with self.assertRaisesRegex(ValueError,'deletion_not_authorized'):creds.delete()

    def test_native_store_mode_only_and_foreign_environment_rejection(self):
        self.bind();c=self.t._common;configuration=c.CONFIG
        module=sys.modules['reviewed_rl_local_config_'+c.CONFIG_SOURCE_SHA256]
        base=configuration.native_wrapper.parent;store=base/'home/.kaggle';store.mkdir(parents=True)
        credential=store/'credentials.json';credential.write_text('SYNTHETIC NEVER PARSED');credential.chmod(0o600)
        original_read=Path.read_bytes
        with mock.patch.object(sys,'prefix',str(base/'venv')),mock.patch.dict('os.environ',{'HOME':str(base/'home'),'KAGGLE_CONFIG_DIR':str(store)},clear=True),mock.patch.object(Path,'read_bytes',autospec=True,side_effect=lambda p: (_ for _ in ()).throw(AssertionError('credential body read')) if p==credential else original_read(p)):
            result=module.credential_guard(configuration);self.assertFalse(result['credential_contents_inspected'])
            credential.chmod(0o644)
            with self.assertRaisesRegex(ValueError,'store_mode'):module.credential_guard(configuration)
            credential.chmod(0o600)
            alternate=store/'access_token.txt';alternate.write_text('SYNTHETIC NEVER PARSED')
            with self.assertRaisesRegex(ValueError,'alternate_credential_store'):module.credential_guard(configuration)
            alternate.unlink()
            with mock.patch.dict('os.environ',{'KAGGLE_API_TOKEN':'SYNTHETIC'}):
                with self.assertRaisesRegex(ValueError,'alternate_auth'):module.credential_guard(configuration)

if __name__=='__main__':unittest.main(verbosity=2)
