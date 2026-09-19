# Decision 0005: Authorize the Kaggle Offline Handoff for ARC-AGI-2 Trial 001

Status: Accepted

Date: 2026-09-19

## Context

Decision 0004 admitted ARC-AGI-2 Trial 001 on a local/offline execution path,
authorized repository implementation, official-source materialization, offline
validation, and preflight, and kept the real model or solver run behind a
separate explicit owner authorization.

The owner has since selected an NVIDIA RTX PRO 6000 96 GB made available in a
Kaggle notebook as the intended execution hardware. The owner has also selected
an explicit manual transport path: build a ZIP package locally, upload it as a
private Kaggle Dataset, run a network-disabled notebook against that immutable
input, download the complete notebook output, and place it in a designated
repository-local `.irisx/` location for validation and evaluation.

This is a material change to the Decision 0004 execution venue and data
transport boundary. It is not an implementation preference. This decision
records that change without rewriting Decision 0004 or changing its domain,
data, intervention, evaluator, acceptance, package, or real-run authorization
boundaries.

## Decision

ARC-AGI-2 Trial 001 may be implemented for a Kaggle-hosted, network-disabled
notebook execution path with manual, digest-bound ZIP transport.

This decision authorizes repository implementation, local package
materialization, package verification, notebook construction, result import,
offline validation, and preflight for that path. It does **not** authorize the
real Trial 001 model run. A real run still requires a later explicit owner
authorization after every model, package, environment, resource, retention,
and preflight binding is complete.

## Relationship to Decision 0004

This decision supersedes Decision 0004 only for these points:

- the intended execution venue is a Kaggle notebook using one NVIDIA RTX PRO
  6000 96 GB rather than the repository host;
- deliberate manual upload and download are authorized transport operations;
  and
- private Kaggle Datasets and the complete downloaded notebook output are
  authorized transient artifact locations under the controls below.

The following Decision 0004 boundaries remain unchanged:

- the domain is ARC-AGI-2;
- the official ARC source and pinned commit remain
  `arcprize/ARC-AGI-2@f3283f727488ad98fe575ea6a5ac981e4a188e49`;
- only the official public training split may influence specialization;
- the complete official 120-task public evaluation split remains frozen;
- third-party, semi-private, and private ARC data remain prohibited;
- evaluator ground truth remains isolated from every solver-facing artifact;
- Trial 001 permits only the existing `prompts_programs` specialization
  difference;
- baseline and candidate use the same model and execution envelope;
- Trial 001 performs no weight training, fine-tuning, retrieval, routing,
  ensemble, workflow search, or additional model-call allocation;
- official pass@2 scoring and the five-percentage-point P2 acceptance gate
  remain unchanged;
- external paid spend remains limited to USD 0; and
- the deployment target remains a self-contained, single-machine, offline
  ARC-AGI-2 research solver package.

Kaggle is an execution venue, not an external model provider. Upload and
download occur before and after the measured notebook execution. Network access
during the measured execution remains prohibited.

## Model binding

The selected Trial 001 base model is the official post-trained checkpoint:

```text
repository: Qwen/Qwen3.8-27B
revision: 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
license: Apache-2.0
```

The checkpoint is selected as a frozen-weight model for Trial 001. Its
selection makes no ARC-AGI-2 performance claim before measurement.

The repository implementation may provide a deliberate, separately invoked
model-materialization path that acquires only this exact official revision,
records source provenance and per-file SHA-256 digests, verifies the applicable
license metadata, and creates an immutable local model package. Default tests,
validation, package inspection, and preflight must not download the model.

No model download may occur from inside the Kaggle notebook. The exact model
artifact used by the notebook must be uploaded from the verified local model
package and bound by its package digest and Kaggle Dataset version.

The model is chosen so a future owner decision may consider parameter-efficient
post-training on the same 96 GB hardware. That future possibility does not
authorize post-training in Trial 001. Full-parameter fine-tuning, LoRA, QLoRA,
SFT, preference optimization, and reinforcement-learning post-training all
remain outside Trial 001 and require a later decision.

## Authorized transport

The supported handoff is deliberately manual. Repository implementation must
not require Kaggle credentials, automate Kaggle Dataset publication, call the
Kaggle API, or download notebook output automatically.

