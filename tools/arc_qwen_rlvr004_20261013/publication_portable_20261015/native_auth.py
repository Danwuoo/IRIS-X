"""Use official API authentication without inspecting or copying token values.

All imports/authentication happen after the reviewed runtime, installed-source and
store metadata checks. The official API alone loads, refreshes and supplies its
credentials. No sign-in, OAuth grant, alternate credential, or token export exists.
"""
from pathlib import Path
import hashlib
import importlib.metadata
import importlib.abc
import importlib.machinery
import json
import math
import os
import sys
import time

LOCK_SHA256 = '3d447ab7fad280fcc378fd18b57c3792c5b39798127f583679646027ab73288d'


def verify_sdk(common):
    root=common['configured']().runtime.sdk_root
    common['secure_path'](root)
    common['need'](root==Path(__import__('sysconfig').get_path('purelib')),'official_sdk_sysconfig_root')
    lock_path=Path(__file__).with_name('sdk-lock.json')
    lock=json.loads(common['verified'](lock_path,LOCK_SHA256,cap=1024**2))
    common['need'](lock['format']=='irisx/run008-native-sdk-source-lock-v1','sdk_lock_schema')
    for name,version in lock['distributions'].items():
        distribution=importlib.metadata.distribution(name)
        common['need'](distribution.version==version,'sdk_distribution_version')
        origin=Path(distribution.locate_file(''))
        common['secure_path'](origin)
        common['need'](origin==root,'sdk_distribution_outside_bound_root')
    actual={}
    for package in ('kaggle','kagglesdk'):
        package_root=root/package;common['secure_path'](package_root)
        common['need'](package_root.is_dir(),'official_sdk_package_missing')
        for path in package_root.rglob('*.py'):
            common['secure_path'](path)
            relative=path.relative_to(root).as_posix()
            digest=lock['sources'].get(relative)
            common['need'](digest is not None,'official_sdk_source_closure')
            raw=common['verified'](path,digest,cap=16*1024**2)
            actual[relative]=hashlib.sha256(raw).hexdigest()
    common['need'](actual==lock['sources'],'official_sdk_source_closure')
    common['need'](not any(name.split('.')[0] in ('kaggle','kagglesdk') for name in sys.modules),'official_api_must_not_be_preimported')
    return root,lock['sources']


class ReviewedSdkFinder(importlib.abc.MetaPathFinder):
    """Compile each pinned official source directly; ignore all bytecode caches."""
    def __init__(self,root,sources,common):self.root=root;self.sources=sources;self.c=common
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] not in ('kaggle','kagglesdk'):return None
        spec=importlib.machinery.PathFinder.find_spec(fullname,path)
        self.c['need'](spec is not None and spec.origin is not None,'official_sdk_import_missing')
        source=Path(spec.origin);self.c['secure_path'](source)
        self.c['need'](source.is_relative_to(self.root),'official_sdk_import_outside_venv')
        digest=self.sources.get(source.relative_to(self.root).as_posix())
        self.c['need'](digest is not None,'official_sdk_unpinned_import')
        raw=self.c['verified'](source,digest,cap=16*1024**2)
        class SourceOnly(importlib.machinery.SourceFileLoader):
            def get_code(self,unused):return compile(raw,str(source),'exec',dont_inherit=True,optimize=sys.flags.optimize)
        spec.loader=SourceOnly(fullname,str(source));return spec


