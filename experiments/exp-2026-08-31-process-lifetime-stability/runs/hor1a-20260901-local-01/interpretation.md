# H-OR1a Run Interpretation — `hor1a-20260901-local-01`

- **Status:** result — reviewed measured run
- **Definition commit:** `da4b698edb1eab8f1b2d59c56fd9c3511aa466f4`
- **Result:** `Stable under declared horizon`
- **Horizon:** 12 tasks × 20 sequence passes × 2 arms = 480 episodes
- **Invalid attempts:** none

## Directly observed result

Both arms completed 240/240 episodes with actual outcome `success`, empirical evidence status `sufficient`, terminal execution status `completed`, and verified-success eligibility true. Acceptance was `not_applicable`, not used as evidence truth. There were zero invalid episodes.

Within each arm, every task retained one deterministic response-core hash across all 20 passes: zero drift records. At every frozen sequence position, each arm completed 20/20 successes with one distinct response-core hash. Every paired request hash and response-core hash matched across arms: zero cross-arm mismatches.

The long-lived arm used one worker PID and its process-local sequence counter was exactly 1 through 240. The fresh arm launched 240 new processes and every process-local counter was 1. Windows reused some PID values, producing 221 distinct PIDs; launch count and counter reset, rather than PID uniqueness, establish the fresh-process arm.

## Resource observations

Both arms read 723,060 bytes and produced 30,900 canonical output bytes. Fresh-process orchestration wall time summed to 31.198 seconds, while long-lived request/response orchestration wall time summed to 1.020 seconds. Worker-internal wall/CPU sums were 0.642/0.641 seconds for fresh workers and 0.954/0.828 seconds for the long-lived worker. These timings are descriptive: process creation is intrinsic to the fresh arm, host scheduling/timer resolution differ, and H-OR1a tests stability rather than performance superiority.

Raw terminal evidence is 480 JSONL records / 771,648 bytes with SHA-256 `c46a38906947b9352991127f192d9313e74efe4d3c1a20fe8e1b42dd815f90ad`.

## Bounded interpretation

Under this frozen deterministic local sequence, keeping the worker alive across 240 ordered requests introduced no observable outcome, evidence, terminal-status, output-hash, or sequence-position drift relative to fresh-process execution. This supports only process-lifetime operational stability for the selected 12 read-only fixtures and 20-pass horizon.

- **Not established:** days/weeks or production operational reliability, a stability threshold, or transfer to other task/configuration families.
- **Not evaluated:** concurrency, memory pressure, stochastic/model behavior, network/provider state, process restart, stateful workspace accumulation, robustness, change reliability, or recovery reliability.
- **Unknown:** electricity, process-launch energy, hardware depreciation, and deployment workload.
