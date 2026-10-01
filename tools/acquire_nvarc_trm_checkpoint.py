"""Download only the source-named public TRM checkpoint, pinned Dataset v1."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.execute_nvarc_overnight_sft import token,client_for
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest


def acquire():
    folder=ROOT/'.irisx/nvarc-original/materials/trm-published-031-20261002'
    metadata=json.loads((folder/'provider-metadata.json').read_bytes())
    inventory=json.loads((folder/'version-1-first-page.json').read_bytes())
    expected=2159719349;name='step_220708'
    if (metadata['ref']!='cpmpml/arc-prize-trm-031' or metadata['currentVersionNumber']!=1 or
            inventory.get('nextPageToken') or
            {row['name']:row['totalBytes'] for row in inventory['datasetFiles']}.get(name)!=expected or
            (folder/'acquisition.json').exists() or (folder/name).exists()):
        raise ValueError('new exact public TRM Dataset-v1 checkpoint acquisition required')
    if shutil.disk_usage(folder).free<expected+2*1024**3:raise ValueError('TRM checkpoint disk reserve differs')
    ledger={'owner_decision':'Decision 0053','dataset':'cpmpml/arc-prize-trm-031/1','file':name,
        'expected_bytes':expected,'provider_metadata_sha256':sha_file(folder/'provider-metadata.json'),
        'download_reserved':1,'maximum_download_seconds':3600,'model_calls':0,'checkpoint_loaded':False,
        'notebook_v18_verified':False,'maximum_paid_usd':0,'state':'downloading'}
    atomic(folder/'acquisition.json',ledger)
    started=time.monotonic();written=0;digest=hashlib.sha256()
    try:
        request=ApiDownloadDatasetRequest();request.owner_slug='cpmpml';request.dataset_slug='arc-prize-trm-031'
        request.dataset_version_number=1;request.file_name=name;request.raw=True
        with client_for(token()) as client:
            with client.datasets.dataset_api_client.download_dataset(request) as response:
                response.raise_for_status()
                with (folder/name).open('xb') as stream:
                    for chunk in response.iter_content(1024**2):
                        if time.monotonic()-started>3600:raise TimeoutError('bounded TRM artifact download expired')
                        written+=len(chunk)
                        if written>expected:raise ValueError('TRM artifact exceeds exact provider size')
                        stream.write(chunk);digest.update(chunk)
        if written!=expected:raise ValueError('raw TRM checkpoint byte count differs')
        ledger.update(state='verified-published-checkpoint-bytes',bytes=written,sha256=digest.hexdigest(),
            elapsed_seconds=time.monotonic()-started,claim='source-linked published checkpoint; no runtime/quality/v18 parity claim')
        atomic(folder/'acquisition.json',ledger)
        print(json.dumps(ledger),flush=True)
    except BaseException as error:
        ledger.update(state='incomplete-retained',bytes_received=written,error_type=type(error).__name__,
            elapsed_seconds=time.monotonic()-started)
        atomic(folder/'acquisition.json',ledger)
        raise


if __name__=='__main__':acquire()
