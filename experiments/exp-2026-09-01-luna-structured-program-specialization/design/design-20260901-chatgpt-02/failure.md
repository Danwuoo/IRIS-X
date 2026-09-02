# H-P1a design run pre-invocation failure

Status: **incomplete — blocked before first formal model invocation**

Run `design-20260901-chatgpt-02` passed the committed provider-schema
preflight, created its append-only run directory, and then terminated while
binding the admission-record path into the run manifest. The runner received a
repository-relative path and attempted `Path.relative_to(EXPERIMENT)` before
normalizing it to an absolute path. Python raised `ValueError`.

No candidate invocation was started. Actual Luna calls, Terra calls, network
calls by the experiment runner, and API calls are all zero. ChatGPT
authentication had been revalidated; API-key fallback remained prohibited.
Provider cost is `Unknown`.

The adapter now normalizes the admission path before the experiment-relative
binding. This directory is immutable and must not be deleted, rewritten, or
reused. A new run identity and independent resource authorization require owner
direction under the controlling plan.
