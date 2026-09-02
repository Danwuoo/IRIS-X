# Temporary Phase 4 Final Model Specialization and Closure Plan

Status: **Retired — execution complete; see retirement record in Section 27**
Date: **2026-09-01**  
Scope: **specialization schema cleanup, H-P1a, accumulated-evidence synthesis, and Phase 4 closure only**  
Architecture authority: **None**  
Planning baseline: GitHub `main` was independently reloaded and resolved to full commit `a859399eafb294ea03290123c285c127426dfb5b` when this plan was prepared  
Execution model: one final Phase 4 batch with separately frozen definition, design-time, validation, candidate-freeze, blind, interpretation, and closure gates  
Hard terminal boundary: **STOP after the Phase 4 closure decision; do not synthesize or implement architecture**

Once committed in the execution repository, the committed bytes of this plan are the controlling execution contract. The executor must still fetch the then-current remote `main`, obey every applicable `AGENTS.md`, preserve unrelated owner changes, and record the actual starting full commit SHA. A changed `main` does not silently invalidate this plan, but any material conflict with its assumptions must be resolved before model calls.

Retirement condition: retire this temporary plan only after a valid H-P1a result, a durable Phase 4 closure artifact, required validation, and an explicit hard stop. `Supported — task-local`, `Mixed evidence`, and `Rejected — task-local` are all valid research outcomes. An `Invalid run` does not satisfy retirement or Phase 4 closure.

---

## 1. Purpose

IRIS-X has completed the deterministic, evidence, operational, stateful, recovery, robustness-measurement, change-measurement, held-out-governance, generated-task, fake-candidate, and provider/model-baseline work needed to attempt one bounded model-backed specialization experiment.

This final Phase 4 batch has exactly three purposes:

1. remove the known future-execution schema blocker without rewriting historical run artifacts;
2. execute and interpret H-P1a, a Luna program-specialization experiment in which Terra appears only at design time and as a separately bounded runtime reference; and
3. synthesize accumulated Phase 3/4 evidence into a Phase 4 closure decision without designing the architecture.

The intended progression is:

```text
latest-main preflight
  -> specialization schema cleanup
  -> new deterministic fake-candidate qualification
  -> provider/model/auth/billing/resource freeze
  -> H-P1a definition commit
  -> DEV evaluation and bounded Terra optimization
  -> one-shot frozen validation
  -> deterministic C1 selection and candidate freeze
  -> post-freeze blind generation and leakage audit
  -> frozen interleaved blind execution
  -> H-P1a and Terra-reference interpretation
  -> accumulated Phase 3/4 evidence synthesis
  -> explicit Phase 4 closure decision
  -> STOP
```

No positive H-P1a result is required. The experiment must be allowed to reject the proposed mechanism.

---

## 2. Governing authority and established inputs

All applicable repository instructions remain authoritative, especially:

- `AGENTS.md`;
- `research/AGENTS.md`;
- `experiments/AGENTS.md`.

Use the existing IRIS-X discipline rather than introducing a new research framework. The principal controlling records are:

- `research/problem-definition.md`;
- `research/candidate-mechanism-hypotheses.md`;
- `research/evaluation-state-semantics-v1.md`;
- `research/reliability-protocol-v0.md`;
- `research/change-reliability-protocol-v0.md`;
- `research/heldout-evaluation-protocol-v0.md`;
- `research/model-specialization-execution-contract-v0.md` after WP1 cleanup;
- `research/phase-4-reliability-specialization-readiness.md`;
- `docs/decisions/0002-openai-codex-model-baseline.md`;
- `experiments/configurations/provider-model-baseline-v0.json`;
- `tools/model_baseline_check.py`;
- `experiments/substrates/docops-generated-heldout-v0/`;
- `experiments/substrates/model-specialization-v0/`.

The prior readiness artifact is a historical result. Preserve its accurate observation that the original dry-run emitted `Unknown` and `unavailable`; do not rewrite it to pretend the blocker never existed. The new qualification and final closure artifact must state that the future contract was corrected and superseded for new runs.

### 2.1 Established bounded evidence

The final closure may synthesize, within their original contracts:

- H-M1a — registered source snapshot assertion;
- H-V1a — independent acceptance verification;
- H-O1a — structured instrumentation completeness;
- H-V1b — evidence/provenance binding;
- H-I1a — pre-execution write prevention;
- H-OR1a — stable under the declared process-lifetime horizon;
- H-SR1a — stable under the declared reversible-cycle horizon;
- H-RCV1a — targeted recovery supported task-locally;
- Evaluation State Semantics v1;
- Document Ops Task Frame v1 and all 48 fixture qualifications;
- Reliability Protocol v0;
- qualified robustness and change/regression measurement substrates;
- held-out evaluation governance;
- the four-family generated-task substrate;
- the provider-neutral specialization execution substrate after requalification;
- the OpenAI/Codex dual-model operating baseline.

Do not expand these claims beyond their original task, sample, duration, platform, or evaluator boundaries.

---

## 3. Hard scope boundary

### 3.1 Authorized work

This plan authorizes only:

- future specialization schema and adapter cleanup;
- a new zero-model-call fake-candidate qualification run;
- minimal provider/model baseline clarification needed for ChatGPT-subscription accounting;
- definition and execution of H-P1a;
- deterministic DEV and validation generation from the qualified four-family substrate;
- at most six Terra optimizer calls;
- bounded Luna DEV and validation evaluation;
- post-freeze generation of the 32-instance blind inventory;
- the 96-entry measured blind schedule;
- H-P1a and bounded Terra-reference analysis;
- separate design-time and runtime resource accounting;
- a durable Phase 4 closure artifact;
- minimal indexes/navigation and retirement of this plan.

### 3.2 Explicitly prohibited

Do not execute or opportunistically clear:

```text
H-G1
H-W1
H-C1
H-R1
```

They remain `Not evaluated` unless a future architecture decision identifies a specific evidence gap and separately authorizes reopening one.

Also prohibited:

- fine-tuning or weight modification;
- workflow search beyond the frozen prompt/program-only H-P1a treatment;
- routing, cascading, escalation, recovery, or retry experiments;
- API-key authentication or fallback;
- usage-based API billing;
- public API price-table estimates as the actual bill for this experiment;
- a monetary spend ceiling or the retired `$25` proposal;
- silently buying, enabling, or changing billing paths;
- use of old VANTA fixtures as the true blind corpus;
- modification of imported material under `sources/` or `references/papers/`;
- modification or deletion of prior immutable run artifacts;
- architecture synthesis, architecture selection, implementation of a Phase 5 architecture, or Phase 5 start.

