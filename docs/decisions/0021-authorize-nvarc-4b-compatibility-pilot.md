# Decision 0021: Authorize one Qwen3.5-4B compatibility pilot

Status: Accepted

Date: 2026-09-23

## Context

The owner chose preparation of a real Qwen3.5-4B Kaggle pilot rather than the
tiny-only GPU A route. The [reviewable package and exact bounds](../../trials/arc-agi-2-qwen35-nvarc/4b-pilot.md)
were committed on main. In response to the final request to authorize the
specified one-kernel launch and one terminal retrieval, the owner said
「授權啟動」. This is a new identity, separate from all closed ARC trials.

## Decision

Authorize exactly one private Kaggle GPU kernel push for
`nvarc-4b-compat-pilot-001` at
`danielwuu/irisx-nvarc-4b-compat-pilot-001`, bounded status checks until a
terminal state, and exactly one terminal output retrieval. Use only the
existing private `danielwuu/irisx-arc-agi-2-trial-002-smoke-001` Dataset v2
with the pinned Qwen3.5-4B model material and offline wheels bound in the
[draft plan](../../trials/arc-agi-2-qwen35-nvarc/configs/draft-4b-pilot.json).
The newly staged notebook and metadata must be private, Internet disabled,
truth-free, and contain no competition source.

The maximums are USD 0 paid cost, one `NvidiaL4` device used (one to four may
be visible; at least 22,000 MiB on device 0), 1,800 seconds for the notebook,
1,500 seconds for its worker and a 300-second finalization reserve, two LoRA
optimizer steps, 128 synthetic training tokens, zero model generations, zero
teacher calls, one kernel push, and one output retrieval. The synthetic grid
demonstration is generated in the runner. No ARC task, evaluator truth,
full-SFT workload, checkpoint export, scoring, competition submission,
publication, external model API, paid work, retry, resume or replacement kernel
is authorized. This pilot tests actual 4B material loading, LoRA gradient
coverage, reset, timing and peak memory only.

Before push, bind the exact owner decision to the unchanged draft plan digest,
stage the approved notebook locally, inspect the resulting wheel/notebook and
metadata digests, and atomically record the launch ledger. Verify the mounted
model and wheel bytes before training. A dependency, hardware, OOM, timeout or
other failure consumes the launch. Retrieve terminal files once, retain their
digests and failure evidence, and stop. Any further work needs new owner
direction; prior trial quotas do not transfer.
