# Minimal Reliable Execution Slice v0

Status: executable qualification slice for the provisional post-Phase-4 candidate architecture

This directory contains exactly one local deterministic vertical slice. It operationalizes identity and artifact binding, pre-execution policy, a replaceable executor adapter, independent semantic and evidence verification, separate adjudication fields, and structured terminal observations. It is not a production runtime or a new mechanism experiment.

The committed fixture freezes:

- task and contract identity;
- one specialization program and its exact SHA-256;
- one in-memory `set` request;
- a protected-path and allowed-write-path policy;
- one semantic success condition; and
- required task-contract and program evidence references.

The executable uses only the Python standard library. It performs zero model, network, API, retry, routing, escalation, and recovery actions. It writes no run directory; the CLI prints one terminal JSON record and tests use temporary files or in-memory state.

Run from repository root:

```powershell
python experiments\substrates\minimal-reliable-execution-v0\scripts\run_slice.py
python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v
```

The implementation boundary and its evidence basis are documented in `research/post-phase-4-architecture-synthesis.md`. Recovery remains an explicit unimplemented extension point.
