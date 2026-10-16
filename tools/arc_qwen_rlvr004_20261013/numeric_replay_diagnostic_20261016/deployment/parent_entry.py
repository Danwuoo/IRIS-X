"""Pinned installed parent calls the genuine reviewed owned-runtime entrypoint."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
import types
def _source_module(name):
    path=HERE/(name+'.py');module=types.ModuleType(name);module.__file__=str(path);module.__package__=''
    sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True),vars(module))
    return module
_source_module('source_loader')
from source_loader import read_regular,parse,digest,need,clean_path,encoded,source_import_paths


def diagnostic_success(result, terminal, outer):
    """Exact source-specific completion; neither PUBLIC nor model-score success."""
    inner = outer.get('inner_closure') or {}
    model = inner.get('model_closure') or {}
    return (result.get('status') == 'owned-numeric-diagnostic-complete-no-update'
        and result.get('run_purpose') == 'training-only-numeric-diagnostic-v1'
        and result.get('diagnostic_complete') is True
        and result.get('comparison_complete') is False
        and result.get('public_benchmark_evidence_eligible') is False
        and result.get('scientific_goal_met') is False
        and result.get('production_admitted') is False
        and result.get('ARC_or_14B_efficacy_claim') is False
        and all(result.get(k) is None for k in ('PUBLIC_score', 'parent_scoring_ref', 'checkpoint_export',
                                               'terminal_error', 'source_integrity_error'))
        and terminal.get('status') == 'diagnostic' and terminal.get('archive_complete') is True
        and terminal.get('model_closed') is False
        and all(terminal.get(k) is False for k in ('model_success_claim', 'scientific_goal_met', 'production_admitted'))
        and outer.get('safe_closure') is True and outer.get('model_stopped') is True
        and outer.get('worker_exited') is True and outer.get('worker_session_empty') is True
        and type(outer.get('worker_returncode')) is int and outer['worker_returncode'] == 0
        and inner.get('status') == 'complete'
        and all(model.get(k) is True for k in ('closed', 'future_operations_blocked',
            'model_references_released', 'device_synchronized', 'model_stopped', 'ledger_settled'))
        and model.get('fatal_native_state') is None)

def diagnostic_completed(result, output_root):
    """Check the actual exported receipt and raw closure before clean parent exit."""
    terminal = result.get('terminal_export', {})
    if result.get('status') != 'owned-numeric-diagnostic-complete-no-update':
        return False
    root = clean_path(output_root)
    outer_ref = result.get('outer_closure_ref', {})
    need(outer_ref.get('path') == str(root / 'outer-closure.json'), 'diagnostic outer path differs')
    outer_raw = read_regular(Path(outer_ref['path']), 16 * 1024**2)
    need(digest(outer_raw) == outer_ref.get('file_sha256'), 'diagnostic actual outer closure differs')
    outer = parse(outer_raw)
    need(diagnostic_success(result, terminal, outer), 'diagnostic completion requires safe closed no-update result')
    need(outer.get('launch_source_sha256') == result.get('source_sha256') and outer.get('output_root') == str(root),
         'diagnostic closure source/output differs')
    ref = terminal.get('terminal_receipt', {})
    need(ref.get('path') == str(root) + '.evidence.zip.terminal.json', 'diagnostic terminal path differs')
    raw = read_regular(Path(ref['path']), 16 * 1024**2)
    need(len(raw) == ref.get('bytes') and digest(raw) == ref.get('sha256') and
         parse(raw) == {k: v for k, v in terminal.items() if k != 'terminal_receipt'},
         'diagnostic actual terminal bytes differ')
    authority = terminal.get('authorization', {})
    need(authority.get('kind') == 'live-owned-process-termination'
         and authority.get('source_sha256') == result.get('source_sha256')
         and authority.get('output_root') == str(root) and authority.get('outer_closure_ref') == outer_ref,
         'diagnostic terminal closure authorization differs')
    archive = terminal.get('archive', {})
    need(archive.get('path') == str(root) + '.evidence.zip', 'diagnostic evidence archive path differs')
    path = clean_path(archive['path'])
    # The live exporter has streamed and verified every archive byte already.
    # Check the actual exclusive output remains present; do not rerun export.
    import stat
    info = path.stat(follow_symlinks=False)
    need(stat.S_ISREG(info.st_mode) and info.st_size == archive.get('bytes') and info.st_nlink == 1,
         'diagnostic evidence archive absent or changed')
    need(archive.get('members', {}).get('outer-closure.json') == {'bytes': len(outer_raw), 'sha256': digest(outer_raw)},
         'diagnostic archive outer closure member differs')
    owned_raw = read_regular(root / 'owned-result.json', 16 * 1024**2)
    need(parse(owned_raw) == {k: v for k, v in result.items() if k != 'terminal_export'} and
         archive.get('members', {}).get('owned-result.json') == {'bytes': len(owned_raw), 'sha256': digest(owned_raw)},
         'diagnostic archive result member differs')
    return True


def main():
    need(len(sys.argv)==3,'exact installed-parent request and hash required')
    raw=read_regular(Path(sys.argv[1]),2*1024**2);need(digest(raw)==sys.argv[2],'installed-parent request bytes differ')
    request=parse(raw);need(request['format']=='irisx/rlvr-installed-parent-request-v1','installed parent schema')
    source=clean_path(request['source_root'])
    source_import_paths(source)
    from owned_runtime.release import inventory,source_digest
    need(source_digest(inventory())==request['source_sha256'],'parent full source identity differs')
    from owned_runtime.bootstrap import reviewed_bootstrap
    result=reviewed_bootstrap(request['config'],request['output_root'],**request['paths'])
    with Path(request['result_path']).open('xb') as stream:stream.write(encoded(result))
    print(encoded({'status':result['status'],'terminal_status':result.get('terminal_export',{}).get('status')}).decode(),flush=True)
    public_complete = result['status'] in ('owned-mechanics-complete-PUBLIC-sealed','owned-mechanics-partial-comparison-PUBLIC-sealed') and result.get('terminal_export',{}).get('status') == 'complete'
    if not public_complete and not diagnostic_completed(result, request['output_root']):
        raise SystemExit(1)

if __name__=='__main__':main()
