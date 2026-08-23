# AGENTS.md

## Scope

This file applies to the entire repository. It defines repository and Codex Work mode behavior only. Empirical project state belongs in `docs/current/PROJECT-STATE.md`; do not move branch, commit, blob, pull-request, or short-lived integration status into that file.

## Required startup sequence

1. Read `docs/current/PROJECT-STATE.md` first.
2. Use its **Task-to-source routing** table to load only the minimum required current sources.
3. Inspect the target files and `git status` before editing.
4. Do not read all research and archive files by default.
5. If a source named by `PROJECT-STATE.md` is unavailable in the checkout, mark it `Unavailable in checkout`; do not replace it with an archive file, external memory, or an inferred answer.

## Document roles

- `docs/current/`: current project definition, evidence records, adjudication, and state artifacts.
- `docs/research/`: research inputs and prior synthesis. These can support provenance but do not directly change current adjudication.
- `docs/archive/`: superseded and historical material. Use only for decision history, earlier assumptions, engineering lessons, and failure cases.
- Root `AGENTS.md`: repository operating instructions for agents.

Repository presence does not establish empirical authority. A file in `docs/archive/` cannot override a current artifact, and a newly added research report cannot change a claim status until the evidence and adjudication workflow is completed.

## Authority and source routing

Use the latest current or explicitly accepted version for each role:

1. Research problem, scope, terminology, and extrapolation rules: current Problem Definition.
2. Claim, counterexample, contradiction, boundary-condition, and gap status: current Evidence Adjudication and Decision Log.
3. Record-level IDs, provenance, benchmark metadata, and verification detail: current Evidence Base.
4. Domain evaluation metrics, data governance, run requirements, stage gates, and SOTA taxonomy: current domain evaluation definition.
5. Specific experiment interpretation: preregistration, run manifest, evaluator output, decision record, and formal experiment report.
6. Historical and Vanta material: historical context only.

When sources conflict, do not silently reconcile them. Record the conflict and follow the authority rules in `PROJECT-STATE.md`.

## Mandatory analytical classifications

Before interpreting or writing any result, comparison, or superiority claim, identify:

### Evaluation unit

- `G`: generalist baseline
- `M`: model specialist
- `S`: system specialist
- `H`: hybrid specialist
- `N`: narrow / formal / verifier-bound solver

Do not attribute gains from tools, retrieval, search, verification, memory, context, routing, scaffolds, or environment access to specialized weights.

### Advantage type

Keep these separate:

- same-backbone relative gain
- contemporary absolute superiority
- persistent superiority
- configuration-level superiority
- cost / efficiency advantage

One does not imply another.

### Capability construct

Keep these separate:

- benchmark proxy
- broad domain capability
- professional workflow capability
- formalized / bounded task capability

A benchmark score alone does not establish full domain or professional capability.

### Generalization status

Report separately:

- held-out task
- out-of-distribution
- temporal shift
- cross-version transfer
- independent replication

Do not infer external generalization from task count inside one benchmark.

## Evidence discipline

- Preserve document terminology, IDs, classifications, and uncertainty labels.
- Use `Unknown`, `TBD`, `Indeterminate`, `Not evaluated`, or `Source does not support` when required.
- Do not turn an unresolved gap into a premise.
- Do not describe a plausible explanation as an empirically resolved contradiction.
- Do not describe a candidate mechanism as an established cause without discriminating evidence.
- Do not combine model-level, system-level, hybrid, and formal-solver outcomes into one count.
- Do not use leaderboard rank to infer the intrinsic superiority of general-purpose learning.
- Every counterexample must state the exact proposition it refutes and the propositions it does not refute.
- ARC-only findings must not be generalized to cross-domain scaling laws, broad professional capability, AGI, or general capability without separate evidence.

## Editing current project documents

- Make the smallest change that satisfies the task.
- Do not overwrite historical versions.
- Major changes require a new version and a change record covering:
  - what changed
  - evidence basis
  - affected claims, records, and decisions
  - old and new status
  - downstream impact
  - confidence
  - reversible-if condition
- A lower-level experiment or report must not silently rewrite a higher-level document.
- If new experimental evidence challenges the Problem Definition, update the Evidence Base and adjudication/decision records first, then propose a Problem Definition revision.
- Do not change empirical claim status only in `PROJECT-STATE.md`.
- Keep repository workflow details in `AGENTS.md`, not in `PROJECT-STATE.md`.
- Do not add branch names, commit SHAs, blob hashes, or temporary integration status to `PROJECT-STATE.md` unless the task is an explicit point-in-time repository audit.

## Spreadsheet and binary artifacts

- Do not edit `.xlsx` files as text.
- Use a spreadsheet-aware tool and preserve formulas, sheet names, IDs, formatting, data validation, and workbook structure.
- Inspect the relevant sheet/range only; do not reconstruct an evidence workbook from Markdown summaries.
- For any workbook write, validate that record IDs remain unique and that formulas/references still resolve.

## Work mode procedure

1. Confirm the requested scope from the issue, prompt, or task.
2. Inspect the current branch, working tree, and relevant files.
3. Create or use a focused branch. When starting from the default branch, use `agent/<short-description>`.
4. Edit only files required for the task. Do not include unrelated user changes.
5. Validate the result:
   - Markdown structure and links
   - referenced paths
   - version and change-log consistency
   - no unsupported empirical-status changes
   - relevant tests, linters, or document checks when available
6. Review the final diff before committing.
7. Use a terse commit message that describes the complete change.
8. Push the branch and open a **draft pull request** unless the user explicitly requests ready-for-review.

## Pull request requirements

The PR body must state:

- what changed
- why it changed
- authoritative documents and versions used
- which statements are source-stated versus inferred
- empirical claim or stage-status impact, including “none” when applicable
- unresolved evidence or unavailable sources that could change the result
- validation performed

For documentation-governance PRs, explicitly confirm whether the change alters any claim adjudication, ARC stage status, or winning hypothesis. Do not imply that it does when it only changes repository instructions or document routing.

## Stop and report instead of guessing

Stop the affected part of the task and report the blocker when:

- a required authoritative artifact is unavailable
- an exact comparator, model snapshot, evaluator version, or resource budget is missing for a frontier claim
- a write would overwrite history or bypass the evidence/adjudication sequence
- repository changes are mixed with unrelated work and scope cannot be isolated
- a binary evidence artifact cannot be edited safely with available tools

Partial completion with explicit uncertainty is preferable to fabricated completion.
