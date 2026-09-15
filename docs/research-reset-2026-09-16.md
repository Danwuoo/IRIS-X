# Research Reset — 2026-09-16

## Scope

This record documents a repository cleanup and research reset, not a new
research task. The reset selects no thesis, architecture, training strategy,
runtime, provider/model, product boundary, or follow-on experiment.

## Recovery reference

- Starting branch: `main`
- Starting commit: `adc5524c9a3ffa499b84e996d044355ba5b4e6a9`
- Recoverable annotated tag: `archive/pre-research-reset-2026-09-16`
- Tag target after peeling: `adc5524c9a3ffa499b84e996d044355ba5b4e6a9`

The tag was created before repository files were changed.

## Classification and preservation

- `sources/`, `references/`, and `corpus/` were classified as preserved source,
  reference, and provenance material. Their tracked contents were unchanged.
- Completed experiment packages, raw records, manifests, hashes, terminal
  records, results, and failure artifacts were classified as preserved empirical
  evidence. Their tracked contents and paths were unchanged.
- The D1a package was classified as a historical, unexecuted
  qualification-development and operational package, not empirical D1 evidence.
- Pre-reset `research/` files were classified as historical interpretations,
  hypotheses, specifications, protocols, decisions, syntheses, or readiness
  material. Their contents and paths were preserved.
- Phase handoffs, state/closure documents, launch/relaunch records, failure
  reports, and all pre-reset `docs/plans/` files were classified as historical
  operational records.
- `tools/` was split by documentation into reusable repository/provenance tools
  and historical research-specific helpers.
- `irisx/` was classified as a preserved Phase 5 prototype required by
  historical tests and substrates, not a current implementation architecture.

## Changes made

The active surface was reset through governance and navigation rather than by
rewriting or physically relocating evidence-sensitive history:

- root `AGENTS.md` was replaced with neutral repository governance;
- root `README.md` was replaced with a concise neutral orientation;
- current indexes were added for `docs/`, historical operational records,
  decisions, historical plans, experiments, research lineage, and `irisx/`;
- `research/AGENTS.md`, `experiments/AGENTS.md`, `docs/maintenance.md`,
  `docs/repository-layout.md`, and `tools/README.md` were updated to reflect the
  reset boundary;
- no tracked files were moved or deleted;
- no experiment record, imported source, paper, corpus registry, research
  conclusion, historical handoff, historical plan, tool implementation, or
  prototype implementation was edited.

Physical archival moves were intentionally avoided. Exact paths are referenced
by historical manifests, artifact hashes, preservation tests, validators, and
evidence ledgers. Moving those records would either reduce reproducibility or
require rewriting preserved scientific/operational records. The new indexes
provide archival grouping while retaining those identities.

Ignored Python cache directories were identified under authored areas. An
attempted scoped removal was rejected by the local destructive-operation guard
before execution. They remain untracked and excluded by `.gitignore`; no
tracked repository artifact depends on them.

## Active assumptions retired

The reset retires the following from automatic current authority without
changing their historical records:

- the foundational synthesis as a controlling project thesis;
- F1, D1, D1a, Phase 7, and every other prior phase or follow-on program;
- prior warranted-agency, configuration-sufficiency,
  failure-directed-intervention, lifecycle-cost, specialization, training,
  verification, provenance, authority, and stateful-reliability formulations as
  default requirements;
- the Phase 5 candidate architecture and `irisx/` prototype as the active
  implementation direction;
- the prior OpenAI/Codex provider/model baseline as current operating policy;
- all pre-reset launch, relaunch, collection, remediation, and temporary-plan
  authority.

No replacement thesis or preferred direction was adopted.

## Checks updated

No validator, test, experiment definition, manifest, or evidence-integrity check
was changed. Only governance, navigation, classification, and maintenance prose
was updated. Existing path-sensitive records were left in place so checks did
not need scientific-content rewrites.

## Validation

Final commands and outcomes:

- `python tools\repository_check.py --self-test` — PASS.
- `python tools\repository_check.py` — PASS: 13 registered sources, 7
  registered artifacts, hashes checked, authored links valid.
- `python tools\migration_audit.py` — PASS: 13 preserved source trees and 7
  preserved artifacts.
- `python -m unittest discover -s irisx\core\tests -v` — PASS: 28 tests.
- Per-directory `unittest` discovery across all 21 test directories under
  `experiments/` and `irisx/` — 317 of 318 tests passed. The only failure is
  the pre-existing
  `HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes` mismatch for
  `docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`: observed
  SHA-256 `4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b`,
  frozen expected SHA-256
  `9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`.
  The plan is unchanged from the pre-reset tag, and neither the plan nor frozen
  record was modified to mask the historical mismatch.
- `python tools\validate_pre_synthesis_readiness.py` — expected historical
  incompatibility: FAIL because its frozen baseline protects the old root,
  research, and experiment governance files and the pre-reset `experiments/`
  tree. The historical baseline was not rewritten. Scientific truth and
  formulation merit were not evaluated by that validator.
- `git diff --check` — PASS.
- Diff checks against `archive/pre-research-reset-2026-09-16^{}` — PASS: no
  tracked changes under `sources/`, `references/`, or `corpus/`; no experiment
  package/evidence changes beyond the zone-level `experiments/AGENTS.md` and
  `experiments/README.md`; no historical research or prototype implementation
  changes.
- Targeted stale-authority search over current entry points and indexes — PASS:
  matches concerning prior phases, syntheses, F1/D1, architecture, or model
  baselines occur only in explicit historical classifications or statements
  denying current authority.
- Final Git worktree — PASS: clean after the reset commit.

## Unresolved cleanup questions

- Historical files retain their original paths and original status language for
  provenance. A future owner may authorize a path migration, but only with a
  deliberate compatibility and evidence-identity plan.
- The repository retains ignored local Python caches. They are generated noise,
  not tracked repository content.
- Whether any historical prototype or substrate should be re-adopted, retired,
  or extracted as reusable infrastructure is intentionally unresolved.
