# E12 native prefix-stop pilot: inert runnable package

This adds a runnable native implementation for the distinct
`stage4-e12-probe-prefix-20261007-001` identity. It prepares notebook version 10
for notebook 137327571. It is offline development and an inert package, not a
record of GPU execution or permission to publish or run it.

The four existing public development tasks contain six test cases. Each task
starts from the same saved baseline separately for the 64-update and 128-update
arms. There are 768 planned optimizer updates and twelve test executions. This
is an engineering/cost mechanism pilot. The original 24-task, 35-test,
two-arm, two-repeat screen remains unexecuted. Shared model loading and a shared
GPU lease do not establish a per-arm total allocated-GPU cost reduction. No
BASE0 comparison, TTT causal improvement, numerical parity, correctness score,
or promotion is inferred.

## Native path

`nvarc_e12_entry.py` checks an exact, fresh, owner-edited confirmation using
standard-library code before importing runtime orchestration. The notebook
configuration defaults to False. Its default execution and download branches
perform no setup, imports, filesystem writes, or launches. An explicit owner
opt-in declares the exact native stack, a fresh single-attempt session, four free
GPU-hours, pay-to-scale disabled, and stopping the Editor after downloading.
Those declarations do not independently attest quota or a provider timeout.
All staged publication and agent-runtime authority fields remain false.

The new stager preserves every frozen v9 source/material member exactly and
adds new E12 modules and a retained frozen-v9 plan. The model, original solver,
Trainer, dependency/readproof, tokenizer, source, binary, and hardware gates
remain those of the accepted v9 package. Historical E10/E11 profiles are not
relaxed. The bounded verification-queue experiment is not integrated.

Each GPU owns one resident NativeEngine. Each arm prepares a new native
Trainer and optimizer, with all 128 prepared examples, batch size one, one
epoch, max_steps=-1, the original 128-step horizon and 13 warmup steps. The
new adapter observes the original RandomSampler base iterator without replacing
its instance type, preserving Accelerate's SeedableRandomSampler conversion.
It retains the entire native permutation. A source check requires permutation
draws to use the local generator and the sole global seed draw to precede all
yields; eagerly retaining the permutation therefore preserves the observed
source RNG control flow.

Hooks bind actual row IDs and labels, forward returns, backward returns,
clipped gradients, all 506 Adam step counters, optimizer returns, scheduler
returns, and post-update Trainer callbacks. The short arm stops only after its
64th completed update and scheduler step. Independent entry guards reject a
65th forward even if the Trainer ignores its stop flag. The zero-LR first
update still executes and advances all Adam moments. No 64-step scheduler is
constructed. Callback checkpoints and failure snapshots retain the new trace;
the existing per-operation epoch ledger retains reservations and completions.

All 506 finite BF16 Adam states are checked and then disposed before inference.
Each arm restores the original baseline afterwards. Complete 905-parameter
metadata, saved-tensor hashes, caches, original forward/AMP transitions, and
all RNG streams are recorded and checked. The initial six synthetic controls
and one final post-reset control run once per worker: 28 total controls, not a
new 56-control design. Intermediate arm resets use exact tensor and metadata
checks without extra model forwards.

Both trained models use original p=.2 INTERLEAVED inference, fresh adapters and
caches, identical generation RNG, 120 generation seconds and 150 total seconds
per test. The same source formatter, transforms, padded verifier inputs, NLL
receipts, and original ranker are replayed on CPU. The native paired proof binds
the first 64 actual input/label/LR/RNG/update events; independently trained
weights need not equal one another. Retained losses are finite observations,
not a claim of cross-run numerical determinism.

## Resources and closure

The sole resource profile is 3,600 seconds on four GPUs, or four allocated
GPU-hours, with no paid spend. Planning reserves are 900 seconds startup,
1,200 seconds combined training, 600 seconds inference, 360 seconds for two
resets, and 300 seconds finalization. Their sum is 3,360 seconds; this arithmetic
is not runtime feasibility proof. A worker cap of 3,060 seconds includes the
full startup allowance and 2,160 seconds of subsequent work. Launch and phase
cutoffs also respect the absolute session deadline. The first arm reserves two
remaining resets; the second reserves one. Saved training time never enlarges
a test's generation or verifier allocation.

The outer supervisor requests TERM at 3,290 seconds, KILL at 3,299.8, confirms
owned-group absence by 3,300, and reserves the remaining 300 seconds for closure.
The coordinator records actual worker process groups and collectively stops all
registered producers on failure. Leader exit alone is insufficient. These are
host-process observations, not GPU preemption or provider billing attestations.

Eight distinct E12 output members use the existing atomic single-marker writer
protocol in a new closed E12 module. Unverified slots remain explicit nulls;
recoverable committed inference prefixes remain unqualified if the worker or
paired training proof failed. The new strict 3,600-second archive/envelope path
preserves the original runtime ZIP, stop proof, sidecar, and subsequent observed
write-completion evidence. It does not put a claim about its own future write
inside that write. The notebook links the verified delivery bundle; a read-only
download cell checks trusted staged verifier bytes and never recovers or runs
work. Missing, failed, or late closure remains explicit.

## Offline verification and staging

Focused tests exercise installed native-hook sequencing with fake Torch and
Trainer objects, zero-LR counters, ignored callbacks, failed backward/scheduler
operations, exact prefix replay and mutated counterexamples, one resident model,
fresh optimizers, failure reset/control behavior, launch cleanup, 900-second
startup boundaries, inference source replay, inert embedded entrypoints, and
closure failure cases. They do not establish actual native CUDA execution.

After committing the exact sources, stage and preflight with:

```sh
python tools/stage_nvarc_e12_prefix_probe.py stage --package NEW_PACKAGE \
  --frozen-runtime EXACT_V9_RUNTIME --source-commit FULL_COMMIT
python tools/stage_nvarc_e12_prefix_probe.py preflight --package NEW_PACKAGE
```

Package preflight checks committed source bytes, frozen material bytes, all
embedded Python compilation, exact rendered notebook payload, immutable package
membership, and disabled authority. Provider publication, quota review, actual
native execution, terminal retrieval, and independent returned-evidence replay
remain separate steps owned by the parent workflow.
