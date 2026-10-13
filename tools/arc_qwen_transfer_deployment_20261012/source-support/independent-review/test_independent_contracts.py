"""Independent CPU/stdlib contract tests. No model execution is implied."""
import copy
import dataclasses
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
s = load('independent_demo_selector', ROOT / 'selection/demo_selector.py')
d = load('independent_arc_adaptation', ROOT / 'data-adaptation/arc_adaptation.py')
sys.modules['demo_selector'] = s
b = load('independent_prompt_budget', ROOT / 'selection/prompt_budget.py')


def selector_fixture():
    task = {'task_id': 'fresh-parent', 'demonstrations': [
        {'demo_id': 'a', 'input': [[1, 0]], 'output': [[2, 0]]},
        {'demo_id': 'b', 'input': [[3], [0]], 'output': [[4], [0]]},
        {'demo_id': 'c', 'input': [[5, 0], [0, 0]], 'output': [[6, 0], [0, 0]]}],
        'query_input': [[7, 0]]}
    policy = {'format': 'irisx/demo-only-grid-portfolio-v1', 'candidate_order': ['base', 'sft', 'ttt'],
              'transform_order': ['identity', 'r90', 'r180', 'r270'], 'maximum_answers': 2}
    candidates = []
    ids = [r['demo_id'] for r in task['demonstrations']]
    for cid in policy['candidate_order']:
        candidates.append({'candidate_id': cid, 'task_id': task['task_id'], 'checkpoint_sha256': s.digest(cid),
            'adaptation_scope': 'task-demonstrations' if cid == 'ttt' else 'none',
            'folds': [{'heldout_demo_id': row['demo_id'], 'conditioning_demo_ids': [i for i in ids if i != row['demo_id']],
                'adaptation_demo_ids': [i for i in ids if i != row['demo_id']] if cid == 'ttt' else [],
                'prediction': copy.deepcopy(row['output']), 'nll_sum': 1.0, 'token_count': 2,
                'receipt_sha256': s.digest([cid, row['demo_id']])} for row in task['demonstrations']],
            'query_predictions': [{'transform_id': tr, 'grid': [[8, 0]], 'inverse_applied': True,
                'receipt_sha256': s.digest([cid, tr])} for tr in policy['transform_order']]})
    policy['fold_conditioning_demo_ids'] = {did: [other for other in ids if other != did] for did in ids}
    policy['candidate_specs'] = {c['candidate_id']: {'role': {'base':'frozen_base','sft':'global_sft','ttt':'task_ttt'}[c['candidate_id']], 'checkpoint_sha256': c['checkpoint_sha256'], 'adaptation_scope': c['adaptation_scope']} for c in candidates}
    return task, policy, candidates


def data_fixture(count=100):
    entries, blobs = [], {}
    for i in range(count):
        tid = f'{0x10000000+i:08x}'
        raw = {'train': [{'input': [[0, j + 1], [j + 1, 0]], 'output': [[j + 1, j + 1, 0]]}
                          for j in range(2 + i % 4)],
               'test': [{'input': [[9]], 'output': [[8]]}]}
        blob = json.dumps(raw, sort_keys=True).encode()
        blobs[tid] = blob
        entries.append(d.SourceEntry(tid, f'data/training/{tid}.json',
            hashlib.sha1(f'blob {len(blob)}\0'.encode() + blob).hexdigest(), len(blob),
            aliases=(f'legacy-parent-{i}',), content_sha256=hashlib.sha256(blob).hexdigest()))
    pin = d.inventory_digest('https://example.invalid/pinned-fixture', 'a'*40, entries)
    inv = d.SourceInventory('https://example.invalid/pinned-fixture', 'a'*40, tuple(entries), pin)
    ids = [e.task_id for e in inv.entries]
    exclusion = d.Exclusions(tuple(ids[32:56]), tuple(ids[56:60]), tuple(ids[60:64]))
    partition = d.partition_parents(inv, ids[:32], exclusion, canary_count=4, holdout_count=8, seed='preregistered')
    return inv, partition, blobs


