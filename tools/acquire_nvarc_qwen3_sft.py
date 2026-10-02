"""Exact source-linked published ARC-SFT model; no pickle or remote code.

Metadata and member downloads have separate finite ledgers. The published
checkpoint is not a reproduction of its training or a clean quality result.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from irisx.errors import ValidationError
from tools.execute_nvarc_overnight_sft import token,client_for

REF='sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1'
DEFAULT=ROOT/'.irisx/nvarc-original/materials/qwen3-published-sft139-20261002-001'


def request_base(cls):
    from kagglesdk.models.types.model_api_service import ModelFramework
    request=cls();request.owner_slug='sorokin';request.model_slug='qwen3_4b_grids15_sft139'
    request.framework=ModelFramework.MODEL_FRAMEWORK_TRANSFORMERS;request.instance_slug='bfloat16'
    return request


def profile(folder):
    from kagglesdk.models.types.model_api_service import ApiGetModelInstanceRequest,ApiListModelInstanceVersionFilesRequest
    if folder.exists():raise ValidationError('new immutable published-model identity required')
    folder.mkdir(parents=True);ledger={'owner_decision':'Decision 0054','ref':REF,
        'metadata_requests_reserved':0,'maximum_metadata_requests':6,'download_requests_reserved':0,
        'model_calls':0,'paid_usd':0,'state':'profiling'}
    atomic(folder/'profile-ledger.json',ledger)
    try:
        with client_for(token()) as client:
            ledger['metadata_requests_reserved']+=1;atomic(folder/'profile-ledger.json',ledger)
            metadata=client.models.model_api_client.get_model_instance(request_base(ApiGetModelInstanceRequest)).to_dict()
            atomic(folder/'provider-instance.json',metadata)
            pages=[];page=''
            for index in range(5):
                request=request_base(ApiListModelInstanceVersionFilesRequest)
                request.version_number=1;request.page_size=100
                if page:request.page_token=page
                ledger['metadata_requests_reserved']+=1;atomic(folder/'profile-ledger.json',ledger)
                response=client.models.model_api_client.list_model_instance_version_files(request)
                data=response.to_dict();atomic(folder/f'files-page-{index}.json',data);pages.append(data)
                page=response.next_page_token
                if not page:break
            if page:raise ValidationError('published model inventory pagination exceeds bound')
        ledger.update(state='metadata-retained',pages=len(pages));atomic(folder/'profile-ledger.json',ledger)
        print(json.dumps({'state':ledger['state'],'metadata':metadata,'pages':pages}),flush=True)
    except BaseException as error:
        ledger.update(state='failed-retained',error_type=type(error).__name__);atomic(folder/'profile-ledger.json',ledger);raise


def acquire(folder):
    from kagglesdk.models.types.model_api_service import ApiDownloadModelInstanceVersionRequest
    ledger_path=folder/'acquisition.json'
    profile=json.loads((folder/'profile-ledger.json').read_bytes())
    if ledger_path.exists() or profile['state']!='metadata-retained' or profile['ref']!=REF:
        raise ValidationError('exact new published-model download required')
    pages=[json.loads((folder/f'files-page-{i}.json').read_bytes()) for i in range(profile['pages'])]
    metadata=json.loads((folder/'provider-instance.json').read_bytes())
    if (metadata['id']!=472720 or metadata['versionId']!=627758 or metadata['versionNumber']!=1 or
            metadata['slug']!='bfloat16' or metadata['framework']!='MODEL_FRAMEWORK_TRANSFORMERS'):
        raise ValidationError('exact notebook model instance version differs')
    entries={row['name']:row for page in pages for row in page['files']}
    if len(entries)!=sum(len(page['files']) for page in pages) or not 1<=len(entries)<=30:
        raise ValidationError('closed published model file inventory differs')
    for name,row in entries.items():
        if (re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:json|safetensors|j2|txt)',name) is None or
                type(row['size']) is not int or not 0<row['size']<=5*1024**3):
            raise ValidationError('published safe model filename/size differs')
    total=sum(row['size'] for row in entries.values())
    if total!=metadata['totalUncompressedBytes'] or total>9*1024**3 or shutil.disk_usage(folder).free<total+8*1024**3:
        raise ValidationError('published model disk/work reserve differs')
    target=folder/'model';target.mkdir()
    ledger={'owner_decision':'Decision 0054','ref':REF,'maximum_download_seconds':3600,
        'maximum_paid_usd':0,'model_calls':0,'expected_total_bytes':total,
        'inventory_bindings':{p.name:sha_file(p) for p in folder.glob('files-page-*.json')},
        'members':[],'state':'downloading'}
    atomic(ledger_path,ledger);started=time.monotonic()
    try:
        with client_for(token()) as client:
            for name,row in sorted(entries.items()):
                event={'path':name,'expected_bytes':row['size'],'request_reserved':True,'bytes_received':0}
                ledger['members'].append(event);atomic(ledger_path,ledger)
                request=request_base(ApiDownloadModelInstanceVersionRequest);request.version_number=1;request.path=name
                digest=hashlib.sha256();written=0
                with client.models.model_api_client.download_model_instance_version(request) as response:
                    response.raise_for_status()
                    with (target/name).open('xb') as stream:
                        for chunk in response.iter_content(1024**2):
                            if time.monotonic()-started>3600:raise TimeoutError('published model download ceiling reached')
                            written+=len(chunk)
                            if written>row['size']:raise ValidationError('published model file exceeds provider bytes')
                            stream.write(chunk);digest.update(chunk);event['bytes_received']=written
                if written!=row['size']:raise ValidationError('published raw model file size differs')
                event.update(sha256=digest.hexdigest(),complete=True);atomic(ledger_path,ledger)
                print(json.dumps({'member_verified':name,'bytes':written}),flush=True)
        ledger.update(state='complete-published-bytes',elapsed_seconds=time.monotonic()-started)
        atomic(ledger_path,ledger)
    except BaseException as error:
        ledger.update(state='incomplete-retained',error_type=type(error).__name__,elapsed_seconds=time.monotonic()-started)
        atomic(ledger_path,ledger);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('profile','acquire'))
    parser.add_argument('--folder',type=Path,default=DEFAULT)
    args=parser.parse_args();(profile if args.action=='profile' else acquire)(args.folder)
