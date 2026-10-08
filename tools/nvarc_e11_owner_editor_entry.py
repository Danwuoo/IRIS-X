"""Owner-only E11 entry: exact local confirmation precedes orchestration imports."""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','dependency','model'):parser.add_argument('--'+name,type=Path,required=name!='model')
    parser.add_argument('--rank',type=int);parser.add_argument('--deadline',type=float);parser.add_argument('--parent-pid',type=int)
    parser.add_argument('--dependency-receipt-sha256');parser.add_argument('--started',type=float)
    parser.add_argument('--owner-pid',type=int);parser.add_argument('--bootstrap',action='store_true');args=parser.parse_args()
    # This helper imports only the standard library. Missing/default/stale
    # declarations never reach the orchestration or native dependency modules.
    from tools.nvarc_e11_owner_editor import parse,verify_confirmation,require
    plan=parse((args.root/'plan.json').read_bytes())
    confirmation=verify_confirmation(args.root,plan)
    require(os.environ.get('PYTHONHASHSEED')=='0' and sys.flags.hash_randomization==0,'fresh hashseed-zero process required')
    from tools import stage_nvarc_e11_owner_editor as api
    from tools import nvarc_e11_paired_floor as runtime
    api.verify_runtime(args.root,require_approved=True)
    if args.rank is not None:
        return runtime.worker(args.root,args.dependency,args.model,args.rank,args.deadline,args.parent_pid,
            args.dependency_receipt_sha256,runtime_api=api)
    require(args.started==confirmation['started_monotonic'],'coordinator start must equal owner confirmation')
    import signal
    from tools.nvarc_public_eval import install_owner_guard
    install_owner_guard(args.owner_pid,signal.SIGTERM)
    return runtime.execute(args.root,args.dependency,args.started,runtime_api=api)


if __name__=='__main__':raise SystemExit(main())
