import tempfile
from pathlib import Path
import unittest
import zipfile
from tools.arc_next_environment import prepare_environment,wheel_identity
class EnvironmentTests(unittest.TestCase):
    def test_disabled_does_nothing(self):
        self.assertEqual(prepare_environment('missing','missing')['network_calls'],0)
    def test_exact_boolean(self):
        with self.assertRaises(ValueError):prepare_environment('missing','missing',enabled='False')
    def test_wheel_identity_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'tiny.whl'
            with zipfile.ZipFile(p,'w') as z:z.writestr('tiny-1.dist-info/METADATA','Name: tiny_package\nVersion: 1.2.3\n')
            self.assertEqual(wheel_identity(p),('tiny-package','1.2.3'))
if __name__=='__main__':unittest.main()
