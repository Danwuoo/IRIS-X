# WSF-04 bounded ARC migration map

Stage base: `756cd560f8d61256ed35e12c3c3637ec456c6141`
(`refactor/workstream-pr3-validation`). Working branch:
`refactor/workstream-pr4-arc-boundary`. Foundation:
`08b1cee49b0c677ec9ca8bfdf76e5e4f16b26059`. Separate run008 source:
`cc14bd1a79aac1fe6135017c9e09d4834300675d`.

The [machine-readable map](MIGRATION.json) is a developer/subagent source audit.
Its `target_code_commit` is initially null; the root integration owner binds it
to the tested implementation checkpoint before delivery. Task state and the
handoff route belong to [WSF-04](../../management/tasks/WSF-04.json), with
independent review pending. No report must contain its own delivery SHA.

## Permitted extraction and retained implementations

Only current ARC parser registration and selected-command dispatch move to
`src/irisx/domains/arc_agi_2/cli.py`. Shared `irisx.cli:main`, `build_parser`,
`execute` and `_path` retain their public names and behavior. Shared CLI supplies
its path converter and repository root explicitly; the deeper facade must not
derive a different root from its own `__file__`.

The facade is the single mutable ARC entrance and calls the original legacy
modules. It does not contain another solver implementation. Shared contracts,
engine and package modules do not import either domain; ARC and line-b do not
import each other. The shared router → parser-only facade and ARC facade →
listed legacy implementation are explicit dependency exceptions.

| Row | Original location / consumers | Target and permitted change | Required check / rollback |
| --- | --- | --- | --- |
| 1 | `src/irisx/cli.py` ARC registration; `__main__.py`, console entry, admission/reference/import-boundary tests | Facade `register_parser`; shared `build_parser` stays; pass the original `_path` converter | Full parser/help/option comparison, normal/optimized import blockers, installed ARC help; revert only the new unmerged boundary commit |
| 2 | `src/irisx/cli.py` ARC execution branches; source/model/trial/result/package/baseline commands and distribution harness | Facade `execute`; shared CLI routes selected commands and passes the original repository root | Mock every dispatcher with synthetic paths, assert outbound-build root, preserve exit 2/error semantics, direction negatives; revert the dispatch commit only |
| 3 | `src/irisx/arc_agi2.py`; ARC unit tests and `arc_trial_002.py` | Same path and blob; facade dependency exception | Git equality against foundation/run008 and public ARC CPU tests; no move to undo |
| 4 | `src/irisx/arc_package.py`; package commands, runner's sibling-path use | Same path and blob; retain its `__file__` sibling-path mechanism | Git equality and synthetic package verification; retain the original path on rollback |
| 5 | `src/irisx/arc_trial_002.py`; trial tests, trial002 runner, outbound core/wheel membership | Same path and blob; retain exact runtime/core and wheel paths | Git equality and synthetic trial controls; no source/manifest rewrite |
| 6 | `src/irisx/kaggle.py`; handoff/checkpoint/benchmark tests and exact v3/v4/v5 runner paths | Same path and blob; facade dependency exception | Git equality and synthetic CPU transport checks; no provider execution on rollback |
| 7 | All other existing `src/irisx/arc*.py` and `kaggle_runner*.py`; notebooks, run assemblies, archival/pickle consumers | Retain every legacy solver/helper at the old path | Whole protected source inventory; unproved consumers remain a limit; no migration or compatibility shim |
| 8 | `tools/irisx_build_backend.py`, `pyproject.toml`; pip/install, distribution tests and repository checks | Retain PR2 nested collector, resource allowlist and `irisx.cli:main`; collect the new facade normally | Reproducible wheel/RECORD, external non-editable install, facade membership and resource exclusions; revert new facade only |

No additional helper is proved mutable with authentic reconstruction inputs
absent. This is an intentional partial isolation, not completed runtime
migration. Original notebook/scorer/manifest/review/archive files are neither
reformatted nor rehashed to accommodate it. Rollback uses a new revert commit
on this development stack; it never resets a published branch, moves a tag or
restarts an experiment.

## Exact source/path pins

| Source | Foundation and fixed run008 blob | Stage-base blob |
| --- | --- | --- |
| `src/irisx/cli.py` | `9870f93591f0afbf9009741953987a61fbae7530` | `771c23b73ae94ae0e18a1ca6eb7d24808a651a7f` (PR2 lazy-import change) |
| `src/irisx/arc_agi2.py` | `a15f79e31bb60ae981e094a27d3e204d2abbc20f` | Same |
| `src/irisx/arc_package.py` | `2c451e4a18979a2d273b07bd7999ce02aba0c6eb` | Same |
| `src/irisx/arc_trial_002.py` | `e2c7ecc12ef6d77734175aad0b7526ceb882d5f1` | Same |
| `src/irisx/kaggle.py` | `10e58c101da0af3d7a725b0b0737ba114a316f1a` | Same |

The existing paths for `irisx.cli:main`, `src/irisx/cli.py`, runner/core wheel
members and `licenses/NeMo-RL-LICENSE.txt` stay fixed. Only the explicitly mutable
CLI glue changes source identity. Git equality of the other blobs is source
preservation evidence, not execution qualification.

The prepared proposal's source scan is bound to the provisional PR3 code
checkpoint `411ed472358391d568d52c48f90211085d2238b2`, before its final handoff.
It reports 1,357 Python paths, 51 notebook code-source paths and 67
source-manifest/inventory paths. The map retains the exact reported matches and
limits; stage-base CLI and retained tree pins were checked against the final
PR3 delivery above.

