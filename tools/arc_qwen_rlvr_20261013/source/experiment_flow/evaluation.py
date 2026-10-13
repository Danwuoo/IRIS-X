"""Owned prediction seals, target-free generation and guarded escrow access."""
from copy import deepcopy
from pathlib import Path
import json
from .contracts import require, digest, canonical, file_sha, write_json


def validate_case(case):
    require(set(case) == {'case_id', 'parent_id', 'scope', 'demos', 'query_input', 'source'}, 'closed target-free case')
    require(case['scope'] in ('dev', 'holdout'), 'evaluation scope')
    require(case['demos'] and all(set(d) == {'input', 'output'} for d in case['demos']), 'visible demos only')
    return deepcopy(case)


def valid_grid(grid):
    return (type(grid) is list and 1 <= len(grid) <= 30 and all(type(row) is list for row in grid) and
            1 <= len(grid[0]) <= 30 and all(len(row) == len(grid[0]) for row in grid) and
            all(type(cell) is int and 0 <= cell <= 9 for row in grid for cell in row))


def validate_generation(receipt, *, case_id, transform, adapter_sha256):
    require(type(receipt) is dict and receipt.get('case_id') == case_id, 'generation case identity differs')
    require(receipt.get('transform') == transform and type(receipt.get('transform')) is int, 'generation transform differs')
    require(receipt.get('adapter_sha256') == adapter_sha256, 'generation adapter differs')
    require(receipt.get('query_targets_used') is False, 'generation target-free boundary differs')
    require(type(receipt.get('dispatched')) is bool, 'actual dispatch receipt required')
    status = receipt.get('status')
    require(status in ('complete', 'invalid', 'context-excluded', 'infrastructure-excluded','not-reached'), 'closed prediction status')
    if status == 'complete':
        require(receipt['dispatched'] and valid_grid(receipt.get('prediction')), 'valid dispatched complete grid required')
    else:
        require(receipt.get('prediction') is None, 'invalid/excluded predictions must remain null')
    if status in ('context-excluded','not-reached'):
        require(not receipt['dispatched'], 'context exclusion cannot claim dispatch')


def safe_closure(closure):
    require(type(closure) is dict and all(closure.get(k) is True for k in
            ('closed', 'future_operations_blocked', 'model_references_released', 'device_synchronized',
             'model_stopped', 'ledger_settled')), 'settled stopped model ownership closure required')
    require(closure.get('fatal_native_state') is None, 'fatal model closure cannot open holdout')
    return deepcopy(closure)


class PredictionAuthority:
    """One run's issued seals/decision/closure; rehashed caller JSON is not owned."""
    def __init__(self, dataset, plan, arms):
        self.dataset = dataset
        self.expected = {'plan_sha256': dataset.plan_sha256, 'experiment_plan_sha256': plan.sha256,
                         'inference_contract': deepcopy(plan.inference),
                         'adapter_identities': {a: arms[a]['adapter_sha256'] for a in ('A','B','C')}}
        self.case_ids = {s: [c['case_id'] for c in dataset.cases(s)] for s in ('dev','holdout')}
        self.issued = {}
        self.selection = None
        self.closure = None
        dataset.bind_evaluator(self)

    def _issue(self, scope, seal):
        require(scope not in self.issued, 'prediction scope already issued')
        self.issued[scope] = canonical(seal)
        self.admit(scope, seal)

    def admit(self, scope, seal):
        require(self.issued.get(scope) == canonical(seal), 'unknown or changed owned prediction seal')
        payload = read_predictions(seal)
        require(payload['scope'] == scope and payload['case_ids'] == self.case_ids[scope], 'owned case coverage/scope differs')
        for key, value in self.expected.items():
            require(payload[key] == value, 'owned prediction binding differs: ' + key)
        return payload

    def _freeze_selection(self, selection):
        require(self.selection is None, 'dev decision already frozen')
        self.selection = canonical(selection)

    def register_closure(self, closure):
        require(self.closure is None, 'closure already registered')
        self.closure = safe_closure(closure)

    def verify_escrow(self, scope, seal, selection):
        payload = self.admit(scope, seal)
        require(all(r['complete'] for rows in payload['methods'].values() for r in rows), 'incomplete predictions cannot open escrow')
        if scope == 'holdout':
            require(self.selection is not None and canonical(selection) == self.selection, 'owned dev selection required')
            safe_closure(self.closure)
        return payload


