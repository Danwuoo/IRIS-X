"""Read source literals without executing expressions or collapsing keys."""
import ast
import unittest
from tools.audit_nvarc_original_ttt_policy import literal_dictionary
from irisx.errors import ValidationError


class SourcePolicyLiteralTests(unittest.TestCase):
    def test_original_dict_constructor_keeps_types(self):
        result=literal_dictionary(ast.parse('dict(r=256, use_rslora=True, loftq_config=None)',mode='eval').body)
        self.assertEqual(result,{'r':256,'use_rslora':True,'loftq_config':None})
        self.assertIs(type(result['r']),int)

    def test_source_calls_unpacking_and_duplicate_keys_are_rejected(self):
        for source in ('dict(r=__import__("os").getcwd())','dict(**other)','dict([(1,2)])','dict(a=1,a=2)',"{'a':1,'a':2}"):
            with self.subTest(source=source),self.assertRaises((ValidationError,ValueError)):
                literal_dictionary(ast.parse(source,mode='eval').body)


if __name__=='__main__':unittest.main()
