# Independent ten-notebook bounded execution security review

Date: 2026-10-09 UTC.

## Result

**Pass within the reviewed bounded-execution, typed-compilation, synthetic-witness, candidate-routing and notebook-bootstrap scope. No open security blocker remains in the exact frozen files below.** This is not whole-experiment approval: prerequisite/report authenticity, global accounting, model supervision, scientific conclusions and publication are covered by the separate lead review.

The approved source lock is `5483b47b573960c4dba64e2af95efdb1a92e19c2f9bdf652a8b45d9db45e290d`.

| File | SHA-256 |
| --- | --- |
| `arc_suite.py` | `d2ee8fee3246b8b36f08842e30ce6c8ecc6efea14404d827833c40193d558571` |
| `arc_suite_policy.py` | `78e1f445acf6763b0f8b28c5434d13414e658c8c8a0ec8b0ad61514843271b75` |
| `arc_typed_ir.py` | `8802c4d8e36f2a43acac1abec5a7c2a5b913461cf9f51f7bc7a3eb274ef72ff9` |
| `arc_curriculum.py` | `158263e2e417e02b80a0726c9a436bcd842500b64407d3bc5afa0f595c43238c` |
| `arc_program_v2.py` | `52bc22ffdf32198ceee209b68f68840869086af7d4372e54ec7d7b0297fe760d` |
| `arc_bounded_v2.py` | `9f210e97ddea7f98358ce8d3551310fe1411d57db27c21d7d80f705ce5d41ab7` |

Unchanged legacy N5 replay references: wrapper `fbcf0c933561067b6c9b4fc1e4c44048f02bbd8348ba312d06da37b3f22ebba7`; runtime8 `410713680242c0af12f4216181cd0a6318f46788e98e0577b4bfb67b9d2fc911`.

Hashes remained identical before/after the affected final tests. All source-lock entries and the exact-file interpreter release were independently rechecked in `final-binding-check.json`. Any change requires affected-test reruns and a new binding.

## Evidence summary

- **186/186 execution-layer cases passed:** 114 new language-extension probes, 37 inherited functional probes, 21 inherited IPC/lifecycle faults and 14 additional lifecycle/strict-IPC tests. Actual worker limits, real timeout/reaping, query-phase child termination, parent interruption and bytecode-cache bypass were tested. See `SECURITY-REVIEW-INTERPRETER-FINAL.md` and its referenced evidence.
- **261/261 compiler/curriculum checks passed:** strict parser/injection/type/value tests, actual execution of every one of the 137 atomic plans against an independent reference, composition/edge cases, finite-prior properties and 24 synthetic episodes across every family. The builder's full 512-episode/1,024-call final artifact was separately inspected. See `SECURITY-REVIEW-COMPILER-CURRICULUM.md`.
- **9/9 candidate-route checks passed**, with 13 genuine fresh CPU verifier subprocess calls, covering raw programs, typed plans, N12 search, both N5 replay wrappers and N13's supplied verifier closure.
- **33/33 policy noninterference checks passed:** altering query prediction, query success/errors, eligibility, timing/gas and synthetic query-marker fields does not affect the visible-demo parent key, repair text or next-message selection.
- **18/18 notebook-loader checks passed:** strict manual Boolean, invalid base64/compressed hash, too short/long decoded size, trailing streams, bounded decompression overflow, missing/extra source inventory, altered source, unsafe paths, source-directory/file symlinks, existing changed source, cache poisoning and a valid intercepted active bootstrap. All ten notebooks contain the same reviewed bootstrap and exact source-lock binding.

These counts mix explicitly labeled semantic comparisons and fault probes; they are not claimed as model or benchmark trials. No evaluator gold or actual model output was needed for the independent final tests.

## Candidate execution routes

Source inspection and focused integration tests establish:

1. Raw Python-like candidates and typed-IR compiler output enter `arc_program_v2.verify_program`. Typed plans are strict data with fixed templates; no arbitrary model source fields, paths, import names or callables are interpolated.
2. N12's shared proposal pool only parses/compiles typed data to production counts. It returns no candidate, performs zero verification calls/steps and explicitly does not claim AST admission. Actual finite-grammar search programs enter the same CPU verifier.
3. N5 replay selects only the exact approved legacy wrapper/runtime or new wrapper/runtime. Both routes were exercised with synthetic replay records; no saved real response or evaluator label was read by these route tests.
4. N13's main-suite closure invokes the source-verified `verify_program` for witnesses and mutations. The standalone helper also loads the exact pinned wrapper source safely after its cache-integrity correction.
5. Direct-grid proposals are bounded JSON/grid data, not program execution.

No direct `execute_program`, Python `eval`, `exec`, or executable-code `compile` call exists in the main suite, policy, typed compiler or curriculum. Trusted application loaders intentionally compile only already-hash-verified application bytes; Python AST parsing is not execution of candidate source. The underlying interpreter is reachable only through the reviewed wrapper on production candidate routes.

