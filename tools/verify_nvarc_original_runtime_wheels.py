"""Bind acquired original-checkpoint runtime wheels to exact PyPI releases."""
from __future__ import annotations
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request,urlopen
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from irisx.canonical import digest_value
from irisx.errors import ValidationError

PACKAGES={'peft':'0.21.0','accelerate':'1.10.1','transformers':'4.53.3',
    'huggingface-hub':'0.35.3','tokenizers':'0.21.4','safetensors':'0.8.0','psutil':'7.2.2'}


def verify(folder):
    journal=folder/'acquisition.json'
    if journal.exists():raise ValidationError('new exact wheel acquisition verification required')
    wheels=sorted(folder.glob('*.whl'))
    if len(wheels)!=7:raise ValidationError('closed seven-wheel runtime inventory required')
    ledger={'owner_decision':'Decision 0054','maximum_release_reads':7,'release_reads_reserved':0,
        'maximum_release_bytes':16*1024**2,'maximum_wheel_bytes':32*1024**2,
        'download_method':'pinned pip --no-deps; Linux wheels acquired before release digest reconciliation',
        'pip_http_request_count_independently_retained':False,'model_calls':0,'optimizer_steps':0,
        'maximum_paid_usd':0,'state':'release-verification'}
    atomic(journal,ledger);rows={};seen={}
    try:
        for path in wheels:
            if path.is_symlink() or path.stat().st_size>32*1024**2:raise ValidationError('bounded regular wheel required')
            if not (path.name.endswith('-py3-none-any.whl') or 'manylinux' in path.name and 'x86_64' in path.name):
                raise ValidationError('Kaggle Linux x86_64 or universal Python wheel required')
            with zipfile.ZipFile(path) as archive:
                metadata=[name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
                if len(metadata)!=1:raise ValidationError('unique wheel package metadata required')
                record=BytesParser().parsebytes(archive.read(metadata[0]))
            package=record['Name'].lower().replace('_','-');version=record['Version']
            if PACKAGES.get(package)!=version or package in seen:raise ValidationError('exact runtime package versions required')
            ledger['release_reads_reserved']+=1;atomic(journal,ledger)
            url=f'https://pypi.org/pypi/{package}/{version}/json'
            with urlopen(Request(url,headers={'User-Agent':'IRIS-X-bound-runtime-material'}),timeout=60) as response:
                if response.status!=200 or not response.geturl().startswith('https://pypi.org/pypi/'):
                    raise ValidationError('exact official PyPI release response required')
                raw=response.read(16*1024**2+1)
            if len(raw)>16*1024**2:raise ValidationError('release metadata byte ceiling reached')
            release=json.loads(raw);matches=[row for row in release['urls'] if row['filename']==path.name]
            actual=sha_file(path)
            if (len(matches)!=1 or matches[0]['size']!=path.stat().st_size or
                    matches[0]['digests']['sha256']!=actual or
                    not matches[0]['url'].startswith('https://files.pythonhosted.org/packages/')):
                raise ValidationError('acquired wheel does not match exact published release bytes')
            (folder/(package+'-release.json')).write_bytes(raw)
            rows[path.name]={'bytes':path.stat().st_size,'sha256':actual,'package':package,'version':version,
                'release_url':url,'release_sha256':hashlib.sha256(raw).hexdigest(),'wheel_url':matches[0]['url']}
            seen[package]=version
        if seen!=PACKAGES:raise ValidationError('complete exact runtime inventory differs')
        manifest={'format':'irisx/nvarc-original-checkpoint-runtime-wheels-v1','inventory':rows,
            'material_digest':digest_value(rows),'total_bytes':sum(row['bytes'] for row in rows.values()),
            'transformers_version_from_published_checkpoint':'4.53.3','historical_unsloth_version':None,
            'historical_runtime_lock_reproduced':False,'generated_program_executions':0,'model_calls':0,
            'maximum_paid_usd':0,'private_dataset_created':False}
        atomic(folder/'manifest.json',manifest);ledger.update(state='verified-published-wheel-bytes',
            manifest_sha256=sha_file(folder/'manifest.json'))
        atomic(journal,ledger)
        return {k:manifest[k] for k in ('material_digest','total_bytes','model_calls','private_dataset_created')}
    except BaseException as error:
        ledger.update(state='verification-failed-retained',error_type=type(error).__name__);atomic(journal,ledger);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(verify(args.folder)))