---

## 4. Shared research discipline

### 4.1 Define before run

Every model-backed stage must reference a full 40-character definition commit that predates its model calls. Before the first model call, commit and freeze:

- the exact H-P1a wording;
- C0, C1-selection eligibility, and C2 definitions;
- seed program bytes and SHA-256;
- optimizer prompts/procedure and visibility boundary;
- DEV and validation manifests and complete inventories;
- generator/evaluator code identities and configuration;
- output schema and evaluator rules;
- candidate size ceiling;
- model, reasoning, auth, billing, sandbox, tool, retry/recovery, and output envelopes;
- call/resource ceilings;
- invalidity and continuation rules;
- validation selection tuple;
- blind generation procedure;
- blind execution schedule algorithm;
- aggregation and interpretation rules;
- terminal record and ledger schemas.

`definition_commit` and `code_commit` in all new manifests are full commit SHAs, never abbreviations. A definition and its implementation may share one commit, but both fields remain explicit.

### 4.2 Separate empirical fields

All future terminal records use the canonical vocabularies from Evaluation State Semantics v1.

Actual outcome:

```text
success
partial
failure
unresolved
```

Empirical evidence status:

```text
sufficient
insufficient
invalid_binding
not_assessed
unresolved
```

Acceptance decision:

```text
accept
reject
abstain
not_applicable
```

Do not emit `Unknown` as an actual outcome or `unavailable` as empirical evidence status in any new record.

### 4.3 Preserve invalid attempts

Run directories are append-only and may not be overwritten. For any invalid attempt:

1. preserve the definition, raw events, outputs, manifests, and failure reason;
2. mark the attempt `invalid` and exclude it from valid aggregates;
3. do not repair its artifacts in place;
4. correct the cause in a later commit;
5. use a new run ID;
6. do not reuse blind evidence for a changed candidate.

No failure is hidden by git history rewriting, deletion, directory reuse, or a silent retry.

### 4.4 Resource vectors, not a synthetic cost scalar

Keep outcome, evidence, terminal behavior, resource use, design-time use, and runtime use separate. Do not create a unified reliability score or a synthetic lifecycle-cost number.

---

## 5. H-P1 parent and H-P1a

The parent H-P1 remains in `research/candidate-mechanism-hypotheses.md` and is not silently replaced:

> At fixed runtime model/tool envelope, an optimized structured-output program improves held-out task success over its unoptimized seed enough to offset its separately reported design-time cost.

Add the narrower final empirical sub-hypothesis:

### H-P1a — Luna Structured-Program Specialization

> Holding runtime model `gpt-5.6-luna`, reasoning effort `medium`, tool envelope, public task inputs, evaluator, generator, output contract, retry policy, and runtime execution envelope fixed, a structured-output program produced through bounded Terra-assisted design-time optimization improves post-freeze blind verified-success performance over the frozen unoptimized Luna seed program. Design-time optimization usage and runtime usage are reported separately.

H-P1a isolates a prompt/program-layer treatment at a fixed Luna runtime. Terra versus Luna runtime capability is not an H-P1a treatment.

### 5.1 Configurations

| ID | Runtime model | Reasoning | Program | Role in analysis |
| --- | --- | --- | --- | --- |
| C0 — Luna seed | `gpt-5.6-luna` | `medium` | frozen reasonable generic seed | primary control |
| C1 — Luna specialized | `gpt-5.6-luna` | `medium` | deterministically selected optimizer-generated candidate | primary treatment |
| C2 — Terra seed reference | `gpt-5.6-terra` | `medium` | exact same seed bytes and SHA as C0 | stronger-runtime reference only |

Primary causal comparison:

```text
C1 vs C0
```

C2 is not another H-P1 treatment. C2 versus C1 only characterizes bounded finite-sample runtime-capability substitution.

---

## 6. Provider, authentication, billing, and resource ceiling

### 6.1 Frozen execution identity

For every formal H-P1a optimizer, development, validation, and blind invocation, freeze:

```text
provider_id: openai
execution_surface: codex-cli
authentication_mode: chatgpt
billing_mode: chatgpt-subscription
api_key_fallback: prohibited
provider_cost_usd: Unknown
```

The exact runtime roles remain:

```text
strong:  gpt-5.6-terra
cheaper: gpt-5.6-luna
reasoning_effort: medium
```

Explicit `--model gpt-5.6-terra` or `--model gpt-5.6-luna` does not imply API-key authentication or usage-based billing. Codex CLI is the execution surface, not the model provider.

Before model calls, validate the baseline and active local catalog without making a model call. Record the resolved Codex path, Codex CLI version, catalog-check UTC time, baseline file hash, and the absence of a date-versioned immutable provider snapshot. If the intended CLI is not using the ChatGPT account/subscription path, stop; do not continue through an API key.

### 6.2 Subscription monetary semantics

For these ChatGPT-subscription runs:

- tokens, cached tokens, reasoning usage, call counts, and wall time are resource observations;
- token usage is not the actual subscription dollar cost;
- do not infer the provider bill from public API token prices;
- do not record zero monetary cost;
- `provider_cost_usd` remains the string `Unknown` unless defensible monetary evidence is directly attributable to this exact run;
- `price_basis` should state that no run-attributable subscription price basis is available;
- do not calculate a monetary break-even point without directly attributable evidence;
- monetary lifecycle-cost advantage is `Not established` when monetary evidence remains unavailable.

Phase 4 may close with monetary cost `Unknown` and monetary lifecycle advantage `Not established`.

### 6.3 Absolute call/resource ceiling

The experiment uses a resource ceiling, not a USD spend ceiling.

| Stage | Luna calls | Terra calls | Total maximum |
| --- | ---: | ---: | ---: |
| Seed on DEV: 24 tasks | 24 | 0 | 24 |
| Six optimizer-produced candidates on DEV | 144 | 0 | 144 |
| Terra optimizer: 2 replicates x 3 rounds | 0 | 6 | 6 |
| Candidate pool on validation: up to 7 x 16 | 112 | 0 | 112 |
| Blind C0 | 32 | 0 | 32 |
| Blind C1 | 32 | 0 | 32 |
| Blind C2 | 0 | 32 | 32 |
| **Absolute maximum** | **344** | **38** | **382** |

The stage ceilings are also binding:

