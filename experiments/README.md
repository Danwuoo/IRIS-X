# Experiments

This directory preserves historical IRIS-X experiment definitions, inputs,
scripts, qualification substrates, raw records, manifests, results, and failure
records. There is currently no active experiment.

The pre-reset packages fall into three preservation classes:

- `exp-*`, `capability-pressure-attribution-v0`,
  `phase-6-pressure-sampling-v0`, and
  `phase-6-predicate-authority-repair-v0` contain completed or otherwise closed
  historical experiment/qualification records and their machinery.
- `substrates/` contains historical deterministic and model-execution
  qualification substrates. Their original package READMEs describe the status
  at the time; they are not current execution instructions.
- `d1a-warrant-discrimination-v0` contains an unexecuted historical
  qualification-development package and operational assets. Its own record
  states that D1a remained unqualified and unexecuted; it is not D1 evidence.
- `configurations/` contains historical configuration records, not current
  provider/model policy.

Paths and contents are intentionally retained because manifests, hashes,
validators, and research records depend on them. Do not reinterpret, normalize,
move, or regenerate evidence during repository cleanup.

Follow [`AGENTS.md`](AGENTS.md) for evidence discipline. Running any historical
experiment, provider/model process, launch helper, or follow-on qualification
requires explicit owner authorization for a new scope.