class SelectionIndependent(unittest.TestCase):
    def test_query_input_and_predictions_never_change_demo_rankings(self):
        task, policy, candidates = selector_fixture()
        expected = s.select_answers(task, policy, candidates)['rankings']
        task['query_input'] = [[9]*30 for _ in range(30)]
        for i, c in enumerate(candidates):
            for j, q in enumerate(c['query_predictions']):
                q['grid'] = [[(i+j)%10]] if j%2 else None
        self.assertEqual(s.select_answers(task, policy, candidates)['rankings'], expected)

    def test_every_input_layer_rejects_outcome_fields(self):
        for layer in ('task', 'policy', 'candidate', 'fold', 'prediction', 'demo'):
            for field in ('query_target', 'public_score', 'exact_test_score', 'target_length'):
                with self.subTest(layer=layer, field=field):
                    task, policy, cs = selector_fixture()
                    obj = {'task': task, 'policy': policy, 'candidate': cs[0], 'fold': cs[0]['folds'][0],
                           'prediction': cs[0]['query_predictions'][0], 'demo': task['demonstrations'][0]}[layer]
                    obj[field] = 99
                    with self.assertRaises(ValueError): s.select_answers(task, policy, cs)

    def test_all_candidate_and_evidence_permutations_preserve_answer_grids(self):
        task, policy, cs = selector_fixture()
        cs[0]['query_predictions'][0]['grid'] = [[1]]
        cs[0]['query_predictions'][1]['grid'] = [[2]]
        cs[0]['query_predictions'][2]['grid'] = [[1]]
        cs[0]['query_predictions'][3]['grid'] = [[2]]
        expected = [r['grid'] for r in s.select_answers(task, policy, cs)['answers']]
        for perm in itertools.permutations(cs):
            items = copy.deepcopy(list(perm))
            for c in items:
                c['folds'].reverse()
                c['query_predictions'].reverse()
            self.assertEqual([r['grid'] for r in s.select_answers(task, policy, items)['answers']], expected)

    def test_checkpoint_evidence_dominates_transform_votes(self):
        task, policy, cs = selector_fixture()
        cs[0]['query_predictions'][0]['grid'] = [[1]]
        for q in cs[0]['query_predictions'][1:]: q['grid'] = None
        for q in cs[1]['query_predictions']: q['grid'] = [[2]]
        out = s.select_answers(task, policy, cs)
        self.assertEqual([a['grid'] for a in out['answers']], [[[1]], [[2]]])

    def test_nll_is_token_weighted_not_fold_mean(self):
        task, policy, cs = selector_fixture()
        cs[0]['folds'][0].update(nll_sum=9, token_count=1)
        cs[0]['folds'][1].update(nll_sum=10, token_count=100)
        cs[0]['folds'][2].update(nll_sum=0, token_count=1)
        for f in cs[1]['folds']: f.update(nll_sum=1, token_count=1)
        for f in cs[2]['folds']: f.update(nll_sum=2, token_count=1)
        self.assertEqual(s.select_answers(task, policy, cs)['rankings'][0]['candidate_id'], 'base')

    def test_missing_other_context_and_unadapted_ttt_fail(self):
        for cid, field in [('base', 'conditioning_demo_ids'), ('sft', 'conditioning_demo_ids'), ('ttt', 'adaptation_demo_ids')]:
            task, policy, cs = selector_fixture()
            next(c for c in cs if c['candidate_id'] == cid)['folds'][0][field] = []
            with self.assertRaises(ValueError): s.select_answers(task, policy, cs)

    def test_packed_fold_subsets_are_shared_by_all_candidates(self):
        task, policy, cs = selector_fixture()
        costs={'a':700,'b':2500,'c':500}
        def render(demos,query): return json.dumps({'demos':demos,'query':query})
        def encode(text): return [1]*(1000+sum(costs[row['demo_id']] for row in json.loads(text)['demos']))
        contexts={}
        for demo in task['demonstrations']:
            pseudo=copy.deepcopy(task); pseudo['query_input']=copy.deepcopy(demo['input'])
            packed=b.pack_demonstrations(pseudo,render=render,encode=encode,withheld_demo_id=demo['demo_id'])
            self.assertTrue(packed['admitted'])
            contexts[demo['demo_id']]=packed['selected_demo_ids']
        self.assertEqual(contexts['a'],['c'])
        policy['fold_conditioning_demo_ids']=contexts
        for c in cs:
            for f in c['folds']: f['conditioning_demo_ids']=contexts[f['heldout_demo_id']][:]
        self.assertEqual(s.select_answers(task,policy,cs)['rankings'][0]['candidate_id'],'base')
        cs[0]['folds'][0]['conditioning_demo_ids']=['b']
        with self.assertRaises(ValueError): s.select_answers(task,policy,cs)

    def test_registered_fold_context_rejects_empty_withheld_unknown_duplicate(self):
        for context in ([],['a'],['unknown'],['b','b']):
            task,policy,cs=selector_fixture()
            policy['fold_conditioning_demo_ids']['a']=context
            with self.assertRaises(ValueError): s.select_answers(task,policy,cs)

    def test_registered_scope_and_checkpoint_cannot_be_self_overridden(self):
        for kind in ('scope', 'checkpoint', 'role'):
            task, policy, cs = selector_fixture()
            if kind == 'scope':
                cs[0]['adaptation_scope'] = 'task-demonstrations'
                for f in cs[0]['folds']: f['adaptation_demo_ids'] = list(f['conditioning_demo_ids'])
            elif kind == 'checkpoint': cs[0]['checkpoint_sha256'] = 'b'*64
            else: policy['candidate_specs']['base']['role'] = 'global_sft'
            with self.assertRaises(ValueError): s.select_answers(task, policy, cs)

    def test_inputs_are_never_mutated(self):
        args = selector_fixture(); before = copy.deepcopy(args)
        s.select_answers(*args)
        self.assertEqual(args, before)


