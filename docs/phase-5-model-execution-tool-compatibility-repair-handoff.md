# Phase 5 Model Execution Tool Compatibility Repair Handoff

- **Status:** completed tool repair / durable handoff
- **Date:** 2026-09-05 Asia/Taipei
- **Scope:** Phase 5 Batch 4 qualification-tool compatibility only
- **Starting SHA:** `78fdeaae907e3f02fea899d10f69f6f4c821c18e`
- **Plan activation:** `ae5fbce70f8e55263ae590a1666c065053af0b75`
- **Tool repair:** `663fdcdffa73305496107a3ed0b86d32f9b90616`
- **Model calls made by this repair:** 0
- **Batch 5:** not started

## Outcome

The qualification tool is repaired for the frozen Codex CLI 0.147.0 target.
The unsupported `tools.view_image=false` config override was removed and the
same capability is now disabled through the version-supported
`--disable view_image` feature path.

A new zero-model compatibility probe loads the exact live config arguments
through:

```text
codex app-server --strict-config --listen off
```

It uses an isolated temporary `CODEX_HOME` and accepts only the exact 0.147.0
post-config no-transport sentinel. Unknown config fields fail before that
sentinel and are rejected. The real installed binary produced:

```text
status: PASS
codex_cli_version_required: codex-cli 0.147.0
method: app-server-strict-config-listen-off
model_calls: 0
transport_started: false
post_config_sentinel: Error: no transport configured; use --listen or enable remote control
```

The standard `--preflight` path now runs this strict compatibility probe before
authentication, catalog, and doctor checks and reports its result explicitly.
It also refuses any Codex version other than the frozen 0.147.0 target.

This repair does not claim that a model-backed execution has succeeded. Both
prior qualification runs remain correctly adjudicated failures. A future live
qualification requires separate owner authorization, a new run identity, and
a newly frozen execution definition.

## Compatibility finding

The current OpenAI Codex configuration reference documents
`tools.view_image`, but the installed frozen Codex CLI 0.147.0 rejects it under
`exec --strict-config`. The 0.147.0 source/config schema exposes `view_image`
as a feature flag, so `--disable view_image` is the compatible form for this
tool. Official reference:
<https://learn.chatgpt.com/docs/config-file/config-reference>.

`codex debug` and `codex doctor` do not exercise the strict exec config path.
`codex exec --help` also exits before loading config. The app-server probe was
therefore selected because it invokes the same strict config loader while
`--listen off` prevents transport startup and no model turn is created.

## Changed files

- `experiments/substrates/model-execution-qualification-v0/scripts/run_qualification.py`
  - removed `tools.view_image=false`;
  - added `--disable view_image`;
  - added exact CLI-version enforcement;
  - added strict config probe construction, result validation, and execution;
  - added `--check-strict-config` zero-call mode;
  - integrated the probe into normal preflight reporting.
- `experiments/substrates/model-execution-qualification-v0/tests/test_qualification.py`
  - verifies the incompatible field is absent;
  - verifies `view_image` is disabled as a feature;
  - verifies probe/live config-argument parity;
  - verifies that only the post-load sentinel is accepted and the observed
    historical unknown-field error is rejected.
- `experiments/substrates/model-execution-qualification-v0/README.md`
  - documents the repaired version-specific command and zero-call probe.

Final SHA-256 values at the tool-repair commit:

- `run_qualification.py`:
  `b18974c3d7cc9c61dc0cc328ef9070d66443bb90db874df537efa1a00e429d0a`;
- `test_qualification.py`:
  `910abe38a86a0f6e2741671f96ac22d96f3fe4e99f509bbe0af97fff470a899c`.

No file in `irisx.core` changed.

## Validation

All repair validation made zero model calls.

- exact Codex 0.147.0 strict config probe: PASS;
- full qualification preflight: PASS, including ChatGPT auth, subscription
  billing, Luna/medium catalog presence, zero retries, disabled WebSockets, and
  strict config compatibility;
- qualification tests: 20/20 PASS;
- core tests: 28/28 PASS;
- deterministic mutation path: 13/13 PASS;
- deterministic read-only path: 9/9 PASS;
- focused total: 70/70 PASS;
- full inventory: 141 total, 140 passed, 1 known historical failure, 0 errors,
  0 skips, 0 new failures;
- repository validation: PASS, 13 sources and 7 paper artifacts;
- accepted provider/model baseline and local Codex catalog: PASS;
- immutable validators for `qualification-20260905-01` and
  `qualification-20260905-02`: PASS.

The unchanged historical failure remains
`HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes` for the
retired Phase 4 plan. It was not modified or suppressed.

## Preservation proof

From starting SHA `78fdeaae907e3f02fea899d10f69f6f4c821c18e` through
tool-repair SHA `663fdcdffa73305496107a3ed0b86d32f9b90616`:

| Preserved tree | Before and after Git tree |
| --- | --- |
| `sources/` | `10e28d83184c789fc468ca1edc3bebf42ba40b46` |
| `references/papers/` | `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` |
| `research/` | `0d89db5ef0d4712e6068bd499c11a852570633da` |
| `qualification-20260905-01` | `1fd6b4779ea936e8e1f6026433143a9106317ffa` |
| `qualification-20260905-02` | `f84fd3563386703303206ed66dc0712652a372e4` |

No run artifact, prior evidence, handoff, retired plan, source, paper,
research record, or frozen deterministic Phase 5 input was changed.

## Explicit exclusions

No model call, new run, retry, model comparison, routing, cascade, fallback,
escalation, recovery, persistence, workflow engine/search, optimizer,
fine-tuning, training, multi-agent work, architecture search, model judge,
non-deterministic verifier, external action, production server/UI/API, or
H-G1/H-W1/H-C1/H-R1 evaluation occurred. Batch 5 was not started.
