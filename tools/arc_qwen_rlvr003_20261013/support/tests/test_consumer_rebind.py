"""Local binder tests on authenticated historical bytes; no model/provider imports."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
OLD = BASE / 'portfolio63-rl-bootstrap-repair-20261013/release-candidate-001/terminal-consumer'
RELEASE = BASE / 'portfolio63-rl-bootstrap-repair-20261013/consumer-binding-final-001'
RUNTIME = BASE / 'portfolio63-rl-environment-repair-20261013'
COLLECTOR = BASE / 'portfolio63-rl-bootstrap-repair-20261013/publication/rl_collect.py'
PATH = ROOT / 'assembly/rebind_consumer.py'
M = types.ModuleType('pin_only_binder_test')
M.__file__ = str(PATH)
exec(compile(PATH.read_bytes(), str(PATH), 'exec', dont_inherit=True), M.__dict__)


class ConsumerRebindTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def bind(self, **changes):
        args = dict(old=OLD, release=RELEASE,
                    source_inventory=RUNTIME / 'RELEASE-SOURCE-INVENTORY.json',
                    source_archive=RUNTIME / 'RELEASE-SOURCE.zip',
                    collector=COLLECTOR, out=self.root / 'out')
        args.update(changes)
        return M.bind(**args)

    def copy(self, src, name):
        dest = self.root / name
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns('__pycache__'))
        return dest

    def test_historical_roundtrip_exact_all24(self):
        result = self.bind()
        self.assertEqual(len(result['files']), 24)
        for name in result['files']:
            self.assertEqual((OLD / name).read_bytes(), (self.root / 'out' / name).read_bytes())
        self.assertFalse(result['production_admission'])

    def test_changed_entry_rejected(self):
        old = self.copy(OLD, 'old')
        (old / 'reviewed_entry.py').write_bytes(b'raise RuntimeError("untrusted")')
        with self.assertRaisesRegex(ValueError, 'outside-in pins'):
            self.bind(old=old)

    def test_extra_file_rejected(self):
        old = self.copy(OLD, 'old')
        (old / 'extra.py').write_text('')
        with self.assertRaisesRegex(ValueError, '24-file'):
            self.bind(old=old)

    def test_changed_helper_rejected(self):
        old = self.copy(OLD, 'old')
        (old / 'production.py').write_text('')
        with self.assertRaisesRegex(ValueError, 'helper bytes'):
            self.bind(old=old)

    def test_changed_release_document_rejected(self):
        release = self.copy(RELEASE, 'release')
        (release / 'environment.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'release descriptor'):
            self.bind(release=release)

    def test_changed_source_hash_rejected(self):
        inventory = json.loads((RUNTIME / 'RELEASE-SOURCE-INVENTORY.json').read_bytes())
        inventory['source_sha256'] = '0' * 64
        path = self.root / 'inventory.json'
        path.write_text(json.dumps(inventory))
        with self.assertRaisesRegex(ValueError, 'source closure'):
            self.bind(source_inventory=path)

    def test_existing_successor_rejected(self):
        (self.root / 'out').mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh successor'):
            self.bind()

    def test_symlink_rejected(self):
        link = self.root / 'collector.py'
        link.symlink_to(COLLECTOR)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.bind(collector=link)


if __name__ == '__main__':
    unittest.main(verbosity=2)
