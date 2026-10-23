"""R001: exact certificate vs finite-probe audit; NOT a model or Lean benchmark.

Only authored univariate polynomial minimum claims are supported. An accepted
certificate proves a lower bound by an exact nonnegative decomposition and
attainment at a rational witness, conditional on this Python checker and the
stated real-field semantics. No code supplied in a certificate is executed.
"""
from __future__ import annotations
import argparse
import copy
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import platform
import random
import re
import sys
import time
import unittest

HERE = Path(__file__).resolve().parent


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def rational(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?\d{1,12}(?:/[1-9]\d{0,11})?", value):
        raise ValueError("exact bounded rational string required")
    return F(value)


def trim(p):
    p = list(p)
    while len(p) > 1 and p[-1] == 0:
        p.pop()
    return p or [F(0)]


def poly(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 13:
        raise ValueError("polynomial requires 1..13 rational coefficients")
    return trim([rational(x) for x in values])


def add(a, b):
    return trim([(a[i] if i < len(a) else F(0)) + (b[i] if i < len(b) else F(0))
                 for i in range(max(len(a), len(b)))])


def scale(a, w):
    return trim([x*w for x in a])


def mul(a, b):
    out = [F(0)] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i+j] += x*y
    return trim(out)


def evaluate(p, x):
    out = F(0)
    for coefficient in reversed(p):
        out = out*x + coefficient
    return out


def strings(p):
    return [str(c) for c in trim(p)]


def verify(target, candidate):
    """Never uses panel labels or counterexamples. Unsupported evidence abstains."""
    try:
        if set(target) != {"id", "task", "domain", "polynomial"} or target['task'] != 'minimum':
            raise ValueError('unsupported target schema')
        if target['domain'] not in {'real', 'nonnegative-real'}:
            raise ValueError('unsupported mathematical domain')
        p = poly(target['polynomial'])
        if set(candidate) != {'answer', 'witness', 'certificate'}:
            raise ValueError('invalid candidate schema')
        answer, witness = rational(candidate['answer']), rational(candidate['witness'])
        cert = candidate['certificate']
        if not isinstance(cert, dict):
            raise ValueError('certificate must be an object')
        if cert.get('statement_sha256') != digest(target):
            raise ValueError('statement binding mismatch')
        if cert.get('kind') != 'nonnegative-decomposition':
            return {'decision': 'unknown', 'reason': 'unsupported evidence; not a disproof'}
        if set(cert) != {'kind', 'statement_sha256', 'terms'}:
            raise ValueError('unknown certificate field')
        terms = cert['terms']
        if not isinstance(terms, list) or not 1 <= len(terms) <= 16:
            raise ValueError('bounded nonempty terms required')
        assembled = [F(0)]
        for term in terms:
            if not isinstance(term, dict) or set(term) != {'weight', 'multiplier', 'square'}:
                raise ValueError('invalid term schema')
            weight = rational(term['weight'])
            if weight < 0:
                raise ValueError('negative square weight')
            if term['multiplier'] not in {'one', 'x'}:
                raise ValueError('unsupported nonnegative multiplier')
            if term['multiplier'] == 'x' and target['domain'] != 'nonnegative-real':
                raise ValueError('missing x >= 0 assumption')
            q = poly(term['square'])
            part = mul(q, q)
            if term['multiplier'] == 'x':
                part = mul([F(0), F(1)], part)
            assembled = add(assembled, scale(part, weight))
        if add(p, [-answer]) != assembled:
            raise ValueError('polynomial identity mismatch')
        if target['domain'] == 'nonnegative-real' and witness < 0:
            raise ValueError('attainment witness outside domain')
        if evaluate(p, witness) != answer:
            raise ValueError('lower bound not attained at submitted witness')
        return {'decision': 'certificate_verified',
                'reason': 'exact identity + nonnegative terms + attainment; trusted Python, not Lean'}
    except (ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        return {'decision': 'rejected', 'reason': str(exc)}


def finite_probe_shortcut(target, candidate):
    """Deliberately unsafe promotion baseline, not an actual agent or proof rule."""
    try:
        points = [F(i) for i in ((0, 1, 2) if target['domain'] == 'nonnegative-real' else (-2, -1, 0, 1, 2))]
        p, a, w = poly(target['polynomial']), rational(candidate['answer']), rational(candidate['witness'])
        return ((target['domain'] == 'real' or w >= 0) and evaluate(p, w) == a
                and all(evaluate(p, x) >= a for x in points))
    except (ValueError, KeyError, TypeError):
        return False


def make_case(case_id, p, answer, witness, square, *, domain='real', multiplier='one'):
    target = {'id': case_id, 'task': 'minimum', 'domain': domain, 'polynomial': strings(p)}
    candidate = {'answer': str(answer), 'witness': str(witness), 'certificate': {
        'kind': 'nonnegative-decomposition', 'statement_sha256': digest(target),
        'terms': [{'weight': '1', 'multiplier': multiplier, 'square': strings(square)}]}}
    return {'id': case_id, 'category': 'valid', 'claim_true': True, 'target': target,
            'candidate': candidate, 'expected': 'certificate_verified'}


def panel():
    """Publicly authored adversaries, deliberately not held-out model evidence."""
    rows = []
    for a in range(-3, 3):
        q = [F(-a), F(1)]
        rows.append(make_case(f'V{len(rows)+1:02}', add(mul(q,q), [F(1)]), 1, a, q))
    for a in range(1, 5):
        q = [F(-a), F(1)]
        p = add(mul([F(0),F(1)], mul(q,q)), [F(2)])
        rows.append(make_case(f'V{len(rows)+1:02}', p, 2, 0, q,
                              domain='nonnegative-real', multiplier='x'))
    for a in (1, 2):
        q = [F(-a*a), F(0), F(1)]
        rows.append(make_case(f'V{len(rows)+1:02}', add(mul(q,q),[F(3)]), 3, a, q))
    base = [F(1)]
    for a in (-2,-1,0,1,2):
        base = mul(base, [F(-a),F(1)])
    for k in range(1,5):
        p = add([F(1),F(0),F(1)], scale(mul(base,base),F(-k)))
        row=make_case(f'F{k:02}',p,1,0,[F(0),F(1)])
        row.update(category='false_claim_finite_grid_trap',claim_true=False,expected='rejected',counterexample='3')
        rows.append(row)
    for k in range(4):
        row=copy.deepcopy(rows[6+k]);row['id']=f'D{k+1:02}'
        row['target'].update(id=row['id'],domain='real')
        row['candidate']['certificate']['statement_sha256']=digest(row['target'])
        row.update(category='false_claim_missing_assumption',claim_true=False,expected='rejected',counterexample='-1')
        rows.append(row)
    for k in range(4):
        row=copy.deepcopy(rows[k]);row['id']=f'W{k+1:02}';row['target']['id']=row['id']
        row['candidate']['certificate']['statement_sha256']=digest(row['target'])
        row['candidate']['certificate']['terms'][0]['weight']='-1'
        row.update(category='true_claim_invalid_certificate',expected='rejected');rows.append(row)
    for k in range(4):
        row=copy.deepcopy(rows[k]);row['id']=f'B{k+1:02}';row['target']['id']=row['id']
        # Keep certificate's old statement digest: no invented mathematical falsity.
        row.update(category='true_claim_wrong_statement_binding',expected='rejected');rows.append(row)
    for k in range(4):
        row=copy.deepcopy(rows[k]);row['id']=f'U{k+1:02}';row['target']['id']=row['id']
        row['candidate']['certificate']={'kind':'llm-critique' if k<2 else 'finite-samples',
          'statement_sha256':digest(row['target']),'claim':'looks correct; deliberately not proof evidence'}
        row.update(category='true_claim_unsupported_evidence',expected='unknown');rows.append(row)
    return rows


class Controls(unittest.TestCase):
    def test_exact_algebra_against_independent_power_sum(self):
        rng=random.Random(1801)
        for _ in range(200):
            a=[F(rng.randrange(-5,6),rng.randrange(1,5)) for _ in range(4)]
            b=[F(rng.randrange(-5,6),rng.randrange(1,5)) for _ in range(3)]
            x=F(rng.randrange(-8,9),rng.randrange(1,7))
            av=sum(c*x**i for i,c in enumerate(a));bv=sum(c*x**i for i,c in enumerate(b))
            self.assertEqual(evaluate(mul(a,b),x),av*bv)
            self.assertEqual(evaluate(add(a,b),x),av+bv)
    def test_supported_certificate_completes_joint_answer_and_proof(self):
        for row in panel()[:12]: self.assertEqual(verify(row['target'],row['candidate'])['decision'],'certificate_verified')
    def test_wrong_answer_rejected(self):
        row=panel()[0];row['candidate']['answer']='0'
        self.assertEqual(verify(row['target'],row['candidate'])['decision'],'rejected')
    def test_lower_bound_alone_is_not_minimum(self):
        row=panel()[0];row['candidate']['answer']='0'
        row['candidate']['certificate']['terms'].append({'weight':'1','multiplier':'one','square':['1']})
        self.assertIn('attained',verify(row['target'],row['candidate'])['reason'])
    def test_all_known_false_claims_have_exact_counterexamples(self):
        for row in panel():
            if not row['claim_true']:
                self.assertLess(evaluate(poly(row['target']['polynomial']),rational(row['counterexample'])),rational(row['candidate']['answer']))
    def test_claim_truth_does_not_validate_an_invalid_certificate(self):
        for row in panel()[20:28]: self.assertEqual(verify(row['target'],row['candidate'])['decision'],'rejected')
    def test_unknown_does_not_become_false(self):
        for row in panel()[28:]: self.assertEqual(verify(row['target'],row['candidate'])['decision'],'unknown')
    def test_float_and_code_strings_rejected(self):
        for value in (1.0,'nan','1/0','__import__("os")','1e2',True):
            with self.assertRaises(ValueError): rational(value)
    def test_witness_domain_checked(self):
        row=panel()[6];row['candidate']['witness']='-1'
        self.assertIn('outside',verify(row['target'],row['candidate'])['reason'])
    def test_checker_read_only(self):
        row=panel()[0];before=canonical(row);verify(row['target'],row['candidate']);self.assertEqual(canonical(row),before)
    def test_unique_bound_targets(self):
        rows=panel();self.assertEqual(len({r['id'] for r in rows}),32)
        self.assertEqual(len({digest(r['target']) for r in rows}),32)
    def test_protocol_counts(self):
        from collections import Counter
        self.assertEqual(dict(Counter(r['expected'] for r in panel())),{'certificate_verified':12,'rejected':16,'unknown':4})


def run(output: Path):
    if output.exists(): raise ValueError('output must not already exist')
    protocol=json.loads((HERE/'protocol.json').read_text())
    rows=panel();results=[];start=time.perf_counter()
    for row in rows:
        result=verify(row['target'],row['candidate'])
        results.append({'id':row['id'],'category':row['category'],'claim_true':row['claim_true'],
          'expected':row['expected'],**result,'finite_probe_promotes':finite_probe_shortcut(row['target'],row['candidate'])})
    elapsed=time.perf_counter()-start
    false=[r for r in results if not r['claim_true']]
    summary={'cases':len(rows),'certificate_verified':sum(r['decision']=='certificate_verified' for r in results),
      'rejected':sum(r['decision']=='rejected' for r in results),'unknown':sum(r['decision']=='unknown' for r in results),
      'expected_decision_mismatches':sum(r['decision']!=r['expected'] for r in results),
      'false_mathematical_claims':len(false),'false_claims_promoted_by_finite_probes':sum(r['finite_probe_promotes'] for r in false),
      'false_claims_accepted_by_certificates':sum(r['decision']=='certificate_verified' for r in false)}
    report={'format':'irisx.math.round001.v1','scope':'authored verifier pilot; NOT model, Lean, IMO, Putnam or TPU efficacy',
      'python':sys.version,'platform':platform.platform(),'optimize':sys.flags.optimize,
      'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'protocol_sha256':digest(protocol),
      'panel_sha256':digest(rows),'summary':summary,'rows':results,'elapsed_seconds':elapsed,
      'model_calls':0,'training_updates':0,'lean_executions':0,'tpu_executions':0,
      'independent_review':'pending','limitations':['Deliberately constructed, non-blinded small panel.',
       'Python certificate checker is not kernel-formalized.','No agent repair or model-accuracy delta measured.']}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,sort_keys=True))
    return 0 if not summary['expected_decision_mismatches'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.self_test:
        outcome=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
        raise SystemExit(0 if outcome.wasSuccessful() else 1)
    if args.output is None: parser.error('--output or --self-test is required')
    try: raise SystemExit(run(args.output))
    except (OSError,ValueError,json.JSONDecodeError) as exc: parser.exit(2,f'{exc}\n')
