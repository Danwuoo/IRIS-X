"""All identities/evidence below are synthetic offline fixtures, never readiness evidence."""
from tests.platform_requirements import requires_linux
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import publish_arc_next_offline_quicksave as p
from tools import stage_arc_next_offline as stage
from tools import stage_arc_next_notebook as previous_stage

HAS_SDK = importlib.util.find_spec('kagglesdk') is not None


@requires_linux('Common fixture requires durable O_DIRECTORY/directory-fsync transport writes before every method')
class OfflineQuickSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-offlinev2-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'
        self.journal = self.root / 'journal'
        self.evidence = self.root / 'assets-evidence.synthetic.json'
        self.previous = self.root / 'previous-source.synthetic.json'
        self.review = self.root / 'independent-review.synthetic.json'
        self.claim_patch = patch.object(p, 'ROOT', self.root / 'repo')
        self.claim_patch.start()
        self.addCleanup(self.claim_patch.stop)
        self.pins = {
            role: dict(reference='danielwuu/' + slug + '/71', manifest_sha256=str(i) * 64, private=True)
            for i, (role, slug) in enumerate((('runtime', 'synthetic-runtime-fixture'),
                ('model', 'synthetic-model-fixture'), ('wheels', 'synthetic-wheels-fixture')), 1)
        }
        self.nb = stage.notebook(self.pins)
        self.meta = dict(id=p.REF, title=p.SLUG, code_file='notebook.ipynb', language='python', kernel_type='notebook',
            is_private=True, enable_gpu=False, enable_internet=False,
            dataset_sources=[self.pins[k]['reference'] for k in p.ROLES],
            competition_sources=list(p.PRESERVED_COMPETITION_SOURCES), kernel_sources=[], model_sources=[])
        p.write(self.package / 'notebook.ipynb', self.nb)
        p.write(self.package / 'kernel-metadata.json', self.meta)
        self.assets = dict(format=p.ASSETS_FORMAT, assets={})
        for role in p.ROLES:
            receipt = self.root / (role + '-receipt.synthetic.json')
            p.write(receipt, dict(synthetic_fixture=True, reference=self.pins[role]['reference']))
            self.assets['assets'][role] = dict(**self.pins[role], dataset_ready=True, files_verified=True,
                receipts=[dict(path=receipt.name, sha256=p.sha(receipt.read_bytes()))])
        p.write(self.evidence, self.assets)
        prior = previous_stage.notebook({'source_digest': 'a' * 64, 'source_commit': 'b' * 40}, {'tools/__init__.py': b''})
        p.write(self.previous, self.source_value(prior, 1, [], []))
        self.calls = []
        self.save_error = None
        self.save_status = 200
        self.post_status = 200
        self.pre_mutation = None
        self.receipt_mutation = None
        self.on_pre_read = None

    def source_value(self, notebook=None, version=2, refs=None, competitions=None):
        return dict(metadata=dict(id=p.KERNEL_ID, ref=p.REF, title=p.SLUG, currentVersionNumber=version,
            isPrivate=True, enableGpu=False, enableTpu=False, enableInternet=False, language='python',
            kernelType='notebook', datasetDataSources=self.meta['dataset_sources'] if refs is None else refs,
            competitionDataSources=self.meta['competition_sources'] if competitions is None else competitions),
            blob=dict(source=p.canonical(self.nb if notebook is None else notebook).decode()))

    def prepare(self):
        # Guard against even an accidental true Requests send during prepare.
        with patch('requests.sessions.Session.send', side_effect=AssertionError('network is forbidden in offline prepare')):
            binding = p.prepare(self.package, self.journal, self.evidence, self.previous)
        p.write(self.review, dict(binding, verdict='PASS', reviewer='synthetic-test-reviewer', reviewed_at=p.utc()))
        return binding

    def client(self):
        from kagglesdk import KaggleClient
        from kagglesdk.kaggle_env import KaggleEnv
        import requests
        client = KaggleClient(env=KaggleEnv.PROD, verbose=False, api_token='OFFLINE-NOT-A-CREDENTIAL')
        client.http_client()._init_session()
        session = client.http_client()._session
        self.active_session = session

        def fake_send(prepared, **kwargs):
            self.assertEqual(kwargs['allow_redirects'], False)
            self.assertEqual(kwargs['stream'], True)
            self.assertEqual(kwargs['timeout'], (15, 120))
            self.calls.append((prepared.url, p.parse(prepared.body)))
            status = 200
            if prepared.url == p.SOURCE_URL:
                request = p.parse(prepared.body)
                self.assertEqual(request, {'userName': p.OWNER, 'kernelSlug': p.SLUG})
                if not any(url == p.SAVE_URL for url, _ in self.calls):
                    body = p.read(self.previous)
                    body['metadata']['competitionDataSources'] = list(p.PRESERVED_COMPETITION_SOURCES)
                    if self.pre_mutation:
                        self.pre_mutation(body)
                    if self.on_pre_read:
                        self.on_pre_read()
                else:
                    body, status = self.source_value(), self.post_status
            elif prepared.url == p.SAVE_URL:
                # Reservation and sends=1 must already be durable before any mutating wire.
                ledger = p.read(self.journal / 'ledger.json')
                self.assertTrue(p.claim_path().is_file())
                self.assertEqual(ledger['publication_reserved'], 1)
                self.assertEqual(ledger['events'][0]['sends'], 1)
                if self.save_error:
                    raise self.save_error
                body = dict(ref=p.REF, url=p.PUBLIC_URL, versionNumber=2, kernelId=p.KERNEL_ID)
                status = self.save_status
                if self.receipt_mutation:
                    self.receipt_mutation(body)
            else:
                raise AssertionError('runtime/status/other network endpoint forbidden')
            response = requests.Response()
            response.status_code = status
            response.url = prepared.url
            response._content = p.canonical(body)
            response._content_consumed = True
            response.headers['content-type'] = 'application/json'
            return response
        session.send = fake_send
        return client

    def publish(self):
        with patch.object(p, 'official_client', side_effect=self.client):
            return p.publish(self.package, self.journal, self.review)

    def test_inspect_staged_assets_remain_pending(self):
        value = p.inspect(self.package)
        self.assertFalse(value['publication_ready'])
        self.assertTrue(value['assets_verification_required'])
        self.assertEqual(value['expected_previous_version'], 1)
        self.assertEqual(value['expected_next_version'], 2)
        self.assertEqual(value['dataset_pins'], self.pins)
        self.assertFalse(self.journal.exists())
        self.assertFalse(p.claim_path().exists())

    def test_closed_scope_and_explicit_versioned_mounts(self):
        _, wire, _ = p.request_fields(self.package)
        self.assertEqual(wire['kernelExecutionType'], 'QUICK_SAVE')
        self.assertEqual(wire['datasetDataSources'], self.meta['dataset_sources'])
        self.assertEqual(wire['competitionDataSources'], ['arc-prize-2026-arc-agi-3'])
        self.assertTrue(wire['isPrivate'])
        for name in ('enableGpu', 'enableTpu', 'enableInternet'):
            self.assertIs(wire[name], False)
        for name in ('id', 'machineShape', 'accelerator', 'sessionTimeoutSeconds'):
            self.assertNotIn(name, wire)
        self.assertNotIn('manual-20261008-001', str(p.claim_path()))

    def test_metadata_public_accelerator_internet_or_external_inputs_blocked(self):
        for key, value in (('is_private', False), ('enable_gpu', True), ('enable_internet', True),
                ('competition_sources', ['arc-prize-2025']), ('dataset_sources', ['danielwuu/unversioned'])):
            with self.subTest(key=key):
                altered = dict(self.meta, **{key: value})
                p.write(self.package / 'kernel-metadata.json', altered)
                with self.assertRaises(RuntimeError):
                    p.package_info(self.package)
        p.write(self.package / 'kernel-metadata.json', self.meta)

    def test_successor_competition_metadata_must_be_exactly_preserved_arc3(self):
        for value in (None, [], ['arc-prize-2025'], ['arc-prize-2026-arc-agi-3', 'arc-prize-2025'],
                      ['arc-prize-2026-arc-agi-3'] * 2, 'arc-prize-2026-arc-agi-3'):
            altered = copy.deepcopy(self.meta)
            if value is None:
                del altered['competition_sources']
            else:
                altered['competition_sources'] = value
            p.write(self.package / 'kernel-metadata.json', altered)
            with self.subTest(competitions=value), self.assertRaises(RuntimeError):
                p.request_fields(self.package)
        p.write(self.package / 'kernel-metadata.json', self.meta)
        nb = copy.deepcopy(self.nb)
        del nb['metadata']['irisx_preserved_competition_sources']
        p.write(self.package / 'notebook.ipynb', nb)
        with self.assertRaises(RuntimeError):
            p.package_info(self.package)

    def test_historical_v1_evidence_stays_without_competition_attachment(self):
        frozen = p.read(self.previous)
        self.assertEqual(p.previous_info(self.previous, journal=self.journal)['historical_previous_competition_sources'], [])
        for competitions in (['arc-prize-2026-arc-agi-3'], ['arc-prize-2025']):
            altered = copy.deepcopy(frozen)
            altered['metadata']['competitionDataSources'] = competitions
            p.write(self.previous, altered)
            with self.subTest(competitions=competitions), self.assertRaises(RuntimeError):
                p.previous_info(self.previous, journal=self.journal)
        p.write(self.previous, frozen)

    def test_successor_source_must_retain_only_exact_preserved_arc3(self):
        for competitions in (None, [], ['arc-prize-2025'], ['arc-prize-2026-arc-agi-3', 'arc-prize-2025'],
                             ['arc-prize-2026-arc-agi-3'] * 2, 'arc-prize-2026-arc-agi-3'):
            raw = self.source_value()
            if competitions is None:
                del raw['metadata']['competitionDataSources']
            else:
                raw['metadata']['competitionDataSources'] = competitions
            with self.subTest(competitions=competitions), self.assertRaises(RuntimeError):
                p.verify_source_value(raw, self.package)
        for key in ('kernelDataSources', 'modelDataSources'):
            raw = self.source_value()
            raw['metadata'][key] = ['danielwuu/unapproved/1']
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                p.verify_source_value(raw, self.package)
        result = p.verify_source_value(self.source_value(), self.package)
        self.assertEqual(result['preserved_competition_sources'], ['arc-prize-2026-arc-agi-3'])
        self.assertTrue(result['preserved_competition_attachment_verified'])
        self.assertFalse(result['competition_data_use_authorized'])

    def test_numeric_versions_and_independent_roles_required(self):
        for reference in ('danielwuu/asset', 'danielwuu/asset/latest', 'other/asset/1', 'danielwuu/asset/0'):
            pins = copy.deepcopy(self.pins)
            pins['model']['reference'] = reference
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                p.verified_pins(pins)
        pins = copy.deepcopy(self.pins)
        pins['wheels']['reference'] = pins['model']['reference'].rsplit('/', 1)[0] + '/72'
        with self.assertRaises(RuntimeError):
            p.verified_pins(pins)

    def test_each_asset_readiness_flag_and_binding_is_required(self):
        for role in p.ROLES:
            for key, value in (('private', False), ('dataset_ready', False), ('files_verified', False),
                    ('reference', 'danielwuu/wrong/1'), ('manifest_sha256', 'e' * 64), ('receipts', [])):
                with self.subTest(role=role, key=key):
                    assets = copy.deepcopy(self.assets)
                    assets['assets'][role][key] = value
                    p.write(self.evidence, assets)
                    with self.assertRaises(RuntimeError):
                        p.assets_info(self.evidence, self.pins, journal=self.journal)
        p.write(self.evidence, self.assets)
        del self.assets['assets']['wheels']
        p.write(self.evidence, self.assets)
        with self.assertRaises(RuntimeError):
            p.assets_info(self.evidence, self.pins, journal=self.journal)

    def test_receipt_missing_changed_empty_or_inside_journal_blocked(self):
        item = self.assets['assets']['runtime']['receipts'][0]
        location = self.root / item['path']
        original = location.read_bytes()
        for body in (b'changed', b''):
            location.write_bytes(body)
            with self.assertRaises(RuntimeError):
                p.assets_info(self.evidence, self.pins, journal=self.journal)
        location.unlink()
        with self.assertRaises(RuntimeError):
            p.assets_info(self.evidence, self.pins, journal=self.journal)
        p.atomic_bytes(self.journal / 'receipt.json', original)
        item['path'] = str(self.journal / 'receipt.json')
        p.write(self.evidence, self.assets)
        with self.assertRaises(RuntimeError):
            p.assets_info(self.evidence, self.pins, journal=self.journal)

    def test_parent_segments_cannot_hide_evidence_inside_journal(self):
        self.journal.mkdir()
        p.write(self.journal / 'evidence.json', self.assets)
        disguised = self.root / 'other' / '..' / 'journal' / 'evidence.json'
        with self.assertRaisesRegex(RuntimeError, 'outside mutable'):
            p.assets_info(disguised, self.pins, journal=self.journal)
        p.write(self.journal / 'previous.json', p.read(self.previous))
        disguised = self.root / 'other' / '..' / 'journal' / 'previous.json'
        with self.assertRaisesRegex(RuntimeError, 'outside new journal'):
            p.previous_info(disguised, journal=self.journal)

    def test_preserved_previous_exact_private_v1_required(self):
        raw = p.read(self.previous)
        for key, value in (('id', 137630088), ('currentVersionNumber', 2), ('currentVersionNumber', True),
                ('isPrivate', False), ('enableGpu', True), ('enableTpu', True), ('enableInternet', True)):
            with self.subTest(key=key, value=value):
                altered = copy.deepcopy(raw)
                altered['metadata'][key] = value
                p.write(self.previous, altered)
                with self.assertRaises(RuntimeError):
                    p.previous_info(self.previous, journal=self.journal)
        p.write(self.previous, raw)

    def test_source_exact_all_cells_flags_pins_and_identity(self):
        result = p.verify_source_value(self.source_value(), self.package)
        self.assertTrue(result['source_only_verified'])
        self.assertTrue(result['dataset_versions_verified'])
        self.assertFalse(result['runtime_state_queried'])
        self.assertFalse(result['gpu_allocation_queried'])
        for mutation in (
            lambda raw: raw['metadata'].update(currentVersionNumber=1),
            lambda raw: raw['metadata'].update(id=p.KERNEL_ID + 1),
            lambda raw: raw['metadata'].update(enableGpu=True),
            lambda raw: raw['metadata'].update(datasetDataSources=[x.rsplit('/', 1)[0] for x in self.meta['dataset_sources']]),
            lambda raw: raw['metadata'].update(competitionDataSources=['wrong']),
        ):
            raw = self.source_value()
            mutation(raw)
            with self.assertRaises(RuntimeError):
                p.verify_source_value(raw, self.package)
        for change in ('markdown', 'switch', 'outputs', 'pin'):
            nb = copy.deepcopy(self.nb)
            if change == 'markdown':
                nb['cells'][0]['source'].append('A changed explanation\n')
            elif change == 'switch':
                nb['cells'][1]['source'] = [s.replace('VERIFY_OFFLINE_INPUTS = False', 'VERIFY_OFFLINE_INPUTS = True')
                    for s in nb['cells'][1]['source']]
            elif change == 'outputs':
                nb['cells'][1]['outputs'] = [{'output_type': 'stream', 'name': 'stdout', 'text': 'run'}]
            else:
                nb['metadata']['irisx_offline_dataset_pins']['model']['manifest_sha256'] = 'f' * 64
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                p.verify_source_value(self.source_value(nb), self.package)

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_actual_official_sdk_dummy_wire_is_fully_offline(self):
        from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
        req, wire, _ = p.request(self.package)
        self.assertEqual(req.kernel_execution_type, KernelExecutionType.QUICK_SAVE)
        with patch('requests.sessions.Session.send', side_effect=AssertionError('real network forbidden')):
            body = p.capture_prepared(req, wire)
        self.assertEqual(p.parse(body), wire)

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_prepare_and_review_bind_wire_source_assets_and_v1(self):
        binding = self.prepare()
        self.assertEqual(binding['assets_evidence_sha256'], p.sha(self.evidence.read_bytes()))
        self.assertEqual(binding['prepared_body_sha256'], p.sha((self.journal / 'prepared-request.body').read_bytes()))
        self.assertEqual(binding['previous_source_sha256'], p.sha(self.previous.read_bytes()))
        self.assertEqual(binding['previous_source_text_sha256'], p.sha(p.read(self.previous)['blob']['source'].encode()))
        self.assertEqual(binding['historical_previous_competition_sources'], [])
        self.assertEqual(binding['expected_live_predecessor_competition_sources'], ['arc-prize-2026-arc-agi-3'])
        self.assertEqual(binding['expected_successor_competition_sources'], ['arc-prize-2026-arc-agi-3'])
        self.assertTrue(binding['preserved_competition_attachment_only'])
        self.assertFalse(binding['competition_data_use_authorized'])
        self.assertEqual(binding['source_implementation_sha256'], p.source_implementation()['source_implementation_sha256'])
        self.assertEqual(binding['prepared_headers_sha256'], p.sha(p.canonical(binding['prepared_headers'])))
        self.assertEqual(binding['prepared_headers']['content-type'], 'application/json')
        self.assertEqual(set(binding['prepared_headers']), {'content-type', 'content-length'})
        for path in self.journal.iterdir():
            if path.is_file():
                self.assertNotIn(b'OFFLINE-NOT-A-CREDENTIAL', path.read_bytes())
        self.assertFalse(p.claim_path().exists())
        ledger, _, _ = p.load_bound(self.package, self.journal)
        self.assertEqual(ledger['state'], 'prepared-not-sent')
        p.verify_review(ledger, self.review)
        for key in ('assets_evidence_sha256', 'prepared_body_sha256', 'source_implementation_sha256', 'previous_source_sha256'):
            value = dict(binding, verdict='PASS', reviewer='synthetic', reviewed_at=p.utc())
            value[key] = '0' * 64
            p.write(self.review, value)
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                p.verify_review(ledger, self.review)

    def test_representation_headers_are_closed_and_secrets_not_retained(self):
        _, wire, _ = p.request_fields(self.package)
        body = p.canonical(wire)
        good = {'Content-Type': 'application/json', 'Content-Length': str(len(body)),
                'Authorization': 'NEVER-RETAIN-AUTH-MARKER', 'Cookie': 'NEVER-RETAIN-COOKIE-MARKER'}
        prepared = SimpleNamespace(method='POST', url=p.SAVE_URL, body=body, headers=good)
        self.assertEqual(p.wire_body(prepared, wire), body)
        self.assertEqual(p.representation_headers(prepared, body),
                         {'content-type': 'application/json', 'content-length': str(len(body))})
        for update in ({'Content-Type': 'text/plain'}, {'Host': 'unreviewed.invalid'},
                {'Content-Length': str(len(body) + 1)}, {'Content-Length': len(body)},
                {'Transfer-Encoding': 'chunked'}, {'Content-Encoding': 'gzip'},
                {'content-type': 'application/json'}):
            prepared.headers = dict(good, **update)
            with self.subTest(update=update), self.assertRaises(RuntimeError):
                p.wire_body(prepared, wire)
        prepared.headers = {'Content-Length': str(len(body))}
        with self.assertRaises(RuntimeError):
            p.wire_body(prepared, wire)
        prepared.headers = {'Content-Type': 'application/json', 'Host': 'api.kaggle.com'}
        self.assertEqual(p.wire_body(prepared, wire), body)
        with self.assertRaises(RuntimeError):
            p.wire_body(prepared, wire, {'content-type': 'application/json'})

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_corrupt_representation_header_blocks_before_source_network(self):
        self.prepare()
        def corrupt_client():
            client = self.client()
            client.http_client()._session.headers['Content-Type'] = 'text/plain'
            client.http_client()._session.headers['Host'] = 'unreviewed.invalid'
            return client
        with patch.object(p, 'official_client', side_effect=corrupt_client), self.assertRaises(RuntimeError):
            p.publish(self.package, self.journal, self.review)
        self.assertEqual(self.calls, [])
        self.assertFalse(p.claim_path().exists())

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_header_change_after_source_blocks_save_and_freezes_reservation(self):
        self.prepare()
        self.on_pre_read = lambda: self.active_session.headers.update({'Content-Type': 'text/plain'})
        with self.assertRaisesRegex(RuntimeError, 'frozen'):
            self.publish()
        self.assertEqual([url for url, _ in self.calls], [p.SOURCE_URL])
        ledger = p.read(self.journal / 'ledger.json')
        self.assertEqual(ledger['state'], 'frozen-uncertain-no-retry')
        self.assertEqual(ledger['events'][0]['sends'], 0)
        self.assertTrue(p.claim_path().exists())

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_post_prepare_receipt_or_implementation_mutation_blocks(self):
        self.prepare()
        with patch.object(p, 'source_implementation', return_value=dict(source_implementation_files={},
                source_implementation_sha256='0' * 64)):
            with self.assertRaises(RuntimeError):
                p.load_bound(self.package, self.journal)
        receipt = self.root / self.assets['assets']['wheels']['receipts'][0]['path']
        receipt.write_text('changed')
        with patch.object(p, 'official_client', side_effect=AssertionError('must block before auth')), self.assertRaises(RuntimeError):
            p.publish(self.package, self.journal, self.review)

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_one_synthetic_sdk_save_exact_source_readback_and_no_resend(self):
        self.prepare()
        result = self.publish()
        self.assertEqual([url for url, _ in self.calls], [p.SOURCE_URL, p.SAVE_URL, p.SOURCE_URL])
        self.assertEqual(result['kernel_id'], p.KERNEL_ID)
        self.assertEqual(result['version'], 2)
        self.assertTrue(result['actual_wire_quicksave_verified'])
        self.assertEqual(p.read(self.journal / 'ledger.json')['state'], 'offline-v2-private-quicksave-source-verified')
        with self.assertRaises(RuntimeError):
            self.publish()
        with self.assertRaises(RuntimeError):
            p.prepare(self.package, self.root / 'second-journal', self.evidence, self.previous)
        self.assertEqual(sum(url == p.SAVE_URL for url, _ in self.calls), 1)

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_live_v1_mismatch_blocks_before_reservation_or_save(self):
        self.prepare()
        self.pre_mutation = lambda raw: raw['metadata'].update(currentVersionNumber=2)
        with self.assertRaises(RuntimeError):
            self.publish()
        self.assertEqual([url for url, _ in self.calls], [p.SOURCE_URL])
        self.assertFalse(p.claim_path().exists())

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_live_predecessor_requires_only_exact_existing_arc3(self):
        self.prepare()
        binding = p.read(self.journal / 'ledger.json')['bindings']
        for index, competitions in enumerate((None, [], ['arc-prize-2025'],
                ['arc-prize-2026-arc-agi-3', 'arc-prize-2025'],
                ['arc-prize-2026-arc-agi-3'] * 2, 'arc-prize-2026-arc-agi-3')):
            def mutate(raw, value=competitions):
                if value is None:
                    del raw['metadata']['competitionDataSources']
                else:
                    raw['metadata']['competitionDataSources'] = value
            self.pre_mutation = mutate
            with self.client() as client, self.subTest(competitions=competitions), self.assertRaises(RuntimeError):
                p.confirm_previous(client, self.root / f'live-invalid-{index}.json', binding)
        self.pre_mutation = None
        with self.client() as client:
            result = p.confirm_previous(client, self.root / 'live-valid.json', binding)
        self.assertEqual(result['preserved_competition_sources'], ['arc-prize-2026-arc-agi-3'])
        self.assertEqual(result['source_text_sha256'], binding['previous_source_text_sha256'])
        self.assertFalse(p.claim_path().exists())
        self.assertTrue(all(url == p.SOURCE_URL for url, _ in self.calls))

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_live_previous_source_text_must_be_byte_identical(self):
        self.prepare()
        # Whitespace preserves canonical notebook/cell hashes but violates exact text bytes.
        self.pre_mutation = lambda raw: raw['blob'].update(source=raw['blob']['source'] + '\n')
        with self.assertRaisesRegex(RuntimeError, 'live v1 source differs'):
            self.publish()
        self.assertEqual([url for url, _ in self.calls], [p.SOURCE_URL])
        self.assertFalse(p.claim_path().exists())
        self.assertEqual(p.read(self.journal / 'ledger.json')['events'], [])

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_review_binds_historical_live_and_successor_competition_lists(self):
        binding = self.prepare()
        ledger = p.read(self.journal / 'ledger.json')
        for key in ('historical_previous_competition_sources', 'expected_live_predecessor_competition_sources',
                    'expected_successor_competition_sources'):
            review = dict(binding, verdict='PASS', reviewer='synthetic', reviewed_at=p.utc())
            review[key] = ['arc-prize-2025']
            p.write(self.review, review)
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                p.verify_review(ledger, self.review)

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_receipt_changed_during_live_source_check_blocks_before_save(self):
        self.prepare()
        receipt = self.root / self.assets['assets']['runtime']['receipts'][0]['path']
        self.on_pre_read = lambda: receipt.write_text('changed-during-read')
        with self.assertRaises(RuntimeError):
            self.publish()
        self.assertEqual([url for url, _ in self.calls], [p.SOURCE_URL])
        self.assertFalse(p.claim_path().exists())

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_ambiguous_save_is_frozen_and_never_retried(self):
        self.prepare()
        self.save_error = TimeoutError('synthetic unknown outcome')
        with self.assertRaisesRegex(RuntimeError, 'frozen'):
            self.publish()
        ledger = p.read(self.journal / 'ledger.json')
        self.assertEqual(ledger['state'], 'frozen-uncertain-no-retry')
        self.assertEqual(ledger['events'][0]['sends'], 1)
        self.assertTrue(p.claim_path().exists())
        with self.assertRaises(RuntimeError):
            self.publish()
        self.assertEqual(sum(url == p.SAVE_URL for url, _ in self.calls), 1)
        with self.assertRaises(RuntimeError):
            p.verify_source(self.package, self.journal)

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_wrong_save_receipt_version_freezes(self):
        self.prepare()
        self.receipt_mutation = lambda raw: raw.update(versionNumber=3)
        with self.assertRaisesRegex(RuntimeError, 'frozen'):
            self.publish()
        self.assertEqual(p.read(self.journal / 'ledger.json')['state'], 'frozen-uncertain-no-retry')
        self.assertEqual([url for url, _ in self.calls], [p.SOURCE_URL, p.SAVE_URL])

    @unittest.skipUnless(HAS_SDK, 'installed official SDK required')
    def test_post_save_source_failure_allows_only_source_retry(self):
        self.prepare()
        self.post_status = 503
        with self.assertRaisesRegex(RuntimeError, 'never resend'):
            self.publish()
        self.assertEqual(p.read(self.journal / 'ledger.json')['state'], 'accepted-source-unverified')
        self.post_status = 200
        with patch.object(p, 'official_client', side_effect=self.client):
            result = p.verify_source(self.package, self.journal)
        self.assertEqual(result['version'], 2)
        self.assertEqual(sum(url == p.SAVE_URL for url, _ in self.calls), 1)
        self.assertEqual(sum(url == p.SOURCE_URL for url, _ in self.calls), 3)


if __name__ == '__main__':
    unittest.main()
