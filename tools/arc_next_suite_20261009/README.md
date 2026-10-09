# IRIS-X N5–N14: ten gated next-phase notebooks

This is an offline, manually started experimental suite, not ten completed GPU runs. All ten notebooks are private inactive QUICK_SAVE artifacts with GPU, TPU and Internet off and MANUAL_START=False. No GPU generation, training, payment, or competition submission was performed during development.

## What changed after the actual N4 result

The sealed N4 artifact contains 93 actual model calls: A32, B32, C29, with three C context exclusions. Direct-grid A solved1/8 exposed engineering tasks; program B/C solved0/8. All61 generated programs had the requested raw-source format;45 parsed, but none entered the original interpreter. Most reimplemented supplied toolbox functions using unsupported while/list methods. Generic syntax feedback did not produce executable repair candidates. This was not a valid test of the benefit of demonstration verification, because the programs never reached demonstrations.

N5's actual CPU replay of the same61 sources changes only the admitted bounded language. It admits29, executes23 on demonstrations and still fits all demonstrations for zero tasks. Language admission and semantic reasoning are therefore separate bottlenecks. This suite does not claim an accuracy improvement from making more programs executable.

The prior N3 raw-grid SFT comparison was base0/32 versus adapter1/32, with many valid uncapped wrong grids and four capped adapter outputs. It does not justify treating NLL or format compliance as program competence. Granite4.2-8B remains the only verified offline model here; Qwen3.5-9B and Seed-Coder8B are later alternatives requiring separately verified assets.

## The ten experiments

| Run | Distinct question | Model-call ceiling | Gate |
|---|---|---:|---|
| N5 | Fixed61-source replay: immutable language versus bounded-v2 | 0 | Security release; original source binding |
| N6 | Detailed contract versus explicit host-owned toolbox API | 64 | Security release |
| N7 | Bounded Python versus typed composition IR | 64 | Compiler/witness coverage |
| N8 | Generic versus precise static repair diagnostics | 64 | Paired first-root check |
| N9 | Raw grids versus exact deterministic object view | 64 | N6 AST/demo-execution admission |
| N10 | Redacted versus true demonstration feedback | 64 | N6 semantic execution gate |
| N11 | Independent breadth versus best-parent repair and bounded readable memory | 64 | N6 semantic execution gate |
| N12 | Uniform versus smoothed neural feature prior versus hard-pruned CPU search | 32 shared | N7 typed-IR admission |
| N13 | Authored, executor-verified F/G/P/R curriculum | 0 | Security and witness coverage |
| N14 | Direct-grid versus preregistered selected agent on N3's32 tasks | 256 | All listed source reports or valid prerequisite-BLOCKED receipts |

The complete suite has an upper ceiling of672 model calls and1,376,256 generated tokens if every gate passes. This is not an execution authorization or cost estimate. N5 and N13 are genuinely CPU-only and do not require CUDA, a model load, G4 hardware, or a scan of model weights.

N9's complete compact object view exceeds6144 prompt tokens on engineering task33067df9; its four slots remain excluded in the fixed denominator. If object policy is selected for N14, taska096bf4d similarly excludes four slots. Other initial policies fit the audited limit. No task or raw grid is truncated/replaced.

## Evidence, exposure, and controls

- N5–N12 use the original eight exposed engineering tasks. N14 uses exactly original tuning_ids[8:40], the32 tasks previously used by N3, disjoint from the eight policy-design tasks. This remains exposed tuning, not a fresh holdout.
- All136 confirmation IDs are protected by a frozen hash. No confirmation queries or answers are used.
- Earlier tuning query scores can choose a single experiment-level N14 policy under a fixed rule. They never choose a candidate within a task, supply feedback, or enter program search.
- N14 requires N6,N7,N9,N10,N11 reports, or valid admission-BLOCKED receipts for N9–N11. Among qualifying tested policies it ranks top2, top1, fewer generated tokens, then fixed policy ID. N12 is excluded because its additional CPU search budget is not inherited.
- Every normal task/arm has four planned calls. Missing, late, invalid, unknown and context-excluded work remain in the denominator. A complete gate receipt means a closed expected ledger with exclusions recorded, zero missing/unknown verification, and clean stop, not that all slots generated.
- Matched ceilings are not matched actual compute. Reports retain actual known prompt/output tokens, call reservations, generation/verifier time and charged interpreter gas. N12 charges full shared model-pool cost to every standalone counterfactual arm and reports physical shared spend once.
- N10 is a feedback-information and trajectory contrast, not an exact equal-token or single-step causal estimate. N11 is a controller package contrast. Identical prompt/seed pairs have response-equality diagnostics.
- Memory signatures summarize bounded feedback and readable source features. They are not exact semantic equivalence and never cause candidate pruning. Diversity is reported within task/condition, not inferred from pooled task shapes.

## Program execution and source integrity

