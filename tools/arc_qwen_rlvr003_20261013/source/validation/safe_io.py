"""Strict bounded byte readers. Never import archived source or execute pickle globals."""
from __future__ import annotations
from pathlib import Path, PurePosixPath
import hashlib, json, math, os, stat, zipfile, struct

class EvidenceError(ValueError):
    pass

def need(condition, message):
    if not condition:
        raise EvidenceError(message)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def is_sha(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)

def finite(value):
    return type(value) in (int, float) and math.isfinite(value)

def integer(value, low=0, high=10**9):
    return type(value) is int and low <= value <= high

def same(a, b):
    return canonical(a) == canonical(b)

def relative(value):
    need(type(value) is str and value and '\\' not in value and '\x00' not in value, 'unsafe relative path')
    p = PurePosixPath(value)
    need(not p.is_absolute() and all(x not in ('', '.', '..') for x in value.split('/')), 'unsafe relative path: ' + value)
    return p

def parse_json(data):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def nonfinite(value):
        raise EvidenceError('nonfinite JSON constant: ' + value)
    def number(value):
        result=float(value);need(math.isfinite(result),'nonfinite JSON numeric overflow');return result
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite,parse_float=number)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise EvidenceError('invalid strict JSON: ' + str(exc)) from exc

class Root:
    def __init__(self, path, *, maximum_bytes=14 * 1024**3, maximum_files=12001):
        self.path = Path(path).absolute()
        need(self.path.is_dir() and not self.path.is_symlink(), 'evidence root must be regular directory')
        # Do not resolve away an attacker-supplied symlink ancestor.
        for ancestor in (self.path, *self.path.parents):
            need(not ancestor.is_symlink(), 'symlink root ancestor')
        self.maximum_bytes, self.maximum_files = maximum_bytes, maximum_files
    def member(self, name):
        p = self.path.joinpath(*relative(name).parts)
        for part in (p, *p.parents):
            if part == self.path.parent:
                break
            need(not part.is_symlink(), 'symlink member: ' + name)
        need(p.is_file() and stat.S_ISREG(p.stat().st_mode), 'missing regular artifact: ' + name)
        return p
    def read(self, name, limit=16 * 1024**2):
        p = self.member(name)
        need(p.stat().st_size <= limit, 'artifact byte limit: ' + name)
        return p.read_bytes()
    def json(self, name):
        return parse_json(self.read(name, 2 * 1024**3))
    def file_sha(self, name, limit=2 * 1024**3):
        p=self.member(name)
        need(p.stat().st_size <= limit, 'artifact byte limit: '+name)
        h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
        return h.hexdigest()
    def inventory(self):
        result, total = {}, 0
        for p in sorted(self.path.rglob('*')):
            need(not p.is_symlink(), 'symlink in evidence inventory')
            if p.is_dir():
                continue
            need(stat.S_ISREG(p.stat().st_mode), 'nonregular evidence member')
            name = p.relative_to(self.path).as_posix()
            relative(name)
            total += p.stat().st_size
            need(total <= self.maximum_bytes and len(result) < self.maximum_files, 'evidence inventory limits')
            result[name] = self.file_sha(name,3 * 1024**3 if name=="checkpoints.zip" else 8192*400000 if name=="physical-journal.jsonl" else 2 * 1024**3)
        return result
    def remap(self, recorded_path, original_root):
        need(type(recorded_path) is str and type(original_root) is str, 'declared lineage path required')
        p, original = PurePosixPath(recorded_path), PurePosixPath(original_root)
        need(p.is_absolute() and original.is_absolute(), 'absolute original lineage path required')
        try:
            name = p.relative_to(original).as_posix()
        except ValueError as exc:
            raise EvidenceError('artifact escapes declared original root') from exc
        self.member(name)
        return name

