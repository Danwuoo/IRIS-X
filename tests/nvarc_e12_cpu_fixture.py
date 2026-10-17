"""Explicit deterministic CPU doubles for E12 tests, not historical evidence.

The immutable public INERT001 plan supplies configuration data only. Literal
challenge rows, model logits, DFS returns, transforms and ranking below are
synthetic. Nothing here authenticates native execution or grants permission to
run, publish, score or replace a historical artifact.
"""
import copy
import math
from types import SimpleNamespace as NS

from tools import nvarc_e12_admission as admission
from tools.nvarc_native_multitask import digest, write
from tests.test_nvarc_e10_probe import FakeTensor as BaseTensor, FakeTorch as BaseTorch
from tests.test_nvarc_e10_ttt_probe import fixture as training_fixture
from tests.test_nvarc_e12_run_admission import fixture as admission_fixture


def fixture(root):
    """Current strict INERT profile with fresh, explicitly synthetic inputs."""
    from tools import nvarc_e12_runtime as runtime
    training_plan, _ = training_fixture(root)
    plan = admission_fixture(automatic=False)
    plan.update(task_specs=training_plan['task_specs'],
                model_material_digest=digest('literal CPU model only'),
                dependency_readproof_digest=digest('literal CPU dependency only'),
                source_files_sha256={}, payload_sha256={},
                original_training_arguments={'synthetic': True})
    challenges = {key: {'train': [{'input': [[1]], 'output': [[1]]}],
                        'test': [{'input': [[index + 1]]} for index in range(count)]}
                  for key, count in runtime.TASK_COUNTS.items()}
    write(root / 'challenges.json', challenges)
    plan['challenges_digest'] = digest(challenges)
    plan['owner_editor_admission'] = admission.admission(plan)
    write(root / 'plan.json', plan)
    write(root / 'screen.json', plan)
    return plan


class Array:
    def __init__(self, value):
        self.value = copy.deepcopy(value)

    def tolist(self):
        return copy.deepcopy(self.value)


class FakeTensor(BaseTensor):
    """Small list-backed tensor operations used by the real NLL observer."""
    def numel(self):
        return math.prod(self.shape)

    def __getitem__(self, key):
        if not isinstance(key, tuple):
            return FakeTensor(self.data[key])
        rows, columns = key
        if isinstance(rows, BaseTensor):
            return FakeTensor([self.data[row][column]
                               for row, column in zip(rows.tolist(), columns)])
        if isinstance(rows, int):
            return FakeTensor(self.data[rows][columns])
        return FakeTensor([row[columns] for row in self.data[rows]])

    def log_softmax(self, axis):
        if axis != -1:
            raise AssertionError('literal tensor supports final-axis log_softmax only')

        def transform(values):
            if isinstance(values[0], list):
                return [transform(row) for row in values]
            maximum = max(values)
            normalizer = math.log(sum(math.exp(value - maximum) for value in values))
            return [value - maximum - normalizer for value in values]

        return FakeTensor(transform(self.data))

    def sum(self):
        def total(value):
            return sum(total(row) for row in value) if isinstance(value, list) else value
        return FakeTensor(total(self.data))

    def item(self):
        if isinstance(self.data, list):
            raise AssertionError('literal scalar required')
        return self.data


class FakeTorch(BaseTorch):
    def tensor(self, data, **_kwargs):
        return FakeTensor(data)

    def arange(self, count, **_kwargs):
        return FakeTensor(list(range(count)))


class LiteralEngine:
    """Exercise real accounting with four explicit candidates per test.

Each fake DFS call returns one candidate after one real adapter call. Every
candidate receives two four-row verifier adapter calls. Uniform literal logits
let the observer calculate NLL independently from the fake scorer's answer.
"""
    def __init__(self):
        self.clock = 100.
        self.generated = self.verified = 0
        self.torch = FakeTorch()
        self.tokenizer = NS(encode=lambda text: [10] if text == 'q' else [int(text), 15])

        class Model:
            device = 'literal-cpu'

            def __init__(self):
                self.calls = []
                self.fail_after = None

            def __call__(self, input_ids, **kwargs):
                if self.fail_after is not None and len(self.calls) >= self.fail_after:
                    raise RuntimeError('literal model failure')
                self.calls.append(dict(ids=input_ids.tolist(),
                                       cached=kwargs.get('past_key_values') is not None))
                rows, width = input_ids.shape
                return NS(logits=FakeTensor([[[0.] * 16 for _ in range(width)]
                                             for _ in range(rows)]),
                          past_key_values=object() if kwargs['use_cache'] else None)

        self.model = Model()
        self.loader = NS(np=NS(asarray=Array), ArcDataset=NS(
            invert_mod=lambda array, _key, **_kwargs: array))
        self.decoder = NS(score_kgmon=lambda votes: [vote['solution'] for vote in votes.values()])
        self.solver = NS(inference_turbo_dfs=self.generate,
                         calc_scores=self.verify, turbo_dfs=None)

    def now(self):
        return self.clock

    def generate(self, adapter, prefixes, length, max_score, deadline):
        adapter(input_ids=FakeTensor(prefixes), use_cache=True)
        candidate = self.generated % 4 + 1
        self.generated += 1
        self.clock += 1.
        return [(0, [(.1, [candidate, 15])])]

    def verify(self, queries, answers, tokenizer, adapter):
        rows = [tokenizer.encode(query) + tokenizer.encode(answer)
                for query, answer in zip(queries, answers)]
        adapter(input_ids=FakeTensor(rows), use_cache=False)
        self.verified += 1
        self.clock += .5
        return [2. * math.log(16.) for _ in rows]

    def views(self, _challenges, key, index, *_args):
        base = f'{key}.{index}'
        keys = [f'{base}.{view:02}' for view in range(16)]
        views = NS(keys=keys, get=lambda *_args: {'input': 'q'})
        formatter = NS(convert_tokens_to_array=lambda tokens: Array([[tokens[0]]]))
        return base, None, views, formatter, [keys[offset:offset + 4] for offset in range(0, 16, 4)]

    def rows(self, _puzzle, base, solution, _loader, _formatter, _tokenizer):
        rows = [{'key': f'{base}.verify.{index}', 'input': 'q', 'reply': str(solution[0][0])}
                for index in range(8)]
        bindings = [{'source_view': row['key'], 'query_ids': [10],
                     'answer_ids': [solution[0][0], 15]} for row in rows]
        return rows, bindings