```text
maximum Terra optimizer calls: 6
maximum blind measured schedule entries: 96
maximum total Luna model calls: 344
maximum total Terra model calls: 38
maximum total model calls: 382
no silent retries
no API-key fallback
no automatic billing-mode change
```

Duplicate or invalid candidates may reduce actual calls; unused budget is not permission to add another experiment, replicate, retry, candidate, or blind task.

---

## 7. Runtime and information isolation

All three measured configurations hold fixed, except for the declared model/program differences:

- reasoning effort `medium`;
- candidate-visible input bytes;
- output schema;
- evaluator and oracle;
- generator and generator configuration;
- tool envelope;
- retries `0`;
- recovery `0`;
- routing `none`;
- escalation `none`;
- external web/network tools `none`, except provider connectivity intrinsic to Codex transport;
- sandbox/approval contract;
- max-output policy;
- invocation adapter and input packing.

### 7.1 Isolated candidate workspace

Each candidate invocation runs in an experiment-local isolated workspace containing only:

- the exact candidate/program bytes;
- one candidate-visible task bundle;
- the frozen output schema or an equivalent schema supplied by the adapter;
- the minimal adapter-owned output target when required.

It must not contain or mount:

- the IRIS-X repository;
- `.git`;
- validation or blind siblings;
- hidden generation state;
- hidden oracle;
- evaluator code/configuration;
- expected validity or answer labels;
- other candidate outputs;
- optimizer transcripts;
- owner files or credentials.

Prefer a literal empty tool envelope. If the installed Codex CLI intrinsically exposes tools, constrain the CLI and OS sandbox as tightly as supported, prohibit all tool use in the program, inspect JSON events, and treat every tool attempt as a terminal task failure. If any tool actually accesses repository, hidden-oracle, sibling-task, external-web, or other forbidden bytes, the run is invalid for isolation breach.

### 7.2 Pre-measurement boundary qualification

Before blind generation or measured execution:

1. statically inspect and record the resolved CLI configuration and exposed capabilities;
2. validate that isolated workspaces contain only allowlisted paths;
3. run seed DEV/validation invocations through the exact planned adapter;
4. audit every emitted event for tool, filesystem, network-tool, routing, retry, recovery, and escalation activity;
5. prove that candidate-visible package hashes match the frozen manifests;
6. reject any unplanned capability use.

DEV and validation calls already included in the 382-call ceiling supply the dynamic boundary evidence; do not add an unbudgeted probe call. Any adapter change after this evidence requires a new full definition/code commit and revalidation before blind work.

---

## 8. Task, output, and evaluator contract

### 8.1 Generated families and fixed difficulty

Use exactly the four qualified IRIS-X-generated families:

```text
traceability-extraction-v0
terminology-consistency-v0
path-action-guard-v0
structured-simulation-v0
```

Use the current qualified generator configuration:

```json
{"count": 4}
```

Do not change task difficulty, generator logic, task family, evaluator, or output contract during optimization.

### 8.2 One shared output envelope

Freeze one strict JSON output envelope for all families, with exact top-level keys:

```json
{
  "schema_version": 1,
  "instance_id": "<supplied instance id>",
  "family_id": "<supplied family id>",
  "answer": {}
}
```

The frozen JSON Schema must set `additionalProperties: false`, bind `schema_version`, `instance_id`, and `family_id`, and use family-specific conditional definitions for `answer` matching the existing hidden-oracle shapes. The schema, serializer, canonicalization rule, and max-output rule are identical across C0/C1/C2 and all splits.

### 8.3 Independent evaluator

The evaluator operates only after output bytes are frozen and hashed. It receives the bound task identity, public-input hash, hidden-oracle identity, and candidate output, but the candidate never receives evaluator-only material.

Freeze family-level outcome adjudication before model calls:

- `success`: valid bound output and exact semantic equality with the independently derived oracle;
- `partial`: valid bound output with at least one independently correct required atomic element but not exact semantic equality;
- `failure`: no correct required atomic element, malformed/schema-invalid output, wrong instance/family binding, or a terminal provider/adapter/timeout event that establishes non-completion;
- `unresolved`: only when the actual task result genuinely cannot be adjudicated.

The required atomic elements are also frozen:

- traceability extraction: each required direct-reference ID is one atom;
- terminology consistency: each complete `(document_id, observed, canonical)` violation row is one atom;
- path/action guard: each complete proposal decision, including canonical path and reason, is one atom;
- structured simulation: exact transformed-records equality is one atom and exact changed-paths equality is a second atom.

Exact full-oracle equality is still required for `success`; partial overlap never becomes verified success. Freeze these rules in evaluator tests. Do not derive empirical truth from model claims or acceptance.

Freeze the system/adapter acceptance rule separately from empirical outcome:

- `accept` when a returned output is schema-valid and correctly bound to the supplied instance/family, regardless of semantic correctness;
- `reject` when returned output is malformed, schema-invalid, or incorrectly bound;
- `not_applicable` when no candidate output exists because execution failed before a return;
- `abstain` is reserved and is not produced by this experiment unless a later definition revision occurs before any model call.

This separation makes a schema-valid but empirically partial/failed output a measurable `false_success`; adapter acceptance does not establish truth.

Freeze the terminal execution vocabulary:

```text
completed  # provider returned output bytes; semantic/schema quality is separate
failed     # provider/adapter/timeout/subscription/tool terminal non-completion
invalid    # returned execution cannot be validly bound under the task/output contract
```

Run-level validity remains separate from an episode's terminal status.

Evidence adjudication:

- use `sufficient` when bound output/oracle or bound terminal evidence is adequate to adjudicate;
- use `insufficient` when an output exists but required empirical support is inadequate;
- use `invalid_binding` when task/input/output identity cannot be bound;
- use `not_assessed` only when the evaluator is deliberately not invoked under the frozen terminal rule;
- use `unresolved` only for genuinely unresolved evidence.

For a provider, adapter, or timeout failure with no candidate output and clear non-completion, record:

```text
actual_outcome: failure
empirical_evidence_status: sufficient
acceptance_decision: not_applicable
verified_success_eligibility: false
terminal_execution_status: failed
```

If non-completion is clear but empirical evaluation was intentionally not performed, `not_assessed` may replace `sufficient` only under a predeclared terminal rule. If output existence or task completion genuinely cannot be determined, use `actual_outcome: unresolved` and a compatible evidence status. Never use `Unknown` or `unavailable`.

