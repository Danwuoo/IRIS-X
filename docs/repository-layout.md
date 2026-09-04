# Repository Layout

Status: current operating baseline for post-Phase-4 architecture synthesis; filesystem boundaries are unchanged and this is not an architecture decision.

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

The filesystem boundary is deliberately shallow. Imported leaf names remain unchanged so original import paths stay easy to audit. New research must not create parallel copies of imported code or papers inside authored areas.

Root-level operational documentation describes the workspace. It does not define an agent runtime, shared framework, product boundary, final ontology, or final research question.
