# H-I1a Interpretation: `hi1a-20260830-local-01`

- **Status:** reviewed valid result
- **Support status:** `Supported — task-local`
- **Code revision executed:** `027088441675ea052db51c81a297cc757367cca0`
- **Frozen definition SHA-256:** `097bd968b8aad558ef111fd602d0fe2d409f9312ee52e5be465de0b6bc7f6cc5`
- **Raw records:** `raw/terminal-records.jsonl`
- **Preserved copied workspaces:** `raw/workspaces/`
- **Derived aggregate:** `results.json`

## Directly Observed Result

The run completed 48/48 valid terminal records: eight identical proposed
actions, two arms, and three repetitions. Every episode began from a fresh copy
matching the frozen template snapshot
`8b4e7d34695317eea85fb0ab0e775c60f01b20041b717cdf5364e57077d1bc40`.
All paired starting states and action-definition hashes were identical.

| Arm | Prohibited proposed | Prohibited executed | Prohibited mutation observed | Prohibited mutation prevented | Post-hoc detections | False permitted blocks | Permitted completed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `post-hoc-check-v0` | 18 | 18 | 18 | 0 | 18 | 0 | 6 |
| `pre-execution-intercept-v0` | 18 | 0 | 0 | 18 | 0 | 0 | 6 |

The post-hoc arm executed and empirically mutated protected state for every
overwrite, append, delete, forbidden-create, rename, and replace episode before
policy detection. The measured path/hash/directory oracle classified all
expected mutation classes correctly.

The pre-execution arm classified those same 18 proposed actions before
execution, never called their mutation primitive, and preserved protected state
in every episode. The read-only and permitted scratch-write positive controls
were both allowed in all three repetitions, so treatment did not pass by
rejecting every action.

The post-state oracle received only before state, after state, action, and
policy—not the interceptor decision. It derived path-set additions/removals,
file-hash modifications, directory-membership change, mutation class, and
protected-state invariance from measured workspace state. All arm/action
outcomes repeated identically across three repetitions. These observations
satisfy every predeclared H-I1a support condition.

## Cost and Preservation Observation

The post-hoc arm recorded 9.7789 ms wall time across 24 records; treatment
recorded 2.3996 ms. Process CPU measurement was 0.0 ms in both arms at this
timer resolution. Terminal records excluding self-size fields totaled 94,198
bytes post-hoc and 94,591 bytes treatment; the combined raw terminal artifact
was 200,852 bytes. Preserved copied-workspace files totaled 8,643 bytes.

These short same-host timings are descriptive and the arms intentionally take
different execution paths. Development, maintenance, electricity, hardware,
policy-authoring, and external failure-impact costs remain `Unknown`; no model,
token, API, credential, network, or paid service was used.

All state changes occurred only in the new run's experiment-local copied
workspaces. The registered Prime Intellect Verifiers snapshot assertion passed,
the registry hash remained unchanged, and `sources/` plus
`references/papers/` remained clean.

## Evidence Boundary

This is finite-sample, task-local support that the tested deterministic
pre-execution policy gate prevents the frozen copied-workspace mutation classes
that post-hoc checking detects only after mutation. It does not establish shell
or process isolation, OS sandbox security, adversarial bypass resistance, model
compliance, long-running or recovery reliability, complete parent H-I1, or an
architecture requirement.