Two independently versioned private Kaggle Dataset inputs are permitted:

1. an immutable model package, prepared infrequently from the exact model
   revision above; and
2. an immutable Trial 001 execution package, prepared for a specific preflight
   binding and uploaded as `trial-input.zip`.

Keeping model and trial packages separate prevents every trial-package change
from requiring a new model upload. Both inputs must be private, immutable for
the run, and identified by their Kaggle Dataset owner, slug, version, and local
package SHA-256 digest before real-run authorization.

The repository-local handoff tree is:

```text
.irisx/arc-agi-2/trial-001/
├── model/<model-package-id>/
│   └── model-package.zip
├── kaggle/
│   ├── outbound/<bundle-id>/
│   │   └── trial-input.zip
│   └── inbound/quarantine/<run-id>/
│       └── result-package.zip
├── run/<run-id>/
└── package/
```

Generated artifacts remain ignored and disposable under `.irisx/`. Their mere
presence is not product authority or accepted trial evidence.

## Outbound execution package

`trial-input.zip` must be closed-world and digest-bound. At minimum it contains:

- a canonical manifest with package identity, format version, byte size, and
  SHA-256 digest for every declared file;
- the exact solver-facing ARC cases;
- the exact baseline and candidate configuration bindings;
- the authorized static specialization artifact and provenance;
- the common execution envelope and attempt policy;
- the notebook runner and runtime dependency identity needed for offline
  execution; and
- the repository revision and notebook source digest expected for the run.

It must not contain:

- `evaluator-truth.json` or any expected evaluation output;
- an expected-output digest or other answer-derived metadata;
- a prior score, correctness label, evaluator verdict, or case-level feedback;
- third-party ARC data;
- a provider credential, Kaggle credential, secret, or personal token; or
- an undeclared file.

The package builder and verifier must reject path traversal, absolute paths,
backslashes in logical paths, symbolic links, duplicate paths, unexpected
files, digest mismatches, unsafe expansion sizes, stale references, and an
incorrect or incomplete solver-facing workload.

## Kaggle notebook boundary

The notebook is a thin offline execution adapter. It must:

1. read immutable inputs only from `/kaggle/input`;
2. verify the model and trial-package identities and digests before execution;
3. extract or copy writable runtime material only under `/kaggle/working`;
4. verify that the accelerator is exactly one NVIDIA RTX PRO 6000 with 96 GB
   before measured execution;
5. verify or record that notebook Internet access is disabled;
6. execute baseline and candidate with the same model, invocation limits,
   attempt limits, timeout, seed policy, and output limits;
7. make no provider call, network request, model download, package install from
   the network, or paid external call;
8. expose no evaluator truth to the model, runner, logs, or returned artifacts;
   and
9. write all returned material beneath `/kaggle/working`.

The implementation may choose the exact offline runtime and dependency-loading
mechanism. Every runtime dependency and material environment difference that
can affect the result must be versioned and recorded. Notebook convenience must
not weaken package identity or data isolation.

## Returned result package

The notebook must create one complete `result-package.zip` under
`/kaggle/working`. It must contain at least:

- a closed-world result manifest;
- all baseline and candidate predictions for every required case, test input,
  and permitted attempt slot;
- input package, model package, notebook, repository, configuration, and
  execution-envelope identities;
- observed hardware, software, dependency, seed, timeout, retry, truncation,
  resource, and wall-clock evidence;
- structured run status and stop-condition evidence;
- complete runner logs suitable for local validation; and
- an observed external paid cost of USD 0.

The result package must not contain evaluator truth, locally computed ARC
scores, a `SelectionDecision`, or a Domain Package. The Kaggle notebook returns
predictions and execution observations only.

The owner downloads the complete notebook output without selecting or rewriting
individual files and places `result-package.zip` at:

```text
.irisx/arc-agi-2/trial-001/kaggle/inbound/quarantine/<run-id>/
```

No artifact in quarantine is trusted. A deterministic offline importer must
apply the same archive-safety and closed-world checks as the outbound verifier,
verify every upstream binding, require exact output completeness, and reject
unexpected or inconsistent evidence. Only a passing import may materialize
normalized evidence beneath `.irisx/arc-agi-2/trial-001/run/<run-id>/`.

