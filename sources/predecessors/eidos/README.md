# Eidos

Eidos is bootstrapping an agent-first research repository. The formal project charter and research architecture have not been approved yet.

Agents start with [`AGENTS.md`](AGENTS.md) and [`eidos.yaml`](eidos.yaml). Governed documents are YAML records discovered through the generated [`docs/index.json`](docs/index.json).

The Chinese ARC document currently in `docs/` is an early concept note only; it is not a formal project document.

## Documentation commands

```powershell
python -m pip install -r tools/docs/requirements.txt
python -m tools.docs.build_index
python -m tools.docs.validate
python -m unittest discover -s tests -v
```

