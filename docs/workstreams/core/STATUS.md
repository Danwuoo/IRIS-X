# Core STATUS

Updated: 2026-10-18. Workstream: `core`.
Task state: [generated board](../../management/BOARD.md).
Document lifecycle: [catalog](../../management/documents.json).

## Branch register

`develop` is the **only active shared engineering baseline**. Its source parent
is `5190def7ccefba964a4e5cbf55e59743ae37d033` (PR9 R5 delivery; code
`41c5c164c255e4fd6df57bc60ccde480072b1a3e`). Creating this baseline preserves
history; it is not a squash, merge into main, independent acceptance or release.
The consolidation changes only current branch routing and the two inherited
workflow stop conditions. Product/runtime/test/research bytes are retained.

| Keep | Role / observed anchor on 2026-10-18 |
| --- | --- |
| `develop` | Shared contracts, packaging, CLI, documentation/task management and validation; future math-line base |
| `feat/arc2-sft-rl-continuation-20261014` | Active ARC research; observed `5badc221ef40f1b8b3924668841119c049dffc1f`; do not change its ref or assume it contains this engineering tree |
| `main` | Existing default branch, unchanged at `baaf47d4f449c534ddd4646ab9b3175bbaf1ef89`; not the new development baseline |
| `feat/run006-local-recovery-20261013` | Historical research/recovery source, `5eae9b2bf45e07a561150528847d15fa016605c7`; not a common engineering line |
| `feat/run007-local-repair-20261013` | Historical research/recovery source, `2901a97a1aa934d15e468e3e6d57bd96d95791e9`; not a common engineering line |
| `feat/run008-native-research-20261013` | Fixed research source, `cc14bd1a79aac1fe6135017c9e09d4834300675d`; preserve all pinned references |

The following engineering branch names are redundant, not worthless source.
Remote comparisons establish their recorded tips are ancestors of the retained
PR9 delivery. No cherry-pick or merge is needed to collect their commits.

| Eligible retired ref | Exact recorded head | Historical PR |
| --- | --- | --- |
| `chore/workstream-foundation-20261014` | `08b1cee49b0c677ec9ca8bfdf76e5e4f16b26059` | #5 |
| `refactor/workstream-pr2-packaging` | `2e706a5a4e4afb67f64517e4ee174584dcb06e18` | #6 |
| `refactor/workstream-pr3-validation` | `756cd560f8d61256ed35e12c3c3637ec456c6141` | #7 |
| `refactor/workstream-pr4-arc-boundary` | `c514e9d5b3c438b70c90824ec1fd2796aa840740` | #8 |
| `fix/workstream-review-r1-r4-20261014` | `5190def7ccefba964a4e5cbf55e59743ae37d033` | #9 |

Retirement procedure: publish and read back `develop` first; close superseded
PRs #5–9 without merging, preserving comments/reviews and linking this register;
then re-read each ref, prove its exact tip is contained in `develop`, ensure no
open PR uses it as head/base, and delete only the recorded ref with an expected-SHA
lease. If it advanced, stop and review its new commits. Do not delete a local
branch/worktree or modify uncommitted files. This register is a policy/inventory,
not a receipt claiming remote deletion already occurred. A separate live readback
must establish cleanup completion. Historical PR/task fields remain unchanged.

Existing WSF states/reviews are retained. In particular, R5 developer delivery
is still subject to independent re-verification; branch consolidation cannot
change `review_ready` to `verified`. Old CI successes are not new-head results.
The two legacy/audit jobs remain explicit BLOCKED/non-success before checkout
and test import on this shared baseline and its descendants, without depending
on a temporary branch name. The public matrix, gate and formal distribution
commands remain intact. Future authorized audit/training requires a distinct,
reviewed scope change, not merely a new branch name.

## Scope

Shared P1 contracts, canonical serialization, deterministic reference evaluation,
selection, Domain Package verification, packaging, CLI routing and repository
management/validation tools. The stacked increments add reproducible nested
wheels, lazy domain execution, controlled test selection and an independent
synthetic line-b flow. WSF-04 extracts mutable ARC parser/dispatch glue while
retaining the legacy implementations at their original paths.

The [migration map](../../verification/WSF-04/MIGRATION.md) supplies the bounded
source scope and dependency exceptions. Follow the board's task record to the
plan, code checkpoint and handoff; STATUS does not duplicate task progress.

## Evidence

