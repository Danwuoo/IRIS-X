"""Bounded DDP full-SFT worker and supervisor for the NVARC compact branch.

DDP synchronizes gradients but does not shard model or optimizer memory. The
fixture model exercises the same collectives without loading real weights.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Mapping

from .arc_nvarc_runtime import atomic_json
from .arc_nvarc_training import FrozenSequenceStore, _torch_batch, collate, load_compact_model
from .canonical import digest_value
from .errors import ValidationError


def tiny_torch_model(seed: int) -> Any:
    import torch

    torch.manual_seed(seed)

    class TinyCausalLM(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embedding = torch.nn.Embedding(16, 16)
            self.head = torch.nn.Linear(16, 16)

        def forward(self, input_ids: Any, labels: Any, attention_mask: Any) -> Any:
            from types import SimpleNamespace

            logits = self.head(self.embedding(input_ids))
            loss = torch.nn.functional.cross_entropy(
                logits[:, :-1].reshape(-1, 16), labels[:, 1:].reshape(-1),
                ignore_index=-100)
            return SimpleNamespace(loss=loss)

    return TinyCausalLM()


def _identity(config: Mapping[str, Any], data_digest: str, model_digest: str,
              world_size: int) -> str:
    return digest_value({"format": "irisx/nvarc-ddp-sft", "config": config,
                         "data_digest": data_digest, "model_digest": model_digest,
                         "world_size": world_size})


def train_ddp(model: Any, sequences: FrozenSequenceStore, output: Path,
              config: Mapping[str, Any], *, model_digest: str, resume: bool = False,
              stop_after_steps: int | None = None, fail_rank_step: tuple[int, int] | None = None) -> dict[str, Any]:
    """Run one rank under torchrun; only rank zero owns the atomic checkpoint."""
    import torch
    import torch.distributed as dist

    if not dist.is_initialized():
        raise ValidationError("DDP worker needs an initialized process group")
    rank, world = dist.get_rank(), dist.get_world_size()
    if config.get("mode") != "ddp-full-sft" or world < 2:
        raise ValidationError("distributed full-SFT mode requires at least two ranks")
    accumulation = int(config["gradient_accumulation"])
    if accumulation < 1 or len(sequences) < world * accumulation:
        raise ValidationError("DDP data must cover every rank and accumulation slot")
    max_steps = int(config["max_steps"])
    max_tokens = int(config["maximum_training_tokens"])
    if max_steps < 1 or max_tokens < 1 or int(config["checkpoint_every"]) != 1:
        raise ValidationError("DDP needs positive limits and step-boundary checkpoints")
    device = torch.device("cuda", rank) if config.get("device") == "cuda" else torch.device("cpu")
    if device.type == "cuda":
        torch.cuda.set_device(rank)
    model.to(device)
    ddp = torch.nn.parallel.DistributedDataParallel(
        model, device_ids=[rank] if device.type == "cuda" else None)
    optimizer = torch.optim.AdamW(ddp.parameters(), lr=float(config["learning_rate"]))
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda step: max(0.0, (max_steps - step) / max_steps))
    identity = _identity(config, sequences.data_digest, model_digest, world)
    checkpoint = output / "ddp-training-state.pt"
    cursor = step = tokens_seen = 0
    if resume:
        state = torch.load(checkpoint, map_location="cpu", weights_only=False)
        if state.get("identity_digest") != identity or state.get("world_size") != world:
            raise ValidationError("DDP checkpoint identity or world size differs")
        ddp.module.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scheduler.load_state_dict(state["scheduler"])
        torch.set_rng_state(state["rank_cpu_rng"][rank])
        if device.type == "cuda":
            torch.cuda.set_rng_state(state["rank_cuda_rng"][rank], device=rank)
        cursor, step, tokens_seen = state["cursor"], state["step"], state["tokens_seen"]
    elif checkpoint.exists():
        raise ValidationError("existing DDP checkpoint requires resume")
    else:
        torch.manual_seed(int(config["seed"]) + rank)
    optimizer.zero_grad(set_to_none=True)
    assignment_trace = []
    stop_reason = "maximum_steps"
    while step < max_steps:
        if stop_after_steps is not None and step >= stop_after_steps:
            stop_reason = "planned_pause"
            break
        if fail_rank_step == (rank, step):
            raise RuntimeError("synthetic DDP rank failure")
        batches = []
        local_total = 0
        for micro in range(accumulation):
            index = (int(config["seed"]) + (cursor + micro) * world + rank) % len(sequences)
            item = sequences[index]
            batch = _torch_batch(collate([item], int(config["max_sequence_length"])), device)
            count = int(batch["attention_mask"].sum().item())
            supervised = int((batch["labels"] != -100).sum().item())
            batches.append((index, batch, count, supervised))
            local_total += count
        all_tokens = torch.tensor([local_total], dtype=torch.long, device=device)
        dist.all_reduce(all_tokens)
        if tokens_seen + int(all_tokens.item()) > max_tokens:
            stop_reason = "maximum_training_tokens"
            break
        for micro, (index, batch, count, supervised) in enumerate(batches):
            all_supervised = torch.tensor([supervised], dtype=torch.long, device=device)
            dist.all_reduce(all_supervised)
            if all_supervised.item() < 1:
                raise ValidationError("DDP step has no supervised tokens")
            context = ddp.no_sync() if micro < accumulation - 1 else nullcontext()
            with context:
                loss = ddp(**batch).loss
                if not torch.isfinite(loss):
                    raise ValidationError("non-finite DDP loss")
                scale = supervised * world / int(all_supervised.item()) / accumulation
                (loss * scale).backward()
            assignment_trace.append(index)
        torch.nn.utils.clip_grad_norm_(ddp.parameters(), float(config.get("clip_grad_norm", 1.0)))
        optimizer.step()
        scheduler.step()
        optimizer.zero_grad(set_to_none=True)
        cursor += accumulation
        step += 1
        tokens_seen += int(all_tokens.item())
        rngs: list[Any] = [None] * world
        dist.all_gather_object(rngs, torch.get_rng_state())
        cuda_rngs: list[Any] | None = [None] * world if device.type == "cuda" else None
        if cuda_rngs is not None:
            dist.all_gather_object(cuda_rngs, torch.cuda.get_rng_state(rank))
        if rank == 0:
            output.mkdir(parents=True, exist_ok=True)
            temporary = checkpoint.with_suffix(".tmp")
            torch.save({"format": "irisx/nvarc-ddp-training-state",
                        "identity_digest": identity, "world_size": world,
                        "model": ddp.module.state_dict(), "optimizer": optimizer.state_dict(),
                        "scheduler": scheduler.state_dict(), "rank_cpu_rng": rngs,
                        "rank_cuda_rng": cuda_rngs,
                        "cursor": cursor, "step": step, "tokens_seen": tokens_seen}, temporary)
            os.replace(temporary, checkpoint)
        dist.barrier()
    report = {"format": "irisx/nvarc-ddp-rank-report", "rank": rank,
              "identity_digest": identity, "step": step, "cursor": cursor,
              "tokens_seen": tokens_seen, "stop_reason": stop_reason,
              "assigned_indices": assignment_trace}
    atomic_json(output / f"rank-{rank}.json", report)
    dist.barrier()
    return report


def _authorized_real_run(path: Path | None, identity: str, config: Mapping[str, Any],
                         wall_seconds: int) -> None:
    if path is None or not path.is_file():
        raise ValidationError("real distributed SFT needs an owner authorization")
    value = json.loads(path.read_bytes())
    if (value.get("approved") is not True or value.get("operation") != "train-ddp-sft" or
            value.get("identity_digest") != identity or not value.get("owner_decision") or
            value.get("maximum_steps") != config["max_steps"] or
            value.get("maximum_training_tokens") != config["maximum_training_tokens"] or
            value.get("maximum_session_seconds") != wall_seconds or
            value.get("maximum_paid_usd") is None):
        raise ValidationError("real DDP SFT authorization does not match limits")


def supervise(*, config_path: Path, data_root: Path, output: Path,
              world_size: int, session_wall_seconds: int, maximum_total_wall_seconds: int,
              fixture: bool = False, model_root: Path | None = None,
              authorization: Path | None = None, resume: bool = False,
              stop_after_steps: int | None = None,
              fail_rank_step: tuple[int, int] | None = None) -> dict[str, Any]:
    """Bound a torchrun process tree and charge failed sessions conservatively."""
    if world_size < 2 or session_wall_seconds < 1 or maximum_total_wall_seconds < session_wall_seconds:
        raise ValidationError("DDP world and wall limits are invalid")
    config = json.loads(config_path.read_bytes())
    store = FrozenSequenceStore(data_root)
    if fixture:
        model_digest = digest_value({"fixture_torch_model_seed": int(config["seed"])})
    else:
        if model_root is None:
            raise ValidationError("real DDP SFT needs a compact model")
        from .arc_nvarc_representation import verify_model_material
        material = json.loads((model_root / "material-manifest.json").read_bytes())
        model_digest = digest_value(material)
        verify_model_material(model_root, model_digest)
    identity = _identity(config, store.data_digest, model_digest, world_size)
    if not fixture:
        _authorized_real_run(authorization, identity, config, session_wall_seconds)
    ledger_path = output / "ddp-ledger.json"
    if resume:
        ledger = json.loads(ledger_path.read_bytes())
        if ledger.get("identity_digest") != identity:
            raise ValidationError("DDP wall ledger identity differs")
    else:
        if ledger_path.exists():
            raise ValidationError("existing DDP wall ledger requires resume")
        ledger = {"format": "irisx/nvarc-ddp-wall-ledger", "identity_digest": identity,
                  "maximum_total_wall_seconds": maximum_total_wall_seconds,
                  "sessions": [], "charged_wall_seconds": 0.0}
    if (ledger["maximum_total_wall_seconds"] != maximum_total_wall_seconds or
            ledger["charged_wall_seconds"] + session_wall_seconds > maximum_total_wall_seconds):
        raise ValidationError("DDP cumulative wall budget would be exceeded")
    session = {"index": len(ledger["sessions"]), "reserved_seconds": session_wall_seconds,
               "charged_seconds": session_wall_seconds, "status": "pending"}
    ledger["sessions"].append(session)
    ledger["charged_wall_seconds"] += session_wall_seconds
    atomic_json(ledger_path, ledger)
    argv = [sys.executable, "-m", "torch.distributed.run", "--rdzv-backend=static",
            "--master-addr=127.0.0.1", "--master-port=0",
            f"--nproc-per-node={world_size}", "-m", "irisx.arc_nvarc_distributed", "worker",
            "--config", str(config_path), "--data-root", str(data_root),
            "--output", str(output)]
    if fixture:
        argv.append("--fixture")
    else:
        argv.extend(["--model-root", str(model_root)])
    if resume:
        argv.append("--resume")
    if not fixture:
        argv.extend(["--authorization", str(authorization),
                     "--session-wall-seconds", str(session_wall_seconds)])
    if stop_after_steps is not None:
        argv.extend(["--stop-after-steps", str(stop_after_steps)])
    if fail_rank_step is not None:
        argv.extend(["--fail-rank", str(fail_rank_step[0]),
                     "--fail-step", str(fail_rank_step[1])])
    env = dict(os.environ)
    # The Windows CPU build can lack libuv while torchrun defaults to requesting it.
    if os.name == "nt" and config.get("device") == "cpu":
        env["USE_LIBUV"] = "0"
    src_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = src_root + os.pathsep + env.get("PYTHONPATH", "")
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    log = output / f"torchrun-session-{session['index']}.log"
    if os.name == "nt" and config.get("device") == "cpu":
        status, code = _run_local_cpu_ranks(
            argv[argv.index("worker"):], world_size, env, log, session_wall_seconds)
    else:
        with log.open("wb") as stream:
            process = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT, env=env,
                                       creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                                       start_new_session=os.name != "nt")
            try:
                code = process.wait(timeout=session_wall_seconds)
                status = "returned" if code == 0 else "worker_failure"
            except subprocess.TimeoutExpired:
                status = "timeout"
                code = None
                _terminate_tree(process)
    elapsed = time.monotonic() - started
    # A failed/uncertain process consumes the reserved session ceiling.
    charged = min(float(session_wall_seconds), elapsed) if status == "returned" else float(session_wall_seconds)
    ledger["charged_wall_seconds"] += charged - session["charged_seconds"]
    session.update({"charged_seconds": charged, "status": status,
                    "elapsed_seconds": elapsed, "exit_code": code})
    atomic_json(ledger_path, ledger)
    return {"identity_digest": identity, "status": status, "exit_code": code,
            "checkpoint_exists": (output / "ddp-training-state.pt").is_file(),
            "charged_wall_seconds": ledger["charged_wall_seconds"], "log": str(log)}


def _terminate_tree(process: subprocess.Popen[Any]) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def _run_local_cpu_ranks(worker_args: list[str], world: int, base_env: dict[str, str],
                         log: Path, wall_seconds: int) -> tuple[str, int | None]:
    """Windows Gloo launcher where the installed torchrun requires absent libuv."""
    from torch.distributed.elastic.utils.distributed import get_free_port

    port = get_free_port()
    processes: list[subprocess.Popen[Any]] = []
    started = time.monotonic()
    with log.open("wb") as stream:
        try:
            for rank in range(world):
                env = {**base_env, "MASTER_ADDR": "127.0.0.1", "MASTER_PORT": str(port),
                       "RANK": str(rank), "LOCAL_RANK": str(rank), "WORLD_SIZE": str(world)}
                processes.append(subprocess.Popen(
                    [sys.executable, "-m", "irisx.arc_nvarc_distributed", *worker_args],
                    stdout=stream, stderr=subprocess.STDOUT, env=env,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)))
            while True:
                codes = [process.poll() for process in processes]
                if any(code is not None and code != 0 for code in codes):
                    return "worker_failure", next(code for code in codes if code is not None and code != 0)
                if all(code == 0 for code in codes):
                    return "returned", 0
                if time.monotonic() - started >= wall_seconds:
                    return "timeout", None
                time.sleep(0.05)
        finally:
            for process in processes:
                if process.poll() is None:
                    _terminate_tree(process)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NVARC bounded DDP full-SFT")
    sub = parser.add_subparsers(dest="command", required=True)
    worker = sub.add_parser("worker")
    parent = sub.add_parser("supervise")
    for command in (worker, parent):
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--data-root", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--fixture", action="store_true")
        command.add_argument("--model-root", type=Path)
        command.add_argument("--resume", action="store_true")
        command.add_argument("--stop-after-steps", type=int)
        command.add_argument("--fail-rank", type=int)
        command.add_argument("--fail-step", type=int)
        command.add_argument("--authorization", type=Path)
        command.add_argument("--session-wall-seconds", type=int)
    parent.add_argument("--world-size", type=int, required=True)
    parent.add_argument("--maximum-total-wall-seconds", type=int, required=True)
    args = parser.parse_args(argv)
    if args.command == "supervise":
        report = supervise(config_path=args.config, data_root=args.data_root,
                           output=args.output, world_size=args.world_size,
                           session_wall_seconds=args.session_wall_seconds,
                           maximum_total_wall_seconds=args.maximum_total_wall_seconds,
                           fixture=args.fixture, model_root=args.model_root,
                           authorization=args.authorization, resume=args.resume,
                           stop_after_steps=args.stop_after_steps,
                           fail_rank_step=((args.fail_rank, args.fail_step)
                                           if args.fail_rank is not None and args.fail_step is not None else None))
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "returned" else 2
    import torch.distributed as dist

    config = json.loads(args.config.read_bytes())
    if os.name == "nt" and config.get("device") == "cpu":
        dist.init_process_group("gloo", init_method=(
            f"tcp://{os.environ['MASTER_ADDR']}:{os.environ['MASTER_PORT']}?use_libuv=0"),
            rank=int(os.environ["RANK"]), world_size=int(os.environ["WORLD_SIZE"]))
    else:
        dist.init_process_group("nccl" if config.get("device") == "cuda" else "gloo")
    try:
        store = FrozenSequenceStore(args.data_root)
        model_digest = (digest_value({"fixture_torch_model_seed": int(config["seed"])})
                        if args.fixture else digest_value(json.loads(
                            (args.model_root / "material-manifest.json").read_bytes())))
        if not args.fixture:
            from .arc_nvarc_representation import verify_model_material
            verify_model_material(args.model_root, model_digest)
            _authorized_real_run(args.authorization,
                                 _identity(config, store.data_digest, model_digest,
                                           dist.get_world_size()), config,
                                 args.session_wall_seconds)
        model = (tiny_torch_model(int(config["seed"])) if args.fixture
                 else load_compact_model(args.model_root))
        report = train_ddp(model, store, args.output, config, model_digest=model_digest,
                           resume=args.resume, stop_after_steps=args.stop_after_steps,
                           fail_rank_step=((args.fail_rank, args.fail_step)
                                           if args.fail_rank is not None and args.fail_step is not None else None))
        print(json.dumps({key: value for key, value in report.items() if key != "assigned_indices"}))
    finally:
        dist.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
