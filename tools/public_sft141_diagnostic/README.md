# Public SFT141 native-Qwen3 diagnostic

This is an independently implemented public-source diagnostic, **not** the
private IRIS checkpoint pipeline, an NVARC reproduction, a training experiment,
or a clean hidden-generalization benchmark. It needs no IRIS Library artifacts.
It never downloads, rebuilds, or loads private IRIS adapters or checkpoints.

## Question and frozen comparison

Can the original public SFT141 weights produce valid outputs for true ARC
`task.test` inputs, with every demonstration retained, on a 6 GB CUDA device?
Does frequency-minus-common-view-NLL ranking alter exact success versus voting
on **the identical generated candidate pool**? The latter costs additional
teacher-forced forwards and is not an equal-compute ablation.

The panel has 12 parents selected using input/support prompt length only: four
length quartiles, three deterministic SHA-selected parents each, with a
predefined replacement to include a multi-query parent when available. All
queries are retained. The fixed seed is `iris-public-diagnostic-20261021`.
There is no result-based task replacement or support truncation. Selection
uses no test answer. Generated local materials contain a gold-free inference
plan and a separate evaluator answer file; neither is committed to Git.

One run uses eight spatial D4 views, fixed demonstration order, unrestricted
native greedy decoding, strict rectangular-grid parsing, and no TTT. The 931
new-token limit includes the maximum 30-by-30 grid and its EOS. Invalid and
truncated generations are retained as failures, not silently repaired. The
second ranker sums answer-token NLL including EOS, averages across the same
eight transformed prompts for every unique candidate, and subtracts that mean
from the candidate's occurrence count. Ties are deterministic and label-free.

## Public sources and non-parity

