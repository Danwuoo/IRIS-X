"""Run the two-rank CPU FSDP worker without Windows torchrun's libuv store."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--compact", type=Path, required=True)
    parser.add_argument("--sequences", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--stop-after-steps", type=int)
    args = parser.parse_args()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    command = [sys.executable, "-m", "irisx.arc_nvarc_fsdp_sft",
               "--plan", str(args.plan), "--compact", str(args.compact),
               "--sequences", str(args.sequences), "--output", str(args.output)]
    if args.resume:
        command.append("--resume")
    if args.stop_after_steps is not None:
        command.extend(("--stop-after-steps", str(args.stop_after_steps)))
    children = []
    logs = []
    deadline = time.monotonic() + 180
    try:
        for rank in range(2):
            environment = {**os.environ, "MASTER_ADDR": "127.0.0.1",
                           "MASTER_PORT": str(port), "WORLD_SIZE": "2",
                           "RANK": str(rank), "LOCAL_RANK": str(rank),
                           "USE_LIBUV": "0", "OMP_NUM_THREADS": "1"}
            log_path = args.output.parent / f"{args.output.name}-rank-{rank}.log"
            log = log_path.open("w", encoding="utf-8")
            logs.append(log)
            children.append(subprocess.Popen(command, env=environment,
                                             stdout=log, stderr=subprocess.STDOUT))
        while any(child.poll() is None for child in children):
            failed = [(rank, child.poll()) for rank, child in enumerate(children)
                      if child.poll() not in {None, 0}]
            if failed or time.monotonic() > deadline:
                raise RuntimeError("CPU FSDP rank failed or timed out: " + str(failed))
            time.sleep(0.2)
        for rank, child in enumerate(children):
            if child.returncode:
                raise RuntimeError(f"rank {rank} failed with {child.returncode}")
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
        for log in logs:
            log.close()
        for rank in range(len(logs)):
            print(f"rank {rank} log: {args.output.parent / f'{args.output.name}-rank-{rank}.log'}")


if __name__ == "__main__":
    main()