The independent [PR6](https://github.com/Danwuoo/IRIS-X/pull/6#pullrequestreview-5515478962),
[PR7](https://github.com/Danwuoo/IRIS-X/pull/7#pullrequestreview-5515483789), and
[PR8](https://github.com/Danwuoo/IRIS-X/pull/8#pullrequestreview-5515492879) reviews
request changes to review freshness, executed-source identity, snapshot package
loading and authoritative gate completeness. Their scope is source review,
constant-only synthetic reproductions and remote CI readback, with no independent
local rerun of the whole project/wheel/onboarding. Original review targets and
receipts remain unchanged; task records link the sourced negative outcomes.

The PR8 review read [workstream run 38527215623](https://github.com/Danwuoo/IRIS-X/actions/runs/38527215623):
28 public-suite jobs, four formal-distribution jobs and the fixed gate passed.
Navigation run 38527215613 passed; arc-public-audit and offline-validation run
38527215654 failed. Its ARC audit artifact records 2,705 tests, 15 failures,
115 errors and 87 unexpected skips at synthetic merge commit
`034f9224a3bc3138923059a1bf0f8c8aa1bd4f7b` on Linux/Python3.14.8.
This attributed reviewer readback is separate from developer local aggregate
counts, and does not make the four demonstrated defects acceptable.

The later [PR9 independent review](https://github.com/Danwuoo/IRIS-X/pull/9#pullrequestreview-5517762334)
targets code `15c1209c88ee54738595b92cf9d35c2f0d4a3177` and delivery
`1a08648603e1af2fe66998a0e53b11d02abf5c6b`. Its exact-helper constant-only
Linux/CPython3.13.5 regressions pass 31 tests normally and the same 31 under -O.
R1–R4 are corrected within that independently tested scope; the new blocker is
WSF-R5, where -I ignores the declared startup seed. This changes_requested
outcome does not retrospectively approve the earlier PR6–8 implementation SHAs.
The sourced [review record](../../verification/WSF-R5/independent-review.json)
also attributes 28 public jobs, four formal jobs and gate/navigation passing in
PR9's prior remote CI. Audit/aggregate stopped before import as BLOCKED/non-success,
and full local project/wheel/onboarding independent reruns remain unavailable.

The synchronized foundation is `08b1cee49b0c677ec9ca8bfdf76e5e4f16b26059`,
descended from the main comparison anchor
`baaf47d4f449c534ddd4646ab9b3175bbaf1ef89`. PR 4 starts from PR 3 delivery
`756cd560f8d61256ed35e12c3c3637ec456c6141`. These identify engineering source,
not scientific or operational baselines.

The [WSF-02 handoff](../../verification/WSF-02/HANDOFF.md) binds nested wheel,
external-cwd non-editable installation, public CLI/import boundaries and
management self-tests to its code checkpoint. The
[WSF-03 handoff](../../verification/WSF-03/HANDOFF.md) binds inventory/runner/CI
gate and synthetic line-b evidence to its own checkpoint. Both reports retain
raw-log fingerprints, exact counts and matched baseline limitations. Their
developer/subagent checks await independent acceptance.

The WSF-04 map retains source/blob comparisons against both foundation and fixed
run008 `cc14bd1a79aac1fe6135017c9e09d4834300675d`. Its final code/report binding
is supplied by the root integration owner's task handoff. Git equality proves
source preservation only; it does not establish reconstruction or runtime parity.

Historical foundation [navigation CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38503686348)
passed. Its completed
[Ubuntu / Python 3.14 aggregate job](https://github.com/Danwuoo/IRIS-X/actions/runs/38503686421/job/115656185090)
reported 1,588 tests, 5 failures, 96 errors and 110 skips; other jobs were
cancelled. It checked synthetic merge commit
`b5d7e10d90bda1e80a3b0971f64ee7f688befafa`, without merging main. Stage-specific
local aggregates remain separately recorded in the handoffs; full CI is not green.

## Blockers

Independent acceptance remains changes_requested. The earlier bounded remote
matrix passed, while its audit jobs failed. Broader ARC/public and legacy audits retain collection,
dependency, platform, missing-input and assertion failures. Attribution needs
matched test IDs/signatures; unmatched observations stay unclassified.

Authentic reconstruction inputs, original Linux/CPython 3.12 replay and GPU
compatibility are outside this engineering task. No other legacy helper is
proved movable under those absent inputs; retention is intentional.

## Next

New shared engineering work uses `develop` and short-lived task branches based
on its exact commit; new Draft PRs target `develop`, never old stack branches.
Continue the independent [WSF-R5](../../management/tasks/WSF-R5.json) review using
its fixed code and [handoff](../../verification/WSF-R5/HANDOFF.md), not an assumed
PASS caused by retiring PR9. Retain [WSF-R1-R4](../../management/tasks/WSF-R1-R4.json)
and all historical reviews, denials and code/delivery identities. The
[small startup plan](../../plan/2026-10-14-workstream-review-r5.md) describes the
original implementation scope; its old branch instruction is historical.
Run only the controlled public/synthetic checks described in
[tests/README](../../../tests/README.md). Preserve previous aggregate receipts
without rerunning unrestricted aggregate/import-time workloads. Return actual branch/code/delivery/PR identities to
the original ChatGPT conversation. Task state stays at `review_ready` until
that conversation supplies independent verification. No merge follows.

## Boundaries

Adopted contracts, admission/promotion semantics and frozen experiments retain
their bytes and identities. Common implementations remain single-sourced;
core contracts/engine/package do not import ARC or line-b implementations.
Shared CLI's explicit parser/dispatch routing is recorded in the migration map.
No run008 branch change, archive/model/evaluator download, training, Kaggle call,
GPU work, main push or tag move is part of this task. Scoped checks are not
full CI, real-domain capability or scientific success.