def evaluate_scope(backend, dataset, scope, arms, root, plan, *, clock, authority, deadline=None):
    cases = tuple(validate_case(c) for c in dataset.cases(scope))
    expected = plan.shape.dev_cases if scope == 'dev' else plan.shape.holdout_cases
    require(len(cases) == expected and len({c['case_id'] for c in cases}) == expected, 'fixed paired case count')
    methods = {}
    evaluation_deadline = plan.deadline - plan.forecast.public_seconds - plan.forecast.closure_seconds if deadline is None else deadline
    require(type(evaluation_deadline) in (int,float) and evaluation_deadline<=plan.deadline,'bounded evaluation deadline')
    for arm in ('A', 'B', 'C'):
        if clock()<evaluation_deadline:
            backend.reload(arms[arm]['checkpoint_path'], deadline=evaluation_deadline)
            backend.assert_safe()
            require(backend.identity()['adapter_sha256'] == arms[arm]['adapter_sha256'], 'evaluation checkpoint adapter drift')
        rows = []
        for index, case in enumerate(cases):
            row = {'case_id': case['case_id'], 'answers': [], 'complete': False,
                   'generations': [None, None], 'status': 'not-reached'}
            rows.append(row)
            for slot, transform in enumerate(plan.transforms):
                if clock() >= evaluation_deadline:
                    break
                result = backend.predict(case, transform=transform, seed=plan.seed,
                                         max_new_tokens=plan.output_cap, deadline=evaluation_deadline)
                backend.assert_settled()
                validate_generation(result, case_id=case['case_id'], transform=transform,
                                    adapter_sha256=arms[arm]['adapter_sha256'])
                seal = write_json(Path(root) / scope / arm / f'{index:03d}-{transform}.json', result)
                row['generations'][slot] = {'prediction': result['prediction'], 'status': result['status'],
                                            'dispatched': result['dispatched'], 'transform': transform, **seal}
                if result['prediction'] is not None and result['prediction'] not in row['answers']:
                    row['answers'].append(result['prediction'])
            row['complete'] = all(g is not None and g['status'] not in ('infrastructure-excluded','not-reached') for g in row['generations'])
            row['status'] = 'complete' if row['complete'] else 'incomplete'
            write_json(Path(root) / scope / arm / f'{index:03d}-prediction.json', row)
        methods[arm] = rows
    payload = {'format': 'irisx/transfer-sealed-predictions-v1', 'scope': scope,
               'case_ids': [c['case_id'] for c in cases], 'plan_sha256': dataset.plan_sha256,
               'experiment_plan_sha256': plan.sha256, 'inference_contract': plan.inference,
               'adapter_identities': {a: arms[a]['adapter_sha256'] for a in ('A','B','C')},
               'methods': methods, 'query_targets_used': False}
    seal = {'sealed': True, 'scope': scope, **write_json(Path(root) / (scope + '-predictions-sealed.json'), payload)}
    seal['payload_sha256'] = digest(payload)
    write_json(Path(root) / (scope + '-prediction-seal.json'), seal)
    authority._issue(scope, seal)
    return seal


def read_predictions(seal):
    require(type(seal) is dict and seal.get('sealed') is True and seal.get('scope') in ('dev','holdout'), 'prediction seal scope')
    require(file_sha(seal['path']) == seal['file_sha256'], 'sealed predictions changed')
    payload = json.loads(Path(seal['path']).read_text())
    require(digest(payload) == seal['payload_sha256'], 'prediction payload changed')
    require(set(payload) == {'format','scope','case_ids','plan_sha256','experiment_plan_sha256','inference_contract',
                             'adapter_identities','methods','query_targets_used'}, 'closed prediction payload fields')
    require(payload['format'] == 'irisx/transfer-sealed-predictions-v1' and payload['scope'] == seal['scope'], 'payload scope differs')
    require(payload['query_targets_used'] is False, 'prediction scope used targets')
    require(type(payload['case_ids']) is list and payload['case_ids'] and
            len(set(payload['case_ids'])) == len(payload['case_ids']) and
            all(type(c) is str and c.startswith(payload['scope'] + ':') for c in payload['case_ids']), 'unique scoped case IDs required')
    inference = payload['inference_contract']
    require(inference.get('transforms') == [0,1] and inference.get('TTT') is False and
            inference.get('maximum_answers') == 2, 'fixed primary inference contract')
    require(set(payload['methods']) == set(payload['adapter_identities']) == {'A','B','C'}, 'exact paired arm inventory')
    for arm, rows in payload['methods'].items():
        require(type(rows) is list and [r['case_id'] for r in rows] == payload['case_ids'], 'paired order differs')
        for row in rows:
            require(set(row) == {'case_id','answers','complete','generations','status'} and
                    type(row['generations']) is list and len(row['generations']) == 2, 'exact two generation slots required')
            actual = []
            for transform, generation in enumerate(row['generations']):
                if generation is None:
                    continue
                require(file_sha(generation['path']) == generation['file_sha256'], 'generation receipt changed')
                receipt = json.loads(Path(generation['path']).read_text())
                validate_generation(receipt, case_id=row['case_id'], transform=transform,
                                    adapter_sha256=payload['adapter_identities'][arm])
                for field in ('prediction','status','dispatched','transform'):
                    require(receipt[field] == generation[field], 'derived generation differs')
                if receipt['prediction'] is not None and receipt['prediction'] not in actual:
                    actual.append(receipt['prediction'])
            complete = all(g is not None and g['status'] not in ('infrastructure-excluded','not-reached') for g in row['generations'])
            require(type(row['complete']) is bool and row['complete'] == complete and
                    row['status'] == ('complete' if complete else 'incomplete'), 'prediction completeness not derived from slots')
            require(row['answers'] == actual[:2], 'answers not derived from actual predictions')
    return payload


