# WSF-R1–R4 corrective increment

Owner scope, 2026-10-14: implement only the four defects reported in the
independent reviews of PRs 6–8. Preserve the accepted architecture direction,
research questions, existing outputs, source pins and previous receipts.

Base: `refactor/workstream-pr4-arc-boundary` at
`c514e9d5b3c438b70c90824ec1fd2796aa840740`.
Head: `fix/workstream-review-r1-r4-20261014`. One new Draft PR against PR4;
no rewriting earlier branches, merge, main/run008 push, force push or tag move.

## Checks and implementation scope

- WSF-R1: effective review selection, explicit source coverage and current
  dependency acceptance must reject stale/superseded positive reviews and
  pending upstream tasks. Historical approval remains attributable to its
  original commit. Metadata-only delivery and unrelated-line changes remain
  valid positive controls. Use synthetic Git repositories, normal and `-O`.
- WSF-R2: commit-bound suite evidence must identify the actually executed
  committed source, inventory and runner, isolated from caller edits. Dirty
  iteration is explicitly non-attestable. Detect staged/unstaged/untracked
  source/input changes and mutations during testing; legitimate ignored
  outputs remain allowed. Preserve failure/blocked reporting.
- WSF-R3: inventory declares validated repository-relative owning package
  roots and module identity. Per-file processes admit only that snapshot;
  reject escaped/linked roots and ambiguous packages. Constant-only synthetic
  snapshots prove loading/isolation; original snapshot sources remain unchanged.
- WSF-R4: gate derives required modules and skip policy independently from
  the target commit's inventory Git object. Reject omission, substitution,
  additional/duplicate modules, mixed inventory and non-attestable evidence,
  even when report-selected paths and totals agree with each other.

Targeted public suites and formal non-editable distribution are regression
checks. Do not run the legacy aggregate, historical reconstruction suites,
training, providers or model/evaluator inputs. Preserve their previous failures;
clearing historical audit errors is not a completion condition for this repair.
Necessary caller/schema integration stays within these four tool fixes.

## Review and delivery

The original independent outcome is `changes_requested`, with source review,
bounded executable reproductions and attributed CI readback. It did not
independently rerun the full project tests, wheel or onboarding locally.
Register those three sourced reviews and mark the affected tasks accordingly;
do not manufacture approval or erase earlier scope failures.

Commit implementation first, run commit-bound checks, then append a compact
machine-readable report and handoff. The repair stops at `review_ready`; original
ChatGPT supplies any subsequent commit-bound independent result. Preserve the
earlier SGD violation and no-training limitations. No watcher or retry loop.
