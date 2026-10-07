"""E12 entry: standard-library exact owner admission precedes native imports."""
import argparse
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'dependency', 'model'):
        parser.add_argument('--' + name, type=Path, required=name != 'model')
    parser.add_argument('--rank', type=int)
    parser.add_argument('--deadline', type=float)
    parser.add_argument('--parent-pid', type=int)
    parser.add_argument('--dependency-receipt-sha256')
    parser.add_argument('--started', type=float)
    parser.add_argument('--owner-pid', type=int)
    parser.add_argument('--bootstrap', action='store_true')
    args = parser.parse_args(argv)
    # The only project module imported before admission is standard library only.
    from tools.nvarc_e12_admission import parse, verify_confirmation, require
    plan = parse((args.root / 'plan.json').read_bytes())
    confirmation = verify_confirmation(args.root, plan)
    require(os.environ.get('PYTHONHASHSEED') == '0' and sys.flags.hash_randomization == 0,
        'fresh hashseed-zero process required')
    from tools import stage_nvarc_e12_prefix_probe as api
    from tools import nvarc_e12_runtime as runtime
    api.verify_runtime(args.root, require_approved=True)
    if args.rank is not None:
        require(type(args.rank) is int and 0 <= args.rank < 4 and args.model is not None and
            args.deadline is not None and args.parent_pid is not None and
            args.dependency_receipt_sha256 is not None, 'complete exact E12 worker arguments required')
        return runtime.worker(args.root, args.dependency, args.model, args.rank, args.deadline,
            args.parent_pid, args.dependency_receipt_sha256, runtime_api=api)
    require(args.started == confirmation['started_monotonic'] and args.owner_pid is not None,
        'coordinator start must equal owner confirmation and retain owner PID')
    import signal
    from tools.nvarc_public_eval import install_owner_guard
    install_owner_guard(args.owner_pid, signal.SIGTERM)
    return runtime.execute(args.root, args.dependency, args.started, runtime_api=api)


if __name__ == '__main__':
    raise SystemExit(main())
