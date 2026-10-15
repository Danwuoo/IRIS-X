"""Independent synthetic regressions for the historical/live observation boundary."""
import importlib.util
from pathlib import Path
import types
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    'context_observer_integrity_fixture', HERE / 'test_context_continuation.py')
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class ObserverIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.ContextTests.setUpClass()

    def make_context(self):
        case = fixture.ContextTests(methodName='runTest')
        self.addCleanup(case.doCleanups)
        case.setUp()
        return case

    def assert_event_mutation_rejected(self, *, completion, publication):
        case = self.make_context()
        if publication:
            case.bind_publication()
        eligible = case.r._document(case.eligibility)
        reservation = case.r._document(eligible['reservation'])
        preparation = case.r._document(reservation['capability']['preparation'])
        if completion:
            seal_path = next(case.state.glob('recovery-epoch-*-sealed.claim.json'))
            rows = case.r._document(case.r.descriptor(seal_path))['files']
        else:
            rows = case.r._document(preparation['inventory'])['files']
        relative = next(row['path'] for row in rows if row['path'].startswith('events/'))
        path = case.state / relative
        root_before = case.r._root_records(case.state)
        event_before = path.read_bytes()

        def observer(review, challenge):
            # No root, manifest, directory membership or native receipt changes.
            # An in-place edit must still invalidate the sealed historical bytes.
            path.write_bytes(event_before + b' ')
            return case.boot

        case.callbacks['recovery_boot_observation'] = observer
        with self.assertRaisesRegex(ValueError, 'descriptor_changed'):
            case.validate()
        self.assertEqual(root_before, case.r._root_records(case.state))

    def test_original_inventory_event_mutation_is_rejected_after_observer(self):
        for publication in (False, True):
            with self.subTest(publication=publication):
                self.assert_event_mutation_rejected(completion=False, publication=publication)

    def test_completion_seal_event_mutation_is_rejected_after_observer(self):
        for publication in (False, True):
            with self.subTest(publication=publication):
                self.assert_event_mutation_rejected(completion=True, publication=publication)

    def test_historical_after_observation_older_than_120_seconds_stays_unsupported(self):
        # Generate an otherwise valid history with the actual frozen finalizer.
        # Never rewrite already-sealed evidence or synthesize a fresh timestamp.
        original_finalize = fixture.f.r.RecoveryOwner.finalize

        def delayed_finalize(owner, *args, **kwargs):
            kwargs['now_epoch'] += 150
            return original_finalize(owner, *args, **kwargs)

        with mock.patch.object(fixture.f.r.RecoveryOwner, 'finalize', delayed_finalize):
            case = self.make_context()
        now = case.fixture.now + 260
        current_boot = fixture.f.write(Path(case.temp.name) / 'fresh-current-boot.json',
            case.fixture.boot(now, case.fixture.now + 50))
        identity = types.SimpleNamespace(state_root=case.state,
            document_sha256=case.fixture.review_value['original_configuration']['sha256'])
        original = case.r.validate_eligibility({'STATE': case.state}, identity, case.pending,
            current_boot_descriptor=current_boot, now_epoch=now)
        self.assertEqual(original, {case.fixture.review_value['unknown_session']:
                                   case.pending[0]['claim']['sha256']})
        before = case.r._scan(case.state)
        with self.assertRaisesRegex(ValueError, 'recovery_eligibility_boot_changed_or_stale'):
            case.validate(current_boot_descriptor=current_boot, now_epoch=now)
        self.assertEqual(case.r._scan(case.state), before)


if __name__ == '__main__':
    unittest.main()
