"""Re-run solver-neutral local scoring from a SHA-bound input recipe.

python tools/report_arc_offline.py --config <recipe.json> --output <new-directory>
Never loads a model, executes archive code, queries a provider or uploads.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]

from tools.arc_kaggle_submission import parse_json, require
from tools.nvarc_native_multitask import digest, write
from tools.nvarc_public_eval import read_archive, sha
from tools.score_nvarc_public_eval import bind_returned_archive, score
from tools.arc_offline_evaluation import (POOL_FORMAT, REPORT_FORMAT, load_pinned_reference,
    compare_sources, evaluate, projections, paired, official_observation)

CONFIG_FORMAT = 'irisx/arc-offline-recipe-v1'
QUESTIONS = [
    'Which search grammar or candidate-generation changes address empty pools under equal measured compute?',
    'Which verification/ranking changes improve top-two selection without evaluator-derived solver feedback?',
    'How should training, search and verification clocks be instrumented and allocated in a future matched trial?',
    'What public-source/exposure controls and untouched evaluation set support a fair multi-solver comparison?',
    'Which local failure probes would distinguish official rerun exception causes before any new submission?',
]
LIMITATIONS = [
    'Source-matched subsets are retrospective projections, not new benchmark executions.',
    'Repeatedly examined public development data and unresolved SFT139 exposure do not establish generalization.',
    'Unknown runtime phases remain unknown; no new GPU numerical replay qualification is made.',
    'Official observations are retained separately; exceptions with null scores have no numeric score.',
    'This local batch grants no kernel, QUICK_SAVE, Dataset mutation, retrieval, submission or model call.',
]


def bound_file(item, base):
    require(isinstance(item, dict) and {'path', 'sha256'} <= set(item), 'SHA-bound file required')
    path = Path(item['path']); path = path if path.is_absolute() else base/path
    require(path.is_file() and not path.is_symlink() and sha(path) == item['sha256'], 'bound file SHA-256 differs: '+str(path))
    return path


def nvarc_pools(archive, package, challenges, solutions):
    manifest, payloads = read_archive(archive)
    plan, returned, terminal = bind_returned_archive(manifest, payloads, package)
    require(returned == challenges, 'paired source bytes/content differ')
    data = parse_json(payloads['candidate-pools.json'])
    require(data['run_id'] == plan['run_id'] and data['plan_digest'] == digest(plan), 'archive pool envelope differs')
    legacy = score(plan, challenges, data['records'], solutions)
    records = []
    for key, value in sorted(data['records'].items()):
        timings = {k: v for k, v in value.get('timings', {}).items()
                   if k in {'training_seconds', 'reset_seconds', 'total_seconds'}}
        if plan['profile'] == 'BASE-30':
            require(value['training_steps'] == 0 and value['training_accounting'] == 'no-TTT', 'BASE no-training evidence differs')
            timings['training_seconds'] = 0
        values = [t.get('wall_seconds') for t in value['tests']]
        timings['solve_seconds'] = sum(values) if all(v is not None for v in values) else None
        records.append({'task_id': key, 'task_digest': digest(challenges[key]), 'timings': timings,
            'tests': [{'test_index': t['test_index'], 'input_digest': digest(challenges[key]['test'][t['test_index']]['input']),
                'ranked_grids': t['ranked_grids'], 'status': 'not_executed' if t['status'] == 'not_executed' else
                    'complete' if t['termination_reason'] == 'all_source_batches_completed' else 'partial'} for t in value['tests']]})
    return {'format': POOL_FORMAT, 'run_id': plan['run_id'], 'method': plan['profile'],
            'challenges_digest': digest(challenges), 'records': records,
            'parent_wall_seconds': terminal.get('wall_seconds')}, legacy, {
                'plan_digest': digest(plan), 'saved_package_summary_sha256': sha(Path(package)/'stage-summary.json'),
                'terminal_outcome': terminal['outcome'], 'strict_portable_gpu_gate': terminal.get('strict_portable_gpu_gate')}


def build_report(config, base):
    require(set(config) == {'format', 'source', 'solutions', 'reference', 'runs', 'official', 'retained_evidence'} and
            config['format'] == CONFIG_FORMAT, 'offline recipe schema differs')
    source_path = bound_file(config['source'], base)
    source = config['source']
    require(set(source) == {'path', 'sha256', 'repository', 'commit', 'locator'}, 'source recipe schema differs')
    require(all(isinstance(source[k], str) and source[k] for k in ('repository', 'commit', 'locator')),
            'explicit source repository/commit/locator required')
    challenges = parse_json(source_path.read_bytes())
    reference_spec = config['reference']
    require(set(reference_spec) == {'root', 'path', 'sha256'}, 'reference recipe schema differs')
    reference_provenance = bound_file(reference_spec, base)
    reference_root = Path(reference_spec['root'])
    if not reference_root.is_absolute(): reference_root = base/reference_root
    reference, reference_truth, reference_identity = load_pinned_reference(reference_root, reference_provenance)
    comparison = compare_sources(challenges, reference)
    comparison['exact_pinned_input_content'] = comparison['exact_reference_input_content']
    solution_spec = config['solutions']; solutions_path = bound_file(solution_spec, base)
    require(set(solution_spec) == {'path', 'sha256', 'challenges_digest'} and
            solution_spec['challenges_digest'] == digest(challenges), 'evaluator source binding differs')
    solutions = parse_json(solutions_path.read_bytes())
    # Truth consistency stays inside evaluator; no truth hashes, labels or grids
    # are sent to a solver or carried into the research brief.
    for match in comparison['matches']:
        key, i, j = match['task_id'], match['test_index'], match['reference_test_index']
        require(solutions[key][i] == reference_truth[key][j], 'content-matched reference truth differs')
    evaluations = []; provenance = []
    require(isinstance(config['runs'], list) and config['runs'], 'at least one frozen run required')
    for run in config['runs']:
        path = bound_file(run, base)
        require(set(run) == {'path', 'sha256', 'adapter', 'package'}, 'run recipe schema differs')
        extra = {}
        if run['adapter'] == 'nvarc-public-archive':
            package = Path(run['package']); package = package if package.is_absolute() else base/package
            pools, legacy, extra = nvarc_pools(path, package, challenges, solutions)
        else:
            require(run['adapter'] == 'offline-pools' and run['package'] is None, 'known local adapter required')
            pools = parse_json(path.read_bytes()); legacy = None
        evaluation = evaluate(challenges, solutions, pools)
        evaluation['strict_portable_gpu_gate'] = extra.get('strict_portable_gpu_gate')
        if legacy:
            require(evaluation['development_metrics']['metrics']['pass_at_2']['value'] == legacy['test_pass2'] and
                    evaluation['development_metrics']['metrics']['candidate_oracle']['value'] == legacy['verified_pool_oracle'],
                    'existing scorer and shared report disagree')
        evaluation['retrospective_projections'] = projections(evaluation, comparison)
        evaluations.append(evaluation)
        provenance.append({'run_id': pools['run_id'], 'input_sha256': run['sha256'], 'adapter': run['adapter'], **extra})
    require(len({r['run_id'] for r in evaluations}) == len(evaluations), 'unique frozen run identities required')
    official = None
    if config['official'] is not None:
        official_path = bound_file(config['official'], base)
        official = official_observation(parse_json(official_path.read_bytes()))
    evidence = []
    for item in config['retained_evidence']:
        require(set(item) == {'path', 'sha256'}, 'retained evidence schema differs')
        bound_file(item, base); evidence.append(dict(item))
    return {'format': REPORT_FORMAT, 'source': {k: source[k] for k in ('repository', 'commit', 'locator', 'sha256')},
        'reference': reference_identity, 'source_comparison': comparison,
        'evaluations': evaluations, 'paired': [paired(evaluations[0], r) for r in evaluations[1:]],
        'official_submission': official, 'provenance': {'recipe_digest': digest(config),
            'solutions_sha256': sha(solutions_path), 'runs': provenance, 'retained_evidence': evidence},
        'new_provider_requests': 0, 'new_model_calls': 0, 'new_canonical_benchmark_run': False}


def research_brief(report):
    """Allowlisted aggregate projection; no per-test labels/IDs, grids or payloads."""
    comparison = report['source_comparison']; official = report['official_submission']
    return {'format': 'irisx/stage4-research-brief-v1', 'date': '2026-10-05', 'timezone': 'Asia/Taipei',
        'scope': 'Stage 4 first local offline foundation; research proposals return through controller for local implementation',
        'success_target': 'official Kaggle score >85; engineering success is not a SOTA claim',
        'source': report['source'], 'reference': report['reference'],
        'source_qualification': {k: comparison[k] for k in ('exact_pinned_input_content', 'exact_reference_input_content', 'common_task_ids',
            'exact_task_content_matches', 'changed_demonstration_tasks', 'matched_test_inputs',
            'matched_test_inputs_and_demonstrations', 'projection_qualification')},
        'executed_denominator': {k: comparison['executed'][k] for k in ('tasks', 'tests', 'challenges_digest')},
        'methods': [{k: r[k] for k in ('run_id', 'method', 'development_metrics', 'runtime', 'retrospective_projections')}
                    for r in report['evaluations']], 'paired': report['paired'],
        'official_submission': None if official is None else {k: official[k] for k in ('reference', 'status', 'outcome',
            'public_score', 'private_score', 'score_units', 'score_state', 'observed_at', 'receipt_sha256')},
        'evidence_hashes': report['provenance'], 'limitations': LIMITATIONS, 'research_questions': QUESTIONS,
        'portable_gpu_qualification': [{'run_id': r['run_id'], 'strict_portable_gpu_gate': r.get('strict_portable_gpu_gate')}
                                        for r in report['evaluations']],
        'return_format': {'required': ['proposal and mechanism', 'primary source links/commit', 'expected observable benefit',
            'small local test', 'failure criteria', 'compute/data/exposure assumptions', 'runtime instrumentation'],
            'routing': 'controller reviews research; local task implements the next approved batch'},
        'contains_raw_grids': False, 'contains_notebook_payload': False, 'uploaded': False}


def brief_markdown(brief):
    lines = ['# Stage 4 local foundation evidence brief', '', brief['scope'], '',
        'Target: '+brief['success_target']+'.', '',
        f"Executed source: {brief['executed_denominator']['tasks']} tasks / {brief['executed_denominator']['tests']} tests.",
        f"Reference: {brief['reference']['repository']} @ {brief['reference']['commit']}, {brief['reference']['tasks']} tasks / {brief['reference']['tests']} tests.", '',
        '| Method | pass@1 | pass@2 | Oracle | Coverage | Empty | Pool miss | Ranking miss |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in brief['methods']:
        m = r['development_metrics']['metrics']; keys = ('pass_at_1','pass_at_2','candidate_oracle','candidate_coverage',
            'empty_pool','pool_miss','ranking_miss')
        lines.append('| '+r['method']+' | '+' | '.join(f"{m[k]['numerator']}/{m[k]['denominator']}" for k in keys)+' |')
    lines += ['', 'Runtime: see the aggregate JSON for measured worker/parent scopes. Separate search, verification and total other time are unknown in these frozen logs.', '']
    if brief['official_submission']:
        o = brief['official_submission']
        suffix = ' No numeric score was returned.' if o['public_score'] is None and o['private_score'] is None else ''
        lines += [f"Official receipt {o['reference']}: {o['outcome']}; public score {o['public_score']}, private score {o['private_score']}.{suffix}", '']
    lines += ['Known limits:', ''] + ['- '+v for v in brief['limitations']]
    lines += ['', 'Research questions:', ''] + ['- '+v for v in brief['research_questions']]
    lines += ['', 'Return: proposal, primary sources, mechanism, local test, failure criteria, compute/data assumptions and instrumentation. The controller reviews it before the next local batch.', '']
    return '\n'.join(lines)


def write_report(output, report):
    output = Path(output)
    require(not output.exists(), 'new immutable report directory required')
    output.mkdir(parents=True); (output/'local').mkdir()
    write(output/'local/evaluation.json', report)
    brief = research_brief(report)
    write(output/'evidence-brief.json', brief)
    (output/'evidence-brief.md').write_text(brief_markdown(brief), encoding='utf-8')
    # Closed handoff inventory: never recurse through evaluator/raw input dirs.
    names = ['evidence-brief.json', 'evidence-brief.md']
    write(output/'manifest.json', {'format': 'irisx/stage4-local-handoff-v1',
        'members': [{'path': n, 'sha256': sha(output/n), 'bytes': (output/n).stat().st_size} for n in names],
        'local_evaluation_sha256': sha(output/'local/evaluation.json'),
        'contains_raw_grids': False, 'contains_notebook_payload': False,
        'contains_model_weights': False, 'uploaded': False})


def synthetic_fixture_report():
    """Tiny declared synthetic example; never claims a pinned ARC benchmark."""
    challenges = {'fixture-a': {'train': [{'input': [[1]], 'output': [[2]]}],
        'test': [{'input': [[3]]}, {'input': [[4]]}]},
        'fixture-b': {'train': [{'input': [[5]], 'output': [[6]]}], 'test': [{'input': [[7]]}]}}
    truth = {'fixture-a': [[[0]], [[8]]], 'fixture-b': [[[9]]]}
    pools = {'format': POOL_FORMAT, 'run_id': 'synthetic-offline-example', 'method': 'synthetic; no model calls',
             'challenges_digest': digest(challenges), 'parent_wall_seconds': None, 'records': []}
    for key, candidates in [('fixture-a', [[], [[[1]], [[2]], [[8]]]]), ('fixture-b', [[[[9]]]])]:
        pools['records'].append({'task_id': key, 'task_digest': digest(challenges[key]), 'timings': {},
            'tests': [{'test_index': i, 'input_digest': digest(challenges[key]['test'][i]['input']),
                       'ranked_grids': v, 'status': 'partial'} for i, v in enumerate(candidates)]})
    comparison = compare_sources(challenges, challenges)
    comparison['exact_pinned_input_content'] = False  # fixture reference is deliberately synthetic
    scored = evaluate(challenges, truth, pools); scored['qualification'] = 'synthetic offline example only'
    scored['retrospective_projections'] = projections(scored, comparison)
    return {'format': REPORT_FORMAT, 'source': {'repository': 'synthetic fixture', 'commit': 'none',
            'locator': 'tools/report_arc_offline.py:synthetic_fixture_report', 'sha256': None},
        'reference': {'repository': 'synthetic fixture', 'commit': 'none', 'tasks': 2, 'tests': 3},
        'source_comparison': comparison, 'evaluations': [scored], 'paired': [], 'official_submission': None,
        'provenance': {'fixture': True}, 'new_provider_requests': 0, 'new_model_calls': 0,
        'new_canonical_benchmark_run': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--config', type=Path); mode.add_argument('--synthetic-fixture', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = synthetic_fixture_report() if args.synthetic_fixture else build_report(
        parse_json(args.config.read_bytes()), args.config.resolve().parent)
    write_report(args.output, report)
    print(json.dumps({'format': report['format'], 'runs': len(report['evaluations']),
                      'report_sha256': sha(args.output/'local/evaluation.json'),
                      'manifest_sha256': sha(args.output/'manifest.json')}))


if __name__ == '__main__': main()
