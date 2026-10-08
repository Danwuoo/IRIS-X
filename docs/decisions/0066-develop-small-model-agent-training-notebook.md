# Decision 0066: next small-model ARC-AGI-2 line, manual training notebook

Status: accepted development and first private QUICK_SAVE scope; no agent GPU execution.
Date: 2026-10-08.

## Current owner direction

The owner requested remote-version verification, analysis of the returned completed
uncapped notebook, then Astra-ultra research with parallel workers integrating the
project's sources, NeMo, NVIDIA AVO, Duck harness, Jev and Prime Agent. Model
preference is Granite 4.2 8B, Qwen3.5-9B, then Seed-Coder-8B-Reasoning, with the
actual choice dependent on measured training outcomes. Source messages:
`Sentinel_684691bb2b188191b0b1ca9dcd5e3689` and
`Sentinel_7220d247415081918d1b911b71ab07d6`.

The clarified hardware boundary is **training on one RTX PRO 6000 in Google
Cloud g4-standard-48**, and **official submission on four L4 GPUs**. The owner
will manually operate paid hardware. This is not permission for the assistant
to provision a VM, attach billing, create credentials, start a session, run GPU
work, upload weights/datasets, or submit to the competition.

## Authorized work and endpoint

- Read-only remote/source research; returned-byte analysis using trusted source.
- New reversible implementation, CPU tests and a reproducible first notebook.
- One new private notebook in the established `danielwuu` workflow, using exact
  reviewed `QUICK_SAVE` only, subject to the final target/payload admission.
- All preparation and execution switches default False. No save starts compute.
- The first manual smoke validates fit, gradients, serialization and reload.
  Separate explicitly selected pilot profiles train a real bounded LoRA on
  public-training demonstrations; a separately enabled architecture pilot uses
  equal charged proposal budgets. No automatic all-model sweep, full SFT or RL.
- Future deployment is offline, four distinct L4s, with source/weight/tokenizer/
  adapter/environment binding and actual per-device fit qualification.

This supersedes Decision 0065's prohibition on developing a G4-targeted notebook,
not its consumed save identity or any immutable uncapped/E13 evidence. Earlier
free-GPU or continuation authority is not reused to run this new line.

## Scientific and operational controls

Model repository/revision and official load-bearing file hashes are pinned.
Full native vocabulary is retained: historical 16-symbol NVARC weights cannot
be silently relabeled as general language/program models. Original model
licenses/attributions remain attached; exact-runtime support is tested rather
than inferred from a family name.

Training and development groups are split by task identity before augmentation
or label inspection. The first calibration uses only public-training
**demonstrations**. Development uses withheld demonstrations of different public-
training task groups. Original test outputs, locked public-evaluation answers,
hidden tests and answer-derived selection labels never enter the solver.

AVO, Duck and Prime Agent's headline ARC-AGI-3 claims are not ARC-AGI-2 evidence.
Typed program proposal, deterministic example checking and failure-feedback
repair are testable adaptations, not claimed improvements. Exact demonstration
fit is not proof of test generalization. Fresh leave-one-demo-out inference and
trajectory SFT/RL remain separate, unperformed experiments.

The first pilot is bounded because the owner pays for execution. Program
watchdogs stop owned processes, not the billed VM. The notebook must explicitly
warn the owner to stop the VM/session. Historical uncapped source remains intact.

## Base and preservation

Fresh read-only remote checks found main `72521b05bf9d217312b2291bdf368cf88915136f`
(tree `d0845922d98ad12d9a73287a7a7e28d4a856b49f`) and recovery
`623e7bb4eae20880f784f2317c8761e979c708f5`
(tree `2d1cc2d5287ae8655fcaa6d4c6358f06252107c4`). Main merges the earlier recovery
snapshot. Latest recovery differs only by 18 added uncapped files and its
AGENTS update. Local `7ac9cca0795e8d8f98f1e2cdb7bcb546fbe30b67` has that exact
969-file recovery tree and is the non-destructive working base. Main is not
rewritten, reset or assumed wrong. Preserve source/history and the final receipt
on the existing private recovery branch with a non-force expected-head lease.