def verify_inventory(root, files, *, excluded=()):
    need(type(files) is dict and files, 'nonempty complete inventory required')
    need(all(is_sha(v) for v in files.values()), 'inventory SHA256 required')
    actual = root.inventory()
    for name in excluded:
        actual.pop(name, None)
    need(set(actual) == set(files), 'missing/extra inventory members: ' + repr(sorted(set(actual) ^ set(files))))
    for name, expected in files.items():
        need(actual[name] == expected, 'inventory bytes differ: ' + name)
    return digest(sorted(files.items()))

def preflight_zip_directory(path, *, maximum_bytes, maximum_members):
    # Reject enormous entry tables before ZipFile allocates one object per entry.
    # Our bounded archives never require sentinel counts/offsets; ordinary ZIP64
    # local storage headers and end records with nonsentinel EOCD remain valid.
    path=Path(path);size=path.stat().st_size
    need(22<=size<=maximum_bytes+16*1024**2,'ZIP physical byte cap')
    with path.open('rb') as f:
        f.seek(max(0,size-65557));tail=f.read(65557)
    at=tail.rfind(b'PK\x05\x06')
    need(at>=0 and len(tail)-at>=22,'ZIP bounded EOCD required')
    _,disk,central_disk,n_disk,n_total,central_bytes,central_offset,comment=struct.unpack('<4s4H2LH',tail[at:at+22])
    need(at+22+comment==len(tail),'ZIP appended/ambiguous tail')
    need(disk==central_disk==0 and n_disk==n_total and 0<n_total<=maximum_members and n_total!=65535,'ZIP central entry cap before parser allocation')
    need(central_bytes!=0xffffffff and central_offset!=0xffffffff and central_bytes<=min(16*1024**2,maximum_members*4096),'ZIP bounded central directory before parser allocation')
    end_offset=size-len(tail)+at
    # Python's ZIP parser honors ZIP64 end records even without classic sentinel
    # fields. Validate its bounded override before it can allocate the table.
    locator=b''
    if end_offset>=20:
        with path.open('rb') as f:f.seek(end_offset-20);locator=f.read(20)
    if locator[:4]==b'PK\x06\x07':
        _,z_disk,z_offset,z_disks=struct.unpack('<4sLQL',locator)
        need(z_disk==0 and z_disks==1 and z_offset==end_offset-76,'bounded single-disk ZIP64 locator')
        with path.open('rb') as f:f.seek(z_offset);record=f.read(56)
        need(len(record)==56,'complete bounded ZIP64 end record')
        sig,length,made,version,disk64,central64,nd64,nt64,cb64,co64=struct.unpack('<4sQ2H2L4Q',record)
        need(sig==b'PK\x06\x06' and length==44 and disk64==central64==0,'bounded fixed ZIP64 end structure')
        need((nd64,nt64,cb64,co64)==(n_disk,n_total,central_bytes,central_offset),'ZIP64/classic directory count/size/offset differs')
    need(central_offset+central_bytes<=end_offset,'ZIP central directory outside body')


def inspect_tensor_zip(path, *, maximum_bytes=2 * 1024**3, maximum_members=4096):
    """Torch ZIP preflight; no extraction and no pickle evaluation here."""
    preflight_zip_directory(path,maximum_bytes=maximum_bytes,maximum_members=maximum_members)
    try:
        with zipfile.ZipFile(path) as z:
            members = z.infolist()
            need(0 < len(members) <= maximum_members, 'tensor archive member cap')
            names, total = set(), 0
            for info in members:
                relative(info.filename.rstrip('/'))
                need(info.filename not in names, 'duplicate tensor ZIP name')
                names.add(info.filename)
                mode = info.external_attr >> 16
                need(not stat.S_ISLNK(mode) and not info.flag_bits & 1, 'unsafe tensor ZIP member')
                total += info.file_size
                need(total <= maximum_bytes, 'tensor archive expanded cap')
                need(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'unsupported tensor compression')
            need(z.testzip() is None, 'tensor archive CRC differs')
    except (OSError, zipfile.BadZipFile) as exc:
        raise EvidenceError('unsupported/corrupt tensor archive') from exc
