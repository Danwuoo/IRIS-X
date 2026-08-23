# Temporary Phase 2 Repository Organization Plan

Status: **Temporary implementation plan**  
Scope: Repository organization and research operations only  
Architecture authority: None  
Removal condition: Replace with durable layout/maintenance documentation after all exit criteria pass

## Why Phase 2 Exists

Phase 1 made the corpus discoverable, but left imported source, paper artifacts, IRIS-X-authored work, and operational metadata mixed at the repository root. It also documented provenance without establishing a complete operating model for adding, updating, checking, and studying material.

Phase 2 must make the repository structurally understandable and safely maintainable by both humans and coding agents. It must not define the eventual IRIS-X system architecture or merge imported projects.

## Required Outcomes

1. A human can distinguish imported predecessors, external references, papers, research work, experiments, operational documentation, and maintenance tools from the filesystem alone.
2. An agent can determine which trees are preserved source material, which areas are IRIS-X-authored, what may be edited, and which validation command must run.
3. Every imported snapshot remains identifiable after relocation, including its original import path and original Git tree OID.
4. Adding or updating a source or paper follows a documented, testable workflow rather than an ad hoc copy operation.
5. Human-readable indexes are derived from, or mechanically checked against, machine-readable records so they cannot silently drift apart.
6. Repository checks detect inventory gaps, bad evidence paths, invalid records, incorrect snapshot identities, unintended imported-source edits, and stale generated navigation.

## Target Layout

The exact spelling may change if implementation evidence requires it, but the boundaries must remain explicit and shallow:

```text
IRIS-X/
  README.md
  AGENTS.md
  .gitignore
  .gitattributes

  sources/
    AGENTS.md
    README.md
    predecessors/
      iris/
      eidos/
      spex/
      vanta/
    external/
      aflow/
      agent_lightning/
      dspy/
      frugalgpt/
      gepa/
      NeMo-Agent-Toolkit-develop/
      prime_agent/
      prime_intellect_verifiers_v1/
      routellm/

  references/
    README.md
    papers/
      *.pdf

  research/
    AGENTS.md
    README.md
    templates/

  experiments/
    AGENTS.md
    README.md

  docs/
    repository-layout.md
    maintenance.md
    decisions/
    plans/

  corpus/
    README.md
    PROVENANCE.md
    RECOVERY_QUEUE.md
    sources.yaml
    artifacts.yaml

  tools/
    README.md
    repository_check.py
```

Leaf names of imported directories should be preserved during this migration. Normalizing upstream names can be considered later, but combining relocation and renaming would make provenance review harder.

Empty hierarchy must not be created merely to resemble a mature project. Each retained directory needs an immediate operational purpose and a short README or scoped instruction.

## Work Package 1: Physical Corpus Boundaries

- Move the four predecessor trees under `sources/predecessors/`.
- Move the nine external reference trees under `sources/external/`.
- Move the seven PDFs under `references/papers/`.
- Do not edit files inside imported trees as part of the move.
- Update all IRIS-X-authored path references, evidence paths, indexes, and validation logic.
- Record both `original_import_path` and current `path` for every source and artifact.
- Preserve source directory tree OIDs and PDF blob/SHA-256 fingerprints.

Migration verification must demonstrate content-preserving renames. Use a temporary Git index or another non-destructive method so verification does not stage the user's real index. Every imported tree and PDF must have zero content changes.

## Work Package 2: Authored Work Zones

Create explicit destinations for new IRIS-X work without inventing a research architecture:

- `research/`: comparative notes, exploratory notes, hypotheses, results, and research synthesis.
- `experiments/`: experiment definitions, inputs, scripts, run manifests, and reviewed results. Do not silently commit bulky transient outputs.
- `docs/`: repository operation, layout, decisions about repository organization, and temporary plans.
- `tools/`: lightweight corpus/repository maintenance utilities only.

Provide a minimal research-note template containing status, question/scope, source IDs, evidence basis, observations, uncertainty, and follow-ups. This is a writing aid, not a mandatory ontology.

## Work Package 3: Agent-Readable Boundaries

Update root `AGENTS.md` to describe the new paths and current operating commands without changing its research philosophy.

Add narrowly scoped instruction files:

- `sources/AGENTS.md`: imported trees are preserved snapshots; inspect freely, edit only when explicitly required, and keep IRIS-X analysis outside them.
- `research/AGENTS.md`: distinguish observation from inference, cite source IDs/evidence paths, label uncertainty, and state document status.
- `experiments/AGENTS.md`: separate definitions, inputs, raw outputs, and interpreted results; require reproducibility and record failures.