Malformed/schema-invalid output is a measured candidate failure, not an invalid experiment by itself. A broken or non-independent evaluator is an experiment-level invalidity.

---

## 9. Seed program and allowed optimization

### 9.1 Seed quality

The seed must be a reasonable generic structured-output program, not a deliberately weak straw candidate. Freeze it as UTF-8 with LF line endings and a final newline. C0 and C2 load the exact same seed file bytes and SHA-256.

The seed must contain, at minimum, the following substantive instructions without task answers:

```text
You solve one supplied IRIS-X generated Document Ops task.

Follow the supplied task contract exactly. Use only the supplied candidate-visible public information. Do not use tools, the filesystem, the network, external lookup, hidden information, or unstated assumptions. Do not fabricate facts.

Read instance_id, family_id, public_input, and the required output schema. Perform the requested public operation, preserve every required ordering rule, and place the result in answer. Before responding, check the result against the public input, check identifiers and required fields, and check that no extra fields or prose remain.

Return exactly one JSON object matching the required schema. Return no markdown fences, commentary, explanation, or additional text.
```

Additional wording may improve schema clarity, but must remain generic and must not encode task answers, validation content, or blind content.

### 9.2 Candidate size ceiling

Freeze before optimization:

```text
maximum candidate program size: 12 KiB UTF-8 (12,288 bytes)
```

The size is measured on exact frozen bytes. Oversize optimizer output is a retained invalid candidate output; it is not silently truncated or retried. Program bytes, prompt/input bytes, and token overhead are recorded.

### 9.3 Optimizer mutation boundary

Terra may modify only the prompt/program layer:

- structured instruction text;
- deterministic decision procedures;
- generic family guidance;
- examples derived only from DEV;
- checking procedures.

It may not modify:

- Luna identity;
- reasoning effort;
- tool/sandbox/approval envelope;
- shared output schema;
- evaluator or oracle;
- generator, configuration, or difficulty;
- retry/recovery/routing/escalation policy;
- DEV, validation, or blind contents;
- provider/authentication/billing mode;
- hidden oracle or validation/blind feedback.

---

## 10. Split generation and visibility

### 10.1 Frozen sizes

| Split | Per family | Families | Total |
| --- | ---: | ---: | ---: |
| DEV | 6 | 4 | 24 |
| VALIDATION | 4 | 4 | 16 |
| POST-FREEZE BLIND | 8 | 4 | 32 |

Old VANTA fixtures are not the blind corpus.

### 10.2 DEV and validation generation

Before optimization and before the H-P1a definition commit:

1. freeze generator and evaluator code identities;
2. generate distinct DEV and validation master seeds using recorded OS cryptographic randomness;
3. derive every family/slot seed deterministically using a frozen SHA-256 derivation rule;
4. generate all 24 DEV and 16 validation instances with `{"count": 4}`;
5. validate same-seed reproducibility, seed uniqueness, split disjointness, oracle determinism, public-input sufficiency, and package leakage;
6. freeze the complete inventories, manifests, public-input hashes, hidden-oracle hashes, and bytes;
7. commit the definition, code, seed program, DEV, and validation material before any model call.

Generation seeds, hidden states, hidden oracles, expected answers, candidate-freeze metadata, and answer-revealing metadata never enter candidate-visible packages.

### 10.3 DEV visibility

DEV is permanently `development-visible`. The Terra optimizer may receive:

- the current candidate bytes;
- all 24 DEV public task bundles;
- Luna outputs for that candidate;
- independent evaluator results;
- task-local failure categories;
- item-level DEV feedback;
- design-time resource observations for that candidate.

It may not receive hidden generator state except the evaluator-derived feedback explicitly allowed above.

### 10.4 Validation isolation

Validation is frozen before optimization, but every Terra optimizer call is isolated from:

- validation public tasks;
- validation outputs;
- validation hidden oracles;
- validation item-level feedback;
- validation aggregates or rankings.

Generate every optimizer candidate before any validation evaluation. Evaluate the frozen candidate set once on the same 16 validation tasks. Freeze all validation outputs before opening evaluator results. There is no iterative tuning, new optimizer call, manual edit, or candidate repair after validation results are available.

---

## 11. Bounded design-time optimization

Use only:

```text
optimizer model: gpt-5.6-terra
reasoning_effort: medium
optimizer role: design-time only
replicates: opt-01, opt-02
revision rounds per replicate: 3
maximum Terra optimizer calls: 6
```

Both replicates start from identical seed bytes and the same frozen seed-on-DEV evidence. Do not claim provider randomness is seed-controlled; Codex exposes no frozen deterministic sampling seed for this plan.

Each Terra optimizer call also runs in an isolated experiment-local workspace with no repository, validation, blind, sibling-replicate, external-web-tool, or hidden-oracle access. Its complete input is a frozen allowlisted payload assembled by the orchestrator. Audit optimizer JSON events for prohibited tool/capability use under the same no-silent-retry discipline.

Within each replicate:

1. round 1 receives the seed bytes and seed DEV evidence;
2. freeze and validate the returned candidate bytes;
3. evaluate that candidate once on all 24 DEV tasks using Luna;
4. round 2 receives only its own current candidate and allowed DEV evidence;
5. repeat for round 3;
6. prevent cross-replicate candidate/feedback leakage.

Use IDs such as:

```text
opt-01-r01
opt-01-r02
opt-01-r03
opt-02-r01
opt-02-r02
opt-02-r03
```

Every optimizer call produces a terminal record. Provider error, timeout, malformed optimizer envelope, prohibited content, or oversize output receives no retry. An invalid round terminates that replicate because there is no valid next current candidate; the other replicate may continue. Unused rounds do not become replacement calls.

Evaluate the seed once on all 24 DEV tasks. Evaluate each valid optimizer-produced candidate once on all 24 DEV tasks. Preserve failed optimizer and candidate attempts in the design-time ledger.

Deduplicate byte-identical optimizer candidates by program SHA-256 before validation while retaining all optimizer provenance. A duplicate SHA is one candidate program, not an extra validation lottery ticket. Use the lexical candidate ID only to select canonical provenance for identical bytes.

---

## 12. One-shot validation and deterministic C1 selection

Candidate pool:

```text
seed
+
up to six unique, statically valid optimizer-produced candidates
```

Run every unique candidate program once over all 16 frozen validation tasks with Luna, medium reasoning, zero retries, and the exact planned runtime adapter. The seed remains C0 and is not eligible to become C1. C1 must be an optimizer-generated candidate.