The scan considered ordinary imports, string/dynamic imports, notebook source,
`inspect.getsource`, relative `__file__`, subprocess references, wheel/manifest
paths, pickle/module identities and monkeypatch consumers. Observed notebook
tokens still point at `irisx.kaggle_runner_trial002`,
`irisx.kaggle_runner_prompt_pilot` and `irisx.arc_nvarc_kaggle`. No observed
direct CLI notebook/manifest/getsource/pickle match authorizes moving legacy
source. Static scans cannot establish absence of every dynamic or archived
consumer. No authentic archive, private owner/readback or evaluator body was
read for this map.

## Fixed run008 retention, references and unverified scope

All paths in the next tables are below `tools/arc_qwen_rlvr004_20261013/`.
The listed retained tree IDs match foundation, stage base and fixed run008.
The run008-only table supplies Git object/path metadata and commit-pinned
references; those paths are not imported into this branch.

| Retained path | Equal Git tree ID |
| --- | --- |
| `source` | `562cea83bce003142618d2e82a039dfc715eebc3` |
| `release` | `07bb5b5b66715a286f7330d8dd2549da26be82c5` |
| `support` | `ba9fb2fae1079d2424a8bddee41249ff03b9d5d9` |
| `driver_path_repair` | `e4a182e28169c8322a03972c0031feb3b6d28bfb` |
| `local_tests` | `b59f5807382053c8993b4fd9da4610c32f696b62` |
| `publication` | `a414353cff6c7aed8684ade82a390f08b7cdc4f5` |
| `publication_local` | `6378a37bac278df2689ede064b66fb05f6e43029` |
| `publication_run005` | `df24265c0cb3abe9d4b1b42a51aef1f390dc7a06` |

| Reference-only run008 path | Fixed run008 tree ID |
| --- | --- |
| `admission_run008` | `c84a292b755258ddad7e31614b715eea43b260c7` |
| `loader_repair_run008` | `597c6093619bfd06e16e6800a2d11af3f2b6dae0` |
| `run008_successor` | `b77cb0ec3fa8b37abf8f9cb350982ceaa00d2b05` |
| `publication_run008` | `d49d5d0af9dc4543e41f61740cca6c5cb73fcc56` |
| `review_run008` | `cd7f8f14fb0c515a90a5276d3b6c35254c942905` |
| `transfer_run008` | `0022be3cbb6934c57650fc8f25a8f0db97cf661b` |
| `transfer_handoff_20261014` | `5dc6472ca9241d6e204c255a40845cf12e78f83d` |
| `preparation_successor` | `3b5dd9bbee9d6c43395ff6474d1260ea0af5279c` |
| `preparation_diagnostics_repair` | `2a53766b7337a841f8094833d940cabbaaa4da68` |
| `cudnn_mapping_repair` | `cbf82999df5748a2a07183b38b536f77abfaf83d` |
| `installer_logging_repair` | `7e80970ee12e48a1fece32da1d35c91e4f5a5618` |
| `publication_run006` | `6ea679237176f0d9f33cbf354d07df32570bba3c` |
| `publication_run007` | `f75d9e2385c99f446615a32d9552996c3d2140cf` |
| `recovery_records` | `f93bda0e1f272425977477554ce7573c8054b1b5` |

Use the fixed [run008 tool tree](https://github.com/Danwuoo/IRIS-X/tree/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013)
and its [handoff](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/native-continuation-20261013/RUN008-LOCAL-HANDOFF.md)
as reference entrances. Local Git object availability does not attest remote
content, provider state, private review truth or archive availability.

| Unverified item | Why it remains separate |
| --- | --- |
| Authentic source/package reconstruction | Original private owner/receipt/archival inputs were not obtained or fabricated |
| Linux CPython 3.12 numerical replay | Windows public CPU tests do not reproduce the original runtime conditions |
| Full 14B/cuDNN/GPU workload and four-L4 deployment | No model, GPU, training or target-topology execution occurs |
| Current provider/source/readback/Drive state | Only fixed Git metadata and attributed historical reports are used |
| PUBLIC120 method efficacy | No new sealed predictions, scoring or successful baseline exists |
| Final PR4 checks and independent acceptance | Bound by the root handoff and later independent target-commit review |

## Research reading exercise and continuation

Follow [ARC STATUS](../../workstreams/arc-agi-2/STATUS.md) →
[RESEARCH](../../workstreams/arc-agi-2/RESEARCH.md) → the individually cataloged
R1–R5 sources and original result reports. R1 synthesizes historical experiments,
R2 evaluates representation/program/feedback directions, R3 preregisters the
portfolio panel, R4 assesses methods and R5 fixes the current experiment.
Their original contents and lifecycle roles are preserved; this map supplies no
new research question or replacement experiment.

Keep architecture A/B/C (direct-grid/program/feedback repair) separate from
training A/B/C (saved/reloaded SFT256/bounded disjoint RL/wall-matched extra SFT).
Keep modified-input BASE/TTT 5/172 → 10/172, exposed uncapped 1/6 and seen-family
portfolio observations separate from canonical PUBLIC120 120-task/167-query
scoring. Retrospective 6/6 does not become prospective confirmation. Missing
run008 score is neither a zero score nor evidence that RL has failed.

R4/R5 retain conditional next steps for environment/numerical failure, complete
zero-signal audit, valid A/B/C gains/losses, missing candidate coverage and
selection gap. The question remains unanswered and no condition authorizes a
run here. The current policy's SFT256/batched design is not replaced by the
earlier SFT64/full-sweep draft. Existing failures, denominators, clocks, charges,
prediction sealing and evaluator isolation retain their original meaning.
