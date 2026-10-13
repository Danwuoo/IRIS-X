# Fixed panel contract for the manual Qwen14B portfolio experiment

## Scope and interpretation

The first release has 63 fixed cases, five retained checkpoint states (base, grid8, grid16, program8, program16), and two output representations. This is 630 fixed representation-case cells before reload controls, scoring, and training costs. The inherited 12-hour hard session limit and measured source-bound runtime forecast decide whether the experiment starts; the data plan is not a runtime guarantee.

- 13 seen regressions: the exact six old authored train controls, six old same-family queries, and training-dev:b1948b0a. These have already been inspected and are never reported as fresh transfer.
- 12 fresh authored same-family queries: two new independent task/grid draws for each of the six trained transforms. Transformation-family overlap with training is intentional and explicit.
- 6 heldout-family queries: two task parents each for pad-zero-border, tile-2x2, and shift-right-zero. These families do not enter the optimizer or canary selector.
- 8 canaries: two independent task parents each for mask-main-diagonal, crop-inner, append-zero-row, and checkerboard-mask. These four declared transform families are disjoint from optimizer and holdout families. Their targets may rank checkpoints; they are development evidence.
- 24 genuine ARC task parents: fixed hash-ranked IDs from the existing 200-parent development partition of the pinned ARC-AGI-2 official training source. All four previously exposed ARC parents are excluded. The last original training demonstration is withheld as the query; original task test fields are discarded. This is neither ARC public evaluation nor a PUBLIC120 score.

Authored grids come from an explicit SHA256 counter generator and fixed seed, without selection using v18 outputs. This does not establish base-model pretraining cleanliness. No prior-project-exposure-free claim is made for genuine ARC. Declared ancestry and exact/D4/color/demo-order duplicates are checked, but arbitrary semantic family independence is not proved; real ARC task IDs are not represented as known independent semantic families.

## Preregistration and source pins

The canonical metadata-only preregistration is `validation/panel-preregistration.json`. It contains every selected official ID and expected upstream Git blob binding. The seed is `irisx-qwen-portfolio-20261012-panels-v1`; IDs are ranked by SHA256(seed + ':' + task_id) before task bytes or model outcomes are read. Evaluation takes the first 24 eligible historical development IDs; the staged training pool takes the first 32 historical training IDs. There are no replacement IDs.

Official source: arcprize/ARC-AGI-2, commit f3283f727488ad98fe575ea6a5ac981e4a188e49. Inventory file SHA256: 53fc35f54fa1b8a29403c5ede3e3880e8588c40c75a4a5783692a9a13a3e95cb.

Production requires an independently mounted closed 1000-file official training directory. Runtime reads only the fixed 56 parents and four historical regression parents, verifies byte count/Git blob, sanitizes to demonstrations only, and checks provenance again on validation. Symlinks, public/evaluation/answer paths, changed inventory, unknown or missing tasks, changed ancestry, and cross-split exact/task/known-variant overlaps fail closed. No official task JSON is downloaded, copied, or packaged in source.

## APIs and data boundaries

- panel_contract.preregister_panels(): reads only pinned inventory metadata and returns explicit IDs, source pins, strata, and stable digest.
- data.load_official_panels(training_root, preregistration=None): verifies the mount and selected source blobs. It never uses a public evaluation task or original test label.
- data.build_dataset(development, output, deadline, ledger, training_root=..., tiny_cpu=False): constructs the fixed panel and 24 grid / 6 bounded-VM-verified authored program optimizer records.
- dataset.solver_cases: exact target-free case schema containing case_id, scope, family, demos, query_input, and closed source metadata. Generation must project only demos and query_input to prompts.
- dataset.canary_targets: eight allowed selector-development labels.
- dataset.target_escrow: 55 other labels. They are separate from solver cases and persisted separately.
- panel_contract.context_eligibility(cases, native_model, ...): uses native prompt tokens and fixed output reservation only. It never reads target lengths to select candidates. Excluded whole examples remain in the fixed denominator; there is no truncation, dropping, or replacement.
- data.open_target_escrow(dataset, prediction_seal): requires the persisted canonical full 5×63 prediction artifact, explicit omissions, all per-task portfolio decisions, both replayable eight-canary rankings, and exact source-case bindings before releasing labels. Sealed ranking inputs must reconcile with sealed canary predictions and scores. The guard enforces application ordering, not an OS isolation boundary; hashes are commitments, not signatures.

The package writes solver-cases.json, target-escrow.json, canary-targets.json, and preregistration.json as separate runtime artifacts. It does not put raw official task JSON into its source package.

## Optional real-training stage

The fixed 32 real training parents are disjoint from the 24 real evaluation parents and from authored canary/heldout parents. prepare_real_training(dataset, witnesses=()) generates all original-demo LOO grid records and retains the original 32-parent denominator. It does not train or enable stage two. Dev anchors use visible demonstrations; no heldout gold is made into an optimizer target.

Optional program records must be supplied as candidate source plus a genuine persisted bounded-VM proof covering exactly the same original training parent's demonstrations. Unknown, evaluation, canary, wrong-parent, and fabricated proofs are rejected. There is no real-ARC reference/gold program table and no program fabricated from an evaluation target. Candidate generation and its source-bound budget/admission run are not implemented or authorized by this helper. Demo fit is not proof of independent semantic correctness. Stage two remains disabled unless a future source-bound budget plan explicitly enables it.

## Verification limits

Synthetic fixtures are explicitly labeled and do not count as genuine ARC results. Cheap normal and Python -O tests cover source closure, fixed membership, ancestry/content rejection, target-blind context eligibility, separate escrow ordering, complete denominator preservation, real persisted bounded-VM witness admission, and the authored optimizer boundary. No native Qwen tokenizer, GPU, provider, or genuine ARC task content was used in these local tests. Thus native-context inclusion counts and actual genuine-task duplicate checks remain runtime admission checks.
