"""Native Windows metadata and owned-process primitives; never read auth bytes.

Requires Windows 10+ (atomic PROC_THREAD_ATTRIBUTE_JOB_LIST). There is deliberately
no CreateProcess/AssignProcess fallback: it would leave a crash-time orphan gap.
Linux unit tests exercise policy/layout only and are not Windows acceptance.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import math
import ntpath
import os
import subprocess
import time
from dataclasses import dataclass

DWORD = C.c_uint32
WORD = C.c_uint16
BOOL = C.c_int32
BYTE = C.c_ubyte
HANDLE = C.c_void_p
SIZE_T = C.c_size_t
ULONG_PTR = C.c_size_t
LPVOID = C.c_void_p
INVALID_HANDLE_VALUE = C.c_void_p(-1).value
WAIT_OBJECT_0, WAIT_TIMEOUT = 0, 258
KILL_ON_JOB_CLOSE = 0x00002000
CREATE_SUSPENDED = 0x00000004
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NO_WINDOW = 0x08000000
JOB_LIST = 0x0002000D
HANDLE_LIST = 0x00020002


class WindowsGuardError(RuntimeError):
    """Fixed, non-secret diagnostic code (no OS message/path interpolation)."""


def need(value, code):
    if not value:
        raise WindowsGuardError(code)


def bounded_seconds(value, maximum=43200.0):
    need(type(value) in (int, float) and math.isfinite(value) and 0 < value <= maximum,
         'windows_invalid_timeout')
    return float(value)


class SECURITY_ATTRIBUTES(C.Structure):
    _fields_ = [('nLength', DWORD), ('lpSecurityDescriptor', LPVOID), ('bInheritHandle', BOOL)]


class FILETIME(C.Structure):
    _fields_ = [('dwLowDateTime', DWORD), ('dwHighDateTime', DWORD)]


class BY_HANDLE_FILE_INFORMATION(C.Structure):
    _fields_ = [('dwFileAttributes', DWORD), ('ftCreationTime', FILETIME),
                ('ftLastAccessTime', FILETIME), ('ftLastWriteTime', FILETIME),
                ('dwVolumeSerialNumber', DWORD), ('nFileSizeHigh', DWORD),
                ('nFileSizeLow', DWORD), ('nNumberOfLinks', DWORD),
                ('nFileIndexHigh', DWORD), ('nFileIndexLow', DWORD)]


class ACL(C.Structure):
    _fields_ = [('AclRevision', BYTE), ('Sbz1', BYTE), ('AclSize', WORD),
                ('AceCount', WORD), ('Sbz2', WORD)]


class ACE_HEADER(C.Structure):
    _fields_ = [('AceType', BYTE), ('AceFlags', BYTE), ('AceSize', WORD)]


class TOKEN_USER(C.Structure):
    _fields_ = [('Sid', LPVOID), ('Attributes', DWORD)]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(C.Structure):
    _fields_ = [('PerProcessUserTimeLimit', C.c_int64), ('PerJobUserTimeLimit', C.c_int64),
                ('LimitFlags', DWORD), ('MinimumWorkingSetSize', SIZE_T),
                ('MaximumWorkingSetSize', SIZE_T), ('ActiveProcessLimit', DWORD),
                ('Affinity', ULONG_PTR), ('PriorityClass', DWORD), ('SchedulingClass', DWORD)]


class IO_COUNTERS(C.Structure):
    _fields_ = [(name, C.c_uint64) for name in ('ReadOperationCount', 'WriteOperationCount',
                'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(C.Structure):
    _fields_ = [('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ('IoInfo', IO_COUNTERS), ('ProcessMemoryLimit', SIZE_T), ('JobMemoryLimit', SIZE_T),
                ('PeakProcessMemoryUsed', SIZE_T), ('PeakJobMemoryUsed', SIZE_T)]


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(C.Structure):
    _fields_ = [('TotalUserTime', C.c_int64), ('TotalKernelTime', C.c_int64),
                ('ThisPeriodTotalUserTime', C.c_int64), ('ThisPeriodTotalKernelTime', C.c_int64),
                ('TotalPageFaultCount', DWORD), ('TotalProcesses', DWORD),
                ('ActiveProcesses', DWORD), ('TotalTerminatedProcesses', DWORD)]


class STARTUPINFOW(C.Structure):
    _fields_ = [('cb', DWORD), ('lpReserved', C.c_wchar_p), ('lpDesktop', C.c_wchar_p),
                ('lpTitle', C.c_wchar_p), ('dwX', DWORD), ('dwY', DWORD), ('dwXSize', DWORD),
                ('dwYSize', DWORD), ('dwXCountChars', DWORD), ('dwYCountChars', DWORD),
                ('dwFillAttribute', DWORD), ('dwFlags', DWORD), ('wShowWindow', WORD),
                ('cbReserved2', WORD), ('lpReserved2', C.POINTER(BYTE)),
                ('hStdInput', HANDLE), ('hStdOutput', HANDLE), ('hStdError', HANDLE)]


class STARTUPINFOEXW(C.Structure):
    _fields_ = [('StartupInfo', STARTUPINFOW), ('lpAttributeList', LPVOID)]


class PROCESS_INFORMATION(C.Structure):
    _fields_ = [('hProcess', HANDLE), ('hThread', HANDLE), ('dwProcessId', DWORD), ('dwThreadId', DWORD)]


class API:
    def __init__(self):
        need(os.name == 'nt', 'native_windows_required')
        self.k = C.WinDLL('kernel32', use_last_error=True)
        self.a = C.WinDLL('advapi32', use_last_error=True)
        self.u = C.WinDLL('userenv', use_last_error=True)
        def sig(dll, name, args, restype=BOOL):
            fn = getattr(dll, name); fn.argtypes = args; fn.restype = restype
            return fn
        sig(self.k, 'GetCurrentProcess', [], HANDLE)
        sig(self.k, 'CloseHandle', [HANDLE])
        sig(self.k, 'LocalFree', [LPVOID], LPVOID)
        sig(self.a, 'OpenProcessToken', [HANDLE, DWORD, C.POINTER(HANDLE)])
        sig(self.a, 'GetTokenInformation', [HANDLE, DWORD, LPVOID, DWORD, C.POINTER(DWORD)])
        sig(self.a, 'ConvertSidToStringSidW', [LPVOID, C.POINTER(C.c_wchar_p)])
        sig(self.a, 'IsValidSid', [LPVOID])
        sig(self.a, 'GetLengthSid', [LPVOID], DWORD)
        sig(self.u, 'GetUserProfileDirectoryW', [HANDLE, C.c_wchar_p, C.POINTER(DWORD)])
        sig(self.a, 'GetSecurityInfo', [HANDLE, DWORD, DWORD, C.POINTER(LPVOID),
            C.POINTER(LPVOID), C.POINTER(LPVOID), C.POINTER(LPVOID), C.POINTER(LPVOID)], DWORD)
        sig(self.a, 'GetSecurityDescriptorDacl', [LPVOID, C.POINTER(BOOL), C.POINTER(LPVOID), C.POINTER(BOOL)])
        sig(self.a, 'GetAce', [LPVOID, DWORD, C.POINTER(LPVOID)])
        sig(self.a, 'ConvertStringSecurityDescriptorToSecurityDescriptorW',
            [C.c_wchar_p, DWORD, C.POINTER(LPVOID), C.POINTER(DWORD)])
        sig(self.k, 'CreateFileW', [C.c_wchar_p, DWORD, DWORD, LPVOID, DWORD, DWORD, HANDLE], HANDLE)
        sig(self.k, 'CreateDirectoryW', [C.c_wchar_p, LPVOID])
        sig(self.k, 'GetFileType', [HANDLE], DWORD)
        sig(self.k, 'GetFileInformationByHandle', [HANDLE, C.POINTER(BY_HANDLE_FILE_INFORMATION)])
        sig(self.k, 'GetFinalPathNameByHandleW', [HANDLE, C.c_wchar_p, DWORD, DWORD], DWORD)
        sig(self.k, 'CreateMutexW', [LPVOID, BOOL, C.c_wchar_p], HANDLE)
        sig(self.k, 'ReleaseMutex', [HANDLE])
        sig(self.k, 'CreateJobObjectW', [LPVOID, C.c_wchar_p], HANDLE)
        sig(self.k, 'SetInformationJobObject', [HANDLE, DWORD, LPVOID, DWORD])
        sig(self.k, 'QueryInformationJobObject', [HANDLE, DWORD, LPVOID, DWORD, C.POINTER(DWORD)])
        sig(self.k, 'TerminateJobObject', [HANDLE, C.c_uint])
        sig(self.k, 'IsProcessInJob', [HANDLE, HANDLE, C.POINTER(BOOL)])
        sig(self.k, 'InitializeProcThreadAttributeList', [LPVOID, DWORD, DWORD, C.POINTER(SIZE_T)])
        sig(self.k, 'UpdateProcThreadAttribute', [LPVOID, DWORD, SIZE_T, LPVOID, SIZE_T, LPVOID, LPVOID])
        sig(self.k, 'DeleteProcThreadAttributeList', [LPVOID], None)
        sig(self.k, 'CreateProcessW', [C.c_wchar_p, C.c_wchar_p, LPVOID, LPVOID, BOOL,
            DWORD, LPVOID, C.c_wchar_p, C.POINTER(STARTUPINFOW), C.POINTER(PROCESS_INFORMATION)])
        sig(self.k, 'ResumeThread', [HANDLE], DWORD)
        sig(self.k, 'TerminateProcess', [HANDLE, C.c_uint])
        sig(self.k, 'WaitForSingleObject', [HANDLE, DWORD], DWORD)
        sig(self.k, 'GetExitCodeProcess', [HANDLE, C.POINTER(DWORD)])
        sig(self.k, 'OpenProcess', [DWORD, BOOL, DWORD], HANDLE)
        sig(self.k, 'CreatePipe', [C.POINTER(HANDLE), C.POINTER(HANDLE), LPVOID, DWORD])
        sig(self.k, 'SetHandleInformation', [HANDLE, DWORD, DWORD])
        sig(self.k, 'ReadFile', [HANDLE, LPVOID, DWORD, C.POINTER(DWORD), LPVOID])
        sig(self.k, 'WriteFile', [HANDLE, LPVOID, DWORD, C.POINTER(DWORD), LPVOID])

    def check(self, ok, code):
        need(ok, code)
        return ok

    def handle(self, value, code):
        need(value not in (None, 0, INVALID_HANDLE_VALUE), code)
        return value

    def sid_text(self, ptr):
        self.check(self.a.IsValidSid(ptr), 'windows_invalid_sid')
        text = C.c_wchar_p()
        self.check(self.a.ConvertSidToStringSidW(ptr, C.byref(text)), 'windows_sid_conversion_failed')
        try:
            return text.value
        finally:
            self.k.LocalFree(C.cast(text, LPVOID))


_API = None


def api():
    global _API
    if _API is None:
        _API = API()
    return _API


@dataclass(frozen=True)
class Identity:
    sid: str
    profile: str


def current_identity():
    a = api(); token = HANDLE()
    a.check(a.a.OpenProcessToken(a.k.GetCurrentProcess(), 0x0008, C.byref(token)), 'windows_token_query_failed')
    try:
        size = DWORD()
        a.a.GetTokenInformation(token, 1, None, 0, C.byref(size))
        need(0 < size.value < 65536, 'windows_token_size_invalid')
        buf = C.create_string_buffer(size.value)
        a.check(a.a.GetTokenInformation(token, 1, buf, size, C.byref(size)), 'windows_token_user_failed')
        sid = a.sid_text(C.cast(buf, C.POINTER(TOKEN_USER)).contents.Sid)
        chars = DWORD()
        a.u.GetUserProfileDirectoryW(token, None, C.byref(chars))
        need(0 < chars.value < 32768, 'windows_profile_size_invalid')
        profile = C.create_unicode_buffer(chars.value)
        a.check(a.u.GetUserProfileDirectoryW(token, profile, C.byref(chars)), 'windows_profile_query_failed')
        return Identity(sid, strict_local_path(profile.value))
    finally:
        a.k.CloseHandle(token)


def strict_local_path(path):
    need(type(path) is str and 3 <= len(path) <= 32700 and '\x00' not in path, 'windows_path_invalid')
    path = path.replace('/', '\\')
    drive, tail = ntpath.splitdrive(path)
    need(len(drive) == 2 and drive[0].isalpha() and drive[1] == ':' and tail.startswith('\\'), 'windows_local_drive_required')
    pieces = tail[1:].split('\\') if tail != '\\' else []
    need(all(p and p not in ('.', '..') and not p.endswith((' ', '.'))
             and not any(c in p for c in ':*?<>|"') for p in pieces), 'windows_ambiguous_path')
    return drive.upper() + '\\' + '\\'.join(pieces)


def profile_relative(path, identity, expected_relative=None):
    path = strict_local_path(path); profile = strict_local_path(identity.profile)
    try:
        within = ntpath.commonpath([path, profile]).casefold() == profile.casefold()
    except ValueError:
        within = False
    need(within and path.casefold() != profile.casefold(), 'windows_original_profile_required')
    if expected_relative is not None:
        need(type(expected_relative) is str and not ntpath.isabs(expected_relative), 'windows_relative_path_required')
        expected = strict_local_path(ntpath.join(profile, expected_relative))
        need(path.casefold() == expected.casefold(), 'windows_store_path_mismatch')
    return path


def validate_acl(owner, current_sid, entries):
    """Policy-only function, independently testable without native claims."""
    need(owner == current_sid, 'windows_owner_sid_mismatch')
    allowed = {current_sid, 'S-1-5-18', 'S-1-5-32-544'}
    grants = set()
    for ace_type, flags, mask, sid in entries:
        need(ace_type in (0, 1), 'windows_acl_unsupported_ace')
        if flags & 0x08:  # INHERIT_ONLY does not apply to this object.
            continue
        if ace_type == 0 and mask:
            need(sid in allowed, 'windows_acl_unapproved_allow_sid')
            grants.add(sid)
    need(current_sid in grants, 'windows_acl_owner_access_missing')
    return tuple(sorted(grants))


def _file_acl(handle, identity):
    a = api(); owner = LPVOID(); sd = LPVOID()
    rc = a.a.GetSecurityInfo(handle, 1, 0x1 | 0x4, C.byref(owner), None, None, None, C.byref(sd))
    need(rc == 0 and owner.value and sd.value, 'windows_security_query_failed')
    try:
        owner_sid = a.sid_text(owner)
        present = BOOL(); defaulted = BOOL(); dacl = LPVOID()
        a.check(a.a.GetSecurityDescriptorDacl(sd, C.byref(present), C.byref(dacl), C.byref(defaulted)), 'windows_dacl_query_failed')
        need(present.value and dacl.value, 'windows_null_or_missing_dacl')
        acl = C.cast(dacl, C.POINTER(ACL)).contents
        need(8 <= acl.AclSize <= 65535 and acl.AceCount <= 4096, 'windows_acl_size_invalid')
        entries = []
        for i in range(acl.AceCount):
            ptr = LPVOID(); a.check(a.a.GetAce(dacl, i, C.byref(ptr)), 'windows_ace_query_failed')
            header = C.cast(ptr, C.POINTER(ACE_HEADER)).contents
            need(header.AceType in (0, 1) and header.AceSize >= 16, 'windows_acl_unsupported_ace')
            need(dacl.value + 8 <= ptr.value and ptr.value + header.AceSize <= dacl.value + acl.AclSize, 'windows_ace_bounds_invalid')
            sid_ptr = LPVOID(ptr.value + 8)
            a.check(a.a.IsValidSid(sid_ptr), 'windows_invalid_sid')
            need(8 + a.a.GetLengthSid(sid_ptr) <= header.AceSize, 'windows_ace_sid_bounds_invalid')
            mask = C.cast(LPVOID(ptr.value + 4), C.POINTER(DWORD)).contents.value
            entries.append((header.AceType, header.AceFlags, mask, a.sid_text(sid_ptr)))
        return owner_sid, validate_acl(owner_sid, identity.sid, entries)
    finally:
        a.k.LocalFree(sd)


class PrivateFileGuard:
    """Metadata-only, held no-follow handles prohibit replacement during use.

    Opening uses READ_CONTROL | FILE_READ_ATTRIBUTES, never FILE_READ_DATA.
    Default sharing allows readers only. The explicitly authorized official
    refresh/save window may allow in-place writes, never deletion/replacement,
    and revalidates the held file metadata/ACL before releasing the guard.
    """
    def __init__(self, path, expected_relative=None, max_bytes=65536, *, allow_write=False):
        self.identity = current_identity()
        self.path = profile_relative(str(path), self.identity, expected_relative)
        need(type(allow_write) is bool, 'windows_guard_mode_invalid')
        self.allow_write = allow_write
        self.max_bytes = max_bytes
        self.handles = []
        self.proof = None

    def __enter__(self):
        a = api()
        try:
            drive, tail = ntpath.splitdrive(self.path)
            parts = tail[1:].split('\\'); cursor = drive + '\\'
            paths = [cursor]
            for part in parts:
                cursor = ntpath.join(cursor, part); paths.append(cursor)
            for i, path in enumerate(paths):
                final = i == len(paths) - 1
                access = 0x80 | (0x20000 if final else 0)
                h = a.handle(a.k.CreateFileW(path, access, 3 if final and self.allow_write else 1, None, 3, 0x00200000 | 0x02000000, None), 'windows_metadata_open_failed')
                self.handles.append(h)
                info = BY_HANDLE_FILE_INFORMATION()
                a.check(a.k.GetFileInformationByHandle(h, C.byref(info)), 'windows_file_info_failed')
                need(not info.dwFileAttributes & 0x400, 'windows_reparse_path_forbidden')
                need(bool(info.dwFileAttributes & 0x10) != final, 'windows_file_kind_invalid')
                buf = C.create_unicode_buffer(32768)
                chars = a.k.GetFinalPathNameByHandleW(h, buf, len(buf), 0)
                need(0 < chars < len(buf), 'windows_final_path_failed')
                resolved = buf.value
                need(resolved.startswith('\\\\?\\') and not resolved.startswith('\\\\?\\UNC\\'), 'windows_nonlocal_resolved_path')
                resolved = strict_local_path(resolved[4:])
                need(resolved.casefold() == path.casefold(), 'windows_path_alias_forbidden')
                if final:
                    need(a.k.GetFileType(h) == 1 and info.nNumberOfLinks == 1, 'windows_regular_single_link_required')
                    size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
                    need(0 < size <= self.max_bytes, 'windows_file_size_invalid')
                    owner, grants = _file_acl(h, self.identity)
                    self.proof = {'format': 'irisx/windows-private-file-metadata-v1',
                        'native_profile': True, 'owner_matches_current_sid': owner == self.identity.sid,
                        'allow_sids_approved': True, 'regular_file': True, 'single_link': True,
                        'reparse_path': False, 'size_bounded': True}
            return self
        except BaseException:
            self.close(); raise

    def revalidate(self):
        need(bool(self.handles), 'windows_guard_closed')
        a = api(); h = self.handles[-1]; info = BY_HANDLE_FILE_INFORMATION()
        a.check(a.k.GetFileInformationByHandle(h, C.byref(info)), 'windows_file_info_failed')
        need(not info.dwFileAttributes & (0x400 | 0x10) and info.nNumberOfLinks == 1, 'windows_guard_file_changed')
        need(0 < ((info.nFileSizeHigh << 32) | info.nFileSizeLow) <= self.max_bytes, 'windows_file_size_invalid')
        _file_acl(h, self.identity)
        return dict(self.proof)

    def close(self):
        a = api()
        while self.handles:
            a.k.CloseHandle(self.handles.pop())

    def __exit__(self, *args):
        try:
            if self.allow_write:
                self.revalidate()
        finally:
            self.close()


private_file_guard = PrivateFileGuard


class SecurityDescriptor:
    """Creation-only descriptor for owned synchronization and probe objects."""
    def __init__(self, sddl, inherit=False):
        self.ptr = LPVOID(); a = api()
        a.check(a.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, C.byref(self.ptr), None), 'windows_security_descriptor_failed')
        self.attributes = SECURITY_ATTRIBUTES(C.sizeof(SECURITY_ATTRIBUTES), self.ptr, inherit)

    def close(self):
        if self.ptr.value:
            api().k.LocalFree(self.ptr); self.ptr = LPVOID()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ExclusiveMutex:
    def __init__(self, scope='publication-worker-v1'):
        need(type(scope) is str and 1 <= len(scope) <= 128, 'windows_mutex_scope_invalid')
        self.handle = None; self.identity = current_identity()
        digest = hashlib.sha256((self.identity.sid + '\0' + scope).encode('utf-8')).hexdigest()
        self.name = 'Global\\IRIS-X-Bridge-' + digest

    def __enter__(self):
        a = api()
        with SecurityDescriptor('D:P(A;;GA;;;' + self.identity.sid + ')(A;;GA;;;SY)') as sd:
            C.set_last_error(0)
            h = a.handle(a.k.CreateMutexW(C.byref(sd.attributes), True, self.name), 'windows_mutex_create_failed')
            error = C.get_last_error()
        if error == 183:
            a.k.CloseHandle(h)
            raise WindowsGuardError('windows_duplicate_worker')
        self.handle = h
        return self

    def close(self):
        if self.handle:
            a = api(); h = self.handle; self.handle = None
            try:
                a.check(a.k.ReleaseMutex(h), 'windows_mutex_release_failed')
            finally:
                a.k.CloseHandle(h)

    def __exit__(self, *args):
        self.close()


class Pipe:
    def __init__(self, handle):
        self.handle = handle

    def read(self, size=65536):
        need(type(size) is int and 1 <= size <= 65536, 'windows_pipe_read_size_invalid')
        a = api(); buf = C.create_string_buffer(size); count = DWORD()
        if not a.k.ReadFile(self.handle, buf, size, C.byref(count), None):
            if C.get_last_error() in (109, 232):
                return b''
            raise WindowsGuardError('windows_pipe_read_failed')
        return buf.raw[:count.value]

    def write(self, data):
        need(type(data) is bytes and len(data) <= 65536, 'windows_pipe_write_size_invalid')
        a = api(); offset = 0
        while offset < len(data):
            count = DWORD(); chunk = data[offset:]; buf = C.create_string_buffer(chunk)
            a.check(a.k.WriteFile(self.handle, buf, len(chunk), C.byref(count), None), 'windows_pipe_write_failed')
            need(count.value > 0, 'windows_pipe_write_empty'); offset += count.value

    def close(self):
        if self.handle:
            api().k.CloseHandle(self.handle); self.handle = None


def _pipe(parent_reads):
    a = api(); read = HANDLE(); write = HANDLE()
    attrs = SECURITY_ATTRIBUTES(C.sizeof(SECURITY_ATTRIBUTES), None, True)
    a.check(a.k.CreatePipe(C.byref(read), C.byref(write), C.byref(attrs), 65536), 'windows_pipe_create_failed')
    parent, child = (read.value, write.value) if parent_reads else (write.value, read.value)
    try:
        a.check(a.k.SetHandleInformation(parent, 1, 0), 'windows_pipe_inherit_failed')
        return Pipe(parent), child
    except BaseException:
        a.k.CloseHandle(parent); a.k.CloseHandle(child); raise


class JobProcess:
    """Only explicit stdio handles inherited; Job handle is never inherited."""
    def __init__(self, argv, *, cwd=None, env=None):
        need(type(argv) in (list, tuple) and argv and all(type(x) is str and '\0' not in x for x in argv), 'windows_argv_invalid')
        strict_local_path(argv[0])
        need(len(subprocess.list2cmdline(argv)) < 32700, 'windows_command_too_long')
        self.job = self.process = None
        self.stdin = self.stdout = self.stderr = None
        self.pid = None; self.closed_proof = None
        a = api(); children = []; attrs = None; attrs_ready = False; pi = PROCESS_INFORMATION()
        try:
            self.job = a.handle(a.k.CreateJobObjectW(None, None), 'windows_job_create_failed')
            limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limits.BasicLimitInformation.LimitFlags = KILL_ON_JOB_CLOSE
            a.check(a.k.SetInformationJobObject(self.job, 9, C.byref(limits), C.sizeof(limits)), 'windows_job_limits_failed')
            verified = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            a.check(a.k.QueryInformationJobObject(self.job, 9, C.byref(verified), C.sizeof(verified), None), 'windows_job_limits_query_failed')
            need(verified.BasicLimitInformation.LimitFlags == KILL_ON_JOB_CLOSE, 'windows_job_breakaway_or_limits_invalid')
            self.stdin, h_in = _pipe(False); children.append(h_in)
            self.stdout, h_out = _pipe(True); children.append(h_out)
            self.stderr, h_err = _pipe(True); children.append(h_err)
            size = SIZE_T()
            a.k.InitializeProcThreadAttributeList(None, 2, 0, C.byref(size))
            need(0 < size.value <= 65536, 'windows_attribute_size_invalid')
            attrs = C.create_string_buffer(size.value)
            a.check(a.k.InitializeProcThreadAttributeList(attrs, 2, 0, C.byref(size)), 'windows_attribute_init_failed')
            attrs_ready = True
            jobs = (HANDLE * 1)(self.job); handles = (HANDLE * 3)(*children)
            a.check(a.k.UpdateProcThreadAttribute(attrs, 0, JOB_LIST, jobs, C.sizeof(jobs), None, None), 'windows_atomic_job_unavailable')
            a.check(a.k.UpdateProcThreadAttribute(attrs, 0, HANDLE_LIST, handles, C.sizeof(handles), None, None), 'windows_handle_list_failed')
            startup = STARTUPINFOEXW()
            startup.StartupInfo.cb = C.sizeof(startup)
            startup.StartupInfo.dwFlags = 0x100
            startup.StartupInfo.hStdInput, startup.StartupInfo.hStdOutput, startup.StartupInfo.hStdError = children
            startup.lpAttributeList = C.cast(attrs, LPVOID)
            environment = None
            if env is not None:
                need(type(env) is dict and all(type(k) is str and type(v) is str and k and '=' not in k and '\0' not in k + v for k, v in env.items()), 'windows_environment_invalid')
                environment = C.create_unicode_buffer('\0'.join(k + '=' + env[k] for k in sorted(env, key=str.upper)) + '\0\0')
            command = C.create_unicode_buffer(subprocess.list2cmdline(argv))
            flags = CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW
            a.check(a.k.CreateProcessW(argv[0], command, None, None, True, flags, environment, cwd,
                C.cast(C.byref(startup), C.POINTER(STARTUPINFOW)), C.byref(pi)), 'windows_suspended_job_spawn_failed')
            self.process = pi.hProcess; self.pid = int(pi.dwProcessId)
            member = BOOL()
            a.check(a.k.IsProcessInJob(self.process, self.job, C.byref(member)), 'windows_job_membership_query_failed')
            need(member.value, 'windows_child_not_in_job')
            need(a.k.ResumeThread(pi.hThread) == 1, 'windows_child_resume_failed')
        except BaseException:
            if pi.hProcess and not self.process:
                a.k.TerminateProcess(pi.hProcess, 125); a.k.CloseHandle(pi.hProcess)
            if self.job:
                a.k.TerminateJobObject(self.job, 125)
            self._close_handles()
            raise
        finally:
            if pi.hThread:
                a.k.CloseHandle(pi.hThread)
            if attrs_ready:
                a.k.DeleteProcThreadAttributeList(attrs)
            for h in children:
                a.k.CloseHandle(h)

    def active_processes(self):
        need(self.job is not None, 'windows_job_closed')
        a = api(); info = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        a.check(a.k.QueryInformationJobObject(self.job, 1, C.byref(info), C.sizeof(info), None), 'windows_job_accounting_failed')
        return int(info.ActiveProcesses)

    def process_ids(self):
        """Query every currently active member; includes native launcher chains."""
        need(self.job is not None, 'windows_job_closed')
        a = api()
        for slots in (64, 256, 1024, 4096):
            raw = C.create_string_buffer(8 + slots * C.sizeof(ULONG_PTR))
            ok = a.k.QueryInformationJobObject(self.job, 3, raw, len(raw), None)
            if not ok:
                need(C.get_last_error() == 234, 'windows_job_members_query_failed')
                continue
            assigned = DWORD.from_buffer(raw, 0).value
            count = DWORD.from_buffer(raw, 4).value
            need(assigned == count and count <= slots, 'windows_job_members_incomplete')
            pids = (ULONG_PTR * count).from_buffer(raw, 8)
            return tuple(sorted(int(pid) for pid in pids))
        raise WindowsGuardError('windows_job_members_excessive')

    def poll(self):
        a = api(); status = a.k.WaitForSingleObject(self.process, 0)
        if status == WAIT_TIMEOUT:
            return None
        need(status == WAIT_OBJECT_0, 'windows_process_wait_failed')
        code = DWORD(); a.check(a.k.GetExitCodeProcess(self.process, C.byref(code)), 'windows_exit_code_failed')
        return int(code.value)

    def terminate_and_prove_empty(self, timeout=5.0, *, close_pipes=True):
        timeout = bounded_seconds(timeout, 30.0)
        if self.closed_proof is not None:
            return self.closed_proof
        a = api()
        try:
            a.check(a.k.TerminateJobObject(self.job, 124), 'windows_job_terminate_failed')
            end = time.monotonic() + timeout
            while self.active_processes() != 0:
                need(time.monotonic() < end, 'windows_job_not_empty')
                time.sleep(0.01)
            self.closed_proof = {'format': 'irisx/windows-job-closure-v1',
                'active_processes': 0, 'kill_on_close': True, 'breakaway_permitted': False,
                'atomic_job_assignment': True}
            return self.closed_proof
        finally:
            # If verification fails, closing the sole handle still enforces kill.
            self._close_handles(close_pipes=close_pipes)

    def _close_handles(self, *, close_pipes=True):
        a = api()
        # Close the Job first: also bounds blocked stdio operations by killing peers.
        for key in ('job', 'process'):
            h = getattr(self, key)
            if h:
                a.k.CloseHandle(h); setattr(self, key, None)
        if not close_pipes:
            return
        for key in ('stdin', 'stdout', 'stderr'):
            pipe = getattr(self, key)
            if pipe:
                pipe.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.terminate_and_prove_empty()


class ParentWatch:
    """Holds an original parent-process handle to avoid PID-reuse ambiguity."""
    def __init__(self, pid=None):
        self.pid = os.getppid() if pid is None else pid
        need(type(self.pid) is int and self.pid > 0, 'windows_parent_pid_invalid')
        self.handle = api().handle(api().k.OpenProcess(0x00100000, False, self.pid), 'windows_parent_open_failed')

    def dead(self):
        result = api().k.WaitForSingleObject(self.handle, 0)
        need(result in (WAIT_OBJECT_0, WAIT_TIMEOUT), 'windows_parent_wait_failed')
        return result == WAIT_OBJECT_0

    def close(self):
        if self.handle:
            api().k.CloseHandle(self.handle); self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def read_source(path, cap):
    """Read bounded public SDK source bytes through locked no-reparse handles.

    This is for the reviewed SDK source inventory only, never credential stores.
    The caller checks source digests and SDK location/ownership separately.
    """
    path = strict_local_path(str(path))
    need(ntpath.splitext(path)[1].lower() in ('.py', '.pyc', '.pyd', '.dll', '.exe', '.whl', '.pth'), 'windows_source_extension_invalid')
    need(type(cap) is int and 0 < cap <= 128 * 1024 * 1024, 'windows_source_cap_invalid')
    a = api(); handles = []
    try:
        drive, tail = ntpath.splitdrive(path); cursor = drive + '\\'; paths = [cursor]
        for part in tail[1:].split('\\'):
            cursor = ntpath.join(cursor, part); paths.append(cursor)
        for index, component in enumerate(paths):
            final = index == len(paths) - 1
            h = a.handle(a.k.CreateFileW(component, 0x80 | (1 if final else 0), 1, None, 3, 0x00200000 | 0x02000000, None), 'windows_source_open_failed')
            handles.append(h); info = BY_HANDLE_FILE_INFORMATION()
            a.check(a.k.GetFileInformationByHandle(h, C.byref(info)), 'windows_source_info_failed')
            need(not info.dwFileAttributes & 0x400, 'windows_reparse_path_forbidden')
            need(bool(info.dwFileAttributes & 0x10) != final, 'windows_file_kind_invalid')
            buf = C.create_unicode_buffer(32768); count = a.k.GetFinalPathNameByHandleW(h, buf, len(buf), 0)
            need(0 < count < len(buf) and buf.value.startswith('\\\\?\\') and strict_local_path(buf.value[4:]).casefold() == component.casefold(), 'windows_source_alias_forbidden')
            if final:
                size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
                need(a.k.GetFileType(h) == 1 and info.nNumberOfLinks == 1 and size <= cap, 'windows_source_file_invalid')
        chunks = []; total = 0
        while True:
            buf = C.create_string_buffer(65536); count = DWORD()
            a.check(a.k.ReadFile(handles[-1], buf, len(buf), C.byref(count), None), 'windows_source_read_failed')
            if not count.value:
                break
            total += count.value; need(total <= cap, 'windows_source_too_large')
            chunks.append(buf.raw[:count.value])
        need(total == size, 'windows_source_size_changed')
        return b''.join(chunks)
    finally:
        for h in reversed(handles):
            a.k.CloseHandle(h)
