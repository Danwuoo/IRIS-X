# Main worktree integration and synchronization

Date: 2026-10-03, Asia/Taipei. The owner requested consolidating the existing
worktrees into main, committing and pushing, followed by a storage audit
without cleaning files.

## Verified integration

Main before this record: `30e9dfab86db475a7e62ddd97c770ae97aa959a0`.
Both worktrees have clean tracked/untracked Git status. Their complete commit
histories are already ancestors of main; the explicit merge commands both
returned `Already up to date.`

| Worktree | Exact head | Existing integration commit |
| --- | --- | --- |
| `C:/Users/wurre/.codex/worktrees/51fa/IRIS-X` | `00db35dfb27f5b609d3edf28973df58da6950fe3` | `f30baa897e9fb04ec13c2f7d9f862d4dc17d5dfd` |
| `C:/Users/wurre/.codex/worktrees/c1e4/IRIS-X` | `26742abf9a0f705fa14f62cb5188b557661d5883` | `a8a85eac3526b9d802fd5054bcf964a2cf29ee0e` |

After fetching origin, main is 73 commits ahead and zero commits behind
`origin/main` at `60be683`. This record is an additional documentation commit
for the requested fast-forward synchronization; it changes no solver, method,
execution authority, frozen material or historical observation.

## Local retention

Ignored files do not enter a Git merge or push. The two worktrees retain
approximately 27.9 MiB and 15.8 MiB of ignored material respectively, including
source Git repositories and offline fixtures. Nine c1e4 trial settings differ
from their present main-path counterparts. Preserve these versions separately
before any future worktree removal; do not overwrite current trial settings.

The owner requested inspection only for duplicate or obsolete model caches.
No worktree, branch, model, source material, result, receipt or cache is deleted
by this integration. Existing hardlink deduplication must be accounted for
before estimating reclaimable storage. Audit outputs stay ignored under
`.irisx/`; they are not new scientific or execution authority.

## Validation observation

The immediately preceding full offline validation discovered 386 tests,
with one failure and four optional skips. The failure was the `pre-ready-fail`
subcase of `CombinedProcessTests.test_failure_before_ready_during_work_and_artifact_failures_keep_sibling`:
the aggregate outcome was `failed` instead of `partial`. Its isolated rerun
passed. Repository invariants and diff whitespace passed. Retain the full-suite
failure and isolated pass as separate observations; this record does not claim
a fully passing suite or a diagnosed root cause.
