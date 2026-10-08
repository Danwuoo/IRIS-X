"""Uncapped, local-only evidence IO and owned-process supervision.

No model/provider imports, timeouts, retention ceilings, or log tails. BLOCK is
only an IO buffer. Operating-system/storage/provider limits still apply. Failed
writes retain their partial files and raise; only a final publication receipt
means archive closure succeeded. Hashes establish bytes, never scientific truth.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import threading
import time
import traceback
import unicodedata
import uuid
import zipfile

BLOCK = 1024 * 1024  # Buffer size, never a file/event/archive capacity limit.
_ENCODER = json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
_RESERVED = {'sequence', 'previous', 'event', 'digest'}
_MANIFEST = '__uncapped_manifest__.jsonl'
_EXCLUDED_DIRS = {'__pycache__', 'triton-cache', 'triton_cache', 'unsloth_compiled_cache',
    'torchinductor', 'torchinductor_cache', '.cache', '.git', '.aws', '.ssh', '.config',
    'models', 'model', 'weights', 'checkpoints', 'wheels', 'dependencies', 'site-packages',
    'secrets', 'credentials'}
_EXCLUDED_SUFFIXES = {'.safetensors', '.pt', '.pth', '.ckpt', '.bin', '.gguf', '.whl',
    '.so', '.o', '.a', '.pyc', '.pyo', '.pem', '.key', '.p12', '.pfx'}
_EVIDENCE_SUFFIXES = {'.json', '.jsonl', '.log', '.txt', '.py', '.md', '.toml',
    '.yaml', '.yml', '.csv', '.tsv'}
_FORBIDDEN_KEYS = {'expected_output', 'expected_outputs', 'expected_output_digest',
    'evaluator_truth', 'solutions', 'correct_output', 'correct_outputs', 'exact_match',
    'official_score', 'api_key', 'access_token', 'refresh_token', 'password', 'private_key'}
_FALSE_KEYS = {'contains_evaluator_truth', 'correctness_scored'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _chunks(value):
    for text in _ENCODER.iterencode(value):
        yield text.encode('utf-8')


def _digest(value):
    value_hash = hashlib.sha256()
    for block in _chunks(value):
        value_hash.update(block)
    return 'sha256:' + value_hash.hexdigest()


def full_diagnostic(error, phase):
    """Full chained traceback/message, including exception notes; no slicing."""
    return {'phase': str(phase), 'type': type(error).__name__, 'message': str(error),
            'traceback': ''.join(traceback.format_exception(type(error), error, error.__traceback__))}


def safe_name(name):
    _require(type(name) is str and bool(name) and not name.startswith('/') and
        '\\' not in name and ':' not in name and
        all(part not in ('', '.', '..') for part in name.split('/')) and
        not any(ord(char) < 32 or ord(char) == 127 for char in name),
        'safe relative evidence path required: ' + repr(name))
    return name


def _open_directory(path):
    """Resolve every absolute component with O_NOFOLLOW, including ancestors."""
    absolute = os.path.abspath(os.fspath(path))
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in absolute.split('/')[1:]:
            if not part:
                continue
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def _parent(path):
    path = Path(path)
    safe_name(path.name)
    fd = _open_directory(path.parent)
    try:
        yield fd, path.name
    finally:
        os.close(fd)


def _regular(fd, name, flags=os.O_RDONLY, mode=0o600):
    opened = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, mode, dir_fd=fd)
    try:
        _require(stat.S_ISREG(os.fstat(opened).st_mode), 'regular evidence file required: ' + name)
        return opened
    except BaseException:
        os.close(opened)
        raise


def _identity(value):
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError('non-finite JSON value: ' + value)


def _parse(value):
    return json.loads(value, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)


def atomic_json(path, value):
    """Replace one regular projection atomically. Failed temporary is retained."""
    path = Path(path)
    with _parent(path) as (parent, name):
        temporary = name + '.' + uuid.uuid4().hex + '.tmp'
        try:
            with os.fdopen(_regular(parent, temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL), 'wb') as out:
                for block in _chunks(value):
                    out.write(block)
                out.write(b'\n')
                out.flush()
                os.fsync(out.fileno())
            try:
                existing = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                _require(stat.S_ISREG(existing.st_mode), 'regular replacement target required')
            os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
        except BaseException as error:
            error.add_note('Existing output and any partial temporary retained: ' + str(path.parent / temporary))
            raise
    return path


def read_json(path):
    with _parent(path) as (parent, name):
        with os.fdopen(_regular(parent, name), 'rb') as stream:
            return _parse(stream.read())


def sha_file(path):
    with _parent(path) as (parent, name):
        with os.fdopen(_regular(parent, name), 'rb') as stream:
            before = os.fstat(stream.fileno())
            digest = hashlib.sha256()
            count = 0
            while block := stream.read(BLOCK):
                count += len(block)
                digest.update(block)
            _require(count == before.st_size and _identity(before) == _identity(os.fstat(stream.fileno())),
                'evidence changed during hash: ' + str(path))
            return digest.hexdigest()


class StreamEvents:
    """Exclusive, fsynced hash-chain writer; memory is at most one event.

    On any partial-write/fsync failure the writer is poisoned, preserving the
    exact tail. It cannot silently retry/repair the chain or claim a committed
    reservation. A new identity is required after such a failure.
    """
    def __init__(self, path, binding):
        _require(type(binding) is dict and not _RESERVED.intersection(binding), 'non-reserved event binding required')
        self.path = Path(path)
        self.binding = _parse(''.join(_ENCODER.iterencode(binding)))
        self.sequence, self.head, self.failed = 0, _digest(self.binding), False
        self._lock = threading.Lock()
        with _parent(self.path) as (parent, name):
            self._stream = os.fdopen(_regular(parent, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL), 'wb')
            os.fsync(parent)

    def emit(self, event, **details):
        with self._lock:
            _require(not self.failed and not self._stream.closed, 'event writer closed or failed')
            _require(not (set(details) & (_RESERVED | set(self.binding))), 'event binding or chain override forbidden')
            row = {**self.binding, 'sequence': self.sequence, 'previous': self.head, 'event': event, **details}
            row['digest'] = _digest(row)
            try:
                for block in _chunks(row):
                    self._stream.write(block)
                self._stream.write(b'\n')
                self.flush()
            except BaseException:
                self.failed = True
                raise
            self.sequence += 1
            self.head = row['digest']
            return row

    def flush(self):
        self._stream.flush()
        os.fsync(self._stream.fileno())

    def close(self):
        if not self._stream.closed:
            try:
                self.flush()
            finally:
                self._stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def stream_events(path, binding):
    return StreamEvents(path, binding)


def iter_events(path, binding):
    """Verify lazily, including the full last line. Never discard a broken tail."""
    head, sequence = _digest(binding), 0
    with _parent(path) as (parent, name):
        with os.fdopen(_regular(parent, name), 'rb') as stream:
            for line in stream:
                _require(line.endswith(b'\n'), 'incomplete event tail retained; chain is not complete')
                row = _parse(line)
                _require(type(row) is dict and type(row.get('sequence')) is int and
                    row['sequence'] == sequence and row.get('previous') == head,
                    'event chain sequence, predecessor, or binding differs')
                _require(all(key in row and _digest(row[key]) == _digest(value) for key, value in binding.items()),
                    'event binding differs')
                claimed = row.get('digest')
                unsigned = {key: value for key, value in row.items() if key != 'digest'}
                _require(claimed == _digest(unsigned), 'event digest differs')
                head, sequence = claimed, sequence + 1
                yield row


class _ForbiddenFields:
    """Streaming lexical guard, including escaped JSON keys and partial tails.

    This supplements the truth-free producer contract; it is not a semantic
    validator or a general secret detector. Large string values are not kept.
    """
    def __init__(self):
        self.string = False
        self.escape = ''
        self.candidate = ''
        self.last = None
        self.check_false = None
        self.literal = ''
        self.targets = _FORBIDDEN_KEYS | _FALSE_KEYS

    def feed(self, block):
        # All protected keys are ASCII. Non-ASCII bytes cannot match a key;
        # escaped ASCII is decoded below. Splitting UTF-8 never changes matches.
        for char in block.decode('latin1'):
            if self.string:
                if self.escape:
                    self.escape += char
                    if self.escape == '\\u' or self.escape.startswith('\\u') and len(self.escape) < 6:
                        continue
                    try:
                        decoded = json.loads('"' + self.escape + '"')
                    except (ValueError, json.JSONDecodeError):
                        decoded = '\ufffd'
                    self.escape = ''
                    self._char(decoded)
                elif char == '\\':
                    self.escape = '\\'
                elif char == '"':
                    self.string = False
                    self.last = self.candidate
                else:
                    self._char(char)
                continue
            if self.check_false is not None:
                if char.isspace() and not self.literal:
                    continue
                if char in ',}] \t\r\n':
                    _require(self.literal == 'false', 'evaluated evidence forbidden: ' + self.check_false)
                    self.check_false, self.literal = None, ''
                else:
                    self.literal += char
                    _require('false'.startswith(self.literal), 'evaluated evidence forbidden: ' + self.check_false)
                    continue
            if char == '"':
                self.string, self.candidate, self.last = True, '', None
            elif char == ':':
                _require(self.last not in _FORBIDDEN_KEYS, 'truth/secret field forbidden: ' + str(self.last))
                if self.last in _FALSE_KEYS:
                    self.check_false = self.last
                self.last = None
            elif not char.isspace():
                self.last = None

    def _char(self, char):
        if self.candidate is not None:
            value = self.candidate + char
            self.candidate = value if any(target.startswith(value) for target in self.targets) else None

    def finish(self):
        if self.check_false is not None and self.literal:
            _require(self.literal == 'false', 'evaluated evidence forbidden: ' + self.check_false)


def _exclusion(name, is_directory):
    parts = name.casefold().split('/')
    leaf = parts[-1]
    if any(part in _EXCLUDED_DIRS or part.startswith('torchinductor_') for part in parts):
        return 'compiler-cache/model/dependency/private-directory'
    if leaf == '.env' or leaf.startswith('.env.') or leaf in {'kaggle.json', 'credentials.json', 'secrets.json'}:
        return 'credential-file'
    if Path(leaf).suffix in _EXCLUDED_SUFFIXES:
        return 'weight/dependency/compiled/credential-file'
    return None


def _default_allowed(name):
    leaf = name.rsplit('/', 1)[-1]
    leaf = re.sub(r'(?:\.[0-9a-f]{32})?\.tmp$', '', leaf)
    return Path(leaf).suffix.casefold() in _EVIDENCE_SUFFIXES or leaf in {'stdout', 'stderr'}


def _fold(name):
    return unicodedata.normalize('NFC', name).casefold()


def _write_jsonl(stream, value):
    for block in _chunks(value):
        stream.write(block)
    stream.write(b'\n')


def _publish(parent, temporary, name):
    # Hard-link publication is atomic and cannot replace an existing target.
    os.chmod(temporary, 0o400, dir_fd=parent, follow_symlinks=False)
    os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
    os.fsync(parent)
    os.unlink(temporary, dir_fd=parent)
    os.fsync(parent)


def stream_archive(root, destination, *, allowed_paths=None):
    """Stream every allowed regular file, verify it, then publish immutably.

    The runtime must be quiescent and constructed only from approved truth-free
    inputs. Known caches/weights/dependencies/credential paths are explicitly
    recorded as excluded. Unexpected files, unsafe paths/symlinks, duplicate
    portable names, changing inputs, and truth/secret JSON keys fail closed.
    Partial JSON/log evidence is preserved; this routine does not qualify it.

    ``allowed_paths`` is an optional collection or predicate of relative names;
    it can narrow/extend evidence names but cannot bypass exclusions. Member
    bodies and the manifest are streamed. zipfile retains ZIP directory metadata
    (not bodies); no member count, member size, tree depth, or elapsed-time caps.
    Successful publication has three immutable files: ZIP, .manifest.jsonl, and
    .receipt.json. Only the last one commits the verified pair. Failures preserve
    already published files and named temporary files for honest diagnosis.
    """
    root, destination = Path(root), Path(destination)
    root_fd = _open_directory(root)
    manifest_path = destination.with_name(destination.name + '.manifest.jsonl')
    receipt_path = destination.with_name(destination.name + '.receipt.json')
    token = uuid.uuid4().hex
    archive_tmp = destination.with_name(destination.name + '.' + token + '.tmp')
    manifest_tmp = manifest_path.with_name(manifest_path.name + '.' + token + '.tmp')
    receipt_tmp = receipt_path.with_name(receipt_path.name + '.' + token + '.tmp')
    own_paths = {os.path.abspath(p) for p in (destination, manifest_path, receipt_path,
                                           archive_tmp, manifest_tmp, receipt_tmp)}
    allow = _default_allowed if allowed_paths is None else allowed_paths if callable(allowed_paths) else set(allowed_paths).__contains__
    if allowed_paths is not None and not callable(allowed_paths):
        for name in allowed_paths:
            safe_name(name)
    counts = {'members': 0, 'bytes': 0, 'excluded': 0}
    seen = {_fold(_MANIFEST)}
    try:
        with _parent(destination) as (parent, destination_name):
            for path in (destination, manifest_path, receipt_path):
                try:
                    os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                raise FileExistsError('immutable archive output already exists: ' + str(path))
            with os.fdopen(_regular(parent, manifest_tmp.name, os.O_RDWR | os.O_CREAT | os.O_EXCL), 'w+b') as manifest, \
                 os.fdopen(_regular(parent, archive_tmp.name, os.O_RDWR | os.O_CREAT | os.O_EXCL), 'w+b') as raw:
                _write_jsonl(manifest, {'format': 'irisx/uncapped-manifest-v1',
                    'claim': 'retained byte identity only; producer truth isolation required'})
                with zipfile.ZipFile(raw, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                    def walk():
                        # Explicit descriptor stack avoids a Python recursion-depth
                        # limit while retaining streaming directory enumeration.
                        frames = [(root_fd, '', os.scandir(root_fd), os.fstat(root_fd))]
                        try:
                            while frames:
                                fd, prefix, entries, before_directory = frames[-1]
                                try:
                                    entry = next(entries)
                                except StopIteration:
                                    _require(_identity(before_directory) == _identity(os.fstat(fd)),
                                        'runtime directory changed during archive inventory: ' + prefix)
                                    entries.close()
                                    if fd != root_fd:
                                        os.close(fd)
                                    frames.pop()
                                    continue
                                name = safe_name(prefix + entry.name)
                                if os.path.abspath(root / name) in own_paths:
                                    continue
                                folded = _fold(name)
                                _require(folded not in seen, 'duplicate portable evidence path: ' + name)
                                seen.add(folded)
                                value = entry.stat(follow_symlinks=False)
                                _require(stat.S_ISDIR(value.st_mode) or stat.S_ISREG(value.st_mode),
                                    'symlink/special evidence forbidden: ' + name)
                                excluded = _exclusion(name, stat.S_ISDIR(value.st_mode))
                                if excluded:
                                    _write_jsonl(manifest, {'excluded': name, 'reason': excluded,
                                        'directory': stat.S_ISDIR(value.st_mode)})
                                    counts['excluded'] += 1
                                    continue
                                if stat.S_ISDIR(value.st_mode):
                                    child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                                    try:
                                        opened = os.fstat(child)
                                        _require((value.st_dev, value.st_ino) == (opened.st_dev, opened.st_ino),
                                            'directory replaced during inventory: ' + name)
                                    except BaseException:
                                        os.close(child)
                                        raise
                                    frames.append((child, name + '/', os.scandir(child), opened))
                                    continue
                                _require(bool(allow(name)), 'unrecognized evidence path: ' + name)
                                with os.fdopen(_regular(fd, entry.name), 'rb') as source:
                                    before = os.fstat(source.fileno())
                                    _require(_identity(before) == _identity(value), 'file replaced during inventory: ' + name)
                                    digest, size = hashlib.sha256(), 0
                                    normalized = re.sub(r'(?:\.[0-9a-f]{32})?\.tmp$', '', name)
                                    guard = _ForbiddenFields() if normalized.endswith(('.json', '.jsonl')) else None
                                    with archive.open(name, 'w', force_zip64=True) as output:
                                        while block := source.read(BLOCK):
                                            if guard:
                                                guard.feed(block)
                                            output.write(block)
                                            digest.update(block)
                                            size += len(block)
                                    if guard:
                                        guard.finish()
                                    _require(size == before.st_size and _identity(before) == _identity(os.fstat(source.fileno())),
                                        'evidence changed while streaming: ' + name)
                                _write_jsonl(manifest, {'path': name, 'bytes': size, 'sha256': digest.hexdigest()})
                                counts['members'] += 1
                                counts['bytes'] += size
                        finally:
                            for fd, _, entries, _ in reversed(frames):
                                entries.close()
                                if fd != root_fd:
                                    os.close(fd)
                    walk()
                    _write_jsonl(manifest, {'complete_inventory': True, **counts})
                    manifest.flush()
                    os.fsync(manifest.fileno())
                    manifest.seek(0)
                    with archive.open(_MANIFEST, 'w', force_zip64=True) as output:
                        while block := manifest.read(BLOCK):
                            output.write(block)
                raw.flush()
                os.fsync(raw.fileno())
            manifest_sha = sha_file(manifest_tmp)
            verification = verify_archive(archive_tmp, manifest_tmp)
            receipt = {'format': 'irisx/uncapped-archive-v1', 'archive_created': True,
                'archive': str(destination), 'archive_sha256': sha_file(archive_tmp),
                'archive_bytes': archive_tmp.stat().st_size, 'manifest': str(manifest_path),
                'manifest_sha256': manifest_sha, 'receipt': str(receipt_path),
                **counts, 'stream_verified': verification['verified'],
                'correctness_scored': False, 'promotion': False}
            with os.fdopen(_regular(parent, receipt_tmp.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL), 'wb') as output:
                _write_jsonl(output, receipt)
                output.flush()
                os.fsync(output.fileno())
            for temporary, path in ((archive_tmp, destination), (manifest_tmp, manifest_path), (receipt_tmp, receipt_path)):
                _publish(parent, temporary.name, path.name)
            return receipt
    except BaseException as error:
        error.add_note('Archive finalization failed; existing/partial evidence retained. Temporary paths: ' +
            ', '.join(map(str, (archive_tmp, manifest_tmp, receipt_tmp))))
        raise
    finally:
        os.close(root_fd)


def verify_archive(path, manifest_path):
    """Read back all ZIP64 bodies incrementally and match the streamed manifest."""
    with _parent(path) as (parent, name), _parent(manifest_path) as (manifest_parent, manifest_name):
        with os.fdopen(_regular(parent, name), 'rb') as raw, \
             os.fdopen(_regular(manifest_parent, manifest_name), 'rb') as manifest, \
             zipfile.ZipFile(raw, 'r', allowZip64=True) as archive:
            header = _parse(manifest.readline())
            _require(header.get('format') == 'irisx/uncapped-manifest-v1', 'archive manifest format differs')
            expected = iter(manifest)
            seen, count, size, excluded = set(), 0, 0, 0
            def next_row():
                nonlocal excluded
                for line in expected:
                    _require(line.endswith(b'\n'), 'partial archive manifest')
                    row = _parse(line)
                    if type(row.get('excluded')) is str:
                        safe_name(row['excluded'])
                        excluded += 1
                        continue
                    return row
                raise ValueError('archive manifest ended early')
            for info in archive.infolist():
                safe_name(info.orig_filename)
                safe_name(info.filename)
                key = _fold(info.filename)
                _require(key not in seen, 'duplicate archive member: ' + info.filename)
                seen.add(key)
                _require(not info.is_dir() and stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG), 'regular ZIP member required')
                if info.filename == _MANIFEST:
                    _require(info is archive.infolist()[-1], 'embedded manifest must be last')
                    claimed = sha_file(manifest_path)
                    declared_size = os.fstat(manifest.fileno()).st_size
                else:
                    row = next_row()
                    _require(row.get('path') == info.filename and type(row.get('bytes')) is int and row['bytes'] >= 0,
                        'archive/manifest member order or size differs')
                    claimed, declared_size = row['sha256'], row['bytes']
                digest, received = hashlib.sha256(), 0
                with archive.open(info) as source:
                    while block := source.read(BLOCK):
                        digest.update(block)
                        received += len(block)
                _require(received == declared_size == info.file_size and digest.hexdigest() == claimed,
                    'streamed member SHA-256/size differs: ' + info.filename)
                if info.filename != _MANIFEST:
                    count += 1
                    size += received
            footer = next_row()
            _require(_MANIFEST in seen and footer == {'complete_inventory': True, 'members': count,
                'bytes': size, 'excluded': excluded}, 'archive inventory/footer differs')
            _require(next(expected, None) is None, 'unexpected trailing manifest row')
            return {'verified': True, 'members': count, 'bytes': size, 'excluded': excluded}


def _process_identity(pid):
    """Linux process identity only; never reads cmdline or environment/secrets."""
    _require(type(pid) is int and pid > 1, 'positive owned PID excluding PID1 required')
    try:
        directory = Path('/proc') / str(pid)
        text = (directory / 'stat').read_text()
        tail = text[text.rfind(')') + 2:].split()
        return {'pid': pid, 'state': tail[0], 'parent_pid': int(tail[1]),
                'pgid': int(tail[2]), 'session': int(tail[3]),
                'start_ticks': int(tail[19]), 'uid': directory.stat().st_uid}
    except (FileNotFoundError, ProcessLookupError):
        return None


def owned_process_state(process, identity):
    """Capture immediately after this process creates a new-session Popen."""
    _require(isinstance(process, subprocess.Popen), 'actual caller-owned Popen required')
    observed = _process_identity(process.pid)
    _require(observed is not None and observed['parent_pid'] == os.getpid() and
        observed['pgid'] == observed['session'] == process.pid and observed['uid'] == os.getuid() and
        process.pid not in {os.getpid(), os.getpgrp(), os.getsid(0)},
        'caller-owned new-session process required')
    return {'identity': str(identity), 'process': process, 'owner_pid': os.getpid(),
            'start_new_session': True, **observed}


def _serial_state(state):
    return {key: state[key] for key in ('identity', 'owner_pid', 'start_new_session',
        'pid', 'parent_pid', 'pgid', 'session', 'start_ticks', 'uid')}


def register_worker(state):
    """Persist an owned launch before releasing worker startup registration.

    With no enclosing supervisor, this returns False; local cleanup still uses
    the state. Under supervision registry failures are fatal, never ignored.
    """
    import fcntl
    path = os.environ.get('IRISX_UNCAPPED_WORKER_REGISTRY')
    nonce = os.environ.get('IRISX_UNCAPPED_OWNER_NONCE')
    if not path and not nonce:
        return False
    _require(bool(path) and bool(nonce), 'complete supervisor registry binding required')
    observed = owned_process_state(state['process'], state['identity'])
    _require(_serial_state(observed) == _serial_state(state), 'worker launch identity changed')
    row = {**_serial_state(state), 'ownership_nonce': nonce}
    with _parent(path) as (parent, name):
        with os.fdopen(_regular(parent, name, os.O_WRONLY | os.O_APPEND), 'ab') as output:
            fcntl.flock(output.fileno(), fcntl.LOCK_EX)
            try:
                _write_jsonl(output, row)
                output.flush()
                os.fsync(output.fileno())
            finally:
                fcntl.flock(output.fileno(), fcntl.LOCK_UN)
    return True


def await_worker_registration():
    """Worker entry barrier before it can spawn any descendants.

    Call after installing the worker's parent-death guard and before model or
    multiprocessing imports. Registration has no timeout. A dead parent is an
    error; this closes the create/register crash window without a work deadline.
    """
    path = os.environ.get('IRISX_UNCAPPED_WORKER_REGISTRY')
    if not path:
        return
    nonce = os.environ.get('IRISX_UNCAPPED_OWNER_NONCE')
    parent_pid = os.getppid()
    _require(parent_pid > 1, 'worker has no living launch parent')
    own = _process_identity(os.getpid())
    while True:
        _require(os.getppid() == parent_pid and _process_identity(parent_pid) is not None,
            'worker parent exited before registered startup')
        with _parent(path) as (parent, name):
            with os.fdopen(_regular(parent, name), 'rb') as registry:
                for line in registry:
                    if not line.endswith(b'\n'):
                        continue  # In-progress registration, not dropped evidence.
                    row = _parse(line)
                    if row.get('pid') == own['pid'] and row.get('start_ticks') == own['start_ticks']:
                        _require(row.get('ownership_nonce') == nonce and row.get('parent_pid') == parent_pid,
                            'worker registration binding differs')
                        return
        time.sleep(.05)  # Observation cadence, not a deadline.


def _registry_states(path, nonce, coordinator):
    with _parent(path) as (parent, name):
        with os.fdopen(_regular(parent, name), 'rb') as registry:
            for line in registry:
                _require(line.endswith(b'\n'), 'incomplete worker registration retained')
                row = _parse(line)
                _require(type(row) is dict and row.get('ownership_nonce') == nonce and
                    row.get('owner_pid') == row.get('parent_pid') == coordinator['pid'] and
                    type(row.get('start_ticks')) is int and row['start_ticks'] >= coordinator['start_ticks'],
                    'worker registry ownership differs')
                row['_registered_by_supervisor'] = os.getpid()
                yield row


def _group_members(pgid):
    members = []
    with os.scandir('/proc') as entries:
        for entry in entries:
            if entry.name.isdigit() and int(entry.name) > 1:
                observed = _process_identity(int(entry.name))
                if observed is not None and observed['pgid'] == pgid:
                    members.append(observed)
    return members


class CleanupError(RuntimeError):
    def __init__(self, report):
        super().__init__('owned process cleanup was not fully confirmed')
        self.cleanup_report = report


def _validate_owned_state(state):
    _require(type(state) is dict and state.get('start_new_session') is True and
        type(state.get('pid')) is int and state['pid'] > 1 and
        state['pid'] == state.get('pgid') == state.get('session') and
        state['pid'] not in {os.getpid(), os.getpgrp(), os.getsid(0)} and
        state.get('uid') == os.getuid() and type(state.get('start_ticks')) is int,
        'safe owned new-session state required')
    process = state.get('process')
    if process is not None:
        _require(isinstance(process, subprocess.Popen) and process.pid == state['pid'] and
            state.get('owner_pid') == os.getpid() and state.get('parent_pid') == os.getpid(),
            'caller-owned process object and launch record required')
    else:
        _require(state.get('_registered_by_supervisor') == os.getpid(), 'trusted supervisor registry required')
    leader = _process_identity(state['pid'])
    if leader is not None:
        _require(all(leader[key] == state[key] for key in ('pid', 'pgid', 'session', 'start_ticks', 'uid')),
            'owned PID identity changed; refuse to signal a reused PID')
    return leader


@contextmanager
def _defer_cancellation():
    previous = {}
    if threading.current_thread() is threading.main_thread():
        for number in (signal.SIGINT, signal.SIGTERM):
            previous[number] = signal.signal(number, signal.SIG_IGN)
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def cleanup_workers(states):
    """TERM then KILL owned groups and wait until no group member can execute.

    No timeout, deadline, worker-count bound, or success-on-timeout. SIGKILL is
    requested immediately after TERM rather than imposing a grace timer. Linux
    zombies are stopped, but retained zombie group IDs are explicitly reported
    separately from absent groups. Escaped/unregistered sessions are outside
    the claim; use registration and the worker-entry barrier above.
    """
    states = list(states)
    report = {'format': 'irisx/uncapped-cleanup-v1', 'workers': [], 'errors': [],
        'all_producers_stopped': False, 'all_process_groups_absent': False,
        'scope': 'owned registered sessions/groups; zombies cannot execute; no GPU attestation'}
    seen = set()
    validated = []
    for state in states:
        try:
            _validate_owned_state(state)
            _require(state['pid'] not in seen, 'duplicate cleanup PID')
            seen.add(state['pid'])
            row = {'identity': str(state['identity']), 'pid': state['pid'],
                'start_ticks': state['start_ticks'], 'signals_requested': [],
                'returncode': None, 'stop_confirmed': False, 'group_absent': None,
                'zombie_pids': []}
            report['workers'].append(row)
            validated.append((state, row))
        except BaseException as error:
            report['errors'].append(full_diagnostic(error, 'ownership-validation'))
    with _defer_cancellation():
        for number in (signal.SIGTERM, signal.SIGKILL):
            for state, row in validated:
                try:
                    _validate_owned_state(state)
                    members = _group_members(state['pgid'])
                    _require(all(member['session'] == state['session'] and member['uid'] == state['uid'] and
                        member['start_ticks'] >= state['start_ticks'] for member in members),
                        'process group membership ownership differs')
                    if any(member['state'] not in {'Z', 'X'} for member in members):
                        os.killpg(state['pgid'], number)
                        row['signals_requested'].append(signal.Signals(number).name)
                except ProcessLookupError:
                    pass
                except BaseException as error:
                    report['errors'].append(full_diagnostic(error, 'signal:' + row['identity']))
                    row['signal_failed'] = True
        pending = [(state, row) for state, row in validated if not row.get('signal_failed')]
        while pending:
            for state, row in tuple(pending):
                try:
                    _validate_owned_state(state)
                    members = _group_members(state['pgid'])
                    running = [member for member in members if member['state'] not in {'Z', 'X'}]
                    if not running:
                        if state.get('process') is not None:
                            row['returncode'] = state['process'].wait()
                        members = _group_members(state['pgid'])
                        row['zombie_pids'] = [member['pid'] for member in members if member['state'] in {'Z', 'X'}]
                        row['group_absent'] = not members
                        row['stop_confirmed'] = not any(member['state'] not in {'Z', 'X'} for member in members)
                        pending.remove((state, row))
                except BaseException as error:
                    report['errors'].append(full_diagnostic(error, 'observe-stop:' + row['identity']))
                    pending.remove((state, row))
            if pending:
                time.sleep(.05)
        for state, row in validated:
            for name, stream in state.get('streams', {}).items():
                if stream is not None:
                    try:
                        stream.flush()
                        stream.close()
                    except BaseException as error:
                        report['errors'].append(full_diagnostic(error, 'close:' + row['identity'] + ':' + name))
    report['all_producers_stopped'] = not report['errors'] and all(row['stop_confirmed'] for _, row in validated)
    report['all_process_groups_absent'] = report['all_producers_stopped'] and all(row['group_absent'] for _, row in validated)
    if not report['all_producers_stopped']:
        raise CleanupError(report)
    return report


class _OwnerCancellation(KeyboardInterrupt):
    pass


def supervise(command, *, cwd, env, capture_path, worker_states=()):
    """Run one new-session coordinator with complete direct stdout/stderr IO.

    There is no startup/runtime/watchdog/capture deadline. Owner SIGINT/SIGTERM
    invokes cleanup and produces a cancelled, unsuccessful receipt. All child
    bytes go directly to an exclusive file, never a pipe/tail retained in RAM.
    The child must report its own write errors; capture fsync failures and all
    nonzero exits are failures. A full filesystem is never called full success.
    """
    capture_path = Path(capture_path)
    registry_path = capture_path.with_name(capture_path.name + '.workers.jsonl')
    nonce = uuid.uuid4().hex
    result = {'format': 'irisx/uncapped-supervision-v1', 'launched': False,
        'launch_failed': False, 'returncode': None, 'cancelled': False,
        'confirmed_stopped': False, 'supervision_failed': False, 'success': False,
        'errors': [], 'worker_registry': str(registry_path),
        'output_capture': {'path': str(capture_path), 'written': False, 'truncated': False,
                           'bytes_retained': None, 'sha256': None}}
    process, state, capture = None, None, None
    handlers = {}
    requested_signal = None
    def cancel(number, frame):
        # Do not raise between Popen creation and ownership registration.
        nonlocal requested_signal
        requested_signal = number
    try:
        with _parent(registry_path) as (parent, name):
            fd = _regular(parent, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            os.fsync(fd)
            os.close(fd)
            os.fsync(parent)
        with _parent(capture_path) as (parent, name):
            capture = os.fdopen(_regular(parent, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL), 'wb', buffering=0)
            os.fsync(parent)
        if threading.current_thread() is threading.main_thread():
            for number in (signal.SIGINT, signal.SIGTERM):
                handlers[number] = signal.signal(number, cancel)
        child_env = dict(env)
        child_env.update(PYTHONUNBUFFERED='1',
                         IRISX_UNCAPPED_WORKER_REGISTRY=str(registry_path.absolute()),
                         IRISX_UNCAPPED_OWNER_NONCE=nonce)
        process = subprocess.Popen(command, cwd=cwd, env=child_env, stdout=capture,
            stderr=subprocess.STDOUT, start_new_session=True)
        result['launched'] = True
        state = owned_process_state(process, 'coordinator')
        result['coordinator_pid'] = process.pid
        result['coordinator_start_ticks'] = state['start_ticks']
        # Avoid poll()/wait() reaping before group cleanup: the original leader
        # identity remains in /proc even after exit, preventing PID-reuse races.
        while True:
            if requested_signal is not None:
                raise _OwnerCancellation('owner signal: ' + signal.Signals(requested_signal).name)
            observed = _process_identity(process.pid)
            _require(observed is not None, 'owned coordinator disappeared before wait')
            _require(observed['start_ticks'] == state['start_ticks'], 'coordinator PID identity changed')
            if observed['state'] in {'Z', 'X'}:
                break
            time.sleep(.05)
    except BaseException as error:
        result['cancelled'] = isinstance(error, KeyboardInterrupt)
        result['launch_failed'] = process is None
        result['supervision_failed'] = True
        result['errors'].append(full_diagnostic(error, 'supervise'))
    finally:
        with _defer_cancellation():
            if state is not None:
                try:
                    result['coordinator_cleanup'] = cleanup_workers([state])
                    result['returncode'] = process.returncode
                except BaseException as error:
                    result['errors'].append(full_diagnostic(error, 'coordinator-cleanup'))
                    result['coordinator_cleanup'] = getattr(error, 'cleanup_report', None)
                registry_valid = False
                try:
                    registered = []
                    registry_valid = True
                    try:
                        for worker in _registry_states(registry_path, nonce, state):
                            registered.append(worker)
                    except BaseException as error:
                        registry_valid = False
                        result['errors'].append(full_diagnostic(error, 'worker-registry'))
                    supplied = list(worker_states)
                    registered_pids = {item['pid'] for item in registered}
                    supplied = [item for item in supplied if item['pid'] not in registered_pids]
                    result['worker_cleanup'] = cleanup_workers(registered + supplied)
                except BaseException as error:
                    result['errors'].append(full_diagnostic(error, 'worker-cleanup'))
                    result['worker_cleanup'] = getattr(error, 'cleanup_report', None)
                result['confirmed_stopped'] = bool(
                    (result.get('coordinator_cleanup') or {}).get('all_producers_stopped') and
                    (result.get('worker_cleanup') or {}).get('all_producers_stopped') and registry_valid)
            elif process is not None:
                # Construction returned a process but ownership capture failed.
                # Never guess a group ID; direct Popen identity is still owned.
                try:
                    process.kill()
                    process.wait()
                except BaseException as error:
                    result['errors'].append(full_diagnostic(error, 'owned-launch-failure'))
            if capture is not None:
                try:
                    os.fsync(capture.fileno())
                    result['output_capture']['bytes_retained'] = os.fstat(capture.fileno()).st_size
                    capture.close()
                    result['output_capture']['sha256'] = sha_file(capture_path)
                    result['output_capture']['written'] = True
                except BaseException as error:
                    result['errors'].append(full_diagnostic(error, 'capture-finalization'))
                    capture.close()
        for number, handler in handlers.items():
            signal.signal(number, handler)
    result['supervision_failed'] = result['supervision_failed'] or bool(result['errors'])
    result['success'] = (result['returncode'] == 0 and result['confirmed_stopped'] and
        result['output_capture']['written'] and not result['cancelled'] and not result['supervision_failed'])
    return result
