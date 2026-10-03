"""Decision 0055: immutable owner-Editor native epoch QUICK_SAVE package."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.arc_nvarc_combined import atomic, sha
from irisx.canonical import canonical_bytes, digest_value
from tools import stage_nvarc_native_long_ttt as base

RUN = 'nvarc-original-qwen3-native-ttt-007'
ARCHIVE = ROOT / 'tools/nvarc_native_editor_archive.py'
require = base.require


def plan_for():
    plan = base.plan_for(RUN, 1500, True)
    plan.update(owner_decision='Decision 0055', owner_editor_only=True,
        kernel_execution_type='QUICK_SAVE', download_archive='結果.zip')
    return plan


def raw_payloads(plan):
    raw = base.raw_payloads(plan)
    source = raw['worker'].decode('utf-8')
    anchor = "plan['owner_decision']=='Decision 0054'"
    require(source.count(anchor) == 1, 'exact native worker authority anchor required')
    raw['worker'] = source.replace(anchor, "plan['owner_decision']=='Decision 0055'").encode()
    raw['editor_archive'] = ARCHIVE.read_bytes()
    return raw


def render(plan, raw):
    hashes = {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()}
    source = base.render(plan['run_id'],
        {key: base64.b64encode(value).decode() for key, value in raw.items()}, hashes)
    anchor = "RUN="
    require(source.count(anchor) == 1, 'exact native parent identity anchor required')
    source = source.replace(anchor, ARCHIVE.read_text(encoding='utf-8') + '\n\n' + anchor, 1)
    anchor = '\nfinally:\n'
    require(source.count(anchor) == 1, 'exact native terminal archive anchor required')
    source = source.split(anchor)[0] + anchor + """    destination=write_editor_archive(work,work.parent/'結果.zip',RUN,plan)
    digest=None if plan is None else 'sha256:'+hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    print(json.dumps({'terminal':json.loads((work/'terminal.json').read_bytes())}))
    show_editor_archive(destination,RUN,digest)
"""
    # Preserve the reviewed download implementation itself in the closed ZIP.
    anchor = "save('plan.json',plan);save('payload-bindings.json',HASHES)"
    require(source.count(anchor) == 1, 'exact native retained input anchor required')
    source = source.replace(anchor, anchor + "\n    (work/'editor-archive.py').write_bytes(raw['editor_archive'])")
    compile(source, 'native-owner-editor-parent', 'exec')
    return source


def download_cell(plan):
    source = ARCHIVE.read_text(encoding='utf-8') + '\n\n' + (
        "# 執行完畢後下載；若上一格報錯，可單獨執行此格，不會啟動模型。\n"
        "show_editor_archive(Path('/kaggle/working/結果.zip')," + repr(plan['run_id']) + ',' +
        repr(digest_value(plan)) + ')\n')
    compile(source, 'native-owner-editor-download', 'exec')
    return source


def metadata(plan):
    return {'id': plan['kernel_id'], 'title': plan['run_id'], 'code_file': 'notebook.ipynb',
        'language': 'python', 'kernel_type': 'notebook', 'is_private': True,
        'enable_gpu': True, 'enable_internet': False, 'docker_image': base.inspection.DOCKER,
        'dataset_sources': [], 'kernel_sources': [base.inspection.REF],
        'competition_sources': plan['competition_sources'], 'model_sources': plan['model_sources']}


def notebook(plan, raw):
    return {'nbformat': 4, 'nbformat_minor': 5,
        'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
        'cells': [{'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [],
            'source': source.splitlines(keepends=True)} for source in (render(plan, raw), download_cell(plan))]}


def stage(package):
    require(not package.exists(), 'new immutable owner-Editor package required')
    plan = plan_for(); raw = raw_payloads(plan)
    (package / 'kernel').mkdir(parents=True)
    (package / 'plan.json').write_bytes(raw['plan'])
    atomic(package / 'kernel/notebook.ipynb', notebook(plan, raw))
    atomic(package / 'kernel/kernel-metadata.json', metadata(plan))
    atomic(package / 'stage-summary.json', {'run_id': RUN, 'plan_digest': digest_value(plan),
        'payload_sha256': {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()},
        'inventory': {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    plan = json.loads((package / 'plan.json').read_bytes())
    summary = json.loads((package / 'stage-summary.json').read_bytes())
    require(plan == plan_for() and digest_value(plan) == summary['plan_digest'],
        'exact Decision 0055 owner-Editor plan required')
    actual = {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*')
        if p.is_file() and p.name != 'stage-summary.json'}
    require(actual == summary['inventory'], 'closed immutable owner-Editor package required')
    raw = raw_payloads(plan)
    require(json.loads((package / 'kernel/notebook.ipynb').read_bytes()) == notebook(plan, raw) and
        json.loads((package / 'kernel/kernel-metadata.json').read_bytes()) == metadata(plan) and
        summary['payload_sha256'] == {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()},
        'exact native owner-Editor code/material/download bytes required')
    return {'run_id': RUN, 'plan_digest': summary['plan_digest'], 'offline_package_verified': True,
        'external_calls': 0, 'execution_type': 'QUICK_SAVE', 'owner_editor_only': True,
        'maximum_optimizer_steps': 128, 'source_input_tokens': 955392,
        'maximum_notebook_wall_seconds': 1500, 'download_archive': '結果.zip'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('stage', 'preflight'))
    parser.add_argument('--package', type=Path, required=True); args = parser.parse_args()
    print(json.dumps(stage(args.package) if args.action == 'stage' else preflight(args.package), ensure_ascii=True))
