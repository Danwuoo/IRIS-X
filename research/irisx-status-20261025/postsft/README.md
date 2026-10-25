# Post-SFT: separate device topics, one evidence standard

## Verified K1 scope

`K1-RESULT.json` is a sanitized static aggregate of retrieved native results.
P1 FP32 compute on four TPU ranks passed the original numerical tolerances on
the executed probes. Method updates were TTT 2, DPO 1 and paired winner-SFT 1;
one further engineering update was reset. RLVR's fresh four-candidate pool was
all correct, so its relative-reward update was scientifically skipped.

Across six pools there were 24 candidate slots but only three distinct
parent/body pairs. All comparable output bodies stayed unchanged. The two
parents were TRAIN engineering cases, not independent evaluation. TTT had
identical maximum wall/token/candidate caps, **not equal actual cost**.
DPO and SFT checkpoints were saved and read back, but their native restore
path was not executed. Do not call this full training acceptance or improvement.

## New topics, not duplicate complete experiments

- **TPU:** natural-pair DPO versus matched winner SFT, one bounded iterative-SFT
  round if justified, and current-policy RLVR reward coverage/updates.
- **GPU:** support-only episodic TTT, diversity/search and selector replay.
  See the separate [GPU study](../gpu-search/README.md). CPU tests and a saved
  notebook are not CUDA execution; no GPU run is authorized by this publication.

Minimal common numerical smoke is useful. A complete three-arm study should
not simply be repeated on both devices. A GPU unadapted TRAIN pool is a
possible offline DPO/SFT source if exact model/adapter/token/prompt/seed/verifier
provenance survives. TPU must recalculate its own reference log-probabilities;
RLVR needs fresh current-policy rollouts. This is a proposal, not a new
cross-service transfer grant or an implemented pipeline.

## Fixed supply versus paid exposure

[DISCOVERY-PANEL.json](DISCOVERY-PANEL.json) selects 16 parents from the prior
32 TRAIN metadata records: one longer public prompt per ten known first-party
families plus six official-training length strata. Official mechanism labels
remain unknown. Selection does not inspect reward or target contents; target
token lengths are checked only afterwards for engineering capacity.

Fixed prefixes of 4/8/16 can be chosen **before rewards** using measured
throughput/memory/remaining budget. The 32-parent extension only reuses the
original source supply. New views, more tokens and repeated epochs are not new
families. No silent support/target truncation is allowed at context 3072.

The supply is not limited to those 32 experimental parents. A separate
reviewed [TRAIN-only length census](../../../tools/grid16_train_length_census_20261025/README.md)
rechecked the existing 800 official demonstration episodes / 2,573 LODO views.
At context 3072 with a 512-token reserve, 743 parents have at least one eligible
view (2,380 views; 727 parents have all views eligible). This is disclosed
TRAIN answer-length engineering screening, not new mechanisms, a clean holdout,
model success or automatic expansion of the fixed 16-parent panel.

[TPU-MATRIX.json](TPU-MATRIX.json) is a disabled conditional matrix, not a
runtime launcher. Initial coverage scout is G2/max512; later G4 and 8/32-update
three-seed comparisons require separate measured cost admission. One 16-parent
G4 pool has a 32,768 new-token ceiling. Multiplying pools/seeds/updates makes a
full matrix far larger than a two-hour job. The recorded K1 short-decode proxy
is not a steady-state throughput guarantee or a GPU benchmark.

All updates remain **frozen 4B base plus LoRA r32**, not full-parameter training.
Record planned/dispatched/valid/unknown/committed work, repeats, actual modelwall,
restore and failure costs. Same updates or maximum caps do not imply equal
FLOPs or realized cost. Uniform reward is not infrastructure failure; skipped
updates cannot be fabricated to complete a comparison.

## Historical decisions retained

The original method-landscape §7 directs sparse signal toward verified supply
and rejection-SFT before blindly adding RL steps. Once RL really updates,
compare with both frozen A and whole-modelwall matched SFT C: B>A with C>=B
does not show extra RL value. Selector work needs a real oracle/selection gap,
not a candidate pool lacking correct answers.

The old 14B DFA/DDIS A256/B32-G8/C study, the separate 17-October full-vocabulary
AF3 successor and present 4B/grid16/P1 study have different contracts. Actual
AF3 CPU loss/gradient parity did not prove model replay or quality. Old v43/v45
had zero RL commits; the v50 terminal effectiveness record remains unknown.

## Promotion remains NO-GO

A genuinely independent grid16 holdout and retention panel are still missing.
The old 544 text/JSON contract is not a substitute, and changing view or device
does not remove base-model or prior-development exposure. Only an isolated
evaluator may bind lawful gold; method selection uses TRAIN discovery, never
final answers or scorer hints. Final evaluation is locked after method/seed/
checkpoint selection. Positive discovery results alone cannot start formal
training: repeatable paired benefit, uncertainty, retention, per-arm restore,
data-cursor correctness, throughput/cost and explicit execution authority are
separate requirements.
