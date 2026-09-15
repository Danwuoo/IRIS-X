# Repository Layout

Status: neutral operating layout after the 2026-09-16 research reset.

| Path | Role | Editability |
| --- | --- | --- |
| `sources/predecessors/` | Preserved predecessor snapshots | Read-only by default |
| `sources/external/` | Preserved external reference implementations | Read-only by default |
| `references/papers/` | Preserved paper artifacts | Read-only |
| `corpus/` | Provenance registries and recovery records | Structured provenance edits only |
| `research/` | Historical IRIS-X research plus neutral scaffolding | New work requires an authorized scope |
| `experiments/` | Preserved experiment packages and empirical records | Evidence-preserving changes only unless a new experiment is authorized |
| `docs/` | Current repository guidance and preserved operational history | Editable with historical records preserved |
| `tools/` | Reusable maintenance and classified historical helpers | Editable with dependent evidence considered |
| `irisx/` | Preserved historical prototype used by prior tests/substrates | Not a current architecture |

Imported leaf names and evidence-sensitive authored paths remain stable for
auditability and reproducibility. Current directory indexes determine active
navigation; physical presence alone does not confer authority.

The layout does not define a runtime, framework, ontology, product boundary,
provider/model baseline, final research question, or preferred next program.