class DataIndependent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inv, cls.partition, cls.blobs = data_fixture()

    def task(self, parent=None):
        parent = parent or self.partition.optimizer_ids[0]
        return d.project_source_bytes(self.blobs[parent], self.inv, parent)

    def test_partition_exclusion_and_panel_invariants(self):
        p = self.partition
        d.assert_sprint_contract(p, inventory=self.inv, archived_optimizer_ids=p.prior_optimizer_ids,
            archived_regression_ids=p.exclusions.old_regression_ids,
            archived_exposed_ids=p.exclusions.old_exposed_ids,
            public120_exclusion_sha256=d.digest(p.exclusions.public120_ids))
        groups = [set(p.optimizer_ids), set(p.canary_ids), set(p.holdout_ids), set(p.excluded_inventory_ids), set(p.reserved_ids)]
        for a,b in itertools.combinations(groups,2): self.assertFalse(a & b)
        self.assertEqual(set.union(*groups), {e.task_id for e in self.inv.entries})
        self.assertEqual(set(p.prior_optimizer_ids),groups[0])
        self.assertEqual(len(p.optimizer_ids),32)
        self.assertEqual(len(p.canary_ids),4); self.assertEqual(len(p.holdout_ids),8)

    def test_missing_fresh_inventory_capacity_cannot_substitute_old_panels(self):
        with self.assertRaises(ValueError):
            d.partition_parents(self.inv,self.partition.prior_optimizer_ids,self.partition.exclusions,
                canary_count=16,holdout_count=32,seed='preregistered')

    def test_inventory_order_does_not_change_partition(self):
        inv = d.SourceInventory(self.inv.repository, self.inv.commit, self.inv.entries[::-1], self.inv.sha256)
        actual = d.partition_parents(inv, reversed(self.partition.prior_optimizer_ids), self.partition.exclusions,
            canary_count=4, holdout_count=8, seed='preregistered')
        self.assertEqual(actual.sha256, self.partition.sha256)

    def test_declared_alias_exclusion_reaches_parent(self):
        e = self.inv.entries[70]
        excluded = d.Exclusions((), (), (e.aliases[0],))
        p = d.partition_parents(self.inv, self.partition.prior_optimizer_ids, excluded, canary_count=4, holdout_count=8, seed='x')
        self.assertIn(e.task_id, p.excluded_inventory_ids)
        self.assertNotIn(e.task_id, p.optimizer_ids+p.canary_ids+p.holdout_ids+p.reserved_ids)

    def test_undeclared_or_duplicate_aliases_cannot_claim_inventory_membership(self):
        with self.assertRaises(ValueError): self.inv.entry('unknown-parent')
        entries = list(self.inv.entries)
        entries[1] = dataclasses.replace(entries[1], aliases=entries[0].aliases)
        with self.assertRaises(ValueError):
            d.SourceInventory(self.inv.repository,self.inv.commit,tuple(entries),d.inventory_digest(self.inv.repository,self.inv.commit,entries))

    def test_changed_bytes_and_pins_rejected(self):
        e = self.inv.entries[0]
        with self.assertRaises(ValueError): d.project_source_bytes(self.blobs[e.task_id]+b' ',self.inv,e.task_id)
        with self.assertRaises(ValueError): d.SourceInventory(self.inv.repository,self.inv.commit,self.inv.entries,'b'*64)

    def test_query_gold_is_not_accessed_or_retained(self):
        from collections.abc import Mapping
        class TrainOnlyMapping(Mapping):
            def __getitem__(self, key):
                if key != 'train': raise AssertionError('Forbidden root access: '+key)
                return [{'input': [[1]],'output': [[2]]},{'input': [[3]],'output': [[4]]}]
            def __iter__(self): raise AssertionError('Root keys may not be enumerated')
            def __len__(self): raise AssertionError('Root length may not be read')
        task = d.project_demonstrations(TrainOnlyMapping(), self.inv, self.inv.entries[0].task_id)
        self.assertEqual(len(task.demos),2)
        self.assertNotIn('test', dataclasses.asdict(task))

    def test_projection_and_record_are_immutable_copies(self):
        raw = json.loads(self.blobs[self.partition.optimizer_ids[0]])
        task = d.project_demonstrations(raw,self.inv,self.partition.optimizer_ids[0])
        old = task.demos[0].input
        raw['train'][0]['input'][0][0] = 9
        self.assertEqual(task.demos[0].input,old)
        with self.assertRaises(dataclasses.FrozenInstanceError): task.demos = ()

    def test_grid_type_and_dimension_adversaries(self):
        for invalid in ([[True]], [[1.0]], [[-1]], [[10]], [], [[]], [[1],[1,2]], [[0]*31], [[0]]*31):
            with self.subTest(value=invalid), self.assertRaises(ValueError): d.freeze_grid(invalid)

    def test_d4_palette_inverse_roundtrip_varied_rectangles(self):
        rng = random.Random(23)
        for h,w in [(1,1),(1,30),(30,1),(2,3),(3,2),(7,11),(30,29)]:
            grid = tuple(tuple(rng.randrange(10) for _ in range(w)) for _ in range(h))
            for op in range(8):
                for seed in ('a','b','pinned-123'):
                    transform = d.Transform(op,d.deterministic_palette(seed,op))
                    self.assertEqual(transform.palette[0],0)
                    self.assertEqual(transform.inverse().apply(transform.apply(grid)),grid)
                    self.assertEqual(transform.apply(transform.inverse().apply(grid)),grid)
                    self.assertEqual(sorted(x for row in transform.apply(grid) for x in row).count(0),
                                     sorted(x for row in grid for x in row).count(0))

    def test_all_loo_records_reconstruct_original_demo_sources(self):
        task = self.task()
        transforms = tuple(d.Transform(op,d.deterministic_palette('seed',op)) for op in range(8))
        records = d.loo_records(task,transforms=transforms,purpose='optimizer',partition=self.partition)
        self.assertEqual(len(records),len(task.demos)*8)
        for record in records:
            inverse = record.transform.inverse()
            self.assertEqual(inverse.apply(record.target),task.demos[record.withheld_demo_index].output)
            self.assertNotIn(record.withheld_demo_index,record.context_demo_indices)
            self.assertEqual(len(record.prompt.examples),len(task.demos)-1)
            with self.assertRaises(ValueError): dataclasses.replace(record,target=((9,),))

    def test_global_optimizer_cannot_ingest_canary_or_holdout(self):
        for tid in self.partition.canary_ids+self.partition.holdout_ids+self.partition.excluded_inventory_ids+self.partition.reserved_ids:
            task = self.task(tid)
            with self.assertRaises(ValueError): d.loo_records(task,purpose='optimizer',partition=self.partition)

    def test_balanced_schedule_all_prefixes_with_unequal_demo_augmentation_counts(self):
        records = []
        for k,tid in enumerate(self.partition.optimizer_ids[:5]):
            transforms = (d.Transform(),) if k%2 else tuple(d.Transform(op) for op in range(8))
            records.extend(d.loo_records(self.task(tid),transforms=transforms,purpose='optimizer',partition=self.partition))
        result = d.budgeted_schedule(records,max_records=147,seed='fixed')
        self.assertEqual(result, d.budgeted_schedule(records[::-1],max_records=147,seed='fixed'))
        parents = set(r.lineage.parent_id for r in records)
        for end in range(len(result.parent_ids)+1):
            counts = [result.parent_ids[:end].count(p) for p in parents]
            self.assertLessEqual(max(counts)-min(counts),1)
        costs = {r.sha256:r.cell_cost for r in records}
        self.assertEqual(result.cells_used,sum(costs[h] for h in result.record_sha256s))
        for cutoff in (0,1,2,8,21,146):
            budget = sum(costs[h] for h in result.record_sha256s[:cutoff])
            limited = d.budgeted_schedule(records,max_records=147,max_cells=budget,seed='fixed')
            self.assertEqual(limited.record_sha256s,result.record_sha256s[:cutoff])
            self.assertEqual(limited.stop_reason,'next_record_exceeds_cell_budget')

    def test_partition_direct_exclusion_and_rank_tampering_rejected(self):
        p = self.partition
        parent = p.excluded_inventory_ids[0]
        with self.assertRaises(ValueError):
            dataclasses.replace(p,optimizer_ids=tuple(sorted((*p.optimizer_ids,parent))),
                excluded_inventory_ids=tuple(i for i in p.excluded_inventory_ids if i != parent))
        with self.assertRaises(ValueError): dataclasses.replace(p,eligible_order=p.eligible_order[::-1])
        with self.assertRaises(ValueError): dataclasses.replace(p,canary_ids=p.holdout_ids[:4],holdout_ids=p.canary_ids+p.holdout_ids[4:])

    def test_reserved_parents_cannot_silently_expand_global_training(self):
        p=self.partition; parent=p.reserved_ids[0]
        with self.assertRaises(ValueError):
            dataclasses.replace(p,optimizer_ids=tuple(sorted((*p.optimizer_ids,parent))),
                reserved_ids=tuple(i for i in p.reserved_ids if i != parent))

    def test_inventory_rederivation_rejects_alias_exclusion_reintroduction(self):
        p = self.partition
        excluded_parent = self.inv.entries[70]
        contaminated = dataclasses.replace(p, exclusions=d.Exclusions(p.exclusions.old_regression_ids,
            p.exclusions.old_exposed_ids,p.exclusions.public120_ids,(excluded_parent.aliases[0],)))
        with self.assertRaises(ValueError): d.validate_partition(contaminated,self.inv)

    def test_outer_ttt_excludes_complete_pair_from_every_supervised_record(self):
        for tid in self.partition.optimizer_ids[:4]:
            task = self.task(tid)
            before = dataclasses.asdict(task)
            for heldout in range(len(task.demos)):
                records = d.outer_ttt_records(task,outer_withheld_demo_index=heldout,
                    transforms=tuple(d.Transform(op,d.deterministic_palette('outer',op)) for op in range(8)))
                self.assertEqual(len(records),8*(len(task.demos)-1))
                visible = tuple(i for i in range(len(task.demos)) if i != heldout)
                for record in records:
                    self.assertEqual(record.lineage.visible_demo_indices,visible)
                    self.assertEqual(record.lineage.excluded_demo_indices,(heldout,))
                    self.assertEqual(record.lineage.origin_projection_sha256,task.lineage.projection_sha256)
                    self.assertNotEqual(record.lineage.projection_sha256,task.lineage.projection_sha256)
                    self.assertEqual(record.demo_count,len(visible))
                    inverse = record.transform.inverse()
                    source_target = visible[record.withheld_demo_index]
                    self.assertEqual(inverse.apply(record.target),task.demos[source_target].output)
                    self.assertEqual(inverse.apply(record.prompt.query_input),task.demos[source_target].input)
                    for local_index, example in zip(record.context_demo_indices,record.prompt.examples):
                        source_index = visible[local_index]
                        self.assertNotEqual(source_index,heldout)
                        self.assertEqual(inverse.apply(example.input),task.demos[source_index].input)
                        self.assertEqual(inverse.apply(example.output),task.demos[source_index].output)
                self.assertEqual(dataclasses.asdict(task),before)

    def test_replay_validates_original_source_and_rejects_same_size_relabeling(self):
        task=self.task(self.partition.optimizer_ids[1])
        records=d.outer_ttt_records(task,outer_withheld_demo_index=0)
        for record in records: d.validate_record(record,task,expected_excluded_demo_indices=(0,))
        record=records[0]
        visible=(0,)+record.lineage.visible_demo_indices[1:]
        misleading=dataclasses.replace(record.lineage,visible_demo_indices=visible,excluded_demo_indices=(1,))
        replay=dataclasses.replace(record,lineage=misleading)
        with self.assertRaises(ValueError): d.validate_record(replay,task,expected_excluded_demo_indices=(1,))
        with self.assertRaises(ValueError): d.validate_record(record,task)
        with self.assertRaises(ValueError): d.validate_record(record,task,expected_excluded_demo_indices=(1,))
        with self.assertRaises(ValueError): d.validate_record(record,self.task(self.partition.optimizer_ids[2]),expected_excluded_demo_indices=(0,))

    def test_replay_cannot_omit_undeclared_original_demonstrations(self):
        tid=self.partition.optimizer_ids[1]
        original=self.task(tid)
        self.assertEqual(len(original.demos),3)
        reduced=d.project_demonstrations({'train':[dataclasses.asdict(original.demos[0])]},self.inv,tid)
        incomplete=dataclasses.replace(reduced.lineage,origin_projection_sha256=original.lineage.projection_sha256,
            visible_demo_indices=(0,),excluded_demo_indices=(1,))
        reduced=dataclasses.replace(reduced,lineage=incomplete)
        record=d.loo_records(reduced,purpose='ttt')[0]
        with self.assertRaises(ValueError): d.validate_record(record,original,expected_excluded_demo_indices=(1,))

    def test_two_demo_outer_ttt_is_one_zero_context_supervision(self):
        task = self.task(self.partition.optimizer_ids[0])
        self.assertEqual(len(task.demos),2)
        for heldout in (0,1):
            records=d.outer_ttt_records(task,outer_withheld_demo_index=heldout)
            self.assertEqual(len(records),1)
            self.assertEqual(records[0].prompt.examples,())
            self.assertEqual(records[0].target,task.demos[1-heldout].output)

    def test_ttt_schedules_reject_cross_parent_and_cross_fold_updates(self):
        tasks=[self.task(tid) for tid in self.partition.optimizer_ids[:2]]
        pools=[list(d.loo_records(task,purpose='ttt')) for task in tasks]
        with self.assertRaises(ValueError): d.budgeted_schedule(pools[0]+pools[1],max_records=4,seed='x')
        records=[]
        for heldout in (0,1): records.extend(d.outer_ttt_records(tasks[0],outer_withheld_demo_index=heldout))
        with self.assertRaises(ValueError): d.budgeted_schedule(records,max_records=4,seed='x')

    def test_replayed_record_visible_index_count_must_match_contents(self):
        task=self.task(self.partition.optimizer_ids[0])
        record=d.loo_records(task,purpose='ttt')[0]
        with self.assertRaises(ValueError):
            misleading=dataclasses.replace(record.lineage,visible_demo_indices=(1,),excluded_demo_indices=(0,))
            dataclasses.replace(record,lineage=misleading)

    def test_schedule_rejects_mixed_purpose_or_partition(self):
        task=self.task()
        a=d.loo_records(task,purpose='optimizer',partition=self.partition)[0]
        b=d.loo_records(task,purpose='ttt')[1]
        with self.assertRaises(ValueError): d.budgeted_schedule([a,b],max_records=3,seed='x')
        with self.assertRaises(ValueError): d.budgeted_schedule([a,a],max_records=3,seed='x')


