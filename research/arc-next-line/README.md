# Next ARC-AGI-2 line: full-vocabulary small-model proposal/check/repair

This is a new implementation and manual calibration package, not a measured
accuracy improvement. No GPU training/inference was performed by the assistant.
See Decision 0066 and the final notebook package/readback receipt for authority.

## Evidence-driven question

The completed uncapped predecessor finished all 512 task-local updates and six
searches. Independent trusted-source verification passed. Its 41 distinct
retained candidates still achieved only top-1/top-2/pool-oracle 1/6 on the six
already exposed development tests. Removing telemetry/search ceilings repaired
completion and expanded coverage; no correct candidate exists in the five missed
pools. More reranking alone cannot recover absent solutions. This is evidence
for trying better proposals/representations/adaptation, not proof that the new
method will work.

## Staged workflow

1. Preserve and verify remote/source/result evidence.
2. Resolve exact research referents and model/hardware identities using primary
   sources. Separate ARC-AGI-3 results from actual ARC-AGI-2 evidence.
3. Lock official model weights/tokenizer/license metadata, training-only data
   inventory and environment choices. No weights are downloaded during research.
4. Publish a new private, unexecuted notebook. Its embedded code is hash-bound,
   every operational switch is False, and it cannot provision or start a VM.
5. Owner prepares public pinned materials and the reviewed environment on the
   intended runtime. Paid G4 placement/entitlement is not inferred from saving
   a notebook on Kaggle. Detect the actual one-GPU device before model work.
6. Run `smoke2`: native full-vocabulary BF16 model, SDPA, text LoRA, two real
   optimizer steps, finite gradients/loss, resource evidence, adapter export and
   reload-equivalence. This establishes compatibility, not ARC accuracy.
7. Manually select `pilot16` or `pilot128`: bounded demonstration-only SFT using
   task-group-disjoint validation. No silent full-training or all-model sweep.
8. Run architecture A/B/C independently before/after the chosen adapter:
   direct-grid proposals; program proposals plus deterministic demonstration
   checking; identical program format plus structured failure-feedback repair.
   Hold model, tasks, seed policy, call/token/context/wall limits fixed. Record
   actual usage and completion; equal caps are not a claim of equal FLOPs.
9. Evaluate sealed outputs in a separate evaluator process/file. The four-task
   default is an engineering screen, too small for promotion. Expand only after
   fit/runtime checks and a declared budget. Select among models using measured
   held-out outcomes, speed, VRAM and deployability; retain preference order as
   a tie-breaker, not an accuracy conclusion.
10. Export exact base identity + safetensors LoRA + full tokenizer + inference
    code/config + license + environment/artifact manifests. Qualify one L4
    replica before four-way task parallelism, then a full offline dry run. No
    official submission is made by this work.

## Scope of the first architecture

Generated Python *syntax* is interpreted by a bounded custom language engine.
There is no Python `eval`/`exec`, import, attribute access, file/network operation
or generated shell command. Generic loops, conditionals, indexing and grid
primitives reduce the prior fixed DSL's search ceiling, but this remains an
explicit restricted language. Unsupported syntax, timeout and empty pools are
measured misses, not silently replaced successes.

Demonstration-perfect programs are merely consistent hypotheses. First A/B/C
results explicitly say `lodo_status=not_run`; replaying training examples is not
leave-one-out validation. Neither Jev hosting nor large API teachers are part of
the offline solution. Full framework integration, trajectory SFT, AVO mutation
learning, preference/RL training and verifier learning require separate evidence.

## Hardware and rules

Google documents g4-standard-48 as one RTX PRO 6000 Blackwell GPU, 48 vCPUs and
180 GiB host RAM; marketed GPU memory is 96 GB. Runtime observations determine
actual available bytes and driver/kernel compatibility.

The official ARC-AGI-2 notebook requirements currently specify four L4 machines,
no Internet, maximum 12 hours and `submission.json`. Four 24 GB devices do not
form one automatically pooled 96 GB device. First deployment assumes four
independent replicas; an 8–9B BF16 model's weights alone do not establish that
its KV cache, workspace and runtime will fit one L4. Do not transfer Blackwell
compiled kernels or assume Blackwell-only quantization will run on Ada.

Primary references:
- https://docs.cloud.google.com/compute/docs/accelerator-optimized-machines#g4-vms
- https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview/description
- https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/rules
- https://www.kaggle.com/docs/notebooks
- https://github.com/arcprize/ARC-AGI-3-Kaggle-Starter#choosing-an-accelerator

Kaggle documents export/upgrade to Google Cloud notebooks. ARC Prize's ARC-AGI-3
starter specifically reserves its Kaggle RTX 6000 option for ARC-AGI-3. This
package does not claim ARC-AGI-2 access to that restricted allocation, reuse it,
or change competition mounts to obtain hardware. The runtime is host-neutral
and fails closed unless the intended training device and material gates pass.
