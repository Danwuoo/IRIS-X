"""Offline budget and prepared-row contracts; no native ML package imports."""
from types import SimpleNamespace
import ast
import hashlib
import unittest

from tools.nvarc_original_training_inspection_worker import digest, prepared_evidence, zero_work_guard
from tools.nvarc_original_ast_binding import portable_ast_dump


class AstBindingTests(unittest.TestCase):
    def test_empty_python_311_fields_match_frozen_312_but_code_changes_do_not(self):
        source = 'class Sample:\n def loss(self, value):\n  return value + 1\n'
        node = ast.parse(source).body[0]
        expected = portable_ast_dump(node)
        for item in ast.walk(node):
            if isinstance(item, (ast.ClassDef, ast.FunctionDef)):
                item._fields = tuple(key for key in item._fields if key != 'type_params')
                if hasattr(item, 'type_params'): del item.type_params
        self.assertEqual(portable_ast_dump(node), expected)
        changed = portable_ast_dump(ast.parse(source.replace('+ 1', '+ 2')).body[0])
        self.assertNotEqual(hashlib.sha256(changed.encode()).digest(), hashlib.sha256(expected.encode()).digest())

    def test_nonempty_type_parameters_remain_rejected(self):
        node = ast.parse('class Sample: pass').body[0]
        node.type_params = [ast.Name(id='T', ctx=ast.Load())]
        with self.assertRaisesRegex(RuntimeError, 'no type parameters'):
            portable_ast_dump(node)


class ZeroWorkTests(unittest.TestCase):
    def fixture(self):
        calls = []

        def actual(*args, **kwargs):
            calls.append('executed')

        module = type('Module', (), {key: actual for key in
            ('__call__', '_wrapped_call_impl', '_call_impl')})
        tensor = type('Tensor', (), {'backward': actual})
        optimizer = type('Optimizer', (), {'__init__': actual})
        adam = type('Adam', (), {'step': actual})
        adamw = type('AdamW', (), {'step': actual})
        torch = SimpleNamespace(nn=SimpleNamespace(Module=module), Tensor=tensor,
            autograd=SimpleNamespace(backward=actual, grad=actual),
            optim=SimpleNamespace(Optimizer=optimizer, Adam=adam, AdamW=adamw))
        return torch, calls

    def test_all_nine_paths_fail_before_work_and_restore_after_error(self):
        torch, calls = self.fixture()
        events = []
        original = torch.nn.Module.__call__
        with self.assertRaisesRegex(RuntimeError, 'test exit'):
            with zero_work_guard(torch, events.append) as check:
                check()
                targets = [getattr(torch.nn.Module, key) for key in
                    ('__call__', '_wrapped_call_impl', '_call_impl')]
                targets += [torch.Tensor.backward, torch.autograd.backward, torch.autograd.grad,
                    torch.optim.Optimizer.__init__, torch.optim.Adam.step, torch.optim.AdamW.step]
                for target in targets:
                    with self.assertRaisesRegex(RuntimeError, 'zero-work inspection forbids'):
                        target(None)
                self.assertEqual(calls, [])
                self.assertEqual(len(events), 9)
                self.assertTrue(all(row['blocked_before_execution'] for row in events))
                raise RuntimeError('test exit')
        self.assertIs(torch.nn.Module.__call__, original)
        torch.nn.Module.__call__(None)
        self.assertEqual(calls, ['executed'])

    def test_native_import_cannot_silently_replace_guard(self):
        torch, _ = self.fixture()
        original = torch.nn.Module._call_impl
        with zero_work_guard(torch, lambda event: None) as check:
            torch.nn.Module._call_impl = original
            with self.assertRaisesRegex(RuntimeError, 'guard changed'):
                check()
        self.assertIs(torch.nn.Module._call_impl, original)


class PreparedRowsTests(unittest.TestCase):
    def test_native_unused_column_removal_and_changed_mask_are_observed(self):
        source = [{'input_ids': [14, 11, 10, 1, 15], 'labels': [-100, -100, -100, 1, 15]} for _ in range(128)]
        raw = [{'text': 'do not pass this string to padding', 'input_ids': row['input_ids']} for row in source]
        removed = []

        def strip(dataset, description):
            removed.append(description)
            return [{'input_ids': row['input_ids']} for row in dataset]

        class Batch:
            shape = (1, 5)
            def __init__(self, values): self.values = values
            def __getitem__(self, index): return self
            def tolist(self): return self.values

        seen = []
        def collator(rows):
            self.assertEqual(set(rows[0]), {'input_ids'})
            index = len(seen); seen.append(index)
            labels = list(source[index]['labels'])
            if index == 127: labels[3] = -100
            return {'input_ids': Batch(rows[0]['input_ids']), 'labels': Batch(labels)}

        trainer = SimpleNamespace(train_dataset=raw, _remove_unused_columns=strip)
        expected = [{'input_ids_digest': digest(row['input_ids']), 'labels_digest': digest(row['labels'])} for row in source]
        result = prepared_evidence(trainer, collator, expected)
        self.assertEqual(removed, ['native-inspection'])
        self.assertEqual(len(result), 128)
        self.assertTrue(all(row['source_input_ids_equal'] for row in result))
        self.assertTrue(all(row['source_labels_equal'] for row in result[:-1]))
        self.assertFalse(result[-1]['source_labels_equal'])
        self.assertEqual(result[-1]['supervised_tokens'], 1)

    def test_native_truncation_cannot_claim_full_views(self):
        trainer = SimpleNamespace(train_dataset=[{}] * 127)
        with self.assertRaisesRegex(RuntimeError, 'all complete source views'):
            prepared_evidence(trainer, None, [{}] * 128)


if __name__ == '__main__':
    unittest.main()
