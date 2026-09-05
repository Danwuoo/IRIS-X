# TEMP Phase 5 — Model Execution Tool Compatibility Repair

- **Status:** Retired — compatibility repair completed
- **Authorization:** Owner-authorized follow-up to repair the Batch 4 qualification tool
- **Date:** 2026-09-05 Asia/Taipei
- **Repository:** Danwuoo/IRIS-X
- **Required starting SHA:** `78fdeaae907e3f02fea899d10f69f6f4c821c18e`
- **Scope:** Batch 4 tool compatibility only; no Batch 5 work
- **Live-call ceiling for this repair:** zero model calls

## Purpose

Repair the Codex CLI 0.147.0 compatibility defect exposed by immutable run
`qualification-20260905-02`. The frozen command used
`tools.view_image=false`, which that CLI version rejects under
`exec --strict-config` even though the current OpenAI Codex configuration
reference documents the key.

This task repairs and validates the tool only. It does not reinterpret either
prior run, authorize another qualification attempt, or establish successful
model-backed execution.

## Authorized changes

Within
`experiments/substrates/model-execution-qualification-v0/`:

1. remove the incompatible `tools.view_image=false` override;
2. disable the same capability through the Codex 0.147.0-supported
   `features.view_image=false` path emitted as `--disable view_image`;
3. add a zero-model strict-configuration compatibility probe using the exact
   installed Codex binary and the same config overrides as the live command;
4. use isolated temporary Codex state and `app-server --strict-config
   --listen off` so configuration is loaded without starting a model turn;
5. fail closed unless the exact 0.147.0 post-config no-transport sentinel is
   observed after all overrides pass strict parsing;
6. add deterministic tests for command parity, invalid-field rejection, and
   the no-model probe result;
7. update the substrate README and create a durable repair handoff.

Provider/model identity, retry limits, authentication policy, tool-free model
catalog, output schema, task, verifier, and core interfaces must not change.
No provider-specific type may enter `irisx.core`.

## Preservation

Both prior run directories are immutable:

- `runs/qualification-20260905-01/`;
- `runs/qualification-20260905-02/`.

Preserve all prior Phase 4/5 evidence, retired plans, handoffs, sources, papers,
research, prior runs, and the four frozen deterministic Phase 5 inputs. The
known Phase 4 retired-plan hash failure must remain unchanged and unsuppressed.

## Validation

All validation in this task must make zero model calls. Required checks:

- Python compilation;
- qualification unit tests;
- a real Codex 0.147.0 strict-config compatibility probe with no model turn;
- provider baseline and local catalog checks;
- both prior immutable-run validators;
- focused core/mutation/read-only/model tests;
- full regression inventory with zero new failures or errors;
- repository and preservation checks.

After validation, commit the tool repair, create a durable handoff, retire this
TEMP plan separately, push `main` normally, confirm ahead/behind `0/0`, and
stop. Do not make a model call or start Batch 5.

## Explicit exclusions

No live qualification attempt, retry, model comparison, routing, cascade,
fallback, escalation, recovery, persistence, workflow engine/search,
optimizer, fine-tuning, training, multi-agent work, architecture search, model
judge, non-deterministic verifier, external action, production server/UI/API,
or H-G1/H-W1/H-C1/H-R1 evaluation is authorized.

## Retirement record

- **Retired:** 2026-09-05 Asia/Taipei
- **Plan activation:** `ae5fbce70f8e55263ae590a1666c065053af0b75`
- **Tool repair:** `663fdcdffa73305496107a3ed0b86d32f9b90616`
- **Durable handoff:** `2a8a0e5050f7a466c7ba8646e844366cbcbaa74d`
- **Model calls:** 0
- **Transport started by strict probe:** false
- **Qualification tests:** 20/20 PASS
- **Focused tests:** 70/70 PASS
- **Full inventory:** 141 total, 140 passed, the same one historical failure,
  0 errors, 0 skips, and 0 new failures

The unsupported `tools.view_image=false` override was replaced by
`--disable view_image`. The exact Codex CLI 0.147.0 config arguments now pass a
real strict-config loader probe before ordinary preflight continues. Both
historical qualification runs remain byte-identical and correctly adjudicated.

The authoritative repair result and preservation proof are in
`docs/phase-5-model-execution-tool-compatibility-repair-handoff.md`. This plan
is no longer active. No live qualification was attempted and Batch 5 was not
started.