- Data: [official ARC-AGI-2](https://github.com/arcprize/ARC-AGI-2/tree/f3283f727488ad98fe575ea6a5ac981e4a188e49), commit
  `f3283f727488ad98fe575ea6a5ac981e4a188e49`. Downloads are verified against
  pinned Git blob identities. Apache-2.0; retain upstream attribution when
  redistributing data. This package distributes identifiers, not task data.
- Model: [official SFT141](https://www.kaggle.com/models/sorokin/qwen3_2b_grids15_sft141),
  `sorokin/qwen3_2b_grids15_sft141/transformers/bfloat16/1`, Apache-2.0 on the
  model card. Eight exact file SHA-256/size pins are in `model_pins.py`.
- Method comparison: [author notebook](https://github.com/1ytic/NVARC/blob/846d0198efa752534594e321fc3289fc0a06c657/ARC-AGI1/002_ivan_arc1.ipynb), commit
  `846d0198efa752534594e321fc3289fc0a06c657`, read statically only. No code
  from it is vendored, imported or executed; its repository has no discovered
  LICENSE at that commit.
- Backend: [official Transformers Qwen3](https://huggingface.co/docs/transformers/en/model_doc/qwen3).

The author notebook instead loads **4B SFT139**, performs per-task LoRA training,
uses Unsloth patches, shuffled supports, color permutations, probability-tree
search and 16 generation views. Its parser is permissive. This diagnostic uses
2B-family SFT141 (approximately 1.409 billion actual trimmed parameters),
standard Transformers with the pinned WordLevel tokenizer, no adaptation, eight spatial views and a strict parser.
The model config includes mRoPE-related metadata, while standard Qwen3 uses
its own rotary implementation. Actual class/config are recorded; author
position-semantics equivalence is **not established**. A low result cannot
alone distinguish weight limitations from this compatibility difference.

The author's [SFT instructions](https://github.com/1ytic/NVARC/blob/846d0198efa752534594e321fc3289fc0a06c657/ARChitects/README.md)
list evaluation-derived subsets, but the SFT141 card does not provide complete
checkpoint lineage. Exposure is possible, not proven for each task. Public
scores are diagnostic and must not be represented as held-out or official
competition scores. Neither ranker's score recreates the private IRIS Anchor
or the private SFT adapter comparison.

## Local Windows/Linux workflow

Use a CUDA-enabled official PyTorch installation and official Transformers
with native Qwen3 support, plus safetensors. The intended Windows environment
was prechecked as Python 3.10, Torch 2.9.1+cu130, Transformers 4.57.3, RTX 3050
6 GB, compute capability 8.6 and native BF16. That is an **environment precheck**,
not evidence that all selected prompts fit or that a complete run succeeded.
The tokenizer is explicitly constructed from the pinned tokenizer.json with
PreTrainedTokenizerFast. Generic AutoTokenizer in Transformers 5.8.1 was observed
to reinterpret this WordLevel vocabulary as BPE and silently drop role words;
this package rejects any token/prompt mismatch before model loading.

No Unsloth, PEFT, bitsandbytes, WSL, compiler, network login or private package
is needed. Do not install unrelated software or change security settings.

Run commands from the repository root. Replace `MODEL_DIRECTORY` with the
already downloaded official eight-file directory. Do not use a private export.
Use a fresh materials/output destination; existing output is never overwritten.

```powershell
python -m unittest discover -s tests -p "test_public_sft141*.py" -v
python -m tools.public_sft141_diagnostic verify-model --model-dir MODEL_DIRECTORY
python -m tools.public_sft141_diagnostic fetch --data-dir .irisx/public-sft141-data
python -m tools.public_sft141_diagnostic prepare --data-dir .irisx/public-sft141-data --materials-dir .irisx/public-sft141-materials
python -m tools.public_sft141_diagnostic run --materials-dir .irisx/public-sft141-materials --model-dir MODEL_DIRECTORY --output .irisx/public-sft141-run-001 --budget-seconds 7200
```

`fetch` alone uses the network, and only to obtain pinned official public task
JSON files. Preparation, verification and inference are offline. Inference
uses `local_files_only=True`, `trust_remote_code=False`, safetensors, BF16 SDPA,
a single CUDA device, and batch size one. No quantization, CPU fallback,
adaptation, training or hidden precision change is allowed. The controller
checks all model pins before dispatch. It does not send gold/raw-data paths to
the worker. This is a process-interface separation, not an OS security sandbox.

## Admission, evidence and stopping

A fresh-run monotonic clock covers verification, loading, admission, generation,
rescoring and finalization. The initial full diagnostic cap is 7,200 seconds,
not an account quota assertion or billing permission. The parent watchdog owns
only its spawned inference process. It never terminates unrelated user work.
There is no resume operation that resets this clock. Stop if the device is busy
before starting; the local executor should follow the user's separate load rule.

Admission runs the shortest, median and longest selected full-context queries
through their longest D4 view, including genuine EOS-bounded generation and
answer scoring. All demonstrations remain. The initial context ceiling is
8,192 total tokens or the model limit, whichever is smaller. A selected input
that does not fit is an explicit hardware/protocol failure, not a reason to
substitute another task. Measured calibration and uncertain runtime projections
are recorded separately. A pessimistic 931-token upper envelope is not proof
that the average run will take that long. Hard deadlines still apply.

Each generation and candidate score is written as an immutable receipt. After
worker exit, the controller seals raw outputs and only then loads evaluator gold.
`evaluation.json` reports full fixed query denominators, task-macro and
all-queries-solved task scores, oracle pool coverage, paired wins/losses, missing
predictions, and completion status. Missing predictions are not silently
excluded. Partial results do not satisfy the complete paired-comparison goal.
A vote-only result can be usable while the rescored comparison is incomplete.

Success means complete source/panel/model binding, real-device evidence, all
planned generation views accounted for, all candidate rescoring finished,
sealed outputs and a full-denominator paired report within the total clock.
No improvement is required to report honest engineering/scientific results.
If the ranker does not win, retain voting; do not tune on these answers.
A valid submission-format file is not a formal submission, and this package
never invokes Kaggle APIs or submits anything.

## Validation boundaries

CPU codec, material-generation, score-alignment and orchestration tests are
release gates, not model capability evidence. Local 6 GB fit, performance,
strict parsing rates and ranking effects remain unknown until the real run.
The full historical repository suite has separate fixture/environment issues;
passing this package's scoped tests is not a claim that that full suite passes.
