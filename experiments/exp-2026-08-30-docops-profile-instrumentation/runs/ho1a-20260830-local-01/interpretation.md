# H-O1a Interpretation: `ho1a-20260830-local-01`

- **Status:** reviewed valid result
- **Support status:** `Supported — task-local`
- **Code revision executed:** `8762f9c0968cccc5be833b28693b615d7e002770`
- **Profile contract SHA-256:** `a8824df437eee5daeb58694d8ba90e97d0c3336b506b41f0a74ec1cfd259d579`
- **Raw terminal records:** `raw/terminal-records.jsonl`
- **Raw structured profiles:** `raw/profiles.jsonl`
- **Derived aggregate:** `results.json`

## Directly Observed Result

The run completed the intended 72/72 episodes: 12 tasks, two instrumentation
arms, and three repetitions. The existing Phase 3
`structured-readonly-v0` implementation produced 36/36 successful valid
episodes in each arm.

| Arm | Required field instances present | Missing | Complete profiles | Success | Invalid / profiler error |
| --- | ---: | ---: | ---: | ---: | ---: |
| `instrumentation-off-v0` | 0/612 | 612 | 0/36 | 36/36 | 0 / 0 |
| `instrumentation-on-v0` | 612/612 | 0 | 36/36 | 36/36 | 0 / 0 |

All 36 task/repetition pairs had identical produced-output hashes, actual
outcomes, terminal statuses, evidence status, and post-input snapshots. Both
arms read 5,391 bytes in 51 operations and serialized 20,760 producer-output
bytes. Every arm/task output, outcome, and status repeated identically across
three repetitions.

These observations satisfy every predeclared H-O1a support condition.

## Artifact and Timing Observation

The instrumentation-on arm serialized 26,295 canonical profile bytes; the
newline-delimited `profiles.jsonl` artifact occupied 28,023 bytes. Terminal
records excluding their self-size fields totaled 100,167 bytes off and 113,063
bytes on. The combined terminal-record artifact occupied 230,186 bytes.

Observed total episode wall time was 31.5331 ms off and 34.8628 ms on across
36 episodes. Paired on-minus-off wall deltas ranged from -0.4798 to 2.4055 ms,
with mean 0.0924917 ms, median 0.0193 ms, 21 positive pairs, and 15 negative
pairs. Process-CPU totals were 31.25 ms off and 15.625 ms on; the coarse timer
produced many zero deltas and does not support a stable direction.

`Timing overhead magnitude/direction: Not established under this horizon.`

The artifact-size increase is directly observed for this profile contract; it
is not a universal storage estimate. Development, maintenance, electricity,
hardware, fixture-authoring, and external failure-impact costs remain
`Unknown`. Model/token/API cost was not applicable and no paid use occurred.

The registered VANTA source assertion passed, the registry hash remained
unchanged, and `sources/` plus `references/papers/` remained clean.

## Evidence Boundary

This result establishes only task-local profile completeness and paired
behavior invariance for a small standard-library profiler around one
deterministic control. It does not establish production observability,
performance overhead, tracing completeness for model/tool systems, long-term
reliability, or an IRIS-X architecture invariant. NeMo Agent Toolkit informed
the measurement design but was not adopted as a dependency.

The supported narrow constraint is: when these runtime fields are required for
the evaluated control, structured profiling can record them completely without
changing the paired deterministic task result under this horizon, at an
explicit artifact-size trade-off.
