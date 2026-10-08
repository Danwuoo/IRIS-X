"""Hash-bound stdlib manual admission precedes every native import."""
import argparse
import json
import hashlib
import os
from pathlib import Path
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','dependency'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--expected-plan-sha256',required=True)
    parser.add_argument('--owner-pid',type=int)
    parser.add_argument('--parent-pid',type=int)
    parser.add_argument('--rank',type=int)
    parser.add_argument('--model',type=Path)
    parser.add_argument('--dependency-receipt-sha256')
    args=parser.parse_args(argv)
    raw=(args.root/'plan.json').read_bytes();plan=json.loads(raw)
    if hashlib.sha256(raw).hexdigest()!=args.expected_plan_sha256:raise RuntimeError('independent plan pin differs')
    receipt=json.loads((args.root/'owner-start-confirmation.json').read_bytes())
    if not (plan.get('kernel_execution_type')=='QUICK_SAVE' and plan.get('agent_execution_authorized') is False and
        plan.get('owner_editor_only') is True and receipt.get('confirmed') is True and receipt.get('manual_only') is True):
        raise RuntimeError('manual owner confirmation required before native runtime imports')
    if os.environ.get('PYTHONHASHSEED')!='0' or sys.flags.hash_randomization:raise RuntimeError('fresh hashseed-zero child required')
    if args.rank is not None:
        import signal
        from tools.nvarc_public_eval import install_owner_guard
        from tools.nvarc_uncapped_artifacts import await_worker_registration
        install_owner_guard(args.parent_pid,signal.SIGKILL)
        await_worker_registration()
    from tools import nvarc_uncapped_runtime as runtime
    runtime.verify_runtime(args.root,args.expected_plan_sha256,confirmed=True)
    if args.rank is not None:
        if not (0<=args.rank<4 and args.model and args.parent_pid and args.dependency_receipt_sha256):raise RuntimeError('complete worker arguments required')
        return runtime.worker(args.root,args.dependency,args.model,args.rank,args.parent_pid,args.dependency_receipt_sha256,args.expected_plan_sha256)
    if not args.owner_pid:raise RuntimeError('owner PID required')
    return runtime.execute(args.root,args.dependency,args.owner_pid,args.expected_plan_sha256)


if __name__=='__main__':
    raise SystemExit(main())
