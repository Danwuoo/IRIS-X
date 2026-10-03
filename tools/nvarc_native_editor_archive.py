"""Small truth-free native diagnostics archive and Editor download link."""
import hashlib
import json
from pathlib import Path
import zipfile


def write_editor_archive(work, destination, run, plan):
    limit = 16 * 1024**2
    entries = []
    for path in sorted(work.rglob('*')):
        if path.is_symlink():
            raise RuntimeError('diagnostic archive cannot contain symbolic links')
        if not path.is_file():
            continue
        name = path.relative_to(work).as_posix()
        if name == 'manifest.json' or not path.resolve().is_relative_to(work.resolve()):
            raise RuntimeError('closed native diagnostic path required')
        size = path.stat().st_size
        if size > limit:
            raise RuntimeError('bounded native diagnostic member required')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        entries.append({'path': name, 'bytes': size, 'sha256': digest})
    digest = None if plan is None else 'sha256:' + hashlib.sha256(json.dumps(
        plan, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    manifest = json.dumps({'format': 'irisx/nvarc-gpu-preflight-archive-v1',
        'run_id': run, 'plan_digest': digest, 'members': entries},
        sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    if sum(row['bytes'] for row in entries) + len(manifest) > limit:
        raise RuntimeError('bounded complete native diagnostics required')
    temporary = destination.with_suffix('.zip.partial')
    if destination.exists() or temporary.exists():
        raise RuntimeError('immutable native Editor archive already exists')
    with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', manifest)
        for row in entries:
            archive.write(work / row['path'], row['path'])
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('native diagnostic ZIP CRC verification failed')
        for row in entries:
            body = archive.read(row['path'])
            if len(body) != row['bytes'] or hashlib.sha256(body).hexdigest() != row['sha256']:
                raise RuntimeError('native diagnostic archive changed during packaging')
    temporary.rename(destination)
    return destination


def show_editor_archive(destination, run, plan_digest):
    with zipfile.ZipFile(destination) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        if manifest['run_id'] != run or manifest['plan_digest'] != plan_digest:
            raise RuntimeError('download archive identity differs')
    print(json.dumps({'download': str(destination), 'run_id': run,
        'plan_digest': plan_digest}, ensure_ascii=True))
    try:
        from IPython.display import FileLink, display
        display(FileLink(str(destination)))
    except ImportError:
        print(str(destination).encode('ascii', 'backslashreplace').decode())
