import ast
import unittest
from irisx.errors import ValidationError
from tools.audit_nvarc_native_ttt_optimizer import function,scalar_functions


class NativeScalarBoundaryTests(unittest.TestCase):
    def test_module_shadowing_selects_final_vendor_binding_and_excludes_nested_definitions(self):
        tree=ast.parse('def schedule(): return 1\ndef holder():\n def schedule(): return 9\ndef schedule(): return 2\n')
        selected=function(tree,'schedule',module_last_binding=True)
        self.assertEqual(ast.literal_eval(selected.body[0].value),2)
        with self.assertRaises(ValidationError):function(tree,'schedule')

    def test_source_scalar_fixture_denies_io_imports_and_unknown_calls_before_execution(self):
        warmup=ast.parse('def get_warmup_steps(self, n: int): return 13').body[0]
        for body in ('__import__("os").getcwd()','open("never-created", "w")','math.sqrt(1)'):
            cosine=ast.parse('def _get_cosine_schedule_with_warmup_lr_lambda(): return '+body).body[0]
            with self.subTest(body=body),self.assertRaises(ValidationError):scalar_functions(warmup,cosine)
        cosine=ast.parse('def _get_cosine_schedule_with_warmup_lr_lambda():\n import os\n return 0').body[0]
        with self.assertRaises(ValidationError):scalar_functions(warmup,cosine)


if __name__=='__main__':unittest.main()
