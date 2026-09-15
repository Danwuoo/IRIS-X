# Maintenance and Historical Tools

No tool in this directory authorizes research, an experiment, or a model call.
Inspect a tool's inputs and dependent records before running it.

Reusable repository/provenance utilities:

- `repository_check.py` validates corpus inventory, provenance, generated
  indexes, authored links, and repository boundaries;
- `migration_audit.py` audits preserved migrations and registered identities;
- `source_snapshot_assertion.py` provides a reusable local source-snapshot
  assertion used by historical experiment machinery.

Historical research-specific helpers retained for reproducibility:

- `build_document_ops_frame.py` builds the prior Document Ops task frame;
- `model_baseline_check.py` validates the retired provider/model baseline and
  optionally a local catalog without making a model call;
- `validate_pre_synthesis_readiness.py` validates the historical pre-synthesis
  package;
- `d1a_custodian_exact_path.ps1` is a machine-specific D1a launch/remediation
  artifact with frozen paths and identities. Do not use it as a current launch
  entry point.

Current repository validation:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
```

Run a historical helper only when reproducing or auditing its preserved scope,
or when the owner explicitly authorizes new work that adopts it.
