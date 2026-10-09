# Independent bounded-v2 interpreter/verifier security review

Date: 2026-10-09 UTC.

## Result and exact scope

**Pass for the bounded-language CPU verifier threat model. No open safety blocker remains in the two exact frozen source files below.** This approval does not approve the still-changing ten-notebook controller, typed compiler, curriculum, deployment, evaluator, publication or scientific conclusions. Those integration boundaries receive separate review.

| File | SHA-256 |
| --- | --- |
| `n5-nextphase/src/arc_bounded_v2.py` | `9f210e97ddea7f98358ce8d3551310fe1411d57db27c21d7d80f705ce5d41ab7` |
| `n5-nextphase/src/arc_program_v2.py` | `52bc22ffdf32198ceee209b68f68840869086af7d4372e54ec7d7b0297fe760d` |

Both hashes were identical before and after the final tests. A later change invalidates this binding and requires affected-test reruns. The wrapper's `AGENT_SHA256` matches the reviewed interpreter.

Approved baseline references, unchanged in this review:
- Prior N4 wrapper `arc_n4_program.py`: `fbcf0c933561067b6c9b4fc1e4c44048f02bbd8348ba312d06da37b3f22ebba7`.
- Prior runtime8 `arc_next_agent.py`: `410713680242c0af12f4216181cd0a6318f46788e98e0577b4bfb67b9d2fc911`.

## Final evidence

All final runs used standard-library CPU processes in the native cloud workspace, with ResourceWarning promoted to an error in functional/lifecycle suites.

- **114/114 newly authored independent extension probes passed**, using real subprocess verification for all candidate tests.
- **37/37 inherited independent functional regression probes passed.** These preserve prior syntax staging, complete static guarding, output-grid admission, task/query separation, caller isolation and shared gas tests.
- **21/21 inherited protocol/cleanup fault probes passed.** They preserve task-bound demo validation, strict admission/result coherence, full unknown-work gas charging and malformed-final feedback retention.
- **14/14 additional lifecycle/strict-IPC probes passed.** Two use real processes: terminating the worker immediately after observing its flushed query-pending record, and interrupting the parent at that same stage. Both workers were killed/reaped; query termination retained validated demo-only feedback and charged the full 200,000-step reservation. Additional cases cover duplicate keys, NaN/Infinity, invalid UTF-8, extra records, invalid gas types/ranges, SystemExit and unexpected IPC errors.
- **Actual OS limits were observed before sending any candidate input:** CPU 2 seconds, address space 268,435,456 bytes, and output-file size 65,536 bytes, hard and soft limits alike.
- **An actual tightened 1 ms timeout killed and reaped its child**, returned no candidate and charged 200,000 steps. The idle limit-inspection worker was also reaped.
- **A matching timestamp/size substituted `.pyc` fixture was ignored.** The loader imported the captured hash-verified source rather than the reviewer-authored alternate bytecode.
- **A changed interpreter source was rejected before AST admission.**

Evidence artifacts:
- `inherited-regression-final.json` and `independent_verifier_probes.py`
- `extension-probes-final.json` and `extension_adversarial_probes.py`
- `lifecycle-extension-final.json` and `lifecycle_extension_probes.py`
- `pinned-import-cache-probe.json` and `pinned_import_cache_probe.py`
- `resource-boundary-probes.json` and `resource_boundary_probes.py`
- Matching `final-interpreter-before.sha256` and `final-interpreter-after.sha256`

## Added-language assessment

### Metered while

Every condition/iteration is charged. Empty-body and continue-only infinite loops exhaust exactly the 200,000-step allowance. Normal completion executes loop-else; break skips it. Nested loop-else break/continue target the proper enclosing lexical loop. A helper cannot break/continue its caller's loop. Standalone loop-else control without an enclosing loop is statically rejected, including unreachable instances. Return inside while works normally.

### Narrow list methods

Only direct `.append`, `.pop` and `.extend` call nodes are admitted. Attribute extraction, attribute assignment, chained host introspection, arbitrary methods, keyword/star arguments and incorrect arity are statically rejected, even if unreachable. Runtime dispatch uses an explicit method-name branch and requires an exact built-in language list; it never uses getattr, a candidate-selected host callable or a host object.

