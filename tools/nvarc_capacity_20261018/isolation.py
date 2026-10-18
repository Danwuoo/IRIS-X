"""Dataset-only workload admission; existing unrelated association is not data.

This is not a filesystem sandbox or hardware/billing eligibility assertion.
Competition-container presence is not an admission failure. Existing unrelated
competition paths stay opaque; every model/train/solver input remains pinned.
"""
from pathlib import Path

from tools.arc2_goal_sprint_20261017.launch import require

FORMAT = 'irisx/capacity-input-admission-v2'
MECHANISM = 'exact dataset-separated mounts; not an OS sandbox'
IGNORED_RELATIVE = ('arc-prize-2026-arc-agi-3', 'competitions')
POLICY = 'unrelated competition containers excluded from workload; contents not inspected'
KEYS = {'format', 'mechanism', 'input_root', 'allowed_input_roots',
        'workload_evaluator_absent', 'original_public_dataset_absent', 'ignored_existing_competition_roots',
        'competition_payloads_admitted', 'competition_input_policy',
        'os_sandbox_claimed', 'filesystem_access_denial_claimed', 'hardware_eligibility_claimed'}


def validate_receipt(receipt):
    require(type(receipt) is dict and set(receipt) == KEYS
            and receipt['format'] == FORMAT and receipt['mechanism'] == MECHANISM
            and receipt['workload_evaluator_absent'] is True
            and receipt['original_public_dataset_absent'] is True
            and receipt['competition_payloads_admitted'] is False
            and receipt['competition_input_policy'] == POLICY
            and all(receipt[k] is False for k in ('os_sandbox_claimed',
                'filesystem_access_denial_claimed', 'hardware_eligibility_claimed')),
            'honest capacity input-admission-v2 receipt required')
    raw = receipt['input_root']
    require(type(raw) is str and Path(raw).is_absolute() and str(Path(raw)) == raw
            and raw != '/' and '..' not in Path(raw).parts,
            'canonical absolute input root required')
    root = Path(raw)
    ignored = receipt['ignored_existing_competition_roots']
    known = {str(root / p) for p in IGNORED_RELATIVE}
    require(type(ignored) is list and all(type(p) is str for p in ignored)
            and ignored == sorted(set(ignored)) and set(ignored) <= known,
            'only recognized competition container paths may be ignored')
    allowed = receipt['allowed_input_roots']
    require(type(allowed) is list and bool(allowed) and all(type(p) is str for p in allowed)
            and allowed == sorted(set(allowed)), 'canonical unique workload input roots required')
    for raw in allowed:
        path = Path(raw)
        require(path.is_absolute() and str(path) == raw and '..' not in path.parts
                and path != root and path.is_relative_to(root)
                and all(not path.is_relative_to(Path(p)) and not Path(p).is_relative_to(path) for p in known),
                'competition or broad ancestor cannot become a workload input')
    return receipt


def admit_inputs(input_root, allowed_input_roots):
    root = Path(input_root).absolute()
    require(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)),
            'regular non-symlink input hierarchy required')
    allowed = sorted({str(Path(p).absolute()) for p in allowed_input_roots})
    ignored = []
    for relative in IGNORED_RELATIVE:
        path = root / relative
        require(not path.is_symlink(), 'input hierarchy symlink forbidden')
        if path.exists():
            require(path.is_dir(), 'regular ignored competition container required')
            ignored.append(str(path))
    # Validate the declared workload before walking metadata. Never let a broad
    # workload grant absorb an opaque competition container.
    receipt = {'format': FORMAT, 'mechanism': MECHANISM,
        'input_root': str(root), 'allowed_input_roots': allowed,
        'workload_evaluator_absent': True, 'original_public_dataset_absent': True,
        'ignored_existing_competition_roots': sorted(ignored),
        'competition_payloads_admitted': False, 'competition_input_policy': POLICY,
        'os_sandbox_claimed': False, 'filesystem_access_denial_claimed': False,
        'hardware_eligibility_claimed': False}
    validate_receipt(receipt)
    old = (root / 'iris-x-public120-data-20261010',
           root / 'datasets/danielwuu/iris-x-public120-data-20261010')
    require(not any(p.exists() or p.is_symlink() for p in old),
            'original evaluator-bearing PUBLIC Dataset is mounted')
    workload = {Path(p) for p in allowed}
    require(all(p.is_dir() and not p.is_symlink() for p in workload), 'regular workload input roots required')
    leaves = workload | {Path(p) for p in ignored}
    pending = [root]
    while pending:
        for path in pending.pop().iterdir():
            require(not path.is_symlink(), 'input hierarchy symlink forbidden')
            if path in leaves:
                continue  # Includes opaque competitions; do not list/open payload.
            require(path.is_dir() and any(p.is_relative_to(path) for p in leaves),
                    'unexpected input mount/file in dataset-separated run: ' + str(path))
            pending.append(path)
    for leaf in workload:
        require(not (leaf / 'evaluator').exists(), 'evaluator directory present in workload source')
    return receipt
