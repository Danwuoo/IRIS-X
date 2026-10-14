# ARC2 offline continuation

A standard-library-only companion to the existing SFT256 / fixed-batch RL /
whole-wall-matched extra-SFT experiment. It prepares an inert source-bound plan
and summarizes explicitly supplied terminal-consumer JSON. It is not a trainer,
collector, scorer, authentication checker, or execution/admission API.

Source baseline: `cc14bd1a79aac1fe6135017c9e09d4834300675d` on
`feat/run008-native-research-20261013`. Development belongs only to
`feat/arc2-sft-rl-continuation-20261014`; main and the engineering branch are
separate. Original source files and pins remain unchanged.

## Interfaces

- `prepare.prepare_plan(repository_root: Path) -> dict` checks five pinned public
  sources as bytes/data and returns an inert plan and original-artifact checklist.
  It never imports frozen runtime code, samples a clock or reads private inputs.
- `analysis.analyze_report(report: dict) -> dict` aggregates the existing batched
  consumer format. Untrusted declarations remain separate from derived counts.
- `io.read_json(path, expected_sha256)` reads one explicit, bounded, strict JSON
  object. Optional collector checkpoint/retrieval links match bytes and hashes;
  their recorded paths are never followed.
- `cli.py prepare` and `cli.py analyze` exclusively write a new local JSON file.
  No watcher, retry, provider call, task creation or automatic next run exists.

File operations require POSIX descriptor-relative no-follow APIs. Unsupported
platforms fail closed, without an unsafe path-based fallback. No third-party
package is required. The separately scoped agent-factory-3 bridge has its own
source, dependency and review boundary; it is not imported here.

## Interpretation and safety

Missing scoring remains `null`, not zero. PUBLIC keeps167 queries and expects120
tasks; compact reports cannot establish the task inventory. Dev count/tie
consistency cannot prove selection chronology or the whole shared case universe.
Pairwise counts stay conditional. B/C matching uses whole synchronized extra
model-phase wall, including failed work, rollback and persistence.

`analysis_authenticated`, `method_efficacy_established` and `dispatch_authorized`
are always false. A caller-provided hash establishes no external authenticity.
`OFFLINE_OUTPUT_WRITTEN` / exit0 means only that a file was written; inspect
`analysis_structurally_consistent`, issue codes and nullable fields.

No-follow directory descriptors prevent ancestor replacement from redirecting
reads/writes. Private staging and exclusive publication refuse overwrite;
cleanup is descriptor-relative. A failure after the exclusive link may leave a
complete output in the original directory: inspect before retrying. The tool
will not unlink a published name or foreign staging entries merely because a
later check failed. Same-UID hostile mutation, SIGKILL/power loss and namespace
changes after the final observation cannot be absolutely excluded by userspace
checks. If staging creation succeeds but its inode cannot be established, an empty
private directory may also remain; deleting an unbound name would be unsafe.
Do not equate a rejection with proof that no output exists.

## Handoff and checks

See [local executor handoff](../../research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md)
and [independent review](../../research/arc2-sft-rl-continuation-20261014/offline-continuation-review.md).
Run focused tests from the repository root:

```sh
python3 -B -m unittest discover -s tools/arc2_sft_rl_continuation_20261014/tests -v
python3 -B -O -m unittest discover -s tools/arc2_sft_rl_continuation_20261014/tests -v
```

The original `0451441` checkpoint was incomplete and contained a reproduced
output-parent race. Final review supersedes that paused-work note only for this
offline companion. No GPU execution, full consumer success-path replay, new ARC
score or Kaggle publication is established. Repository CI and missing historical
fixtures are reported separately, not waived by focused tests.
