# PS1-G7 Artifact-Backed Context OS Evaluation Pilot

Plan ID: `PS1-LC-CTX-PLAN-001`
Gate policy: `PS1-LC-CTX-GATE-001`
Evaluation mode: `artifact_backed_post_freeze_evaluation`
Final pilot status: `pass_artifact_backed_evaluation_pilot`
Evaluation fingerprint: `sha256:97bc3d8b263e998de460fae8d063c2d3d629b48cfee9daf4b6f4e14091516680`
Source Lane A run: `20260601_113121` (`accepted_by_closure`)
Model calls issued by this pilot: `0`
OpenClaw measured runs issued by this pilot: `0`

## Fixed Controls

- model: `openai-codex/gpt-5.4-mini`
- harness: `openclaw_agent_local`
- context planner adapter: `Vanta.OpenClawContextPlannerAdapter`
- OpenClaw agent: `vanta-verifier` (post-hoc user-authorized coordinator attestation; not source-run-native metadata)
- prompt / response budgets: `20000` / `12000` characters
- response format: `json_only`
- action / recovery attempt limits: `6` / `1`
- tool policy: `embedded_context_only`
- context budget: global `null` means `uses_frozen_per_fixture_budgets`; the complete map is in `run.json` and `fixture_inventory.md`

## Lane A Structural / Fixture-Oracle Evidence

| Metric | Baseline | Treatment | Label source |
| --- | ---: | ---: | --- |
| `working_set_budget_adherence` | 1.0000 | 1.0000 | `automated_structural` |
| `working_set_provenance_completeness` | 0.6667 | 1.0000 | `automated_structural` |
| `context_omission_error_rate` | 0.7778 | 0.0000 | `fixture_oracle` |
| `working_set_relevance_score` | 0.2167 | 0.9667 | `fixture_oracle` |
| `long_task_stability` | 1.0000 | 1.0000 | `automated_structural_and_task_outcome` |

These Lane A values are automated structural or fixture-oracle evidence.
They are not human-labeled evidence.

## Lane B Human-Label Evidence

| Interpreted arm | Blinded arm | Omission | Relevance |
| --- | --- | ---: | ---: |
| Baseline | `context_arm_A` | 0.7368 (14/19) | 0.4545 (5/11) |
| Treatment | `context_arm_B` | 0.0000 (0/19) | 0.9500 (19/20) |

The packet is small, so raw counts are reported. Relevance must be read
together with omission; empty or sparse context must not be treated as
sufficient merely because selected-ref precision appears high.

## Claim Boundary

This pilot validates the completeness and internal consistency of the named
artifact-backed evaluation only. It is not a new model run, a full Context
OS experiment, H3 validation, production readiness, runtime approval,
runtime action authority, schema authority, memory authority, side-effect
authority, or a new `accepted_by_closure` decision.
