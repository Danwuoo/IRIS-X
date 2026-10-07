"""Four-L4 resource attachment only; never opens competition file contents."""
from pathlib import Path
from tools.nvarc_native_multitask import require

COMPETITION_SOURCE = 'arc-prize-2026-arc-agi-2'
COMPETITION_MOUNT = '/kaggle/input/competitions/'+COMPETITION_SOURCE
SCIENTIFIC_SCOPES = {'synthetic control tensors only', 'frozen public solver-visible development challenges only'}


def attachment(scientific_scope):
    require(scientific_scope in SCIENTIFIC_SCOPES, 'closed scientific input scope required')
    return {'format':'irisx/native-four-l4-resource-attachment-v1',
        'competition_sources':[COMPETITION_SOURCE], 'competition_mount':COMPETITION_MOUNT,
        'purpose':'four-L4 hardware entitlement only', 'competition_files_allowed':[],
        'scientific_input_scope':scientific_scope}


def validate_attachment(value, scientific_scope):
    require(value == attachment(scientific_scope), 'exact resource-only competition attachment required')


def verify_mount(plan, scientific_scope):
    """Check only exact directory metadata, without listing or reading members.

    This is a source-enforced IO policy, not independent OS access attestation.
    Hardware inventory must separately establish the actual four-L4 allocation.
    """
    validate_attachment(plan['resource_attachment'], scientific_scope)
    directory = Path(COMPETITION_MOUNT)
    require(not directory.is_symlink() and directory.is_dir(),
        'exact four-L4 resource-only competition mount required')
    return {'resource_attachment':attachment(scientific_scope), 'mount_directory_verified':True,
        'competition_files_opened':0, 'competition_directory_members_listed':False,
        'os_access_attestation':False}
