# Qwen3.5-4B pilot 003 pre-version retry

Status: **Decision 0023 authorized one corrected submission; not yet pushed**.

Pilot 002's `SaveKernel` call returned HTTP 400 without a version receipt or
model work. The owner directed retry. This distinct identity preserves the
failed pilot 002 bytes and uses the shorter title `IRIS-X 4B LoRA pilot 003`
and matching slug `danielwuu/iris-x-4b-lora-pilot-003`. The previous 54
character title is a possible, unproven source of the validation failure;
the corrected title and slug are 24 characters and match the installed
Kaggle CLI slugification result.

The [draft plan](configs/draft-4b-pilot-003.json) binds the same private
Qwen3.5-4B model Dataset v2 and offline wheels, official
`arc-prize-2026-arc-agi-2` competition mount for challenge-file presence
only, one L4 device 0 with at least 22,000 MiB, Internet disabled and USD 0
paid cost. Only one synthetic grid demonstration may be trained, for at most
two LoRA steps and 128 training tokens. There are zero model generations,
teacher calls, ARC scoring or competition submissions. The notebook's
hardware and mount preflights and runner's failure diagnostics remain the
same as pilot 002. The 1,800-second notebook, 1,500-second worker and
300-second finalization bounds also remain.

The local draft refuses execution until an authorization file binds Decision
0023, draft-plan SHA-256
`14f95a83953777e7261b530e38d5cf2d0b33486ee4dc62fe52ad435f91cfb443`,
new run ID and final kernel ID. One `SaveKernel` call is authorized for this
exact package. If a version is accepted, only that version may be followed
to terminal and retrieved once. If the provider rejects before a version,
retain its response and repair under a separate bound identity; never repeat
the same failed payload unchanged.
