# IRIS-X Corpus Workspace

IRIS-X is currently in **research preparation**. It separates preserved predecessors, external references, paper artifacts, and IRIS-X-authored work. It is not a merged framework, product, runtime, or final architecture.

Root-level `AGENTS.md` controls how agents should work with this material. There are 13 imported sources and 7 paper artifacts. Imported trees live under `sources/`; PDFs live under `references/papers/`; editable work zones are `research/`, `experiments/`, `docs/`, and `tools/`.

## Navigation

- Read [docs/repository-layout.md](docs/repository-layout.md) for zone ownership and editability.
- Read [corpus/README.md](corpus/README.md) for the corpus map.
- Read [corpus/PROVENANCE.md](corpus/PROVENANCE.md) for field meanings.
- Use [corpus/sources.yaml](corpus/sources.yaml) and [corpus/artifacts.yaml](corpus/artifacts.yaml) for machine-readable inventory.
- Track unresolved provenance work in [corpus/RECOVERY_QUEUE.md](corpus/RECOVERY_QUEUE.md).
- Read [research/problem-definition.md](research/problem-definition.md) for the current provisional project-level research problem.
- Read [docs/decisions/0002-openai-codex-model-baseline.md](docs/decisions/0002-openai-codex-model-baseline.md) and [experiments/configurations/provider-model-baseline-v0.json](experiments/configurations/provider-model-baseline-v0.json) for the accepted OpenAI/Codex dual-model operating baseline.
- Begin research with [research/templates/research-note.md](research/templates/research-note.md).

Validate the repository from its root:

```powershell
python tools\repository_check.py
python tools\model_baseline_check.py --check-local-catalog
```

Registries use a JSON-compatible YAML subset. Semantic Git checks also use the local Git executable. The layout is an evolving research-workspace baseline, not a final IRIS-X design.