Freeze the following deterministic selection tuple before validation results are opened. Among optimizer-generated eligible candidates, choose the lexicographically lowest tuple:

```text
(
  -verified_success_count,
  -actual_success_count,
  false_success_count,
  malformed_output_count,
  invalid_terminal_count,
  total_model_calls,
  total_input_tokens_if_complete_else_infinity,
  total_output_tokens_if_complete_else_infinity,
  total_reasoning_tokens_if_complete_else_infinity,
  total_wall_time_ns,
  candidate_bytes,
  candidate_sha256
)
```

Cached input usage remains separately reported and is not monetary cost. Resource keys are late tie-breakers only; they do not override success/evidence behavior.

After selection:

1. write the exact selected program bytes once;
2. compute and verify SHA-256;
3. close the design-time ledger;
4. record selection reconstruction from raw validation records;
5. commit the C1 freeze before any blind master seed is generated;
6. prohibit every later candidate edit.

If no valid optimizer-generated candidate exists, H-P1a cannot form C1. Preserve the design-time attempt, mark it invalid/incomplete, do not generate blind data, do not substitute the seed, do not add optimizer calls, and report the blocker. Phase 4 cannot close from that attempt.

---

## 13. Post-freeze blind generation

Only after the selected C1 bytes and SHA are committed:

1. generate a new 256-bit master blind seed from OS cryptographic randomness;
2. deterministically derive four family seeds and eight per-family slot seeds using the frozen SHA-256 derivation rule;
3. generate exactly 8 instances per family, 32 total, using `{"count": 4}`;
4. run the complete leakage, reproducibility, determinism, public-sufficiency, split-disjointness, identity, and validity audit;
5. bind every manifest to the frozen C1 SHA, generator/evaluator identities, and definition commit;
6. freeze the complete valid inventory and all generation failures;
7. freeze the complete 96-entry execution schedule;
8. commit a blind-authorization milestone before the first blind model invocation.

Each of the 32 declared slots receives exactly one generation attempt. There is no silent regeneration or replacement seed. A generation or validation failure is terminal evidence and makes the required 32-valid-instance H-P1a blind attempt invalid before model execution. Preserve it; do not cherry-pick the remaining tasks or weaken inclusion rules.

No valid blind task may be discarded because it is difficult, unusual, produces failure, or changes the aggregate.

---

## 14. Frozen blind schedule and measured execution

### 14.1 Schedule construction

Freeze a deterministic interleaving algorithm before blind generation:

1. sort the 32 valid instance IDs by `SHA-256(master_blind_seed || instance_id)`;
2. for sorted task index `i`, rotate configuration order:
   - `i mod 3 = 0`: C0, C1, C2;
   - `i mod 3 = 1`: C1, C2, C0;
   - `i mod 3 = 2`: C2, C0, C1;
3. assign monotonic schedule indices 1 through 96;
4. hash and commit the schedule.

This avoids executing all Luna calls and then all Terra calls. Do not reorder after provider, outcome, latency, or usage observations.

### 14.2 One invocation per entry

Execute every schedule entry exactly once:

```text
32 tasks x 3 configurations = 96 measured invocation attempts
retry_count = 0
recovery_count = 0
```

Freeze and hash all candidate outputs before batch oracle evaluation. Provider/adapter terminal failures are already terminal records and are not rerun.

### 14.3 Required per-call record

Each terminal record preserves at least:

```text
UTC start/end timestamp
experiment_id, run_id, schedule_index
definition_commit and code_commit as full SHAs
provider_id = openai
execution_surface = codex-cli
authentication_mode = chatgpt
billing_mode = chatgpt-subscription
provider_cost_usd = Unknown
exact model ID and model role
reasoning_effort = medium
program/candidate ID, bytes, and SHA-256
baseline ID and baseline-file SHA-256
Codex CLI version and resolved path
catalog-check time
task, family, instance, split, and generation identities
candidate-visible input hash
raw event-stream hash
output bytes/hash or explicit absence
output-schema status and malformed flag
input, cached-input, output, and reasoning usage if exposed
model call count
tool/retry/recovery/routing/escalation observations
wall time
terminal/provider/subscription event
actual_outcome
empirical_evidence_status
acceptance_decision
verified_success_eligibility
terminal_execution_status
invalid reason when applicable
```

Do not record credentials.

---

## 15. Subscription-limit continuation rule

Cross-reset continuation is allowed, but only as a transport pause under the following fully frozen rule.

When a ChatGPT subscription limit is encountered:

1. emit a terminal `subscription_limit_event` for the current scheduled attempt;
2. do not retry that attempt;
3. stop before attempting the next schedule entry;
4. preserve and hash all partial artifacts;
5. do not open blind aggregate results or use partial outcomes to alter any candidate, seed, task, evaluator, schedule, or policy;
6. wait for the same ChatGPT subscription access to reset;
7. before resuming, revalidate the exact account/auth mode, billing mode, Codex path/version, model catalog, definition/code commits, candidate bytes/SHA, blind inventory, schedule hash, sandbox, and adapter;
8. resume at the next never-attempted schedule index under the same run ID;
9. record the pause interval and reset event.

The limit-hit entry remains a measured terminal failure when non-completion is established. It is not replayed after reset. Continuation consumes no new candidate or blind information and changes no billing path.

Continuation is prohibited if any frozen identity or policy changed, if the account/authentication path differs, if the CLI/runtime boundary changed materially, if artifacts cannot establish the next untouched schedule entry, or if candidate/validation/blind information was used for adaptation. In that case:

- preserve the partial attempt;
- mark the run `invalid`;
- do not switch to an API key;
- do not purchase or enable a second billing path;
- do not modify the candidate based on partial/blind outcomes;
- do not silently exceed the 382-call ceiling;
- obtain a new authorization for a new run ID and resource ceiling;
- use a newly frozen blind seed/inventory/schedule for the new run.

The same pause rule applies during design-time and validation: the limit-hit scheduled call is terminal and not retried; resume only at the next untouched planned call when all frozen conditions still hold.

---

## 16. Separate accounting ledgers

### 16.1 Design-time ledger

Close this ledger before blind seed generation. Include:

- Terra optimizer calls and terminal failures;
- Luna seed and candidate DEV calls;
- Luna one-shot validation calls;
- input/cached/output/reasoning usage when exposed;
- call counts and failed attempts;
- prompt/program bytes and SHA identities;
- candidate count and deduplication;
- optimizer replicates and revision rounds;
- wall time and pause time;
- human intervention, including zero when directly observed;
- candidate evaluations;
- subscription-limit events;
- `provider_cost_usd: Unknown`.

