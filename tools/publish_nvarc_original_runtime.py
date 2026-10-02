"""One private exact original-checkpoint runtime Dataset, without model work."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from irisx.canonical import digest_value
from irisx.errors import ValidationError

REF='danielwuu/irisx-nvarc-original-qwen3-ttt-runtime-001'


def publish(root):
    journal=root/'dataset-ledger.json';manifest=json.loads((root/'manifest.json').read_bytes())
    acquisition=json.loads((root/'acquisition.json').read_bytes())
    if (journal.exists() or acquisition['state']!='verified-published-wheel-bytes' or
            acquisition['manifest_sha256']!=sha_file(root/'manifest.json') or
            digest_value(manifest['inventory'])!=manifest['material_digest']):
        raise ValidationError('new private publication of exact verified runtime material required')
    folder=root/'dataset';folder.mkdir()
    for name,row in manifest['inventory'].items():
        path=root/name
        if path.stat().st_size!=row['bytes'] or sha_file(path)!=row['sha256'] or path.is_symlink():
            raise ValidationError('verified immutable runtime wheel differs')
        os.link(path,folder/name)
    atomic(folder/'runtime-manifest.json',manifest)
    atomic(folder/'dataset-metadata.json',{'id':REF,'title':'IRIS-X original Qwen3 TTT runtime 001',
        'licenses':[{'name':'other'}],'description':'Private runtime wheels. Original package licenses inside each immutable wheel govern its contents.'})
    staged={p.name:{'bytes':p.stat().st_size,'sha256':sha_file(p)} for p in folder.iterdir()}
    ledger={'owner_decision':'Decision 0054','dataset_id':REF,'dataset_version':1,'create_reserved':1,
        'status_checks_reserved':0,'maximum_status_checks':6,'maximum_paid_usd':0,'is_private':True,
        'material_digest':manifest['material_digest'],'staged_inventory':staged,'state':'create-reserved',
        'model_calls':0,'optimizer_steps':0,'generations':0}
    atomic(journal,ledger)
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api=KaggleApi();api.authenticate()
        response=api.dataset_create_new(str(folder),public=False,quiet=True,convert_to_csv=False)
        receipt=response.to_dict() if hasattr(response,'to_dict') else response
        atomic(root/'dataset-receipt.json',receipt)
        if not (isinstance(receipt,dict) and receipt.get('status','').lower()=='ok' and not receipt.get('error') and
                receipt.get('url')=='https://www.kaggle.com/datasets/'+REF):
            raise ValidationError('exact private Dataset receipt not confirmed; no repeat create')
        ledger.update(state='accepted-private-version-1',receipt_sha256=sha_file(root/'dataset-receipt.json'))
        atomic(journal,ledger);return {'dataset_id':REF,'state':ledger['state'],'model_calls':0,'maximum_paid_usd':0}
    except BaseException as error:
        ledger.update(state='create-outcome-not-confirmed-no-repeat',error_type=type(error).__name__)
        atomic(journal,ledger);raise


def status(root):
    journal=root/'dataset-ledger.json';ledger=json.loads(journal.read_bytes())
    if ledger['dataset_id']!=REF or ledger['create_reserved']!=1 or ledger['status_checks_reserved']>=6:
        raise ValidationError('exact bounded private runtime status allowance required')
    ledger['status_checks_reserved']+=1;atomic(journal,ledger)
    from kaggle.api.kaggle_api_extended import KaggleApi
    api=KaggleApi();api.authenticate()
    raw=json.loads(api.dataset_status(REF,format='json'))
    atomic(root/f"dataset-status-{ledger['status_checks_reserved']:02d}.json",raw)
    ledger.update(last_status=raw);atomic(journal,ledger)
    return {'dataset_id':REF,'status':raw}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('publish','status'));parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();print(json.dumps((publish if args.action=='publish' else status)(args.root)))
