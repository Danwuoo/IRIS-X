# Frozen integration contract, revision 1

This is a runnable research implementation, with actual GPU performance unverified.
Legacy sources are dependencies and remain byte-identical. Primary result is the
project PUBLIC120 micro pass@2; task-macro and all-test task success are secondary.

## Files and ownership

* Data/training writer: data.py, training.py, tests/test_data.py,
  tests/test_training.py, tests/test_training_neural.py.
* Native model writer: grid_codec.py, native_model.py,
  tests/test_grid_codec.py, tests/test_native_model.py,
  tests/test_native_model_neural.py.
* Agent writer: controller.py, program_tools.py,
  tests/test_controller.py, tests/test_program_tools.py.
* Lead: budget.py, session.py, worker.py, evaluation.py, build_notebook.py,
  source_pack.py, remaining integration tests, documentation and release.

All interfaces use JSON-safe dictionaries/lists at boundaries. No module import
may load torch, weights, datasets, evaluator answers, or start work. Neural imports
occur only inside explicitly called production/tiny-test functions.

## Data and prompts

A solver task is {'train': [{'input': grid, 'output': grid}, ...],
                    'test': [{'input': grid}, ...]}.
A grid is a rectangular, nonempty list of lists of exact ints 0..9, <=30x30.
No extra task/example keys. Training records have:
record_id, split ('train'/'dev'), parent_ids (nonempty strings), family_id,
kind ('grid'/'program'/'repair'), messages (chat roles/content), completion.
Global training admission rejects unknown parents, any protected ancestor, and
cross-split parent/family overlap. Synthetic records have independently verified
reference behavior and explicit generator-family provenance. No public label
inspection or model-generated unverified target becomes a training row.

Grid text is compact digits with newline-separated rows, no fences or JSON.
Grid prompts include all demos and one query input. Query targets never appear.
Program prompts use transform(grid) with the pinned safe-Python toolbox; returned
programs are validated and interpreted by the old bounded VM, never host exec.

## NativeModel API (native_model.py)

NativeModel(model, tokenizer, config=None) wraps already-loaded objects for tiny
CPU tests and production. NativeModel.from_config(config) loads the pinned local
Granite through existing native loader/hardware admission. Expose .model,
.tokenizer. Default context limit8192, prompt cap6144, output cap2048, full native
vocabulary, no remote code, local files only. Production hardware admission must
be retained; tiny CPU mode explicit and cannot claim production.

.generate(messages, *, kind, seed, max_new_tokens, deadline) returns
{text, input_tokens, output_tokens, elapsed_seconds, finish_reason,
 prompt_sha256, output_token_ids, valid, error?}. kind is 'grid' or 'program'.
Invalid/context-excluded/time-expired calls are explicit receipts. Native EOS IDs
come from the native tokenizer/generation config, never decoded-text guesses.
Grid constraints describe all rectangular <=30 grids, not a finite solution list.
If constraints cannot be proven against actual tokenizer, fail admission rather
than silently use a malformed-prefix/EOS fallback. Program decoding may be free
text and must be honestly labeled; no finite-5965 restriction.

.score_completion(messages, completion, *, deadline) returns
{nll_sum, token_count, mean_nll, input_tokens, elapsed_seconds, valid, error?}.
Use full native head shifted log-softmax and exact completion mask, native EOS,
no compact16-vocabulary slicing. Token accounting includes scoring forwards.
.close() releases owned model references; process shutdown is proven externally.

grid_codec.py exports encode_grid(grid), decode_grid(text),
grid_messages(demos, query), program_messages(task, facts=None, feedback=None).
Task memory supplied to prompts is verifier-authored typed facts, never arbitrary
model instructions. Actual native tokenizer material exists outside repository.

## Trainer API (training.py)