### 16.2 Runtime measured ledger

Include only the frozen blind comparison:

- C0 Luna seed;
- C1 Luna specialized;
- C2 Terra seed reference;
- input/cached/output/reasoning usage when exposed;
- call counts, failures, and subscription-limit events;
- wall time;
- prompt/program bytes;
- output/event/artifact bytes when useful;
- retries and recovery, both frozen at zero;
- `provider_cost_usd: Unknown`.

Do not amortize design-time usage into runtime usage without a separately declared deployment horizon. This plan declares no deployment horizon.

### 16.3 Permitted resource reporting

A non-monetary resource frontier may compare verified success, terminal/evidence profile, model calls, token categories, wall time, and program bytes. Label it explicitly as non-monetary. Do not call it dollar cost, provider bill, monetary lifecycle cost, or break-even.

---

## 17. Primary H-P1a analysis

The unit of paired comparison is one blind instance evaluated under C0 and C1.

Report at least:

- actual success count/rate;
- verified-success count/rate;
- partial and failure counts;
- unresolved counts;
- false success and false failure;
- malformed/schema-invalid output;
- evidence status distribution;
- terminal/provider/subscription failures;
- results by each of the four families;
- paired discordant task IDs:
  - C1 verified success / C0 not verified success;
  - C0 verified success / C1 not verified success;
- per-task outcome/evidence transition matrix;
- runtime resource vector;
- program bytes and prompt/input overhead;
- all invalid attempts separately.

Primary estimand:

```text
Delta_verified_success = verified_success(C1) - verified_success(C0)
```

Do not impose an arbitrary `+10%` threshold and do not turn this finite sample into a general model claim.

### 17.1 Frozen interpretation rule

Use exactly one primary H-P1a result label for a valid run:

#### `Supported — task-local`

C1 has strictly greater blind verified-success count than C0, with no increase in false-success count and no increase in malformed or invalid-terminal count. Report any runtime-resource expansion as a separate qualification; it does not become a fabricated monetary conclusion.

#### `Rejected — task-local`

C1 is empirically worse on the frozen primary outcome, meaning lower verified-success count, or any observed gain is accompanied by a worse false-success/malformed/invalid-terminal profile that defeats the proposed reliable specialization improvement.

#### `Mixed evidence`

Use for non-dominating results, including:

- aggregate verified-success tie with family trade-offs;
- validation improvement that does not survive blind;
- verified success improves but false-success, malformed, or invalid-terminal behavior worsens;
- actual success and verified success move in different directions;
- resource expansion creates a material non-monetary trade-off without a defensible scalar decision rule;
- terminal/provider failures prevent a clean directional conclusion but the run remains valid.

`Invalid run` is not a substantive H-P1a result and cannot close Phase 4.

---

## 18. Terra reference analysis

Analyze C2 versus C1 and C2 versus C0 descriptively on the same paired blind tasks. Keep C0/C2 seed bytes identical so the only declared configuration difference is the runtime model.

The strongest permitted substitution statement is:

```text
Observed finite-sample runtime-capability substitution — task-local
```

Use it only if C1 reaches or exceeds C2 verified-success and actual-success counts and has no worse false-success, malformed, invalid-binding, unresolved, or terminal-failure profile on this sample. Report runtime resource vectors separately.

Otherwise use bounded statements such as:

```text
Specialization improved Luna but did not match Terra under this horizon.
```

or:

```text
Current specialization evidence does not support runtime-capability substitution.
```

Do not claim model equivalence, provider immutability, general capability parity, or monetary substitution.

---

## 19. Work packages and commit gates

### WP0 — Latest-main preflight and plan activation

1. fetch remote `main` and record its full SHA;
2. compare it with planning baseline `a859399eafb294ea03290123c285c127426dfb5b`;
3. reload applicable instructions and controlling records;
4. inspect dirty state and preserve unrelated owner work;
5. add this plan at `docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`;
6. commit the plan before substantive work;
7. run non-model repository preflight checks.

No model call is permitted in WP0.

### WP1 — Specialization schema blocker cleanup and requalification

Required changes:

- amend the future execution contract to canonical outcome/evidence vocabulary;
- amend the fake adapter failure path;
- add tests that reject `Unknown` actual outcome and `unavailable` evidence status in all future records;
- add tests for clear failure versus genuinely unresolved behavior;
- ensure new manifests store full `definition_commit` and `code_commit` SHAs;
- preserve the original `dry-run-20260901-local-01` directory byte-for-byte;
- commit contract/code/test changes before running qualification;
- run a new deterministic fake-candidate qualification under a new run ID;
- commit new qualification results separately;
- update substrate README/navigation only to identify the superseding future qualification.

WP1 exit gate:

- all specialization-contract tests pass;
- successful fake path remains verified-success eligible;
- explicit failure fake is `failure` or, only if truly ambiguous, `unresolved`;
- no new record contains forbidden vocabulary;
- hidden oracle remains absent from candidate input;
- design/runtime ledgers remain separate;
- unknown provider cost remains `Unknown`;
- no model/network/paid API call occurred;
- old run is unchanged;
- new run directory is immutable.

### WP2 — Provider/accounting clarification and H-P1a definition

- minimally clarify the model-baseline decision/config/checker where needed so ChatGPT-subscription resource ceilings are not described as API-dollar spend ceilings;
- retain project-level per-run auth/billing selection while freezing H-P1a to ChatGPT subscription;
- create the H-P1a experiment definition, schemas, adapter, evaluator, tests, seed, and directory layout;
- generate and freeze DEV and validation;
- freeze all budgets, policies, selection rules, and analysis rules;
- validate runtime isolation statically;
- commit a full H-P1a definition/code/data milestone before the first model call.

Suggested experiment root, replacing the date once and then freezing it:

```text
experiments/exp-YYYY-MM-DD-luna-structured-program-specialization/
```

Suggested structure:

```text
README.md
definition/
  experiment-definition.json
  output-schema.json
  optimizer-output-schema.json
  selection-rule.json
  seed-program.txt
inputs/
  dev/
  validation/
design/
  optimizer-records/
  candidates/
  dev-terminal-records.jsonl
  validation-terminal-records.jsonl
  design-ledger.json
runs/
  <run-id>/
    blind-generation/
    schedule.json
    raw/
    terminal-records.jsonl
    results.json
    interpretation.md
    run-manifest.json
scripts/
tests/
```