class OfficialSession:
    """Dedicated process: guard official client's context before API authentication."""
    def __init__(self, module, common):
        self.c=common;self.api=None;self.client=None;self.originals=[]
        self.mutations={};self.refreshing=False;self.next_renew=0;self.finder=None

    def _pending_refresh(self):
        c=self.c
        for path in c['STATE'].glob('native-auth-refresh-*.claim.json'):
            journal=c['STATE']/(path.name[:-len('.claim.json')]+'-journal.json')
            c['need'](journal.is_file(),'auth_refresh_unknown_reconcile_only')
            proof=c['obj'](journal)
            c['need'](proof.get('stage')=='refresh_accepted' and proof.get('claim_sha256')==c['file_sha'](path),'auth_refresh_unknown_reconcile_only')

    def _patch(self,owner,name,value):
        self.originals.append((owner,name,getattr(owner,name)));setattr(owner,name,value)

    def open(self):
        c=self.c;c['credential_guard']();root,sources=verify_sdk(c);self._pending_refresh()
        self.finder=ReviewedSdkFinder(root,sources,c);sys.meta_path.insert(0,self.finder)
        from kagglesdk import KaggleClient,KaggleCredentials
        original_enter=KaggleClient.__enter__
        def enter(client):
            result=original_enter(client)
            if not getattr(client,'_irisx_bound',False):
                try:c['bound_sdk_client'](client,self.mutations)
                except BaseException:client.__exit__(None,None,None);raise
                client._irisx_bound=True
            return result
        self._patch(KaggleClient,'__enter__',enter)
        # Correct the pinned SDK's late-expiry predicate using only expiry metadata.
        # Token retrieval and refresh remain exclusively inside its official methods.
        def expired(creds):
            return not creds._access_token_expiration or time.time()+300>=creds._access_token_expiration.timestamp()
        self._patch(KaggleCredentials,'access_token_has_expired',expired)
        original_refresh=KaggleCredentials.refresh_access_token
        def refresh(creds):
            c['credential_guard']();self._pending_refresh()
            c['need'](creds.get_username()=='danielwuu','native_auth_account')
            expiry=creds._access_token_expiration.timestamp() if creds._access_token_expiration else 0
            c['need'](type(expiry)in(int,float) and math.isfinite(expiry) and expiry>=0,'auth_expiration_invalid')
            name='native-auth-refresh-'+c['sha'](c['canonical']({'account':'danielwuu','old_expiration_epoch':expiry}))[:24]
            claim=c['claim'](name,{'old_expiration_epoch':expiry,'account':'danielwuu','existing_grant_only':True,'time_epoch':time.time()})
            proof={'stage':'refresh_intent','claim_sha256':claim['sha256'],'old_expiration_epoch':expiry,'attempts':1}
            c['journal'](name,proof)
            # A new distinct expiration permits one refresh. Resource counters remain.
            self.mutations.pop('GenerateAccessToken',None);self.refreshing=True
            try:result=original_refresh(creds)
            except BaseException:
                raise c['AuthRefreshUncertain']('official_existing_credential_refresh_uncertain') from None
            finally:self.refreshing=False
            c['credential_guard']()
            new_expiry=creds._access_token_expiration.timestamp() if creds._access_token_expiration else 0
            c['need'](math.isfinite(new_expiry) and new_expiry>time.time()+300,'refreshed_credential_expiration_invalid')
            c['journal'](name,{**proof,'stage':'refresh_accepted','time_epoch':time.time(),'new_expiration_epoch':new_expiry,'new_grant_created':False})
            return result
        self._patch(KaggleCredentials,'refresh_access_token',refresh)
        # Never let the official CLI's 401 fallback delete the owner's credential.
        def no_delete(*args,**kwargs):raise c['GuardError']('credential_deletion_not_authorized')
        self._patch(KaggleCredentials,'delete',no_delete)
        # Restrict refresh RPC to the durably claimed official refresh method.
        original_bound=c['bound_sdk_client']
        def guarded_bound(client,counts):
            original_bound(client,counts)
            send=client.http_client()._session.send
            def guarded(request,**kw):
                if request.url.split('?',1)[0].endswith('/GenerateAccessToken'):
                    c['need'](self.refreshing,'unclaimed_auth_refresh')
                return send(request,**kw)
            client.http_client()._session.send=guarded
        c['bound_sdk_client']=guarded_bound
        self.originals.append((None,'bound_sdk_client',original_bound))
        try:
            # The official package authenticates its singleton internally. No token
            # is read from credentials/config, returned, copied or printed here.
            import kaggle
            self.api=kaggle.api
            c['need'](self.api.get_config_value('username')=='danielwuu','native_api_account')
            c['need'](self.api.get_config_value('auth_method')=='OAUTH','native_official_oauth_required')
            self.client=self.api.build_kaggle_client();self.client.__enter__()
            self._download_response(self.client)
            self.next_renew=time.monotonic()+300
            return self.client
        except BaseException:
            self.close();raise

    def _download_response(self,client):
        from kagglesdk.common.types.http_redirect import HttpRedirect
        original=client.http_client()._prepare_response
        def prepare(kind,response):
            if kind is HttpRedirect and 200<=response.status_code<400:return response
            return original(kind,response)
        client.http_client()._prepare_response=prepare

    def renew_if_due(self):
        if time.monotonic()<self.next_renew:return self.client
        self.c['credential_guard']();self._pending_refresh()
        # Official method refreshes/supplies the token wholly inside official code.
        self.c['need'](self.api._authenticate_with_oauth_creds() is True,'native_oauth_renew_failed')
        self.c['need'](self.api.get_config_value('username')=='danielwuu','native_api_account')
        replacement=self.api.build_kaggle_client()
        try:replacement.__enter__();self._download_response(replacement)
        except BaseException:replacement.__exit__(None,None,None);raise
        old=self.client;self.client=replacement;old.__exit__(None,None,None)
        self.next_renew=time.monotonic()+300
        return self.client

    def close(self):
        try:
            if self.client is not None:self.client.__exit__(None,None,None);self.client=None
        finally:
            for owner,name,original in reversed(self.originals):
                if owner is None:self.c[name]=original
                else:setattr(owner,name,original)
            self.originals.clear()
            if self.finder is not None and self.finder in sys.meta_path:sys.meta_path.remove(self.finder)
            self.finder=None
