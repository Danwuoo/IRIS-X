# ARC-AGI-1 Development Query Log

- **Version:** v0.1
- **Established:** 2026-08-05
- **Scope:** Required disclosure record for use of ARC-AGI-1 public evaluation data during development
- **Data record:** [`artifacts/arc-agi-1/development-query-log.jsonl`](../../artifacts/arc-agi-1/development-query-log.jsonl)
- **Authority:** [ARC Evaluation Definition v0](./ARC-Eval-Definition-v0.md) section 6; [ARC-AGI-1 Substrate v0](./ARC-AGI-1-Substrate-v0.md)

This is an append-only JSONL record. Each event must identify its timestamp, tier, task IDs or an explicit aggregate-only scope, whether an aggregate score was observed, whether it informed architecture selection, the actor/process, and a concise effect on subsequent development.

The initial event is not a task query, model call, score, or architecture decision. Historical use before log establishment is `Unknown`, not inferred as clean. The local A1 evaluation set remains `public-exposed`; logging does not make it sealed or private.
