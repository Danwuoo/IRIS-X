# Independent typed compiler and synthetic curriculum review

Date: 2026-10-09 UTC.

## Result

**Pass for candidate-data handling, bounded compilation, synthetic witness correctness and the repaired standalone verifier loader in the exact files below.** This is not approval of the broader controller, gate/accounting system, notebooks, model runs or scientific claims.

| File | SHA-256 |
| --- | --- |
| `arc_typed_ir.py` | `8802c4d8e36f2a43acac1abec5a7c2a5b913461cf9f51f7bc7a3eb274ef72ff9` |
| `arc_curriculum.py` | `158263e2e417e02b80a0726c9a436bcd842500b64407d3bc5afa0f595c43238c` |
| Required verifier | `52bc22ffdf32198ceee209b68f68840869086af7d4372e54ec7d7b0297fe760d` |
| Required interpreter | `9f210e97ddea7f98358ce8d3551310fe1411d57db27c21d7d80f705ce5d41ab7` |

The actual `n5-nextphase/src` copies were used. All four hashes remained unchanged across the final independent run.

## Independent evidence

**261/261 independent adversarial and semantic checks passed** in `typed-ir-adversarial-final.json`, produced by `typed_ir_adversarial_probes.py`.

- Strict parser rejects malformed/wrapped/trailing JSON, duplicate keys including escaped-key collisions, booleans/floats/nonfinite parameters, unknown operations, missing/extra keys, source/path injection fields, private/host-looking operation names, overlong/invalid-Unicode input and overly nested data.
- Every numeric parameter is an exact integer selected from a finite allowed set. Operation names never become arbitrary source identifiers. Compilation interpolates only already-validated bounded integer literals into fixed trusted templates. There is no candidate-selected file, module, callable or arbitrary source fragment.
- The interface is at most 4,096 input bytes and one to three operations. Compiled source is checked against 32,768 bytes and 2,048 AST nodes. It remains candidate AST data and must enter the reviewed verifier.
- **All 137 atomic parameterizations** were run through actual fresh verifier subprocesses and compared to a separately authored mathematical reference implementation. Additional tests cover three-step compositions, both connectivity modes, empty-foreground behavior, deterministic component selection/crops and scale/tile runtime axis bounds.
- The finite search inventory contains exactly **1,277 distinct plan identities**, including all 137 atoms and 1,140 selected two-step compositions. It contains no task/model/evaluator inputs. Uniform and fixed-alpha=1 smoothed masses are positive and normalized; ordering is deterministic; empty hard-pruned support is explicit. The language is intentionally smaller than arbitrary three-step composition and no complete ARC coverage is claimed.
- **24 independently executed synthetic episodes** span all eight authored families at augmentation offsets 0, 31 and 63. Independent reference formulas agree with every demonstration and query target. Their 48 witness/mutation subprocess calls confirm witnesses fit and match synthetic query targets, while every mutation is AST-admitted, executes all visible demos, fails semantically with `demo_mismatch` and does not execute the query.

The reference test implementation is ordinary trusted reviewer code. Generated candidate source is never executed as Python.

## Full builder-artifact audit

`curriculum-evidence-audit.json` independently checks the builder's full final run under `components/typed_ir/evidence/curriculum-512-reviewed`:

- 512 unique episodes, eight families with 64 episodes each; 384 train and 128 validation, split by family before augmentation.
- 1,024 validated, known-usage calls and 3,832,550 interpreter steps, with matching payload, ledger and source hashes.
- Every stored witness/identical-repair receipt is demo-fit and query-successful; every mutation receipt is admitted/executed but a visible semantic mismatch.
- F/P/R targets are byte-identical raw source; F explicitly supplies the target program as a formatting/copy objective. R input contains visible-demo feedback and query input, not its synthetic target.

Manifest SHA-256: `d1b383d634278050920a1511adf5227dc34169542995c00e266c27c0c83f33c8`.

Payload SHA-256: `6c52d04171d84d57dcaa7e77d46e38b0c8b6e57c7c1e29582eec48411aa95fb4`.

This is independent inspection of the builder's full-run evidence, not a claim that the reviewer independently repeated all 1,024 full-curriculum calls. The separate independent 137-atom and 24-episode executions are described above. Earlier exports with superseded source/grammar/format bindings are not the approved artifact.

## Corrected source-cache integrity finding

The first `fresh_verifier` helper imported `arc_program_v2` normally, then reported the `.py` file hash. A matching timestamp/size `.pyc` containing a reviewer-authored marker was executed while provenance still reported the authentic wrapper source hash and claimed a fresh OS-limited worker. This was an integrity gap in a trusted loader, not a demonstrated candidate filesystem-write escape. The main suite's supplied source-verified closure did not use that vulnerable helper.

Final `fresh_verifier` captures the explicit wrapper source, checks the frozen expected verifier hash, and uses a cache-bypassing loader to import exactly those captured bytes. It also checks the pinned interpreter. The independent poisoned-cache fixture, using the explicit fixture wrapper path, now passes; source/candidate execution remains separated. Evidence: `curriculum-verifier-cache-initial.json`, `curriculum-verifier-cache-corrected.json`, and `curriculum_verifier_cache_probe.py`.

## Remaining scope and assumptions

Synthetic generator formulas are explicitly authored independent Python operations, not execution of their compiled witness source. There are no imported evaluation generators, actual ARC inputs, evaluator gold, model calls or training in these review tests. Synthetic query targets are legitimate authored labels and are compared only to independently verified witness outputs.

The injected `verify_fn` API is trusted host test/integration infrastructure, not model-controlled input. Main-suite integration must supply the reviewed `verify_program` closure. A caller deliberately supplying forged receipts/provenance is outside this candidate-data threat model. Path/module/OS integrity and immutability after verification remain deployment responsibilities.

No production code was edited by this reviewer. No GPU/paid run, authentication, publication, local-computer task or network action was used. Detailed accounting, prerequisite authenticity, overall process supervision and final notebooks are reviewed separately.