ARC scoring, `EvaluationResult` construction, generic selection, the P2
acceptance decision, and Domain Package construction and verification occur
only on the repository host, where evaluator truth remains isolated.

## Preflight and real-run authorization

Technical preflight must remain separate from owner run authorization. Before
a real run can be authorized, immutable evidence must bind at least:

- the exact model source revision, local model-package digest, and private
  Kaggle Dataset version;
- the exact `trial-input.zip` digest and private Kaggle Dataset version;
- the notebook and runner source digests;
- the repository revision;
- the exact baseline and candidate configurations;
- the execution envelope, including invocation, attempt, timeout, seed, output,
  wall-clock, and resource limits;
- one NVIDIA RTX PRO 6000 96 GB;
- Internet disabled and no usable provider credentials;
- the complete expected return-package shape and local quarantine path;
- external paid spend of USD 0; and
- dataset and output retention or deletion behavior.

This decision does not supply that later run authorization. Creating packages,
uploading private Dataset versions for preflight, or obtaining a passing static
preflight must not be interpreted as permission to execute the model over the
real frozen workload.

## Stop conditions

In addition to the unchanged Decision 0004 stop conditions, the Kaggle path
must stop and preserve failure evidence on any of the following:

- a Dataset is public or has unexpected access;
- the model, trial package, notebook, runner, repository, or Dataset version is
  missing, mutable, stale, substituted, or digest-mismatched;
- the accelerator is absent, substituted, or has less than the bound memory;
- Internet is enabled or a network or provider call is attempted;
- a credential or secret is present;
- an undeclared input, output, or ARC source is observed;
- evaluator truth or answer-derived metadata crosses the outbound boundary;
- baseline and candidate execution envelopes differ;
- the complete notebook output cannot be downloaded unchanged;
- the return package is incomplete, unsafe, or non-recomputable; or
- any external paid cost is incurred.

Failures must not be repaired silently or by editing returned evidence.

## Implementation scope

The next implementation slice may add only the minimum required:

- model-package materialization and offline verification;
- Trial 001 outbound ZIP construction and offline verification;
- the network-disabled Kaggle notebook and thin runner adapter;
- result-package construction;
- safe local quarantine import and normalization;
- Kaggle-specific preflight evidence;
- current documentation and CLI integration; and
- deterministic offline positive and negative tests.

It must not build a general cloud execution framework, a provider SDK, Kaggle
credential management, automatic publication or download, a general training
framework, or a production runtime.

## Required tests

Tests must remain offline and use small synthetic fixtures. They must cover at
least:

- deterministic outbound and result ZIP construction;
- closed-world manifests and byte digests;
- evaluator-truth and answer-derived-metadata exclusion;
- archive traversal, symbolic-link, duplicate-path, expansion-size, missing,
  extra, and digest-mismatch rejection;
- exact model, package, configuration, notebook, repository, and execution-
  envelope bindings;
- hardware, Internet, credential, provider-call, and external-cost gates;
- baseline/candidate envelope equality;
- exact result completeness at the existing ARC case/test/attempt granularity;
- quarantine remaining untrusted until successful import;
- local-only evaluation and selection; and
- continued P0, P1, historical P2-admission, and Decision 0004 behavior except
  for the execution-venue change explicitly made here.

Tests must not download a model, access Kaggle, call an external provider, run
the real ARC workload, or incur cost.

## Consequences

- The Trial 001 execution venue and manual transport path are now owner-
  selected and may be implemented and preflighted.
- Network transport is permitted only for deliberate manual private Dataset
  upload and complete output download; measured notebook execution remains
  network-disabled.
- Evaluator truth remains local and never enters a Kaggle Dataset or notebook.
- Qwen3.8-27B is selected as the frozen Trial 001 model, but its materialized
  package and execution envelope must still pass preflight.
- Trial 001 remains a prompt/program specialization trial and performs no
  post-training or fine-tuning.
- The real model run remains unauthorized until a later explicit owner
  authorization binds the exact Dataset versions, digests, notebook, hardware,
  resource limits, retention, and passed preflight evidence.
- Decision 0003 remains immutable historical blocked-state evidence, Decision
  0004 remains authoritative outside the narrow changes above, and existing P1
  contracts and selection semantics remain unchanged.
