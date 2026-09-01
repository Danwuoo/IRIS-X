# Decision 0002: Establish the OpenAI Codex Dual-Model Baseline

- **Status:** Accepted operating baseline
- **Date:** 2026-09-01
- **Scope:** Model-backed Phase 4 follow-up work and later IRIS-X project work

## Decision

IRIS-X adopts one provider and two explicit model roles:

| Concern | Accepted value |
| --- | --- |
| Model provider | OpenAI (`openai`) |
| Execution surface | Codex CLI (`codex`) |
| Strong role | `gpt-5.6-terra` |
| Cheaper role | `gpt-5.6-luna` |
| Comparison reasoning baseline | `medium` |
| Automatic routing or escalation | Not established |

Codex CLI is the client and agent execution surface, not the model provider. A
run must therefore record `openai` as the provider and `codex-cli` separately as
the execution surface.

The machine-readable authority for this baseline is
[`experiments/configurations/provider-model-baseline-v0.json`](../../experiments/configurations/provider-model-baseline-v0.json).
Experiments may copy and freeze that record into an experiment definition, but
must not silently reinterpret the two roles.

## Evidence and rationale

- **Source-stated:** Official OpenAI model guidance describes GPT-5.6 Terra as
  balancing intelligence and cost, and GPT-5.6 Luna as intended for
  cost-sensitive, high-volume workloads.
- **Source-stated:** Both model pages list `medium` as the default reasoning
  effort and support the tools needed by Codex-style agent work.
- **Directly observed locally:** Codex CLI `0.147.0` exposed both exact model IDs
  in its active model catalog on 2026-09-01, with `medium` as their default
  reasoning level.
- **Inferred operating choice:** Using the same initial reasoning effort creates
  a cleaner first comparison boundary. Later experiments may vary effort only
  as an explicitly frozen factor.

Official evidence checked on 2026-09-01:

- <https://developers.openai.com/api/docs/guides/latest-model>
- <https://developers.openai.com/api/docs/models/gpt-5.6-terra>
- <https://developers.openai.com/api/docs/models/gpt-5.6-luna>
- <https://developers.openai.com/codex/config-reference>
- <https://developers.openai.com/codex/cli/reference>

## Selection policy

Each run must select `strong` or `cheaper` explicitly. This decision does not
make either role a universal default and does not define a cascade, retry,
fallback, or escalation policy.

`strong` is a project-relative role meaning the stronger member of this frozen
two-model comparison. It is not a claim that Terra is OpenAI's flagship or most
capable available model.

- Use `cheaper` as the candidate for cost-sensitive or repeated work.
- Use `strong` as the stronger comparison/reference arm or when a separately
  stated task policy selects it.
- Treat any change of model, reasoning effort, tool envelope, prompt, or Codex
  version as configuration drift unless the experiment declares it as a factor.

## Reproducibility boundary

The official model pages listed only the aliases `gpt-5.6-terra` and
`gpt-5.6-luna` on the decision date; no distinct date-versioned snapshot ID was
available to freeze. The alias is therefore a named provider baseline, not proof
of immutable model bytes or behavior.

Every model-backed experiment must preserve at least:

- baseline ID and frozen baseline-file hash;
- provider ID, model role, and exact model ID;
- Codex CLI version and catalog-check time;
- resolved Codex executable or command-shim path, because more than one local
  installation can exist;
- reasoning effort, tool envelope, sandbox/approval settings, and prompt or
  candidate identity;
- authentication/billing mode without recording credentials;
- input, cached-input, output, and reasoning usage when exposed;
- price basis and date, observed provider cost, retries, failures, and wall time.

If provider cost or an immutable provider snapshot cannot be established, record
`Unknown`; do not substitute zero.

## Operational entry points

The model choice can be applied without changing a user's global Codex config:

```powershell
codex exec --strict-config --model gpt-5.6-terra --config 'model_reasoning_effort="medium"' --json -
codex exec --strict-config --model gpt-5.6-luna --config 'model_reasoning_effort="medium"' --json -
```

The prompt is read from standard input. Each experiment must additionally set
its own workspace, sandbox, approval, output-schema, and artifact paths.

Validate the committed baseline and the bundled local Codex catalog with:

```powershell
python tools\model_baseline_check.py --check-local-catalog
```

This validation performs no model call and authorizes no paid use.

## Boundaries

This decision selects a provider/model operating baseline only. It does not:

- rewrite completed Phase 4 results or their historical `Unknown` fields;
- start or establish H-P1;
- authorize a paid run without a separately recorded experiment scope and spend
  ceiling;
- establish model quality, reliability, cost advantage, routing, specialization,
  or a final IRIS-X architecture.