Runtime8 and the five existing Dataset pins remain unchanged. A separately versioned bounded-v2 interpreter adds metered while, exact-list append/pop/extend, eager bounded generator expressions, list(), is/is-not, and the ordinary lone underscore variable. It does not expose imports, arbitrary attributes, strings/dicts/sets, host APIs, nested definitions, augmented assignment, or unrestricted Python.

Every generated Python program and every compiled typed plan goes through the independently reviewed verifier, never Python exec/eval. Each candidate is interpreted in a fresh isolated CPU process with a200,000-step shared demo/query allowance,3-second parent timeout,2 CPU seconds,256MiB address-space limit and bounded JSON IPC. Unknown work reserves the full candidate allowance. Query outputs/errors never enter repair feedback.

The trusted-source loader checks the exact captured source bytes and bypasses pyc. The notebook verifies the closed embedded payload before writing or importing it. Inputs, output roots, source-directory symlinks and immutable output identities are checked. Prior evidence ZIPs reject traversal/symlinks/duplicates/oversize content and verify the post-score closed inventory. These hashes provide integrity, not digital-signature authentication against an owner who fabricates an entire artifact.

## N13 curriculum

There are512 deterministic episodes across eight explicitly authored families,64 per family. Six named families are training, two are validation, with family-level assignment before sampling. These are source-family IDs, not proof of primitive-disjoint or ARC-family-disjoint generalization. No ARC answer or evaluation-derived generator is used.

F copies a supplied program into the same raw-source format as P; it is an interface control. G predicts synthetic grids. P predicts a verified program from demonstrations. R sees an AST-valid but semantically failing mutation, bounded visible-demo feedback and the verified replacement. Witness and byte-identical repair share one verification; the bad mutation has a separate verification. Independent synthetic query inputs have separate seed namespaces.

All512 episodes were checked by1,024 fresh actual CPU verifier calls with zero unknown usage and3,832,550 charged steps. This proves data/executor readiness, not SFT benefit. Program-SFT, repair-SFT, task-local TTT, RL and four-L4 deployment remain later, separately specified measured studies.

## Run and inspect

Open the individual notebook, leave Internet off, retain pinned Dataset versions, set actual paths if needed and supply prerequisite ZIP/directory paths through PRIOR_RESULTS. Only set MANUAL_START=True when intentionally starting that specific run. Missing/failed prerequisites produce an immutable BLOCKED receipt before installation/model load. Download the evidence ZIP shown after EXPERIMENT-FINISHED or EXPERIMENT-BLOCKED.

GPU studies target the proven G4 profile: one96GB-class RTX PRO6000 Blackwell,48CPUs,host RAM≥170GiB, the pinned CPython3.12/cu128 stack. They have not been run on GPUs in this delivery. CPU-only receipts record host Python separately.

Generation's120-second limit is cooperative. Controller ceilings are9600 seconds,32400 for N14,600 for N5 CPU replay and1200 for N13 curriculum. Initial verification, interpreter preparation, sealing/scoring/export and cleanup can overrun these windows. The notebooks do not stop VM billing; stop the VM yourself after use.

## Reproduce validation

From this directory:

- python3 -m unittest discover -s tests -p 'test_*.py' -v
- python3 build_source_lock.py (only after reviewed source edits)
- PYTHONPATH=<pinned CPU tokenizer package directory> python3 audit_tokens.py <verified tokenizer assets>
- python3 build_source_lock.py && python3 build_notebooks.py

The typed-IR full-export test uses saved CPU evidence if present; otherwise it safely regenerates512 episodes on CPU, taking a few minutes. GPU responses in harness tests are fixtures; program verification is real isolated CPU execution. See VALIDATION.md for exact passed/not-run scopes. Do not interpret this focused suite as a clean full historical repository baseline.

## Research provenance

DESIGN-FROZEN.json and docs/PRIOR-RESEARCH-SOURCE-INDEX.json connect the staged interventions to the earlier project/named-model/open-web study. AVO contributes lineage and bounded restart ideas; Duck motivates exact task views; Jev typed decisions; Prime bounded task state; NeMo explicit rollout/profile contracts. These are mechanism transfers, not claims that those projects provide validated ARC weights. Neural CPU search is a finite typed candidate inventory with smoothed feature-prior ranking, not a reproduction of an entire PCFG/HySynth system.

The reviewed publication manifest retains the original publication-workspace paths as provenance. In a fresh checkout, use `notebooks/<filename>` for those same hash-bound artifacts; do not treat the historic absolute path as a required machine location.

## Repository location

The additive suite lives under `tools/arc_next_suite_20261009/`, as required by the repository Python-layout invariant. From the repository root run `python3 -m unittest discover -s tools/arc_next_suite_20261009/tests -p 'test_*.py' -v`. See [Traditional Chinese quickstart](README.zh-TW.md) for the manual run order, pinned mounts and prior-result transfer.
