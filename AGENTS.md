# IRIS-X Repository Governance

## Purpose and Current State

IRIS-X is a research workspace concerned broadly with task- and
domain-specialized AI systems. Its final research question, architecture,
training strategy, platform design, and product boundary are open.

The repository is in a research-reset and direction-selection state. It has no
active thesis, phase, experiment, implementation program, or preferred follow-on
research question. Historical IRIS-X work is preserved as research lineage, not
as automatic authority for future work.

Beginning a new major research program, model/provider execution, experiment,
architecture effort, or product implementation requires explicit owner
authorization with a new scope. Do not infer authorization from a historical
plan, handoff, synthesis, decision, prototype, or experiment package.

## Repository Boundaries

| Path | Classification | Default treatment |
| --- | --- | --- |
| `sources/` | Preserved imported source and reference implementations | Read-only; follow `sources/AGENTS.md` |
| `references/papers/` | Preserved reference artifacts | Read-only |
| `corpus/` | Provenance registries and recovery records | Preserve identities and history; edit only for concrete provenance work |
| `experiments/` | Historical definitions, inputs, machinery, raw records, results, and qualification packages | Preserve evidence and reproducibility; follow `experiments/AGENTS.md` |
| `research/` | Historical IRIS-X interpretations plus neutral research scaffolding | Use the indexes and follow `research/AGENTS.md` |
| `docs/` | Current repository guidance and historical operational records | Treat handoffs, closures, state files, and plans as historical unless a current index says otherwise |
| `tools/` | Reusable maintenance utilities and historical research-specific helpers | Check `tools/README.md` before use |
| `irisx/` | Preserved historical prototype code | Not a current or production architecture |

The active neutral surface consists primarily of the root entry points, scoped
governance files, current directory indexes, provenance machinery, and reusable
repository checks. A file's physical presence does not make its claims current.

## Authority and Historical Material

Historical research records preserve what was proposed, observed, inferred, or
decided at the time. Do not silently revise them to fit a new direction. Do not
promote them into current requirements merely because they use words such as
`current`, `active`, `foundational`, `controlling`, or `authoritative` within
their original historical context.

Prior syntheses, problem definitions, hypotheses, specifications, phase
records, operating baselines, and candidate architectures are historical inputs
unless explicitly re-adopted by the owner in a new scope. No prior concept or
synthesis is the default center of IRIS-X after the reset.

When historical and current guidance appear to conflict, preserve the
historical record and follow the current root and directory-level governance.
Record any later re-adoption as a new decision rather than retroactively editing
the old record.

## Preservation and Provenance

- Do not modify imported material under `sources/` or preserved artifacts under
  `references/` except for an explicitly authorized hygiene or provenance fix.
- Preserve `corpus/` registry IDs, snapshot histories, hashes, source refs,
  evidence paths, and unresolved provenance fields.
- Preserve experiment definitions, inputs, raw outputs, terminal records,
  manifests, hashes, reviewed results, failure records, and interpretation
  boundaries.
- Do not normalize or rewrite old empirical data. A historical result must not
  be reclassified to support a new interpretation.
- Keep historical paths stable when manifests, hashes, validators, or evidence
  ledgers depend on them. Prefer indexes and status clarification over moves that
  would damage reproducibility.
- When uncertain whether material is evidence, infrastructure, historical
  interpretation, or noise, preserve it and label the uncertainty.

Git history and the reset snapshot tag preserve recovery, but they do not make
destructive edits acceptable by default.

## Research Discipline

Before drawing a conclusion:

1. inspect the original source or empirical record;
2. distinguish source-stated behavior, direct observation, inference, and
   unknowns;
3. cite stable corpus IDs and exact evidence paths where applicable;
4. preserve negative evidence, incompatible assumptions, scope limits, and
   failure cases;
5. compare mechanisms by the problem they solve, not only by API shape;
6. separate IRIS-X research contribution from commodity or reusable substrate;
7. define uncertainty and falsifiers instead of filling gaps with confident
   guesses.

Use `Unknown`, `Unclear`, `Not established`, `Not evaluated`, or `Conflicting
evidence` when those labels are accurate.

Imported projects are evidence and reference material, not authority over
IRIS-X. Repetition of a concept across multiple projects does not establish that
the concept belongs in a future IRIS-X design.

## Working Rules

- Keep new IRIS-X-authored work within `research/`, `experiments/`, `docs/`,
  `tools/`, `corpus/`, or `irisx/` as appropriate; do not create a broad new
  hierarchy without an immediate, authorized purpose.
- Prefer small, reversible changes and research-enabling organization over code
  volume or framework integration.
- Do not launch a model/provider process, start an experiment, or extend a
  historical prototype without explicit owner authorization.
- Do not treat a successful tool call, benchmark score, low inference price, or
  historical decision as proof of general reliability or present suitability.
- Keep temporary plans and session handoffs out of current navigation. If they
  must be preserved at fixed paths, classify them through the historical index.
- Update links and indexes when current documentation moves. Do not rewrite
  preserved scientific records solely to modernize their links.

## Validation

Run from the repository root after repository or provenance changes:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
```

Use focused tests for any historical machinery that was intentionally touched.
If a check encodes a retired governance assumption, distinguish that governance
check from evidence-integrity checks. Update only the former when justified;
never alter empirical records merely to obtain a passing result.

The repository reset and its preservation choices are recorded in
`docs/research-reset-2026-09-16.md`.
