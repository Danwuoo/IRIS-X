# Repository Layout

Status: current operating baseline for Phase 5 provisional architecture development; this remains a provisional organization rather than a final architecture decision.

| Path | Role | Editability |
|---|---|---|
| `sources/predecessors/` | Preserved predecessor snapshots | Read-only by default |
| `sources/external/` | Preserved external reference implementations | Read-only by default |
| `references/papers/` | Preserved paper artifacts | Read-only by default |
| `research/` | IRIS-X-authored notes, synthesis, hypotheses, comparisons | Editable with scoped guidance |
| `experiments/` | Explicit experiment definitions, shared configuration inputs, runs, results | Editable with reproducibility guidance |
| `docs/` | Repository operation, layout decisions, temporary plans | Editable |
| `tools/` | Lightweight maintenance commands | Editable |
| `corpus/` | Registries and provenance operations | Editable as structured records |
| `irisx/` | Minimal provisional IRIS-X-authored architecture code | Editable within owner-authorized architecture scope |

The filesystem boundary is deliberately shallow. Imported leaf names remain unchanged so original import paths stay easy to audit. New research must not create parallel copies of imported code or papers inside authored areas.

The `irisx/` package is not a production-stable SDK or framework. Experiment substrates may depend on it, but it must not depend on `experiments/` or imported source trees. Imported implementations remain separate reference material and are never architecture authority.

Root-level operational documentation describes the workspace. It does not define an agent runtime, shared framework, product boundary, final ontology, or final research question.