Trainer(native_model, config=None) operates on the same model/tokenizer. It may
attach LoRA when configured; tiny mode uses actual small neural objects, not fake
losses. Default proposed global rank32/alpha64, seven projection targets; rank is
one frozen session setting. Task adaptation clones the global adapter at that
same rank; it does not silently compose untested nested PEFT adapters.

.train(records, *, max_steps, deadline, checkpoint_dir=None, resume=None)
returns actual steps/tokens/loss/time/optimizer-state and checkpoint receipts.
Completion-only loss; no training if admission/context/deadline fails. Resume is
bound to model/source/data/config and includes optimizer, RNG and data cursor;
atomic save, never claim exact resume from adapter weights alone.

.snapshot(label) returns an immutable in-memory snapshot handle + fingerprints.
.restore(snapshot) restores trainable tensors, clears gradients, optimizer,
scheduler and task-local RNG state; verify exact fingerprints. Training code
must support .begin_task(task_id) and .end_task() against .freeze_global(), with
try/finally reset and receipts. No cross-task optimizer or adapter carryover.

.adapt_task(task_id, demos, *, max_steps, deadline) builds demo-only LODO records
and trains a fresh task state. One-demo task has no valid LODO; explicit skip.
Global refinement consumes only execution-verified train-parent trajectories.
Data preparation exports build_records(tasks_by_id, split_manifest, ...) and
validate_records(records, split_manifest, protected_ids). Writer may add helpers
without changing these entrypoints; message lead about necessary interface fixes.

## Controller API (controller.py)

solve_task(task_id, task, *, model, trainer, config, deadline, output_dir) returns
{task_id, policies, evidence, physical_usage, status}.
Policies keys 'global_grid', 'task_ttt', 'full_agent'. Each maps one item per query
input: {'candidates': [grid, ... <=2], 'status': ..., 'evidence_ids': [...]}.
Global_grid uses pre-task global adapter candidates; task_ttt uses adapted direct
candidates; full_agent fuses direct + verified program candidates. Direct grids
need not fit a program. Only all-demo-fit programs execute query inputs.

Calls and updates are physical events, shared logical policy views do not multiply
cost. Default per task: <=2 global views per query, <=4 adapted views per query,
<=2 initial programs + <=2 repair attempts total, <=8 common scoring views per
unique grid, <=32 unique grid candidates/query. Up to2 program hypotheses; repair
parent is deterministic best verifier score, not public answer. Deadline and
explicit total call/token/CPU caps further restrict these maxima. Select output
grids deterministically using declared verifier tier, common-view mean NLL,
unique augmentation support and stable tie-break. Invalid/missing likelihood is
explicit and cannot improve rank. No text 'confidence' counts as evidence.

Controller chooses tools from actual state: preserve initial direct-grid floor,
run demo-only adaptation, collect reversible views, escalate to programs when
budget and evidence justify, return to failed programs with bounded verifier
feedback, deduplicate, rank and stop on declared evidence/budget conditions.
Task memory is a bounded append-only typed record of hypotheses, receipts and
parent links, cleared between tasks. Model prose never becomes trusted control.

program_tools.py uses unchanged VM/verifier. API verify_program(text,demos,
output_dir,call_id) returns source/sha/demo result/partial score/errors/gas/receipt;
execute_queries(verified_candidate,query_inputs,output_dir,call_id) uses fresh
bounded subprocess only after all-demo-fit proof. Tool errors are data.

## Session ownership and scoring

The lead-owned worker runs all model/training/controller work in a separate owned
process/session. It receives solver/train paths only, no evaluator path. Its
parent enforces persisted session and stage deadlines, records PID incarnation,
waits for complete owned-process closure, validates predictions, then seals.
Only a fresh CPU evaluator imports the pinned historical scorer and reads public
gold after seal verification. Same-UID dataflow isolation is not claimed to be
an adversarial OS security boundary. Missing tasks keep fixed denominators.

Future default notebook is inert. Real assets/data/source/env hashes bound before
admission. No feature may auto-run a model, GPU, training, or external service.
