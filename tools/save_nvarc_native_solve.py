"""One owner-requested native-solve QUICK_SAVE; never Run All or status/output IO."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.arc_nvarc_combined import atomic, read, sha
from tools.execute_nvarc_overnight_sft import token, client_for, utc, bindings
from tools.stage_nvarc_native_solve import preflight, OWNER_RUN_INSTRUCTION
import re

if sys.flags.optimize:
    raise RuntimeError('optimized Python is not supported for save-only admission checks')


def run_identity(package):
    plan=read(package / 'plan.json');run=plan['run_id']
    assert re.fullmatch(r'nvarc-original-qwen3-native-solve-\d{3}',run)
    assert plan['format']=='irisx/nvarc-native-trained-solve-v1'
    return run


def request_fields(package):
    RUN=run_identity(package)
    plan = read(package / 'plan.json'); meta = read(package / 'kernel/kernel-metadata.json')
    assert plan['run_id'] == RUN and plan['owner_decision'] == 'dots-control-kit-v1.2.0' and plan['owner_execution_instruction_ref']==OWNER_RUN_INSTRUCTION
    assert plan['approved'] is True and plan['maximum_notebook_wall_seconds'] == 3600 and plan['maximum_child_wall_seconds'] == 3000
    assert plan['controller_admission_sha256'] and plan['agent_execution_authorized'] is False and plan['save_helper_status_calls'] == 0
    assert plan['owner_editor_only'] is True and plan['kernel_execution_type'] == 'QUICK_SAVE'
    assert meta['id'] == 'danielwuu/' + RUN and meta['title'] == RUN
    assert meta['is_private'] is True and meta['enable_internet'] is False and meta['enable_gpu'] is True
    notebook = read(package / 'kernel/notebook.ipynb')
    for cell in notebook['cells']:
        assert cell['cell_type'] == 'code' and cell['execution_count'] is None and not cell['outputs']
        if isinstance(cell['source'], list):
            cell['source'] = ''.join(cell['source'])
    return dict(slug=meta['id'], new_title=meta['title'], text=json.dumps(notebook, ensure_ascii=False),
        language='python', kernel_type='notebook', is_private=True, enable_gpu=True,
        enable_tpu=False, enable_internet=False, session_timeout_seconds=3600,
        dataset_data_sources=meta['dataset_sources'], competition_data_sources=meta['competition_sources'],
        kernel_data_sources=meta['kernel_sources'], model_data_sources=meta['model_sources'],
        machine_shape='NvidiaL4', docker_image=meta['docker_image'], kernel_execution_type='QUICK_SAVE')


def request(package):
    RUN=run_identity(package)
    from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
    from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
    req = ApiSaveKernelRequest()
    fields = request_fields(package)
    for key, value in fields.items():
        setattr(req, key, KernelExecutionType.QUICK_SAVE if key == 'kernel_execution_type' else value)
    wire = req.to_dict()
    assert wire['kernelExecutionType'] == 'QUICK_SAVE' and req.kernel_execution_type == KernelExecutionType.QUICK_SAVE
    assert wire['isPrivate'] is True and not wire.get('enableInternet', False)
    assert wire['sessionTimeoutSeconds'] == 3600 and wire['machineShape'] == 'NvidiaL4'
    assert wire['competitionDataSources'] == ['arc-prize-2026-arc-agi-2']
    assert wire['slug'] == 'danielwuu/' + RUN and wire['newTitle'] == RUN
    return req, wire


def execute(action, package, journal_dir):
    RUN=run_identity(package)
    run_root = ROOT / '.irisx/nvarc-original/runs' / RUN
    assert package.resolve() == (run_root / 'package-l4').resolve()
    assert journal_dir.resolve() == (run_root / 'editor-save-final').resolve()
    assert action in {'init', 'save'}
    journal_dir.mkdir(parents=True, exist_ok=True)
    ledger, wire_path, receipt_path = (journal_dir / name for name in
        ('save-ledger.json', 'save-request.json', 'save-receipt.json'))
    checked = preflight(package)
    if action == 'init':
        assert not ledger.exists() and not wire_path.exists() and not receipt_path.exists()
        _, wire = request(package)
        atomic(journal_dir / 'preflight.json', checked)
        atomic(wire_path, wire)
        atomic(ledger, {'owner_decision': 'dots-control-kit-v1.2.0', 'owner_execution_instruction_ref': OWNER_RUN_INSTRUCTION, 'run_id': RUN,
            'execution_type': 'QUICK_SAVE', 'push_reserved': 0, 'status_checks_reserved': 0,
            'retrieval_reserved': 0, 'agent_execution_authorized': False,
            'bindings': bindings(package), 'request_sha256': sha(wire_path), 'prepared_utc': utc(), 'events': []})
        print(json.dumps(checked)); return
    journal = read(ledger)
    assert journal['owner_decision'] == 'dots-control-kit-v1.2.0' and journal['owner_execution_instruction_ref']==OWNER_RUN_INSTRUCTION and journal['run_id'] == RUN
    assert journal['execution_type'] == 'QUICK_SAVE' and journal['agent_execution_authorized'] is False
    assert journal['status_checks_reserved'] == journal['retrieval_reserved'] == journal['push_reserved'] == 0
    assert journal['bindings'] == bindings(package) and journal['request_sha256'] == sha(wire_path)
    assert not receipt_path.exists()
    req, wire = request(package); assert wire == read(wire_path)
    value = token()
    with client_for(value) as client:
        http = client.http_client(); http._init_session(); session = http._session
        original = session.send; sends = []
        def exact_send(prepared, **kwargs):
            assert prepared.method == 'POST' and prepared.url == 'https://api.kaggle.com/v1/kernels.KernelsApiService/SaveKernel'
            assert not sends and json.loads(prepared.body) == wire
            assert json.loads(prepared.body)['kernelExecutionType'] == 'QUICK_SAVE'
            sends.append('SaveKernel/QUICK_SAVE')
            return original(prepared, **kwargs)
        session.send = exact_send
        event = {'action': 'SaveKernel', 'execution_type': 'QUICK_SAVE', 'reserved_utc': utc()}
        journal['push_reserved'] = 1; journal['events'].append(event); atomic(ledger, journal)
        try:
            response = client.kernels.kernels_api_client.save_kernel(req)
            receipt = response.to_dict(); atomic(receipt_path, receipt)
            invalid = any(receipt.get(key) for key in
                ('invalidDatasetSources', 'invalidCompetitionSources', 'invalidKernelSources', 'invalidModelSources'))
            journal.update(accepted=not response.error and response.version_number == 1 and not invalid and
                response.url == 'https://www.kaggle.com/code/danielwuu/' + RUN,
                provider_version=response.version_number, url=response.url)
            event.update(completed_utc=utc(), sends=len(sends), receipt_sha256=sha(receipt_path),
                outcome='accepted' if journal['accepted'] else 'rejected-or-uncertain-no-retry')
            atomic(ledger, journal)
            print(json.dumps({'accepted':journal['accepted'],'provider_version':response.version_number,'url':response.url,'agent_execution_started':False,'status_or_output_calls':0}))
            assert journal['accepted'], 'rejected or uncertain QUICK_SAVE; no retry'
        except Exception as error:
            event.update(completed_utc=utc(), sends=len(sends), error_type=type(error).__name__)
            event.setdefault('outcome', 'uncertain-no-retry')
            if getattr(error, 'response', None) is not None:
                event['http_status'] = error.response.status_code
            atomic(ledger, journal)
            raise SystemExit('QUICK_SAVE failed or uncertain: ' + type(error).__name__ + '; identity frozen')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('init', 'save'))
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--journal', type=Path, required=True); args = parser.parse_args()
    execute(args.action, args.package, args.journal)
