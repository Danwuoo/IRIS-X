"""Local pin-only consumer successor. No imports of producer, model or provider."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import zipfile

OLD_ENTRY = '5fb10db771fe20ba3ae5d35587f638d8225e7691c256d4427ec8d44eebc8e8b3'
OLD_OPERATOR = 'e561857bfaee09b7cfde1eab9aae95422d69c0781577cf419612283b50a78144'
INVENTORY = 'd88b66c3b45435c2b328c2cc36c9c605c889ba76e48a36c22729db0ec2fda710'
POLICY = '3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def read(path, cap=64 * 1024**2):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'symlink forbidden')
    need(path.is_file() and path.stat().st_size <= cap, 'bounded regular file required')
    return path.read_bytes()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def bind(old, release, source_inventory, source_archive, collector, out):
    old, release, out = Path(old), Path(release), Path(out)
    inventory_raw = read(old / 'CONSUMER-INVENTORY.json')
    need(sha(inventory_raw) == INVENTORY, 'historical helper inventory differs')
    inventory = json.loads(inventory_raw)
    need(set(inventory) == {'format', 'files'} and inventory['format'] == 'owned-rl-batched-consumer-helpers-v1', 'helper inventory schema')
    helpers = inventory['files']
    need(len(helpers) == 21, 'exact historical 21 helpers required')
    expected = set(helpers) | {'CONSUMER-INVENTORY.json', 'CONSUMER-OPERATOR.json', 'reviewed_entry.py'}
    actual = {p.relative_to(old).as_posix() for p in old.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    need(actual == expected, 'exact historical 24-file consumer required')
    files = {name: read(old / name) for name in sorted(expected)}
    need(all(sha(files[n]) == h for n, h in helpers.items()), 'historical helper bytes differ')
    need(sha(files['reviewed_entry.py']) == OLD_ENTRY and sha(files['CONSUMER-OPERATOR.json']) == OLD_OPERATOR, 'historical outside-in pins differ')
    release_raw = read(release / 'release.json')
    release_doc = json.loads(release_raw)
    for name in ('material_review', 'environment', 'phase_policy', 'owner_protocol'):
        need(sha(read(release / (name + '.json'))) == release_doc[name + '_sha256'], 'exact release descriptor: ' + name)
    need(release_doc['phase_policy_sha256'] == POLICY, 'unchanged measured policy required')
    frozen = json.loads(read(source_inventory))
    source_files = frozen['files']
    canonical = json.dumps(sorted(source_files.items()), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    source_sha = sha(canonical)
    need(source_sha == frozen['source_sha256'] == release_doc['source_sha256'], 'runtime source closure differs')
    archive_raw = read(source_archive)
    with zipfile.ZipFile(source_archive) as z:
        need(len(z.namelist()) == 259 and len(set(z.namelist())) == 259 and set(z.namelist()) == set(source_files), 'exact 259-member runtime archive required')
        need(sum(i.file_size for i in z.infolist()) <= 64 * 1024**2, 'bounded expanded runtime')
        need(all(sha(z.read(n)) == h for n, h in source_files.items()), 'runtime archive member differs')
    pins = {
        'format': 'owned-rl-batched-consumer-operator-v1',
        'source_sha256': source_sha,
        'source_archive_sha256': sha(archive_raw),
        'policy_sha256': POLICY,
        'release_sha256': sha(release_raw),
        'collector_entry_sha256': sha(read(collector)),
        'helper_inventory_sha256': INVENTORY,
    }
    operator_raw = encoded(pins)
    entry_raw, count = re.subn(rb"(?m)^REVIEWED_OPERATOR_PINS_SHA256 = '[0-9a-f]{64}'$", ("REVIEWED_OPERATOR_PINS_SHA256 = '" + sha(operator_raw) + "'").encode(), files['reviewed_entry.py'])
    need(count == 1, 'one literal entry pin required')
    files['CONSUMER-OPERATOR.json'] = operator_raw
    files['reviewed_entry.py'] = entry_raw
    need(not out.exists() and not out.is_symlink(), 'fresh successor consumer directory required')
    out.mkdir(parents=True)
    for name, data in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        path.chmod(0o644)
    return {
        'format': 'irisx/rlvr004-consumer-pin-only-rebind-v1',
        'source_sha256': source_sha,
        'source_archive_sha256': sha(archive_raw),
        'release_sha256': sha(release_raw),
        'collector_sha256': pins['collector_entry_sha256'],
        'prior_entry_sha256': OLD_ENTRY,
        'prior_operator_sha256': OLD_OPERATOR,
        'helper_inventory_sha256': INVENTORY,
        'all_21_helpers_and_inventory_unchanged': True,
        'entry_only_operator_literal_changed': True,
        'consumer_root': str(out.absolute()),
        'files': {n: sha(b) for n, b in sorted(files.items())},
        'provider_calls': 0,
        'model_calls': 0,
        'production_admission': False,
        'independent_final_monitor_review_required': True,
    }


def main():
    parser = argparse.ArgumentParser()
    for name in ('old', 'release', 'source-inventory', 'source-archive', 'collector', 'out', 'receipt'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    receipt = Path(args.receipt)
    need(not receipt.exists(), 'fresh receipt required')
    result = bind(args.old, args.release, args.source_inventory, args.source_archive, args.collector, args.out)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    with receipt.open('xb') as stream:
        stream.write(encoded(result))
    print(encoded(result).decode())


if __name__ == '__main__':
    main()