def exact_scores(payload, targets):
    require(set(targets) == set(payload['case_ids']), 'exact target/prediction coverage')
    result = {}
    for arm, rows in payload['methods'].items():
        require(all(r['complete'] for r in rows), 'incomplete evaluation cannot score/select')
        exact_ids = [r['case_id'] for r in rows if any(answer == targets[r['case_id']] for answer in r['answers'])]
        result[arm] = {'exact': len(exact_ids), 'denominator': len(rows), 'exact_case_ids': exact_ids,
                       'prediction_file_bound': True}
    return result


def select_dev(dataset, seal, root, *, authority):
    require(type(authority) is PredictionAuthority and authority.dataset is dataset, 'owned evaluator authority')
    payload = authority.verify_escrow('dev', seal, None)
    targets = dataset.open_targets('dev', seal, selection=None, authority=authority)
    scores = exact_scores(payload, targets)
    chosen = max(('A','B','C'), key=lambda arm: scores[arm]['exact'])
    selection = {'selected_arm': chosen, 'rule': 'dev-exact-fixed-tie-A-B-C', 'scores': scores,
                 'dev_prediction_file_sha256': seal['file_sha256'], 'holdout_labels_opened': False}
    result = {**selection, **write_json(Path(root) / 'dev-selection.json', selection)}
    authority._freeze_selection(result)
    return result


def score_holdout(dataset, seal, selection, root, *, authority):
    require(type(authority) is PredictionAuthority and authority.dataset is dataset, 'owned evaluator authority')
    payload = authority.verify_escrow('holdout', seal, selection)
    require(file_sha(selection['path']) == selection['file_sha256'], 'selection seal changed')
    frozen = json.loads(Path(selection['path']).read_text())
    require(frozen == {k:v for k,v in selection.items() if k not in ('path','file_sha256')}, 'selection changed after dev')
    targets = dataset.open_targets('holdout', seal, selection=selection, authority=authority)
    scores = exact_scores(payload, targets)
    base = set(scores['A']['exact_case_ids'])
    paired = {a: {'gained_case_ids': sorted(set(scores[a]['exact_case_ids']) - base),
                  'lost_case_ids': sorted(base - set(scores[a]['exact_case_ids']))} for a in ('B','C')}
    result = {'scope': 'reused-experiment-heldout-not-pristine-confirmation', 'scores': scores,
              'paired_vs_A': paired, 'selection': selection['selected_arm'], 'prediction_file_sha256': seal['file_sha256']}
    return {**result, **write_json(Path(root) / 'holdout-scores.json', result)}


def public_integration_request(selection, arms, plan, root):
    arm = selection['selected_arm']
    request = {'status': 'integration-pending-not-scored', 'score': None,
               'authority': 'unchanged-original-sealed-PUBLIC-scorer-only', 'selected_arm': arm,
               'checkpoint_path': arms[arm]['checkpoint_path'], 'adapter_sha256': arms[arm]['adapter_sha256'],
               'checkpoint_manifest_sha256': arms[arm]['manifest_file_sha256'],
               'dev_selection_file_sha256': selection['file_sha256'], 'inference_contract': plan.inference,
               'original_query_count': 167, 'original_generation_count': 334, 'production_admitted': False,
               'requirements': ['integrate selected PUBLIC generations before final owner close',
                                'restore selected checkpoint', 'unchanged target-free original PUBLIC solver',
                                'seal actual original-query predictions', 'close model owner',
                                'original separate sealed scorer opens labels'],
               'caller_supplied_score_accepted': False}
    return {**request, **write_json(Path(root) / 'PUBLIC-integration-request.json', request)}


def deterministic_prediction_signature(row):
    values = []
    for generation in row['generations']:
        if generation is None:
            values.append(None); continue
        receipt = json.loads(Path(generation['path']).read_text())
        native = receipt.get('generation', {})
        values.append({'transform': receipt['transform'], 'prediction': receipt['prediction'],
                       'status': receipt['status'], 'dispatched': receipt['dispatched'],
                       'output_token_ids': native.get('output_token_ids'), 'text': native.get('text'),
                       'finish_reason': native.get('finish_reason')})
    return digest({'case_id': row['case_id'], 'complete': row['complete'], 'generations': values})


def verify_common_deterministic_views(a,b):
    """No-update identity on jointly observed views, with coverage kept separate."""
    require(a['case_id']==b['case_id'],'paired deterministic case differs')
    compared=0
    for left,right in zip(a['generations'],b['generations']):
        if left is None or right is None or left['status'] in ('infrastructure-excluded','not-reached') or right['status'] in ('infrastructure-excluded','not-reached'):
            continue
        l=json.loads(Path(left['path']).read_text());r=json.loads(Path(right['path']).read_text())
        for field in ('transform','prediction','status','dispatched'):
            require(l.get(field)==r.get(field),'deterministic no-update A/B predictions differ')
        for field in ('output_token_ids','text','finish_reason'):
            require(l.get('generation',{}).get(field)==r.get('generation',{}).get(field),'deterministic native no-update view differs')
        compared+=1
    return compared
