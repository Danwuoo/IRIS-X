# NVARC source/export continuation and complete teacher stages

Status: implementation on `main`; execution authorized by Decision 0033.
The owner requested merging the NVARC worktree and continuing on main.
Worktree `51fa` at `00db35d` was already contained by merge `f30baa8`;
`git merge --ff-only 00db35d` returned `Already up to date`. The separate
planning commit `8511736` is patch-equivalent to main's `81b5289`. No old
P2 worktree, remote push or new worktree is part of this continuation.

Decision 0032's [terminal evidence](../../trials/arc-agi-2-qwen35-nvarc/m2-m3-decision-0032-terminal.md)
supersedes its earlier pending-execution status. The owner authorized local
development here and subsequently directed Kaggle execution and continued
development. [Decision 0033](../decisions/0033-authorize-nvarc-source-and-direct-teacher.md)
now governs the two distinct continuations. Earlier review-only observations
below retain their historical meaning.

## Approved execution preparation

The exact six tokenizer/configuration files were acquired from the pinned
revision and checked against the existing model manifest. Transformers 5.8.1
loads its `Qwen2Tokenizer`; direct-mode template and tensor handling passed.
The exact summary prompt has 143 input tokens. Synthetic prior-output budget
probes have 740, 1,142 and 4,218 tokens for the later three stages, below their
4,096, 4,096 and 8,192 caps. These are budget probes, not actual teacher replies;
runtime still checks every actual dependent input. No model calls occurred.

The approved M2 Dataset uses the successful flat model-file layout. Its
material manifest retains the original training identity; detailed training
evidence is embedded in the kernel. No folder/archive extraction convention
is assumed. All model shard bytes and the export digest remain unchanged.
Authorization guards bind exactly Decision 0033 and unchanged draft hashes;
old decisions cannot activate these packages.

| Binding | M2 `source-cont-approved-001` | M3 `teacher-direct-approved-004` |
| --- | --- | --- |
| Plan SHA-256 | `643f0b65ae0f818adf37000b4dd2780fb615cf271c8c5fd8aec260580fb96781` | `d2bdb4e9507c41e6f23efa7aeb850025090da8860cf7381f8c00e523d60da402` |
| Notebook SHA-256 | `afa16185557d119c130a137d9d8c2570e924b9ff090ed5292e74c9bd88186d8f` | `8a5b491c12b694adfb4e872a957d9217a3ee50bd0de3c667428ee2d40f9be2ef` |
| Runtime wheel SHA-256 | `48de077bfb3c0cf4abddfb16211882fd65db8cedd712ae7c22fc8531192f1edf` | same |

Approved packages and the atomic `decision-0033-execution-ledger.json` live
under `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`. Source identity remains
`sha256:625b010706dabfce5df58c036f5921af4e782da133bd27038bc442abdc79e1a4`.

## M2 deployment repair

The source bundle carries the unchanged Qwen notebook v10 and source manifest,
with a closed inventory and caller-supplied digest. The notebook is 38,975 bytes
and contains no output cells. Only approved writefile definitions/AST selections
execute; install and runner cells do not execute. An operation-local explicit
bundle path prevents checkout fallback. Missing, extra, symlinked or changed
members fail before model work. All three source entries are exercised before
model loading.

`nvarc-m2-source-cont-001` references the verified SFT export and its training
identity, with zero SFT steps and no optimizer-resume claim. A separate
`continuation-chain.json` binds its source result to old training evidence;
the failed original run never receives a fabricated chain. The original visible
task and source config bytes remain unchanged.

Proposed future bounds: one private immutable export Dataset; one private,
Internet-disabled four-L4 kernel, one L4 used; 1,800 seconds; visible dev task
`00576224`; one demo-only LoRA step; at most four 64-token DFS calls with 128
expansions per call; one retrieval; USD 0; no retry. Empty candidates do not
establish nonempty ranking. No scorer or dev test output is included.

## M3 direct-response profile

`nvarc-m3-teacher-small-004` uses the same pinned full-vocabulary Qwen3.5-4B
and two public training parents. Original prompts stay frozen; concise effective
prompts have a distinct digest and retain the source-prompt digest as provenance.
The profile disables thinking, keeps greedy generation, retains raw token IDs
and termination, and passes only validated content or complete extracted code
to dependent stages.

| Stage | Maximum input | Maximum output | Reservation |
| --- | ---: | ---: | ---: |
| summary | 4,096 | 512 | 4,608 |
| mix | 4,096 | 1,024 | 5,120 |
| input-logic | 4,096 | 3,072 | 7,168 |
| output-logic | 8,192 | 3,072 | 11,264 |
| Total | 20,480 | 7,680 | 28,160 |

