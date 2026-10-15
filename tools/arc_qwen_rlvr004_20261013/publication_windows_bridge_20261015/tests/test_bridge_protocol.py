"""Offline protocol fault injection, equally active under python -O."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import unittest

PATH = Path(__file__).resolve().parents[1] / 'protocol.py'
spec = importlib.util.spec_from_file_location('test_windows_bridge_protocol', PATH)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
NONCE = 'a' * 64
HASH = 'b' * 64


def req(operation='dataset', arguments=None, sequence=1):
    arguments = {} if arguments is None else arguments
    payload = {'operation': operation, 'arguments': arguments,
               'deadline_epoch': 1792044000, 'max_seconds': min(120, p.OPERATION_TIMEOUTS[operation])}
    digest = p.request_hash(operation, arguments, deadline_epoch=payload['deadline_epoch'], max_seconds=payload['max_seconds'])
    return {'protocol': p.PROTOCOL, 'kind': 'request', 'nonce': NONCE, 'sequence': sequence,
            'request_sha256': digest, 'payload': payload}


def wire(message):
    raw = json.dumps(message, separators=(',', ':')).encode()
    return p.HEADER.pack(p.MAGIC, p.CONTROL, len(raw)) + raw


def content_wire(raw, known=True):
    descriptor = {'cap': max(len(raw), 1), 'expected_bytes': len(raw) if known else None,
                  'expected_sha256': hashlib.sha256(raw).hexdigest() if known else None}
    stream = io.BytesIO()
    result = p.FramedIO(io.BytesIO(), stream, nonce=NONCE).send_content(
        io.BytesIO(raw), descriptor, sequence=1, request_sha256=HASH)
    return stream.getvalue(), descriptor, result


class ShortReader(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 3))


class ShortWriter(io.BytesIO):
    def write(self, raw):
        return super().write(raw[:2])


class ProtocolTests(unittest.TestCase):
    def recovery_open(self):
        return {'account':'danielwuu','versions':{'code_predecessor':20,'code':21,
            'inactive_predecessor':39,'inactive':40,'active':41},'configuration_sha256':HASH,
            'bridge_configuration_sha256':HASH,'publication_manifest_sha256':HASH,
            'deadline_epoch':1792044000,'max_seconds':600,
            'recovery':{'capability_sha256':'c'*64,'reservation_sha256':'d'*64}}

    def test_recovery_open_extends_only_exact_hash_binding(self):
        args=self.recovery_open();p.validate_request('open',args)
        legacy={k:v for k,v in args.items() if k!='recovery'};p.validate_request('open',legacy)
        self.assertNotEqual(p.request_hash('open',args,deadline_epoch=1792044000,max_seconds=120),
                            p.request_hash('open',legacy,deadline_epoch=1792044000,max_seconds=120))
        for value in (None,True,{}, {'capability_sha256':'c'*64},
                      {'capability_sha256':'c'*64,'reservation_sha256':'d'*64,'mode':'recovery'},
                      {'capability_sha256':'c'*64,'reservation_sha256':'raw-secret'}):
            bad=self.recovery_open();bad['recovery']=value
            with self.subTest(value=value),self.assertRaises(p.ProtocolError):p.validate_request('open',bad)

    def test_recovery_metadata_never_extends_later_operation_schema(self):
        for operation in p.OPERATIONS-{'open'}:
            with self.subTest(operation=operation),self.assertRaises(p.ProtocolError):
                p.validate_request(operation,{'recovery':self.recovery_open()['recovery']})

    def test_request_roundtrip_short_io(self):
        message = req()
        out = ShortWriter()
        sender = p.FramedIO(io.BytesIO(), out, nonce=NONCE)
        sender.send('request', message['payload'], sequence=1, request_sha256=message['request_sha256'])
        result = p.FramedIO(ShortReader(out.getvalue()), io.BytesIO(), nonce=NONCE).receive(kinds={'request'})
        self.assertEqual(result, message)

    def test_closed_envelope_keys(self):
        for key in ('token', 'Authorization', 'url', 'pickle', 'path'):
            message = req()
            message[key] = 'secret'
            with self.subTest(key=key), self.assertRaises(p.ProtocolError):
                p.validate_envelope(message)

    def test_upload_cap_separate_from_download_cap(self):
        self.assertGreaterEqual(p.MAX_CONTENT_BYTES, 5 * 1024**3 + 16 * 1024**2)
        for operation, args in [('start_upload', {'name': 'code.zip'}), ('upload_once', {'handle': HASH})]:
            with self.subTest(operation=operation), self.assertRaises(p.ProtocolError):
                p.validate_request(operation, {**args, 'bytes': p.MAX_UPLOAD_BYTES + 1, 'sha256': HASH})

    def test_closed_operation_and_request_fields(self):
        for operation in ('login', 'run_command', 'read_file', 'quota', 'install', 'request', 'get_url'):
            with self.subTest(operation=operation), self.assertRaises(p.ProtocolError):
                p.validate_request(operation, {})
        with self.assertRaises(p.ProtocolError):
            p.validate_request('dataset', {'url': 'https://example.invalid'})

    def test_nonce_sequence_hash_binding(self):
        for field, value in (('nonce', 'c' * 64), ('sequence', 2), ('request_sha256', 'd' * 64)):
            message = req()
            message[field] = value
            channel = p.FramedIO(io.BytesIO(wire(message)), io.BytesIO(), nonce=NONCE)
            with self.subTest(field=field), self.assertRaises(p.ProtocolError):
                channel.receive(kinds={'request'}, sequence=1, request_sha256=req()['request_sha256'])
            self.assertTrue(channel.poisoned)

    def test_deadline_in_request_hash(self):
        message = req()
        changed = copy.deepcopy(message)
        changed['payload']['deadline_epoch'] += 1
        with self.assertRaisesRegex(p.ProtocolError, 'bridge_request_hash'):
            p.validate_envelope(changed)

    def test_request_timeout_caps(self):
        for maximum in (True, -1, 0, 121, float('inf'), float('nan')):
            with self.subTest(maximum=maximum), self.assertRaises(p.ProtocolError):
                p.request_hash('dataset', {}, deadline_epoch=1792044000, max_seconds=maximum)
        p.request_hash('output', {'name': 'evidence.zip', 'version': 1, 'cap': 5 * 1024**3 + 16 * 1024**2,
            'expected_bytes': None, 'expected_sha256': None}, deadline_epoch=1792044000, max_seconds=900)

    def test_wrong_types_and_bool_are_not_integers(self):
        for field, value in (('sequence', True), ('sequence', 0), ('nonce', b'a' * 64),
                             ('request_sha256', 'B' * 64), ('protocol', 1), ('kind', [])):
            message = req()
            message[field] = value
            with self.subTest(field=field), self.assertRaises(p.ProtocolError):
                p.validate_envelope(message)
        with self.assertRaises(p.ProtocolError):
            p.validate_request('list_files', {'dataset': True, 'version': True})

    def test_strict_json_duplicates_all_depths(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}', b'{"x":1,"\\u0078":2}'):
            with self.subTest(raw=raw), self.assertRaisesRegex(p.ProtocolError, 'bridge_duplicate_key'):
                p.strict_json(raw)

    def test_strict_json_no_nonfinite(self):
        for raw in (b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(p.ProtocolError):
                p.strict_json(raw)
        with self.assertRaises(p.ProtocolError):
            p.canonical({'value': float('nan')})

    def test_json_depth_number_unicode_and_size_limits(self):
        cases = [b'{"x":' + b'[' * 30 + b'0' + b']' * 30 + b'}',
                 b'{"x":99999999999999999999999}', b'{"x":"\xff"}', b'{"x":"\\ud800"}', b'[]']
        for raw in cases:
            with self.subTest(raw=raw[:30]), self.assertRaises(p.ProtocolError):
                p.strict_json(raw)
        with self.assertRaises(p.ProtocolError):
            p.canonical({'x': 'a' * (p.MAX_STRING_BYTES + 1)})
        with self.assertRaises(p.ProtocolError):
            p.canonical({'x': [0] * p.MAX_NODES})

    def test_strings_with_braces_do_not_increase_depth(self):
        self.assertEqual(p.strict_json(b'{"x":"[[[{{{\\\""}'), {'x': '[[[{{{"'})

    def test_frame_size_rejected_before_payload_read(self):
        for magic, kind, size in ((b'NOPE', p.CONTROL, 1), (p.MAGIC, 99, 1),
                                 (p.MAGIC, p.CONTROL, p.MAX_CONTROL_BYTES + 1),
                                 (p.MAGIC, p.CONTENT, p.MAX_CHUNK_BYTES + p.CONTENT_HEADER.size + 1)):
            channel = p.FramedIO(io.BytesIO(p.HEADER.pack(magic, kind, size)), io.BytesIO(), nonce=NONCE)
            with self.subTest(kind=kind, size=size), self.assertRaises(p.ProtocolError):
                channel.receive(kinds={'request'})
            self.assertTrue(channel.poisoned)

    def test_truncated_frame_poison_no_retry(self):
        raw = wire(req())
        for length in (0, 1, p.HEADER.size - 1, len(raw) - 1):
            channel = p.FramedIO(io.BytesIO(raw[:length]), io.BytesIO(), nonce=NONCE)
            with self.subTest(length=length), self.assertRaises(p.ProtocolError):
                channel.receive(kinds={'request'})
            with self.assertRaisesRegex(p.ProtocolError, 'bridge_connection_poisoned'):
                channel.receive(kinds={'request'})

    def test_deadline_before_and_after_read(self):
        for times in ([10], [0, 0, 10]):
            values = iter(times)
            channel = p.FramedIO(io.BytesIO(wire(req())), io.BytesIO(), nonce=NONCE,
                                 clock=lambda: next(values, 10), deadline=10)
            with self.subTest(times=times), self.assertRaisesRegex(p.ProtocolError, 'bridge_deadline_exceeded'):
                channel.receive(kinds={'request'})
            self.assertTrue(channel.poisoned)

    def test_unbound_reply_forbidden(self):
        channel = p.FramedIO(io.BytesIO(), io.BytesIO(), nonce=NONCE)
        with self.assertRaisesRegex(p.ProtocolError, 'bridge_expected_binding'):
            channel.receive(kinds={'response'})

    def test_sequence_replay_and_parallel_commands(self):
        guard = p.SequenceGuard()
        guard.accept(req())
        with self.assertRaises(p.ProtocolError):
            guard.accept(req(sequence=2))
        self.assertTrue(guard.failed)
        with self.assertRaises(p.ProtocolError):
            guard.complete(1, req()['request_sha256'])
        guard = p.SequenceGuard()
        guard.accept(req())
        guard.complete(1, req()['request_sha256'])
        with self.assertRaises(p.ProtocolError):
            guard.accept(req())
        self.assertTrue(guard.failed)

    def test_mutation_attempt_consumed_before_outcome(self):
        args = {'name': 'code.zip', 'bytes': 3, 'sha256': 'c' * 64}
        first, second = req('start_upload', args), req('start_upload', args, sequence=2)
        guard = p.SequenceGuard()
        guard.accept(first)
        guard.complete(first['sequence'], first['request_sha256'])
        with self.assertRaisesRegex(p.ProtocolError, 'bridge_mutation_replay'):
            guard.accept(second)
        self.assertTrue(guard.failed)

    def test_error_message_never_raw_exception(self):
        payload = {'code': 'PROVIDER_FAILURE', 'classification': 'PROVIDER_ERROR',
                   'http_status': None, 'retry_after_seconds': None, 'mutation_uncertain': True}
        channel = p.FramedIO(io.BytesIO(), io.BytesIO(), nonce=NONCE)
        channel.send('error', payload, sequence=1, request_sha256=HASH)
        for key, value in (('message', 'Bearer secret'), ('code', 'HTTP https://signed.invalid/?token=x')):
            invalid = {**payload, key: value}
            with self.subTest(key=key), self.assertRaises(p.ProtocolError):
                p.FramedIO(io.BytesIO(), io.BytesIO(), nonce=NONCE).send('error', invalid, sequence=1, request_sha256=HASH)

    def test_host_paths_never_accepted(self):
        for name in ('/tmp/x.zip', '../x.zip', 'a/../x.zip', 'a//x.zip', 'C:\\x.zip', 'C:x.zip',
                     'x.zip:stream', '\\server\\x.zip', 'a/x.zip', '.zip\x00'):
            with self.subTest(name=name), self.assertRaises(p.ProtocolError):
                p.validate_request('start_upload', {'name': name, 'bytes': 1, 'sha256': HASH})

    def test_refresh_proofs_closed_and_bound(self):
        messages = [('refresh_request', {'refresh_id': HASH, 'account': 'danielwuu', 'old_expiration_epoch': 1}),
            ('refresh_ack', {'refresh_id': HASH, 'phase': 'intent', 'claim_sha256': NONCE, 'journal_sha256': HASH}),
            ('refresh_result', {'refresh_id': HASH, 'new_expiration_epoch': 10,
                'official_save_completed': True, 'credential_acl_verified': True}),
            ('refresh_ack', {'refresh_id': HASH, 'phase': 'accepted', 'claim_sha256': NONCE, 'journal_sha256': HASH})]
        stream = io.BytesIO()
        sender = p.FramedIO(io.BytesIO(), stream, nonce=NONCE)
        for kind, payload in messages:
            sender.send(kind, payload, sequence=1, request_sha256=HASH)
        receiver = p.FramedIO(io.BytesIO(stream.getvalue()), io.BytesIO(), nonce=NONCE)
        for kind, payload in messages:
            self.assertEqual(receiver.receive(kinds={kind}, sequence=1, request_sha256=HASH)['payload'], payload)
        invalid = dict(messages[2][1], credential_acl_verified=False)
        with self.assertRaises(p.ProtocolError):
            p.FramedIO(io.BytesIO(), io.BytesIO(), nonce=NONCE).send('refresh_result', invalid, sequence=1, request_sha256=HASH)

    def test_open_session_context_handshake(self):
        args = {'account': 'danielwuu', 'versions': {'code_predecessor': 20, 'code': 21,
            'inactive_predecessor': 39, 'inactive': 40, 'active': 41}, 'configuration_sha256': HASH,
            'bridge_configuration_sha256': HASH, 'publication_manifest_sha256': HASH,
            'deadline_epoch': 1792044000, 'max_seconds': 43200}
        p.validate_envelope(req('open', args))
        p.validate_result('open', {'authenticated': True})
        stream = io.BytesIO()
        channel = p.FramedIO(io.BytesIO(), stream, nonce=NONCE)
        channel.send('ready', {'sdk_lock_sha256': HASH, 'sdk_source_count': 170,
            'account': 'danielwuu', 'existing_official_store': True}, sequence=1, request_sha256=HASH)
        channel.send('ready_ack', {'ready': True}, sequence=1, request_sha256=HASH)
        for field in ('configuration_sha256', 'publication_manifest_sha256', 'bridge_configuration_sha256'):
            changed = copy.deepcopy(args)
            changed[field] = NONCE
            self.assertNotEqual(req('open', args)['request_sha256'], req('open', changed)['request_sha256'])

    def test_metadata_dto_frozen_consumer_fields(self):
        metadata = {'id': 138123872, 'ref': p.REF, 'isPrivate': True, 'currentVersionNumber': 41,
            'title': 'IRIS-X', 'language': 'python', 'kernelType': 'notebook', 'kernelDataSources': [],
            'enableGpu': True, 'enableTpu': False, 'enableInternet': False, 'modelDataSources': ['model'],
            'datasetDataSources': ['dataset'], 'competitionDataSources': ['arc-prize-2026-arc-agi-3'],
            'dockerImage': 'docker', 'machineShape': 'NvidiaRtxPro6000'}
        kernel = p.dto({'metadata': metadata, 'blob': {'source': '{"cells":[]}'}}, 'kernel')
        self.assertEqual(kernel.metadata.current_version_number, 41)
        self.assertTrue(kernel.metadata.is_private)
        self.assertEqual(kernel.metadata.to_dict(), metadata)
        self.assertEqual(kernel.blob.source, '{"cells":[]}')
        status = p.dto({'status': 'ERROR', 'failureMessage': 'GPU unavailable'}, 'status')
        self.assertEqual(status.status.name, 'ERROR')
        self.assertEqual(status.failure_message, 'GPU unavailable')
        dataset = p.dto({'id': 12504696, 'ref': p.DREF, 'isPrivate': True,
            'currentVersionNumber': 21, 'title': 'Code', 'licenseName': 'Other (specified in description)',
            'ownerRef': 'danielwuu', 'versions': [{'versionNumber': 21}]}, 'dataset')
        self.assertEqual(dataset.versions[0].version_number, 21)
        snapshot = kernel.metadata.to_dict()
        snapshot['title'] = 'changed'
        self.assertEqual(kernel.metadata.title, 'IRIS-X')
        with self.assertRaises(AttributeError):
            kernel.metadata = 1

    def test_metadata_unknown_sensitive_keys_rejected(self):
        with self.assertRaises(p.ProtocolError):
            p.validate_result('status', {'status': 'ERROR', 'failureMessage': 'Bearer secret'})
        with self.assertRaises(p.ProtocolError):
            p.validate_result('status', {'status': 'ERROR', 'failureMessage': '', 'token': 'secret'})

    def test_content_roundtrip_known_and_unknown(self):
        for raw in (b'', b'x', b'ab' * 100000):
            for known in (True, False):
                data, descriptor, result = content_wire(raw, known)
                sink = ShortWriter()
                received = p.FramedIO(ShortReader(data), io.BytesIO(), nonce=NONCE).receive_content(
                    sink, descriptor, sequence=1, request_sha256=HASH)
                self.assertEqual(received, result)
                self.assertEqual(sink.getvalue(), raw)

    def test_content_first_envelope_after_refresh_loop(self):
        data, descriptor, result = content_wire(b'hello')
        receiver = p.FramedIO(io.BytesIO(data), io.BytesIO(), nonce=NONCE)
        first = receiver.receive(kinds={'content_start'}, sequence=1, request_sha256=HASH)
        self.assertEqual(receiver.receive_content(io.BytesIO(), descriptor, sequence=1,
            request_sha256=HASH, first=first), result)

    def test_content_iterator_and_oversize_chunks(self):
        stream = io.BytesIO()
        descriptor = {'cap': 3, 'expected_bytes': None, 'expected_sha256': None}
        result = p.FramedIO(io.BytesIO(), stream, nonce=NONCE).send_content(iter([b'a', b'bc']),
            descriptor, sequence=1, request_sha256=HASH)
        self.assertEqual(result['bytes'], 3)
        with self.assertRaises(p.ProtocolError):
            p.FramedIO(io.BytesIO(), io.BytesIO(), nonce=NONCE).send_content(iter([b'a' * (p.MAX_CHUNK_BYTES + 1)]),
                {'cap': p.MAX_CONTENT_BYTES, 'expected_bytes': None, 'expected_sha256': None}, sequence=1, request_sha256=HASH)

    def test_complete_upload_verified_before_network_callback(self):
        original, descriptor, _ = content_wire(b'payload')
        # Alter content bytes, leave trailer and expected hash intact.
        offset = p.HEADER.size + p.HEADER.unpack(original[:p.HEADER.size])[2] + p.HEADER.size + p.CONTENT_HEADER.size
        corrupt = original[:offset] + b'X' + original[offset + 1:]
        for raw in (corrupt, original[:-1]):
            calls = []
            def perform_upload():
                verified = p.FramedIO(io.BytesIO(raw), io.BytesIO(), nonce=NONCE).receive_content(
                    io.BytesIO(), descriptor, sequence=1, request_sha256=HASH)
                calls.append(verified)
            with self.assertRaises(p.ProtocolError):
                perform_upload()
            self.assertEqual(calls, [])

    def test_content_wrong_nonce_index_and_request(self):
        original, descriptor, _ = content_wire(b'payload')
        offset = p.HEADER.size + p.HEADER.unpack(original[:p.HEADER.size])[2] + p.HEADER.size
        prefix = list(p.CONTENT_HEADER.unpack(original[offset:offset + p.CONTENT_HEADER.size]))
        for index, value in ((0, bytes.fromhex(HASH)), (1, 2), (2, bytes.fromhex(NONCE)), (3, 1)):
            changed = prefix.copy()
            changed[index] = value
            raw = original[:offset] + p.CONTENT_HEADER.pack(*changed) + original[offset + p.CONTENT_HEADER.size:]
            with self.subTest(index=index), self.assertRaisesRegex(p.ProtocolError, 'bridge_content_binding'):
                p.FramedIO(io.BytesIO(raw), io.BytesIO(), nonce=NONCE).receive_content(
                    io.BytesIO(), descriptor, sequence=1, request_sha256=HASH)

    def test_content_excess_and_wrong_declared_length(self):
        for descriptor in ({'cap': 2, 'expected_bytes': None, 'expected_sha256': None},
                           {'cap': 4, 'expected_bytes': 4, 'expected_sha256': None},
                           {'cap': 4, 'expected_bytes': 3, 'expected_sha256': HASH}):
            channel = p.FramedIO(io.BytesIO(), io.BytesIO(), nonce=NONCE)
            with self.subTest(descriptor=descriptor), self.assertRaises(p.ProtocolError):
                channel.send_content(io.BytesIO(b'abc'), descriptor, sequence=1, request_sha256=HASH)
            self.assertTrue(channel.poisoned)

    def test_rpc_phases_strict_and_supervisor_observed(self):
        stream = io.BytesIO()
        sender = p.FramedIO(io.BytesIO(), stream, nonce=NONCE)
        sender.send('phase_start', {'phase_id': 1, 'kind': 'official_rpc', 'max_seconds': 120, 'deadline_epoch': 1792044000},
                    sequence=1, request_sha256=HASH)
        sender.send('phase_end', {'phase_id': 1}, sequence=1, request_sha256=HASH)
        events = p.FrameObserver(NONCE, direction='response').feed(stream.getvalue())
        self.assertEqual([e['kind'] for e in events], ['phase_start', 'phase_end'])
        for invalid in ({'phase_id': True, 'kind': 'official_rpc', 'max_seconds': 120, 'deadline_epoch': 1792044000},
                        {'phase_id': 1, 'kind': 'storage', 'max_seconds': 120, 'deadline_epoch': 1792044000},
                        {'phase_id': 1, 'kind': 'official_rpc', 'max_seconds': 121, 'deadline_epoch': 1792044000}):
            with self.assertRaises(p.ProtocolError):
                p.FramedIO(io.BytesIO(), io.BytesIO(), nonce=NONCE).send(
                    'phase_start', invalid, sequence=1, request_sha256=HASH)
        with self.assertRaises(p.ProtocolError):
            p.FrameObserver(NONCE, direction='request').feed(stream.getvalue())

    def test_observer_split_controls_and_content(self):
        message = req()
        raw = wire(message)
        observer = p.FrameObserver(NONCE, direction='request')
        observed = []
        for byte in raw:
            observed.extend(observer.feed(bytes([byte])))
        observer.finish()
        self.assertEqual(observed, [message])
        data, _, _ = content_wire(b'x' * 100000)
        observer = p.FrameObserver(NONCE, direction='response')
        observed = []
        for offset in range(0, len(data), 177):
            observed.extend(observer.feed(data[offset:offset + 177]))
        observer.finish()
        self.assertEqual([item['kind'] for item in observed], ['content_start', 'content_end'])
        self.assertEqual(observer.body, bytearray())

    def test_observer_invalid_direction_nonce_and_truncation(self):
        with self.assertRaises(p.ProtocolError):
            p.FrameObserver(NONCE, direction='response').feed(wire(req()))
        with self.assertRaises(p.ProtocolError):
            p.FrameObserver(HASH, direction='request').feed(wire(req()))
        observer = p.FrameObserver(NONCE, direction='request')
        observer.feed(wire(req())[:-1])
        with self.assertRaises(p.ProtocolError):
            observer.finish()


if __name__ == '__main__':
    unittest.main()
