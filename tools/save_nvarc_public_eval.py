"""Decision 0060: one journaled QUICK_SAVE per package; no runtime query or run API."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from tools.nvarc_public_eval import RUNS, sha
from tools.nvarc_native_multitask import write, digest, require
from tools.stage_nvarc_public_eval import preflight
from tools.execute_nvarc_overnight_sft import token, client_for, utc, bindings


def request(package):
    from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
    from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
    plan = json.loads((package/'plan.json').read_bytes()); meta = json.loads((package/'kernel/kernel-metadata.json').read_bytes())
    require(plan['run_id'] in RUNS.values() and plan['owner_editor_only'] is True and
        plan['agent_execution_authorized'] is False and meta['is_private'] is True and
        meta['enable_internet'] is False and meta['id'] == 'danielwuu/'+plan['run_id'], 'exact private owner save required')
    notebook = json.loads((package/'kernel/notebook.ipynb').read_bytes())
    for cell in notebook['cells']:
        if isinstance(cell['source'], list): cell['source'] = ''.join(cell['source'])
        if cell['cell_type'] == 'code':
            require(cell['execution_count'] is None and cell['outputs'] == [], 'unexecuted notebook required')
    fields = dict(slug=meta['id'], new_title=meta['title'], text=json.dumps(notebook, ensure_ascii=False),
        language='python', kernel_type='notebook', is_private=True, enable_gpu=True, enable_tpu=False,
        enable_internet=False, session_timeout_seconds=plan['maximum_notebook_wall_seconds'],
        dataset_data_sources=meta['dataset_sources'], competition_data_sources=meta['competition_sources'],
        kernel_data_sources=meta['kernel_sources'], model_data_sources=meta['model_sources'],
        machine_shape='NvidiaL4', docker_image=meta['docker_image'])
    req = ApiSaveKernelRequest()
    for key, value in fields.items(): setattr(req, key, value)
    req.kernel_execution_type = KernelExecutionType.QUICK_SAVE
    wire = req.to_dict()
    require(wire['kernelExecutionType'] == 'QUICK_SAVE' and wire['isPrivate'] is True and
        wire.get('enableInternet', False) is False and wire['sessionTimeoutSeconds'] == plan['maximum_notebook_wall_seconds'] and
        wire['slug'] == 'danielwuu/'+plan['run_id'] and wire['newTitle'] == plan['run_id'] and
        wire['machineShape'] == 'NvidiaL4', 'exact SDK QUICK_SAVE wire required')
    return req, wire


def execute(action, package, journal):
    package, journal = Path(package), Path(journal); checked = preflight(package)
    plan = json.loads((package/'plan.json').read_bytes()); run = plan['run_id']
    parent = ROOT/'.irisx/nvarc-public-eval/runs'/run
    require(package.resolve() == (parent/'package-l4').resolve() and
        journal.resolve() == (parent/'editor-save').resolve(), 'fixed run/package/journal path required')
    journal.mkdir(parents=True, exist_ok=True)
    ledger, request_path, reservation, receipt_path = [journal/name for name in
        ('save-ledger.json', 'save-request.json', 'save-reserved.json', 'save-receipt.json')]
    req, wire = request(package)
    if action == 'init':
        require(not any(p.exists() for p in (ledger, request_path, reservation, receipt_path)), 'one offline initialization required')
        write(journal/'preflight.json', checked); write(request_path, wire)
        write(ledger, {'run_id': run, 'owner_decision': 'Decision 0060', 'execution_type': 'QUICK_SAVE',
            'push_reserved': 0, 'status_checks_reserved': 0, 'retrieval_reserved': 0,
            'agent_execution_authorized': False, 'bindings': bindings(package),
            'request_sha256': sha(request_path), 'prepared_utc': utc()})
        print(json.dumps(checked)); return
    require(action == 'save' and not reservation.exists() and not receipt_path.exists(), 'sole save already consumed')
    value = json.loads(ledger.read_bytes())
    require(value['bindings'] == bindings(package) and value['request_sha256'] == sha(request_path) and
        wire == json.loads(request_path.read_bytes()) and value['push_reserved'] == 0 and
        value['status_checks_reserved'] == value['retrieval_reserved'] == 0, 'journal/package/request differs')
    # Exclusive reservation precedes even credential refresh. A crash cannot resend.
    with reservation.open('xb') as stream:
        stream.write(json.dumps({'run_id': run, 'plan_digest': digest(plan), 'request_sha256': sha(request_path),
            'reserved_utc': utc(), 'execution_type': 'QUICK_SAVE'}, sort_keys=True).encode())
        stream.flush(); os.fsync(stream.fileno())
    value.update(push_reserved=1, outcome='reserved-no-retry'); write(ledger, value)
    sends = []
    try:
        access = token()
        with client_for(access) as client:
            http = client.http_client(); http._init_session(); session = http._session; original = session.send
            def exact_send(prepared, **kwargs):
                require(prepared.method == 'POST' and
                    prepared.url == 'https://api.kaggle.com/v1/kernels.KernelsApiService/SaveKernel' and
                    not sends and json.loads(prepared.body) == wire, 'one exact QUICK_SAVE send required')
                sends.append('SaveKernel/QUICK_SAVE'); return original(prepared, **kwargs)
            session.send = exact_send
            response = client.kernels.kernels_api_client.save_kernel(req)
            receipt = response.to_dict(); write(receipt_path, receipt)
            invalid = any(receipt.get(k) for k in
                ('invalidDatasetSources', 'invalidCompetitionSources', 'invalidKernelSources', 'invalidModelSources'))
            accepted = (not response.error and response.version_number == 1 and not invalid and
                response.url == 'https://www.kaggle.com/code/danielwuu/'+run)
            value.update(accepted=accepted, provider_version=response.version_number, url=response.url,
                outcome='accepted' if accepted else 'rejected-or-uncertain-no-retry', sends=len(sends),
                completed_utc=utc(), receipt_sha256=sha(receipt_path)); write(ledger, value)
            print(json.dumps(receipt)); require(accepted, 'rejected/uncertain QUICK_SAVE; no retry')
    except Exception as error:
        value.update(sends=len(sends), error_type=type(error).__name__, completed_utc=utc())
        if value.get('accepted') is None: value['outcome'] = 'failed-or-uncertain-no-retry'
        if getattr(error, 'response', None) is not None: value['http_status'] = error.response.status_code
        write(ledger, value)
        raise SystemExit('QUICK_SAVE failed or uncertain: '+type(error).__name__+'; identity frozen')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('init', 'save'))
    parser.add_argument('--package', type=Path, required=True); parser.add_argument('--journal', type=Path, required=True)
    args = parser.parse_args(); execute(args.action, args.package, args.journal)