class PackingIndependent(unittest.TestCase):
    def task(self): return selector_fixture()[0]

    @staticmethod
    def render(demos, query): return json.dumps({'demos':demos,'query':query},sort_keys=True)

    def test_real_character_token_count_and_full_grids(self):
        task=self.task()
        out=b.pack_demonstrations(task,render=self.render,encode=lambda text:list(text.encode()))
        self.assertTrue(out['admitted'])
        self.assertEqual(out['prompt_tokens'],len(out['prompt'].encode()))
        rendered=json.loads(out['prompt'])
        self.assertEqual(rendered['demos'],task['demonstrations'])
        self.assertEqual(rendered['query'],task['query_input'])
        self.assertLessEqual(out['prompt_tokens']+out['output_cap'],out['context_limit'])

    def test_callback_inputs_cannot_mutate_original_task(self):
        task=self.task(); original=copy.deepcopy(task)
        def mutate(demos,query):
            if demos: demos[0]['input'][0][0]=9
            query[0][0]=9
            return 'x'
        b.pack_demonstrations(task,render=mutate,encode=lambda text:[1])
        self.assertEqual(task,original)

    def test_outer_heldout_pair_is_never_exposed_to_renderer(self):
        task=self.task()
        held=task['demonstrations'][0]
        task['query_input']=copy.deepcopy(held['input'])
        def inspect(demos,query):
            self.assertNotIn(held['demo_id'],[d['demo_id'] for d in demos])
            self.assertEqual(query,held['input'])
            return self.render(demos,query)
        out=b.pack_demonstrations(task,render=inspect,encode=lambda text:list(text.encode()),withheld_demo_id=held['demo_id'])
        self.assertTrue(out['admitted'])
        self.assertEqual(out['selected_demo_ids'],['b','c'])

    def test_completion_cap_boundary_is_inclusive_and_nonmutating(self):
        for length in (1,1023,1024,1025,3000):
            tokens=[5]*length; before=tokens[:]
            out=b.validate_training_completion(tokens,1024)
            self.assertEqual(out['eligible'],length<=1024)
            self.assertFalse(out['truncated'])
            self.assertEqual(tokens,before)

    def test_training_completion_rejects_invalid_ids(self):
        for bad in ([],[True],[-1],[0.0],(1,2)):
            with self.assertRaises(ValueError): b.validate_training_completion(bad,1024)


if __name__ == '__main__': unittest.main(verbosity=2)
