# Shared Experiment Configurations

This directory contains accepted, machine-readable configuration baselines that
future experiments may copy and freeze. A shared baseline is an input to an
experiment, not a result and not authorization to call an external provider.

- [`provider-model-baseline-v0.json`](provider-model-baseline-v0.json) defines
  the accepted OpenAI provider, Codex CLI execution surface, GPT-5.6 Terra
  `strong` role, and GPT-5.6 Luna `cheaper` role.

An experiment using a baseline must preserve the exact bytes or SHA-256 of the
copied configuration in its definition and run manifest. Experiment-local
settings such as task scope, prompt, tools, sandbox, approvals, sample size,
retry policy, and spend ceiling remain explicit experiment inputs.