Tests cover method return values, negative/positive pop indices, empty/out-of-range/noninteger pop, tuple/list extension, nonsequence rejection, list aliases, nested receiver calls, self-extension, shallow returned aliases, snapshot iteration while mutating, direct/indirect cycles, attempted cycle creation followed by removal, recursive-item overflow and depth overflow. Cycles fail immediately and cannot be hidden by a subsequent pop.

### Eager generator expressions and list(xs)

Generator expressions deliberately produce bounded lists immediately. Tests establish eager side effects, nested generators/filters, snapshot iteration, locally scoped comprehension bindings and shared nested aliases. Async generators, invalid iterables and overlarge products fail safely. `list(xs)` accepts only bounded list/tuple language values and preserves shallow-copy alias semantics; invalid arity, keywords, integers, bools and None are rejected.

### Identity and lone underscore

`is` and `is not` compare language-object identity; they expose no address or host capability. Tests cover None/bool identities, identical list aliases and distinct equal lists. The lone underscore works as an ordinary loop variable; other leading-private names remain forbidden. Identity of immutable values follows underlying object identity and is not a numerical equality operation.

Named helpers still take precedence over primitive names and contain only interpreted AST bodies. Host-looking helper names such as `eval` or `open` are safe when explicitly declared with bounded bodies; the corresponding undeclared host calls are rejected statically. Helper-over-primitive precedence was already present in N4/runtime8 and is not characterized as a new safety fix.

## Preserved boundaries

- Candidate text travels through bounded JSON stdin and is treated exclusively as AST data. It never enters Python eval/exec/compile-as-executable-code, a shell, import, dynamic attribute lookup or filesystem/network API. Python's AST parser and hash-verified trusted application-module import are distinct from candidate execution.
- The full-tree wrapper guard is mandatory. Direct `execute_program` is not the approved external admission boundary because additional complete static checks live in the wrapper. Every suite candidate path must use `verify_program`.
- Worker execution is fresh `sys.executable -I -B -S`, with closed unrelated descriptors, OS limits before input parsing, file-backed bounded stdout/stderr and unconditional child cleanup.
- The exact captured interpreter bytes are hashed once and imported through a loader that ignores bytecode caches and performs no second source read.
- Source size is 32,768 UTF-8 bytes; AST size 2,048 nodes; functions 8; locals 128; call depth 12; value depth 16; recursively counted value items 16,384; integer magnitude 1,000,000. All demonstrations and the single query share 200,000 interpreter steps.
- Query execution begins only after every visible demonstration fits. Demo-fit evidence is flushed before query execution. Query prediction/errors never enter repair feedback. Hard query failures retain only previously validated visible-demo evidence.
- A successful candidate is a rectangular 1–30 by 1–30 list grid of exact integer colors 0–9. Booleans, tuples, None, empty/ragged grids and out-of-range colors fail.
- Parent IPC validation remains strict JSON, validates types/fields/phase coherence and binds demo count, shapes and target colors to the exact serialized task sent to the child. Unknown work and malformed output fail closed with full reservation charged.

## Corrections during this review

Two misleading documentation phrases were corrected by the writer before the frozen run: the new separately pinned bounded-v2 was labeled runtime8 in the wrapper description, and a blanket attribute prohibition contradicted the explicit narrow list-method extension. Their corrected wording is included in the approved wrapper hash.

The broader controller review separately found a trusted component import time-of-check/time-of-use gap: `arc_suite.component` originally hashed a file, then captured and compiled different unchecked bytes. A reviewer-authored marker fixture reproduced it. The writer added a hash of the exact captured bytes, and the corrected fixture now rejects. This controller finding is documented in `component-source-binding-initial.json` and `component-source-binding-corrected.json`; it is not represented as a candidate filesystem escape or as whole-suite approval.

## Limits

This is a bounded interpreter with independent OS containment, not a security proof for unrestricted Python. Interpreter gas is deterministic accounting, not total host instructions or a global live-heap bound. Per-value recursive bounds do not imply a global heap cap; the OS address-space limit supplies that independent boundary. Source paths, wrapper bytes, Python executable, OS and parent-owned configuration are trusted. The interpreter cannot spawn descendants.

No evaluator gold, model weights, GPU/paid computation, authentication, local-computer task, publication or network action was used. No production source was edited by this reviewer. Kaggle execution, native model compliance, dataset mounts, full-run termination, scoring and scientific usefulness are outside this exact-file approval.
