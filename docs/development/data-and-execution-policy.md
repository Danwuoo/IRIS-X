# Data and Execution Policy

Status: current P0 policy. This policy establishes safe defaults; it does not
authorize a provider, model, dataset, trial, or product runtime. Execution work
also follows the [`Development Operating Model`](operating-model.md).

## Secrets and credentials

- Never commit API keys, tokens, passwords, private keys, session material, or
  other secrets.
- Supply secrets only through an approved environment or secret-management
  mechanism for an explicitly authorized task.
- Do not print secrets into logs, prompts, trial records, screenshots, or
  Domain Packages. Stop and report suspected exposure before continuing.

## Domain and sensitive data

- Treat non-public domain data as sensitive until its owner, permitted uses,
  access boundary, and retention requirements are established.
- Use the minimum data necessary for the authorized question. Do not upload or
  disclose domain data to an external provider/model without explicit approval
  covering that provider/model, data class, purpose, and retention behavior.
- Record applicable consent, licensing, privacy, security, residency, and
  human-review constraints rather than assuming them.

## Local outputs, retention, and provenance

- Put generated local working output under `.irisx/`. It is ignored, local,
  disposable by default, and is not authoritative evidence merely because it
  exists.
- Promote an output into Git only after review confirms that it is authorized,
  necessary, appropriately redacted, and suitable for the intended retention.
- Retained trial or product evidence must identify its source, procedure or
  command, relevant configuration, time, costs, transformations, and known
  limitations. Preserve provenance and failures; do not rewrite observations
  to support a preferred decision.
- Follow any stricter source-specific deletion or retention requirement. Git
  history is not an appropriate store for secrets or data that must be erasable.

## External execution and budgets

Ordinary P0 validation is deterministic and offline. It may inspect local files
and Git objects but must not call a provider/model, access an external service,
start paid compute, or transmit domain data.

Any external or paid execution requires explicit owner authorization that
identifies the purpose and scope, provider/model or service, permitted data,
maximum budget or resource limit, stop conditions, and expected output and
retention. Budget approval must precede paid execution; absent an approved
limit, the permitted spend is zero. Approval of product direction or repository
work is not approval to spend money or execute a model.

External execution must use a deliberate command or authorized Engineering
Trial path separate from default tests and repository validation. Unexpected
network activity, cost, credential use, or data disclosure is a stop condition
and must be reported.
