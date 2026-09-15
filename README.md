# IRIS-X

IRIS-X is a research workspace concerned broadly with task- and
domain-specialized AI systems. The repository is currently in a
**research-reset / direction-selection state**: no previous thesis, research
program, architecture, training strategy, or product boundary is automatically
active.

The workspace contains several distinct kinds of material:

| Path | Contents |
| --- | --- |
| [`sources/`](sources/README.md) | Preserved predecessor and external source snapshots |
| [`references/`](references/README.md) | Preserved papers and reference artifacts |
| [`corpus/`](corpus/README.md) | Provenance registries, source identities, and recovery records |
| [`experiments/`](experiments/README.md) | Preserved historical experiments, qualification packages, and empirical records |
| [`research/`](research/README.md) | Historical IRIS-X research lineage and neutral research scaffolding |
| [`docs/`](docs/README.md) | Current repository guidance and indexed operational history |
| [`tools/`](tools/README.md) | Repository maintenance utilities and classified historical helpers |
| [`irisx/`](irisx/README.md) | Preserved historical prototype code; not a current architecture |

Historical conclusions remain available for inspection, but their original
status language does not make them current project authority. New research or
implementation requires a separately authorized scope.

Start with [`AGENTS.md`](AGENTS.md) for repository governance and
[`docs/research-reset-2026-09-16.md`](docs/research-reset-2026-09-16.md) for the
reset record.

Validate repository integrity from the root:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
```
