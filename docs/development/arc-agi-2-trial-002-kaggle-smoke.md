# ARC-AGI-2 Trial 002 Kaggle repair smoke

This guide applies only to Decision 0015 run `trial-002-smoke-002`. It preserves
the failed Decision 0014 attempt `trial-002-smoke-001` and does not resume or
reinterpret Trial 001.

## Bound inputs

- Competition source: `arc-prize-2026-arc-agi-2`.
- Runtime challenge file: `arc-agi_training_challenges.json`, SHA-256
  `779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5`.
- Model: `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
- Tasks/test indices: `2dd70a9a/0`, `992798f6/0`, `305b1341/0`, and
  `d968ffd4/0`.
- Compute request: `NvidiaL4` with the competition attached. This request is
  not evidence of hardware; notebook and runner both require exactly four L4
  devices with at least 22,000 MiB each before model work.
- Workload: exactly four `generate` invocations, one per task/GPU, with
  `num_return_sequences=1`; no TTT, LoRA, warm-up generation, retry, multi-view
  generation, or fifth invocation on resume.

Competition solution files and local evaluator truth must not enter the
Dataset, notebook, checkpoint, or result.

## Local layout

Generated material stays under `.irisx/arc-agi-2/trial-002/`:

```text
competition-source/   downloaded challenge input only
failed-run-001/       retained first-attempt server source, metadata, log, output
trial-smoke-002/      fixed workload, local truth, and run binding
runtime-smoke-002/    offline Python 3.12 wheels
outbound-smoke-002/   truth-free closed-world ZIP
dataset-smoke-002/    private Dataset version staging
kernel-smoke-002/     bound kernel staging
download-smoke-002/   one later returned-output retrieval
quarantine-smoke-002/ untrusted result verification target
verified-smoke-002/   local score and verified summary
```

## Build and preflight

Source/model acquisition is separate from validation and execution. Default
tests perform neither. Run the repository version by setting `PYTHONPATH` or by
installing it editable, then prepare against both the pinned local ARC source
and the actual competition challenge input:

```powershell
$env:PYTHONPATH = "src"
python -m irisx arc-agi-2 baseline prepare `
  --source C:\Users\wurre\Desktop\IRIS-X\.irisx\dev-source `
  --competition-challenges .irisx\arc-agi-2\trial-002\competition-source\arc-agi_training_challenges.json `
  --output .irisx\arc-agi-2\trial-002\trial-smoke-002

python -m irisx arc-agi-2 baseline outbound-build `
  --trial .irisx\arc-agi-2\trial-002\trial-smoke-002 `
  --model .irisx\arc-agi-2\trial-002\model\qwen3.5-4b-851bf6e `
  --nvarc .irisx\arc-agi-2\trial-002\source\NVARC `
  --wheels .irisx\arc-agi-2\trial-002\runtime-smoke-002\linux-cp312 `
  --output .irisx\arc-agi-2\trial-002\outbound-smoke-002\trial-002-smoke-002.zip

python -m irisx arc-agi-2 baseline kernel-stage `
  --template trials\arc-agi-2-baseline `
  --output .irisx\arc-agi-2\trial-002\kernel-smoke-002 `
  --dataset-ref danielwuu/irisx-arc-agi-2-trial-002-smoke-001 `
  --outbound-digest sha256:c5abe026303920cc79376e0bc111abbbcd9c616e23ea243f11cbf6488a848c01

python -m irisx arc-agi-2 baseline preflight `
  --trial .irisx\arc-agi-2\trial-002\trial-smoke-002 `
  --outbound .irisx\arc-agi-2\trial-002\outbound-smoke-002\trial-002-smoke-002.zip `
  --model .irisx\arc-agi-2\trial-002\model\qwen3.5-4b-851bf6e `
  --nvarc .irisx\arc-agi-2\trial-002\source\NVARC `
  --wheels .irisx\arc-agi-2\trial-002\runtime-smoke-002\linux-cp312 `
  --competition-challenges .irisx\arc-agi-2\trial-002\competition-source\arc-agi_training_challenges.json `
  --dataset .irisx\arc-agi-2\trial-002\dataset-smoke-002 `
  --kernel .irisx\arc-agi-2\trial-002\kernel-smoke-002 `
  --dataset-ref danielwuu/irisx-arc-agi-2-trial-002-smoke-001 `
  --output .irisx\arc-agi-2\trial-002\preflight-smoke-002.json
```

The current verified outbound SHA-256 is
`c5abe026303920cc79376e0bc111abbbcd9c616e23ea243f11cbf6488a848c01`.
The bound preflight reports `technical_ready: true` and has SHA-256
`c67153b81a13d5087c4ee7c0cb920324ff67ff6709a093a45bf6e5d991337967`.

Package readiness also requires a new immutable version of the existing private
Dataset. Reuse the already uploaded model/source/wheel bytes and add the new
runtime wheel and outbound ZIP; do not re-download the model. The kernel staging
validator requires exactly the expected Dataset reference, competition source,
machine shape, Internet-disabled setting, and outbound digest.

## One authorized submission

`kernels push` starts execution. Call it once only after the private Dataset
version is accepted and the bound preflight passes:

```powershell
kaggle kernels push `
  -p .irisx\arc-agi-2\trial-002\kernel-smoke-002 `
  --accelerator NvidiaL4 `
  --timeout 3600
```

After acceptance, save the static server source/metadata and verify that it
names the competition source and requested machine shape. This is a submission
receipt, not proof that the model started or that four GPUs were allocated.
Only returned hardware evidence can establish the runtime shape.

For the submitted repair, Kaggle normalized the title to the actual platform
ref `danielwuu/iris-x-arc-agi-2-trial-002-repair-smoke-002`, kernel ID
`135334870`, version 1. Its saved server metadata includes
`competition_sources: ["arc-prize-2026-arc-agi-2"]`,
`machine_shape: "NvidiaL4"`, and Internet disabled. The internal run identity
remains `trial-002-smoke-002`; the platform slug normalization is retained as a
transport receipt rather than rewritten into the already submitted package.

Do not poll. Do not issue repeated `kernels status`, follow logs, or repeatedly
download output. After the 3,600-second bound plus a finalization allowance,
make exactly one status/output retrieval. If it is still queued, report that
state without polling or resubmitting.

## Quarantine and score

Download the exact submitted kernel version's output into
`download-smoke-002/`, then verify before importing:

```powershell
python -m irisx arc-agi-2 baseline result-verify `
  --package .irisx\arc-agi-2\trial-002\download-smoke-002\result.zip `
  --outbound .irisx\arc-agi-2\trial-002\outbound-smoke-002\trial-002-smoke-002.zip

python -m irisx arc-agi-2 baseline result-import `
  --package .irisx\arc-agi-2\trial-002\download-smoke-002\result.zip `
  --outbound .irisx\arc-agi-2\trial-002\outbound-smoke-002\trial-002-smoke-002.zip `
  --quarantine .irisx\arc-agi-2\trial-002\quarantine-smoke-002
```

Verification requires the exact run identity, competition observation, four-L4
inventory, four globally ordered invocation records, raw completions, and four
terminal job records. Score only the verified quarantine directory with local
truth. Report exact-match pass@1 over the four selected outputs, valid generation
rate, completion rate, terminal statuses, timing, tokens, and peak memory
separately. This workflow does not make a competition submission.