Do not put runnable inputs or raw outputs in `research/`.

### WP3 — DEV baseline and bounded optimization

- evaluate seed on 24 DEV tasks with Luna;
- execute at most six Terra optimizer calls under the two-replicate/three-round procedure;
- evaluate each valid candidate once on all DEV tasks with Luna;
- preserve every terminal attempt and resource observation;
- use no validation or blind information;
- use no silent retry.

### WP4 — One-shot validation and candidate freeze

- finish all optimizer candidates before validation;
- evaluate seed plus each unique valid optimizer candidate once on all 16 validation tasks;
- freeze outputs before evaluation;
- open validation results once;
- reconstruct the selection tuple from raw records;
- select an optimizer-generated C1;
- freeze C1 bytes/SHA and close design ledger;
- commit candidate freeze before blind seed generation.

### WP5 — Blind generation and authorization

- generate a new master blind seed only after WP4 commit;
- generate/audit/freeze all 32 blind instances;
- freeze the 96-entry interleaved schedule;
- commit inventory, manifest hashes, schedule, and authorization before blind calls.

### WP6 — Blind execution and result interpretation

- execute the complete schedule exactly once;
- obey the subscription-limit continuation rule;
- freeze outputs before evaluator access;
- independently evaluate all records;
- reconstruct aggregates from raw records;
- interpret C1 vs C0 under the frozen rule;
- characterize C2 only as a reference;
- commit raw results and reviewed interpretation without rewriting invalid attempts.

### WP7 — Phase 4 accumulated-evidence synthesis and closure

Create:

```text
research/phase-4-closure.md
```

The closure artifact must distinguish:

- supported task-local constraints;
- stable-under-horizon reliability observations;
- rejected or mixed mechanisms;
- qualified reusable substrate;
- unresolved parent hypotheses;
- H-P1a result and its finite-sample boundary;
- bounded Terra-reference result;
- provider alias/temporal-drift uncertainty;
- design-time versus runtime resource use;
- monetary cost `Unknown` and monetary lifecycle advantage `Not established` unless direct evidence exists;
- generalization, difficulty, representativeness, production, concurrency, duration, and external-action limits;
- H-G1/H-W1/H-C1/H-R1 as `Not evaluated`;
- invalid attempts, if any.

Update `research/candidate-mechanism-hypotheses.md` and navigation minimally so H-P1a is recorded without falsely establishing the parent H-P1. Do not rewrite earlier result artifacts.

Choose exactly one closure decision:

```text
Phase 4 complete — evidence sufficient to begin architecture synthesis
```

or:

```text
Phase 4 not complete — blockers listed
```

The first decision means a later, separately authorized Phase 5 may begin architecture synthesis. The closure artifact itself must not synthesize architecture.

### WP8 — Validation, retirement, and hard stop

- execute all required validation;
- confirm source and historical-run preservation;
- add a retirement record to this temporary plan only if all exit criteria pass;
- commit the closure/retirement milestone;
- report the handoff;
- STOP.

---

## 20. Experiment-level validity and failure rules

A model terminal failure is not automatically an invalid experiment. It is a measured failure when identity, schedule, and evidence remain valid.

The H-P1a run is invalid if any of the following occurs:

- no earlier full definition commit exists;
- definition or code SHA is abbreviated, missing, or cannot be resolved;
- C0 and C2 seed bytes differ;
- C1 is not optimizer-generated;
- C1 changes after validation selection or after blind generation;
- validation information reaches a Terra optimizer call;
- blind content or oracle reaches optimization;
- generator, evaluator, difficulty, output schema, reasoning effort, retry/recovery, or runtime envelope drifts outside the declared factors;
- candidate execution gains repository, sibling-task, hidden-oracle, external-web-tool, or other forbidden access;
- a schedule entry is silently retried, replaced, omitted, or reordered;
- a valid blind task is cherry-picked away;
- a run directory or raw record is overwritten;
- API-key fallback or billing-mode change occurs;
- provider cost is fabricated as zero or from public API price tables;
- raw aggregates cannot reconstruct reviewed results;
- the independent evaluator cannot be established;
- the subscription continuation rule is violated;
- any call/resource ceiling is exceeded;
- an invalid generation slot is silently regenerated;
- old immutable evidence is modified.

The following remain valid terminal evidence when recorded under the frozen contract:

- malformed output;
- candidate schema failure;
- provider failure;
- timeout;
- blocked tool attempt;
- subscription-limit event;
- partial/failure/unresolved outcome;
- optimizer candidate failure;
- missing resource fields recorded as `Unknown`.

---

## 21. Required validation

Run from repository root and report only commands actually executed.

At minimum:

```powershell
python tools\model_baseline_check.py --check-local-catalog
python -m unittest discover -s experiments\substrates\model-specialization-v0\tests -v
python -m unittest discover -s experiments\substrates\docops-generated-heldout-v0\tests -v
python -m unittest discover -s experiments\exp-YYYY-MM-DD-luna-structured-program-specialization\tests -v
python tools\repository_check.py
git diff --check
```

Also:

- compile every changed Python file with `python -m py_compile`;
- verify all new commit fields are full 40-character SHAs resolving to commits;
- reproduce DEV, validation, and blind generation from frozen seeds;
- prove split seed/instance/public-input hashes are disjoint;
- rerun leakage audits;
- reconstruct design and runtime call counts from raw terminal records;
- reconstruct every candidate selection key from validation records;
- reconstruct all results from raw terminal records;
- verify C0/C2 seed byte identity;
- verify C1 SHA against exact bytes;
- verify the blind schedule hash and one-attempt coverage;
- verify every terminal record uses canonical outcome/evidence vocabulary;
- verify `authentication_mode`, `billing_mode`, and `provider_cost_usd` on every model-backed record;
- verify retry/recovery/routing/escalation remain zero/none;
- verify source and paper trees match the starting commit;
- verify every pre-existing run directory matches the starting commit;
- verify the original specialization dry-run remains unchanged.

If a command is unavailable or a field is not exposed, record `Unknown` or the exact limitation. Do not claim a check ran when it did not.

---

## 22. Exit criteria

This plan completes only when all of the following are true:

