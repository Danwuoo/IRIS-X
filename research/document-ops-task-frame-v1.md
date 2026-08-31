# Document Ops Task Frame v1 Qualification

- **ID:** `document-ops-task-frame-v1`
- **Status:** comparative — qualified local research frame
- **Scope:** Accounts for all 48 preserved VANTA Document Ops fixtures and identifies bounded local/substrate eligibility. It does not create a representative, general, or validated benchmark.
- **Corpus records:** `src.vanta`
- **Machine record:** `research/task-frames/document-ops-v1.json`

## Result

All 48 source fixture directories were inspected through their `task.json`, declared input bytes, `expected/acceptance.json`, and other fixture-local expected artifacts. Relevant source mechanisms were also inspected in VANTA's action executor, structured-edit implementation, path guard, recovery policy/runner, replay runner, and working-set compiler. Imported behavior remains evidence rather than architecture authority.

| Qualification status | Count |
| --- | ---: |
| `qualified-local` | 21 |
| `qualified-with-copied-workspace` | 14 |
| `qualified-for-substrate-only` | 7 |
| `deferred-framework-dependent` | 6 |
| `deferred-contract-unclear` | 0 |
| `rejected-for-current-frame` | 0 |
| **Total** | **48** |

| Source stratum | `qualified-local` | copied workspace | substrate only | framework deferred | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Traceability extraction | 6 | 0 | 0 | 0 | 6 |
| Terminology consistency | 6 | 0 | 0 | 0 | 6 |
| Simulated patch and diff | 0 | 0 | 6 | 0 | 6 |
| Reversible edit and commit | 0 | 6 | 0 | 0 | 6 |
| Invalid action and path guard | 6 | 0 | 0 | 0 | 6 |
| Evidence and verifier challenge | 3 | 3 | 0 | 0 | 6 |
| Journal, replay, and recovery | 0 | 5 | 1 | 0 | 6 |
| Working-set long context | 0 | 0 | 0 | 6 | 6 |

## Qualification decisions

The 12 traceability/terminology tasks are the existing IRIS-X read-only frame and remain eligible for controlled local execution. Six reversible tasks have explicit local mutation payloads and baseline bytes and qualify only inside validated copies with independent state oracles. Five recovery fixtures have explicit frozen-failure ingredients and targeted policies suitable for a narrow IRIS-X-authored recovery experiment. The replay fixture is substrate-only because its success depends on predecessor journal/runtime identity rather than a targeted recovery failure state.

The six simulation fixtures are retained as substrate-only. Their local actions are deterministic, but candidate-content/diff oracle artifacts are not uniform across the stratum; this batch does not invent a common executable arm merely to include them. Three evidence challenges are local wrong-output/diff cases; three state-changing fault injections require copied workspaces.

The six working-set fixtures are deferred as framework-dependent. Their candidate refs and expected inclusions are explicit, but executable success depends on the VANTA Working Set Compiler's required-first ordering, kind priority, and character-budget behavior. Adopting those semantics as an IRIS-X contract would be a research decision outside this qualification.

## Machine-readable groups and experiment use

The machine record provides `frame_v1_readonly`, `frame_v1_simulation`, `frame_v1_reversible_state`, `frame_v1_guard`, `frame_v1_evidence`, `frame_v1_recovery`, and `frame_v1_long_context` groups. A qualification group is not an instruction to execute every member.

This batch selects only:

- all 12 `frame_v1_readonly` fixtures for H-OR1a;
- all six `frame_v1_reversible_state` fixtures for H-SR1a; and
- five explicitly listed `frame_v1_recovery` fixtures for H-RCV1a.

No working-set fixture is currently executable in the frame, and no model candidate is run on any group.

## Provenance and validation

The active registered source identity is `src.vanta` / `snap.src.vanta.initial-import`, tree `4e095233520418705168f40a556177477839b052`. `tools/build_document_ops_frame.py` reconstructs the machine record from the preserved source files and fails on a missing/duplicate fixture, invalid status, path escape, ID mismatch, stale generated record, or changed registered VANTA tree.

## Claim boundary and uncertainty

- **Unknown:** original upstream revision and pre-import modifications to the VANTA snapshot.
- **Unclear:** real-world difficulty and representativeness of the 48 fixture contracts.
- **Not established:** benchmark validity, task-family generalization, or adequacy of source-authored expected artifacts beyond their role as declared local oracles.
- **Not evaluated:** model performance, system robustness, full working-set behavior, or all-fixture end-to-end execution.