Do not copy large portions of the root instructions into scoped files. Each scoped file should state only the rules added by that boundary.

## Work Package 4: Provenance and Version Operations

Evolve the registries only as far as needed to support maintenance:

- Stable source/artifact ID.
- Current path and original import path.
- Classification and research role.
- Upstream identity and evidence.
- Declared package version and evidence, explicitly separate from upstream revision.
- Active local snapshot identity.
- Snapshot history or an equivalent append-only acquisition history so future refreshes do not erase earlier provenance.
- License status/evidence, local modifications, verification state, and unresolved questions.

Unknown facts must remain `Unknown`, `Unclear`, `Not established`, `Not evaluated`, or `Conflicting evidence` as appropriate. Do not infer precise upstream revisions from package versions.

Document concrete workflows for:

1. adding a new external source;
2. refreshing an existing source;
3. adding a predecessor snapshot;
4. adding or replacing a paper artifact;
5. deprecating/removing material without erasing provenance;
6. creating a research note that cites corpus records.

## Work Package 5: Operational Checks

Move or replace the Phase 1 validator with a clearly named root-level maintenance command, preferably:

```powershell
python tools\repository_check.py
python tools\repository_check.py --self-test
```

The check must remain standard-library-only unless a dependency is clearly justified. It must validate:

- registry syntax, required fields, stable-ID uniqueness, enums, relationships, and evidence paths;
- exact coverage of imported source roots and registered paper artifacts;
- semantic snapshot identity by resolving `import_commit:original_import_path` and comparing the resulting Git tree/blob OID;
- current path existence and classification boundary;
- PDF byte length, blob OID, and SHA-256 unless hash checking is explicitly disabled;
- behavior of `--no-verify-hashes` (fix the Phase 1 bug or remove the option);
- generated human indexes are current, if generation is used;
- repository-authored links affected by the migration resolve;
- no unexpected top-level imported source/PDF remains after migration.

Self-tests must include positive and negative cases for missing inventory, bad paths, duplicate IDs, illegal enum values, broken relationships, bad evidence paths, wrong tree/blob OIDs, stale generated output, and hash-skip behavior.

Avoid turning the validator into a second package manager or general policy engine. If the current 669-line script can be simplified while retaining checks, prefer the smaller implementation.

## Work Package 6: Human Operations Documentation

Provide durable documents that answer operational questions directly:

- Root `README.md`: what IRIS-X currently is, major zones, first commands, and where to begin research.
- `docs/repository-layout.md`: why each top-level area exists, ownership/editability, and what does not belong there.
- `docs/maintenance.md`: step-by-step source/artifact lifecycle procedures and validation expectations.
- `sources/README.md`: generated or mechanically checked inventory grouped by predecessor/external role.
- `references/README.md`: paper inventory and relation to source IDs.

Add one repository-organization decision record explaining why imported material is physically separated without making that structure a research architecture decision.

## Non-Goals

- No agent runtime, shared framework abstraction, final ontology, final research question, or product structure.
- No refactoring, formatting, dependency installation, or cleanup inside imported trees.
- No attempt to make imported projects build together.
- No claim that a registered source is approved for dependency use.
- No invented upstream revisions, licenses, or acquisition histories.
- No large set of empty placeholder directories.

## Execution Order

1. Fix the two Phase 1 validator findings and expand self-tests.
2. Add original/current path support and snapshot-history semantics to metadata.
3. Create target boundary directories and scoped instructions.
4. Perform content-preserving moves.
5. Update root instructions, registries, evidence paths, and human documentation.
6. Add authored work-zone templates and maintenance workflows.
7. Run validator, link/path checks, semantic Git snapshot checks, and content-preserving migration audit.
8. Review the complete Git status/diff and confirm imported content changed only by rename.

## Exit Criteria

- Root contains no imported project directory or corpus PDF.
- All 13 sources and 7 artifacts exist in their classified locations.
- A human can identify editable versus preserved areas from the root layout and repository-layout document.
- An agent entering `sources/`, `research/`, or `experiments/` receives concise scoped guidance.
- One documented command validates the operational state from repository root.
- The check fails on every required negative case and passes on the migrated repository.
- All original import tree/blob identities remain reproducible from Git history.
- Migration audit shows no content edits inside imported source trees or PDFs.
- Current unknown provenance remains explicit in the recovery queue.
- The result remains a research workspace, not a prematurely defined IRIS-X architecture.

## Implementation Judgment

The implementing task may adjust exact filenames or consolidate documents when that produces a smaller, clearer operating model. It must preserve the boundaries, outcomes, non-goals, and exit criteria above. Any material deviation must be explained in the final report with evidence.
