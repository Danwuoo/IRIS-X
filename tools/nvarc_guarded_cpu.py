"""Install a Linux owner-death guard before executing a CPU-only Python script."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import runpy
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.nvarc_native_multitask import require
from tools.nvarc_public_eval import install_owner_guard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-pid', type=int, required=True)
    parser.add_argument('--script', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    require(remaining and remaining[0] == '--', 'explicit guarded-script argument boundary required')
    remaining = remaining[1:]
    require(os.environ.get('CUDA_VISIBLE_DEVICES', '') == '' and os.environ.get('PYTHONHASHSEED') == '0',
            'fresh seed-zero CPU-only guarded script required')
    install_owner_guard(args.owner_pid, signal.SIGKILL)
    sys.argv = [str(args.script), *remaining]
    runpy.run_path(str(args.script), run_name='__main__')


if __name__ == '__main__': main()
