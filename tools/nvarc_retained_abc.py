"""Local historical wheel audit for the consumed ABC identities.

These digests are bound by the five tracked compact-abc-editor status pages.
This read-only audit never authorizes re-saving or running an old identity.
New package preflights must still compare every module with current source.
"""

from pathlib import Path
import hashlib

from irisx.errors import ValidationError

WHEELS = {
    'nvarc-compact-abc-editor-001':'d56754e63b22f5d05cd205cb80d00ddf9d2177afc8977675443a22ac2bf38ae6',
    'nvarc-compact-abc-editor-002':'aa506aa87b1e4e31bc92cdecd3126d7535eadb78f7c6e8bddf8faef5dbc62ac9',
    'nvarc-compact-abc-editor-003':'1a2158c1f2ed88afc161e6553b4485acea6a21212d8536a0ae6f950c815e7d5f',
    'nvarc-compact-abc-editor-004':'9010b3ec2688d0f7e8c506d61d1959b0ff74aaaecd6be13355fe1252a1b6b012',
    'nvarc-compact-abc-editor-005':'4bb7f4fb32f1efbeaf2b5be0dbac494703d1ab0a22d125f73a9bb676b9ae2bd2',
}


def verify_retained_wheel(path: Path, run_id: str) -> None:
    if run_id not in WHEELS or hashlib.sha256(path.read_bytes()).hexdigest() != WHEELS[run_id]:
        raise ValidationError('retained ABC wheel differs from tracked historical binding')