Route fixtures replace trusted setup/component lookup and shrink the grammar/full curriculum body to a small synthetic workload, while forwarding actual candidate verification to genuine subprocesses. They prove the routing boundary, not full pipeline, budget or prerequisite correctness. These limits are recorded in `entrypoint-routes-final.json` and its test source.

## Compressed notebook entrypoint

Every final notebook embeds the source lock and hashes for the same closed source inventory. Bootstrap SHA-256 is `dc14bcbb53acff7ad4f344a796d818adbc5025585f791c0f5b76a59d38716e96`; exact final notebook file hashes are recorded in `notebook-loader-security-final.json`.

Before an active import, the bootstrap validates the compressed digest, bounded decompression length and stream completion, complete source inventory, safe names and each source hash. It rejects symlink output/source paths and mismatched existing files. The entry loader uses verified bytes retained in the decoded payload rather than rereading the filesystem, so a timestamp/size-matching substituted `.pyc` is ignored. Child components then apply their own exact-captured-source validation/cache bypass.

The notebook fault tests executed trusted bootstrap application code in reviewer-owned temporary directories. The actual suite launch was intercepted immediately after the genuine entry-module import, so no model, GPU, dataset production, evaluator or real curriculum run could start. The lead review separately checks all ten notebooks' inactive behavior and full embedded hashes.

## Corrected findings

Two concrete trusted-loader integrity defects were found and fixed by the assigned writers:

- `arc_suite.component` originally hashed a source file, then separately captured/compiled unchecked bytes. An independent reviewer marker fixture reproduced the time-of-check/time-of-use gap. Final code hashes the exact capture before import/cache reuse. `component-source-binding-final.json` confirms rejection.
- Standalone `arc_curriculum.fresh_verifier` originally used ordinary import but reported source-file hashes. Matching poisoned bytecode could therefore run under authentic provenance. Final code verifies the frozen wrapper hash and uses a captured-source, cache-bypassing loader. `curriculum-verifier-cache-final.json` confirms correct behavior at the explicit fixture path.

Neither was demonstrated to be writable or reachable by a model candidate. They were source-identity/cache guarantees required by the review threat model. Two misleading contract/documentation phrases were also corrected before the interpreter freeze.

## Final evidence files

- `entrypoint-routes-final.json`, `entrypoint_execution_route_probes.py`
- `feedback-isolation-final.json`, `feedback_isolation_probes.py`
- `component-source-binding-final.json`, `component_source_binding_probe.py`
- `curriculum-verifier-cache-final.json`, `curriculum_verifier_cache_probe.py`
- `notebook-loader-security-final.json`, `notebook_loader_security_probes.py`
- `final-binding-check.json`
- Identical `final-integration-before.sha256` and `final-integration-after.sha256`
- The two detailed scoped reports and their referenced execution/compiler evidence

Earlier drafts and failed harness expectations remain as historical evidence. The initial proposal-pool routing expectation was updated when that path intentionally became parse-only; the initial notebook cache harness counted unrelated standard-library imports before being narrowed to the entry module. Neither was a production defect. Only the final hash-bound evidence above supports this result.

## Final localized revalidation

After the first integrated approval, the writer made exactly two localized changes relative to captured main source `d983346748eb68691c9d04ab41f25a08e3a244af062a573a12103246d8dc0017`: malformed prior-loading errors now return fail-closed BLOCKED before installation/model loading; and independent model-root counts exclude CPU replay/search with an explicit scope label. The exact two-hunk delta is retained in `final-localized-revalidation.diff`.

No candidate capability, compiler, policy, interpreter or verifier changed. The final `d2ee8fee…` / `5483b47b…` binding reran nine candidate-route checks (13 genuine CPU verifier calls), all18 notebook-loader probes, the component captured-source race probe and all source-lock/release checks. All passed. The unchanged186 execution-layer,261 compiler/curriculum and33 policy tests retain their exact-file bindings; the full507 were deliberately not rerun. `final-localized-revalidation.json` records this evidence reuse explicitly. Broader gate/report correctness remains the lead review's scope.

## Limits and authorization

This remains a bounded-language interpreter with OS containment, not a proof for unrestricted Python. Source paths, source immutability, executable, OS and host-supplied configuration/callbacks are trusted. Gas is not total host instructions or total live heap; OS limits provide the independent resource boundary. Query error/outputs stay outside repair feedback, but this review does not independently certify the complete evaluator/gating system.

All reviewer work was native-cloud, CPU-only and synthetic. No production source was edited. No evaluator gold, GPU/paid/model run, training, authentication, publication, local-computer task or network action occurred. Approval is hash-bound and scope-bound, not authorization to execute or publish the notebooks.