The runtime tokenizes each actual rendered input and rejects an excess before
generation, without silent truncation. The real local Qwen3.5 tokenizer-class
test covers tensor handling, direct-mode selection, EOS and stage reservation.
Full pinned teacher tokenizer files are not currently present in this checkout
or local HF cache: exact full-vocabulary prompt counts remain a readiness
limitation, not a passed dry run. No acquisition or teacher call bypassed it.

Rejected stages retain raw responses, digests and reasons and consume their
call. Later stages stop; reopening a ledger never retries. Required program
entries must be complete, unambiguous Python with expected signatures. Parsing
does not execute code; execution uses the existing WSL namespace sandbox.
Five fixed seeds produce ten program executions, with original grid/pair
filters unchanged. Replay now retains `pairs.json`, `messages.json`,
`programs.json`, parents, seeds and artifact/ledger hashes. Fixture replay stays
fixture evidence. Structural acceptance does not establish semantic quality
or upstream teacher parity.

Proposed future bounds: one private Internet-disabled four-L4 kernel, one L4
used, 1,800 seconds, at most four dependent teacher calls and 28,160 reserved
tokens, one retrieval, USD 0, no automatic retry. Local sandbox replay is
separate from model execution. Generated data requires lineage/quality review
before entering training.

## Validation and review packages

`tests/nvarc_deployment_strict.py` installs the actual wheel into an isolated
directory, removes checkout imports, blocks network and runs tiny actual
Qwen3.5 SFT/export/TTT/search, with missing/changed/extra-source regressions.
`tools/verify_nvarc_deployment.py` adds WSL user/mount/network namespaces,
hides the checkout under an empty mount and exposes only copied deployment
files through an alias. It uses cached Linux wheels, installed pure-Python
PEFT and local Linux torch 2.5.1; this is not Kaggle-image parity.

```powershell
python tools/stage_nvarc_source_continuation.py --output <new-local-directory>
python tools/preflight_nvarc_source_continuation.py <package>
python tools/stage_nvarc_m3_teacher.py --draft-plan trials/arc-agi-2-qwen35-nvarc/configs/m3-teacher-draft-004.json --output <new-local-directory>
python tools/preflight_nvarc_m2_m3.py <package>
```

Packages contain an inspectable plan, exact payloads, wheel, notebook and
preflight evidence. `approved: false` and unpushable IDs stop execution before
dependency installation or model work. New authorization must bind the exact
reviewed bytes and limits; Decision 0032 cannot be reused. After any future
authorized submission, wait for the owner's terminal report rather than monitor.

## Local handoff evidence

The repository check passed 217 tests with four existing optional skips. The
strict ML/source/sandbox/FSDP/deployment profile passed 29 tests without skips.
Windows installed-wheel tests passed. The WSL test additionally hid the actual
checkout and used a separate network namespace: one tiny SFT step, one TTT
step, four generation calls, zero network calls and zero likelihood calls.
The last count means nonempty candidate ranking was not observed in this tiny
probe. Existing source differential and fixture ranking tests remain separate
evidence. No new 4B model work or teacher calls occurred.

Review artifacts under `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`:

Both final package preflights passed with `approved: false`, a verified
early execution guard and zero external calls. An additional real-package
negative check rejected an undeclared M2 Dataset member before model hashing;
removing that synthetic member restored a passing preflight.

| Binding | M2 `source-cont-review-003` | M3 `teacher-direct-review-003` |
| --- | --- | --- |
| Plan digest | `sha256:389fb819e923c2d9c646d0fc9c134d14d0a6101c044c07ff180814d1d2a4ae3b` | `sha256:c66e11b47bff7c757b7112aa619734ab28c8cf4949bbc089ffca9ddc6b553623` |
| Notebook SHA-256 | `acc1292d67958343e844f2c6bc1c3be2722e54a2d93439794e5c27386286e565` | `84cbde2fc58e2ba31fe6ad4cfcc9bfb2784c01e64939172381bcf875b00e592f` |
| Runtime wheel SHA-256 | `1f5754422a9ddaa5a5919f91e0846f63f86190b28e4e9003d0f81edd932be9e1` | same |

Source bundle identity is
`sha256:625b010706dabfce5df58c036f5921af4e782da133bd27038bc442abdc79e1a4`.
The local Linux namespace report is
`.irisx/nvarc-linux-deployment-002/deployment-report.json`, SHA-256
`3874c54dbc1cd588938b3f1465a73a03316d9e6db31c494ba010bff3556c09c2`.
The test logs are `.irisx/nvarc-continuation-repository-check.txt` and
`.irisx/nvarc-continuation-ml-check.txt`. These retained observations are local
validation evidence only, not a new external execution or acceptance claim.
