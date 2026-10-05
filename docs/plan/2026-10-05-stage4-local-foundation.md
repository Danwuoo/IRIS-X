# Stage 4 first local foundation

Date: 2026-10-05, Asia/Taipei. Scope: local offline implementation on main.

The owner opened Stage 4: Astra ultra handles cloud research, the local task
implements, and the controller reviews/dispatches/accepts. The owner later
chose manual message relay. The local dispatch requested
`gpt-6.1-sol / xhigh`; no independent current-model introspection was available.
The starting main HEAD was `62a849755396520341be8f12b844a37e36ada266`.
The controller subsequently committed its separate research snapshot. This
batch does not alter its research files, initiate cloud work, or push Git.

The earlier Stage-4-unopened statements describe prior decisions. The owner's
new instruction opens research and this finite local batch; it does not renew
consumed run identities, submission slots, provider requests or monitoring.
The old Stage 3 failure and all saved/executed bytes remain frozen. Owner ZIP
originals remain untouched and untracked at the checkout root. No Goal, timer,
automation, GPU work, QUICK_SAVE, Dataset change or provider query is part of
this batch. Routine implementation needs no new Decision.

The shared [offline evaluator and CLI schema](../development/arc-offline-evaluation.md)
adds content/demo/multi-test identity, explicit denominators/aggregation,
candidate loss accounting, paired outcomes and runtime observability. Its
NVARC adapter extends the existing archive/scorer workflow; no new solver or
scientific method is selected. Official status/error/null score stays separate
from public development metrics. Evaluator truth and diagnostic labels never
return to solver/outbound bytes.

The existing frozen comparison is reproduced at
`.irisx/stage4-local-foundation-001/`, with root aggregate brief/manifest and
evaluator-only `local/` reports/recipe. Only manifest-listed briefs are needed
for a research handoff. The full source, owner ZIPs, solutions, package
payloads, weights, and per-test diagnostics remain local. No automatic upload
occurs. The controller's separate research snapshot/ZIP need not be rebuilt.

The required return format is proposal, primary source/commit links, mechanism,
expected measurable benefit, small local test, failure criteria, compute/data
and exposure assumptions, and instrumentation. The controller routes accepted
research back for the next local batch. This task stops after a finite tested
local commit. The owner's final target remains an official Kaggle score >85;
engineering success and retrospective projections are not SOTA or official
score claims.

Validation and exact artifact bindings are recorded in the batch handoff
under `.irisx/stage4-local-foundation-001/local/`; known full-suite failures
remain visible and no frozen evidence or deadline threshold is changed.

## Reproducible local evidence

The byte-bound challenge source is TinyRecursiveModels commit
`e7b68717f0a6c4cbb4ce6fbef787b14f42083bd9`, retained through
[NVARC](https://github.com/1ytic/NVARC/tree/846d0198efa752534594e321fc3289fc0a06c657)
commit `846d0198efa752534594e321fc3289fc0a06c657`; the existing source manifest
is also hash-bound by the recipe. The original saved model/method envelopes
remain in the prior [public diagnosis](../../trials/arc-agi-2-qwen35-nvarc/public-eval-notebooks-001-diagnosis.md).

Re-run against the retained local inputs, choosing a new output directory:

```powershell
.irisx\nvarc-ml-venv\Scripts\python.exe tools\report_arc_offline.py --config .irisx\stage4-local-foundation-001\local\recipe.json --output .irisx\stage4-local-foundation-replay-003
```

Two executions produced identical report, brief and manifest bytes. Source
checks retain 120 tasks/172 executed tests, 120 tasks/167 reference tests, 114 exact full
task matches, two changed demonstration sets, and 167 input-content matches
(164 also have identical demonstrations). BASE/TTT pass@2 remains 5/172 versus
10/172, with six gains/one loss. The official observation remains
`Notebook Threw Exception` with both scores null. Separate search, verification
and complete other durations remain unknown.

| Artifact under `.irisx/stage4-local-foundation-001/` | SHA-256 |
| --- | --- |
| `local/evaluation.json` | `a3ce1dcc37bb3703e2374e95de636d43390fdaa0b03dd726a29b42d571573d94` |
| `evidence-brief.json` | `ad06adf383b09615b49e1363cf80fdcb2a7e3951194bfe0298d5b0c6bf8f1b38` |
| `evidence-brief.md` | `07f4f61929883905a38b40b538736751ab3c2399f19dee0e2257f6efaea9a28e` |
| `manifest.json` | `426db05528e526a35a47afc12b76cb614c09b3cc766e5eb1ccb618ac32b3eddf` |
| `local/recipe.json` | `41525cc544e942c22f1c0daee45792eb2aca77e9234b5d97f82eaa6717aa75ea` |

Focused validation passed 26 tests (13 new shared-evaluator tests and 13
existing public-evaluation tests) in 22.836 seconds. The required
`python tools\repository_check.py --all` ran in the retained Python 3.12.10
ML environment: three helper tests passed; 546 unit tests ran in 521.560
seconds with one failure, zero errors and zero skips. The failure and the
invariant errors identify only the two preserved owner root ZIPs. The existing
Windows combined short-deadline success test passed this time. Full validation
remains **failed**, not a full-suite pass claim. Diff whitespace passed.

The test environment used the existing hash-bound code-only source fixture
at `.irisx/public-eval-analysis-20261005-001/verified-source/`,
`PYTHONPATH=src`, `PYTHONHASHSEED=0` and offline HF/Transformers flags. This
includes source tests that would otherwise skip; tiny CPU fixture tests are
not real model/GPU execution or numerical method qualification. Log hashes,
environment and exact commands are in `local/handoff.json`. No checker
exception, relaxed timing threshold or evidence rewrite was used.