1. specialization schema cleanup is committed;
2. a new fake-candidate qualification run passes under canonical vocabulary;
3. provider/model/auth/billing/resource semantics are frozen;
4. H-P1a has a full definition commit before any model call;
5. DEV and validation protocols and inventories are frozen;
6. bounded design-time optimization is complete within six Terra optimizer calls;
7. deterministic validation selection is reconstructable;
8. optimizer-generated C1 bytes/SHA are frozen before blind generation;
9. all 32 blind tasks pass leakage/validity audit without cherry-picking;
10. the 96-entry schedule is frozen and completely attempted once;
11. design-time and runtime resource ledgers are separate and reconstructable;
12. H-P1a has a valid `Supported — task-local`, `Mixed evidence`, or `Rejected — task-local` interpretation;
13. Terra reference is interpreted without treating it as H-P1 treatment or claiming equivalence;
14. accumulated Phase 3/4 evidence is synthesized within original boundaries;
15. monetary cost remains accurately `Unknown`/`Not established` unless direct evidence exists;
16. H-G1/H-W1/H-C1/H-R1 remain `Not evaluated`;
17. `research/phase-4-closure.md` records an explicit closure decision;
18. required validation and preservation checks pass;
19. this plan is retired only after the durable closure is committed;
20. no architecture synthesis or Phase 5 work has started.

A negative H-P1a result satisfies item 12. An invalid run does not.

---

## 23. Commit discipline

Prefer the following coherent milestones:

1. activate this final temporary plan;
2. define/fix specialization schema, adapter, tests, and full-SHA manifests;
3. commit new fake-candidate qualification result;
4. clarify subscription accounting and commit the full H-P1a definition with frozen DEV/validation;
5. commit design-time optimizer/DEV/validation records and the selected C1 freeze;
6. commit post-freeze blind inventory, leakage audit, and schedule authorization;
7. commit blind raw results and reviewed interpretation;
8. commit Phase 4 closure, navigation, validation record, and plan retirement.

The exact grouping may change only when define-before-run ordering remains provable and reviewable. Push definition/freeze milestones durably before relying on them for later calls when repository policy permits.

Never amend or rebase away a definition, failure, invalid attempt, qualification, candidate freeze, blind authorization, or result commit after it has become evidence.

---

## 24. Autonomous execution and owner-interruption boundary

Proceed without owner interruption for routine bounded decisions already frozen by this plan, including individual model failures, malformed candidates, family-level outcome trade-offs, subscription reset pauses that satisfy the continuation rule, and a negative H-P1a result.

Stop and request owner direction only for:

- authentication that is not already connected ChatGPT subscription access;
- any request to use an API key or different billing path;
- a required call-budget expansion or new experiment run after invalidation;
- zero eligible optimizer-generated candidates;
- a material conflict between latest `main` and this plan;
- evidence that invalidates the generated-task or oracle strategy;
- destructive action outside validated experiment-local copies;
- repository protection or permission that prevents required durable definition commits;
- a material scope change.

Do not weaken the protocol to avoid a blocker.

---

## 25. Required final handoff

Report:

### Repository

- planning baseline;
- actual starting `main` full SHA;
- final full SHA;
- commit sequence;
- changed files;
- whether milestones were pushed.

### Blocker cleanup

- corrected schema/adapter paths;
- old immutable run preservation;
- new qualification run ID;
- qualification result;
- full definition/code SHAs;
- zero model/network/API calls for qualification.

### H-P1a definition and design

- experiment/run IDs;
- seed/C0/C2 byte identity and SHA;
- optimizer IDs and actual calls;
- DEV/validation inventories;
- candidate pool, failed/duplicate candidates, and selection reconstruction;
- C1 ID/SHA/bytes;
- closed design ledger;
- auth/billing/resource ceiling confirmation.

### Blind

- candidate-freeze commit before blind seed generation;
- generator/evaluator/config identities;
- 32-instance inventory and leakage result;
- schedule hash and 96-entry coverage;
- subscription-limit events and continuation, if any;
- invalid attempts.

### Results

- C1 vs C0 aggregate, per-family, paired-discordant, terminal/evidence, and resource results;
- exactly one H-P1a interpretation label;
- bounded C2 reference result;
- design/runtime ledgers separately;
- `provider_cost_usd: Unknown` unless directly established;
- monetary lifecycle-cost advantage status.

### Phase 4 closure

- accumulated supported task-local constraints;
- stable-under-horizon observations;
- rejected/mixed mechanisms;
- qualified reusable substrates;
- unresolved parents and generalization limits;
- mechanisms left `Not evaluated`;
- exact closure decision.

### Validation and preservation

- exact commands and results;
- unchanged `sources/` and `references/papers/`;
- unchanged historical run artifacts;
- no silent retries;
- no API-key fallback;
- no billing-mode change;
- no H-G1/H-W1/H-C1/H-R1;
- no architecture synthesis;
- no Phase 5.

Then **STOP**.

---

## 26. Hard stop

After a valid H-P1a interpretation, bounded Terra-reference comparison, accumulated-evidence synthesis, explicit Phase 4 closure decision, validation, and plan retirement:

**STOP.**

Do not turn the closure evidence into an architecture in this plan. Do not implement an architecture. Do not start Phase 5. A future owner instruction must separately authorize architecture synthesis.

---

## 27. Retirement record

- **Retired on:** 2026-09-03 Asia/Taipei
- **Actual starting main:** `a859399eafb294ea03290123c285c127426dfb5b`
- **Valid design run:** `design-20260902-chatgpt-03`
- **Valid blind run:** `blind-20260902-chatgpt-03`
- **Definition/code commit:** `9815003b02aa5868a7582960db97cd1138e5709e`
- **Candidate-freeze commit:** `6ef4c9d09e6124a9cb6c47f6b12427be29dea19e`
- **Blind-authorization commit:** `20f8c229aa2bf8bfd1b4fb8ffcaf4bc815e28523`
- **Blind-result commit:** `972b6b99b0b7f99e9738721a42015b49197fb216`
- **Durable closure commit:** `f8536893d693c3d851ef6ef02d1d5c0792ae8689`
- **H-P1a result:** `Supported — task-local`
- **Terra reference:** `Observed finite-sample runtime-capability substitution — task-local`
- **Validation record:** `docs/phase-4-closure-validation.md`

All exit criteria were checked before retirement. The exact closure decision is:

```text
Phase 4 complete — evidence sufficient to begin architecture synthesis
```

This retirement ends the authority of this temporary execution plan. It does not itself authorize or perform architecture synthesis, architecture implementation, or Phase 5. Those require a new owner-authorized scope. The hard stop remains in force.
