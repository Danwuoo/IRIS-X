"""Retain the pinned published SDG artifact archive without executing programs."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.execute_nvarc_overnight_sft import token,client_for
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import inventory_archive,sha_file
from kagglesdk.datasets.types.dataset_api_service import ApiListDatasetFilesRequest


def acquire():
    folder=ROOT/'.irisx/nvarc-original/materials/sdg-artifacts-20261002'
    metadata=json.loads((folder/'provider-metadata.json').read_bytes())
    if metadata['ref']!='sorokin/nvarc-artifacts-puzzles' or metadata['currentVersionNumber']!=1:
        raise ValueError('pinned published SDG artifact version differs')
    if (folder/'acquisition.json').exists() or (folder/'nvarc-artifacts-puzzles.zip').exists():
        raise ValueError('new pinned archive acquisition required')
    if shutil.disk_usage(folder).free < metadata['totalBytes'] + 20*1024**3:
        raise ValueError('archive would consume the model/runtime disk reserve')
    files=json.loads((folder/'version-1-first-page.json').read_bytes())
    entries=list(files['datasetFiles']);page=files.get('nextPageToken','')
    with client_for(token()) as client:
        for index in range(1,40):
            if not page:break
            req=ApiListDatasetFilesRequest();req.owner_slug='sorokin';req.dataset_slug='nvarc-artifacts-puzzles'
            req.dataset_version_number=1;req.page_size=100;req.page_token=page
            files=client.datasets.dataset_api_client.list_dataset_files(req).to_dict()
            atomic(folder/f'version-1-page-{index+1}.json',files)
            entries.extend(files['datasetFiles']);page=files.get('nextPageToken','')
    if page or len({entry['name'] for entry in entries})!=len(entries):
        raise ValueError('closed SDG provider inventory differs')
    expected={entry['name']:entry['totalBytes'] for entry in entries}
    if sum(expected.values())!=metadata['totalBytes']:raise ValueError('SDG version-1 provider byte sum differs')
    atomic(folder/'provider-closed-inventory.json',expected)
    ledger={'owner_decision':'Decision 0053','dataset':'sorokin/nvarc-artifacts-puzzles/1',
        'provider_metadata_sha256':sha_file(folder/'provider-metadata.json'),'file_count':len(expected),
        'provider_raw_bytes':sum(expected.values()),'download_reserved':1,'maximum_download_seconds':5400,
        'model_calls':0,'program_executions':0,'maximum_paid_usd':0,'state':'downloading'}
    atomic(folder/'acquisition.json',ledger)
    command=[sys.executable,'-m','kaggle','datasets','download','-d','sorokin/nvarc-artifacts-puzzles/1',
        '-p',str(folder),'--quiet']
    started=time.monotonic()
    try:
        with (folder/'download.log').open('wb') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            ledger['local_download_pid']=process.pid;atomic(folder/'acquisition.json',ledger)
            try:code=process.wait(timeout=5400)
            finally:
                if process.poll() is None:
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                    process.wait(timeout=15)
        if code:raise ValueError('pinned SDG download process failed; retain its local diagnostic')
        ledger['state']='inventory-verification';atomic(folder/'acquisition.json',ledger)
        report=inventory_archive(folder/'nvarc-artifacts-puzzles.zip',folder/'archive-inventory.json')
        if {item['path']:item['bytes'] for item in report['members']}!=expected:
            raise ValueError('downloaded SDG archive differs from exact version-1 file inventory')
        ledger.update(state='verified-published-raw-artifacts',archive_sha256=report['archive_sha256'],
            archive_bytes=report['archive_bytes'],raw_bytes=report['uncompressed_bytes'],
            inventory_sha256=sha_file(folder/'archive-inventory.json'),crc_verified=True,
            extracted=False,elapsed_seconds=time.monotonic()-started)
        atomic(folder/'acquisition.json',ledger)
        print(json.dumps(ledger),flush=True)
    except BaseException as error:
        ledger.update(state='incomplete-retained',error_type=type(error).__name__,elapsed_seconds=time.monotonic()-started)
        atomic(folder/'acquisition.json',ledger)
        raise


if __name__=='__main__':acquire()
