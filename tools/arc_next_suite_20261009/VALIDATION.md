# Validation scope and exact release

## Discovery scope correction: evidence-inputs-fix2-20261010

Acceptance passed: **97 CPU tests, zero failures/errors/skips, 141.307s**. Helper SHA256 is `06326cb8d4d3c303d348aef8d8c7898b64724053fccfce19d960cdde21e75943`. The actual returned N6/N7 Dataset and canonical runtime8 were used; all six generated notebooks were checked against a synthetic reproduction of the reported competition/.git directory tree. The competition namespace was not enumerated, ordinary repository evidence still participates in ambiguity checks, and a reproduced zero-call depth BLOCKED receipt safely advances to a fresh attempt without changing old bytes.

All scientific source bytes, source lock, N5–N8 notebooks and Dataset versions remain unchanged. Rebuilding the repaired notebooks is byte-identical. No GPU/model/training run, paid spend or Git action was performed. Exact acceptance and independent review are under `evidence/input-scopefix/`; see `docs/NOTEBOOK-INPUT-SCOPEFIX-20261010.md`.

## Notebook input repair: evidence-inputs-fix1-20261010

All scientific source bytes and source lock `29172a035efc7704cd3f60e663a714a7570c18f636fdca32304be94d02689d50` remain unchanged. The separately hash-bound helper is `b4bfe41fcb03d79086de279580549ccbe6acf2b68bc229c82190184311f77002`.

Acceptance passed: **88 focused CPU tests, zero failures/errors/skips, 141.249s**, with real canonical runtime8 and actual user-returned N6/N7 evidence. This includes 21 new input/retry tests. A further three actual provider-readback tests pass against the new private Dataset's downloaded auto-extracted layout, including all four N9–N12 gates and their generated notebook entrypoints up to a mocked CPU backend boundary. N14 still fails closed for missing N9–N11; N13 does no prior/model scan. Rebuilding the notebook-only repair is byte-reproducible.

No live GPU/model/training run or paid execution was performed. The first four notebooks and all scientific contracts are unchanged. Exact logs and receipt are under `evidence/input-repair/`; see `docs/NOTEBOOK-INPUT-REPAIR-20261010.md` for behavior and remaining runtime limitations.

## Current repair: runtime8-manifest-fix1-20261010

The 2026-10-09 identity and evidence below are historical. The owner’s first N6 launch exposed a real mounted-manifest integration gap despite the prior57 fixture tests. The repaired runner is `f1f8dfde826fa6c0dbf4ef4e88b1ae60df8964215af8ff02d197b7c49a1e2570`; source lock is `29172a035efc7704cd3f60e663a714a7570c18f636fdca32304be94d02689d50`. The canonical runtime8 manifest bytes are now separately pinned and tested; all scientific inputs and limits remain unchanged.

**Repair acceptance passed:**67 focused tests,0 failures/errors/skips,124.322s, including the real mounted-runtime regressions. Full repaired N5 and N13 CPU launches both completed; no model/training calls.

See [repair report](docs/RUNTIME8-MANIFEST-HOTFIX-20261010.md) and `evidence/runtime8-repair/` for the exact final tests, independent release, original-failure reproduction, and repaired full N5/N13 CPU launch receipts. Old evidence is not auto-migrated into current gates. For real mounted-asset regressions, run the focused suite with `IRISX_RUNTIME8_TEST_ROOT` set to the verified full runtime8 directory; without it, the mounted checks explicitly skip and do not satisfy repair release acceptance.

## Historical 2026-10-09 frozen production identity

- Source lock: `5483b47b573960c4dba64e2af95efdb1a92e19c2f9bdf652a8b45d9db45e290d`
- Runner: `d2ee8fee3246b8b36f08842e30ce6c8ecc6efea14404d827833c40193d558571`
- Bounded interpreter: `9f210e97ddea7f98358ce8d3551310fe1411d57db27c21d7d80f705ce5d41ab7`
- Program verifier: `52bc22ffdf32198ceee209b68f68840869086af7d4372e54ec7d7b0297fe760d`
- Typed compiler: `8802c4d8e36f2a43acac1abec5a7c2a5b913461cf9f51f7bc7a3eb274ef72ff9`
- Curriculum: `158263e2e417e02b80a0726c9a436bcd842500b64407d3bc5afa0f595c43238c`

## Passed

1. **57 focused tests** against an immutable copy of the final release. This includes all ten inert notebooks; active source-directory symlink rejection; missing and malformed prerequisite BLOCKED paths; every model-run schedule; typed compilation; actual isolated verification; fixed task/call/seed contracts; rehashed-contract tampering; post-score inventory and prior-ZIP validation; no-gold-before-seal; true/redacted feedback; durable interrupted CPU-search accounting; known-model-response versus incomplete-verification accounting; and N5 CPU reservations/unknown-work charging.
2. **Exact CPU tokenizer audit:** all560 initial prompts across40 exposed tasks and14 policies, using pinned Transformers5.8.1/tokenizers0.22.2/Jinja3.1.6 and the exact Granite vocabulary/template. No weights/GPU loaded. Object-view exclusions are explicit:33067df9 at6981 tokens and a096bf4d at7009. All other initial policy prompts fit6144.
3. **N5 actual replay:**122 isolated verifier invocations over61 unchanged N4 sources in each language. Both have61 CPU reservations and zero unknown CPU work. Old language:45 parsed,0 admitted,0 demonstration execution. Bounded-v2:45 parsed,29 admitted,23 demonstration executions,0 all-demo fits,0 selected query exact. Charged v2 gas1,529,608. Solver processes stopped and evidence sealed before evaluator gold was read. No gold was exported.
4. **N13 actual full suite launch:**512 episodes;1,024 attempted and known verifier calls;zero raised/unknown usage;3,832,550 steps;CPU-only;no model/training calls. Final payload SHA256 `6c52d04171d84d57dcaa7e77d46e38b0c8b6e57c7c1e29582eec48411aa95fb4`. The full run emitted live progress, run/source identities, family/objective provenance, a per-call ledger, completed marker and closed final archive.
5. **Typed language coverage:**171 independent-reference witnesses cover all137 atomic parameterizations and34 two-operation classes. The finite search inventory is1,277 programs. This is authored witness coverage, not an ARC language-completeness claim.
6. **Independent review:** separately scoped design, interpreter/IPC/resource, compiler/curriculum, source-cache/entrypoint, candidate routing, query-field noninterference, final contract/tokenizer/notebook and artifact reviews. Exact receipts are retained under evidence/review and docs/security.

The focused harness uses synthetic model responses to test scheduling and accounting. Its program-verifier subprocesses are real. The N5 replay uses actual saved model programs. N13 uses explicitly authored generators and independent formula targets. None of these establishes live GPU program generation, trained-model quality or Kaggle execution reliability.

## Not run here

- No real N6–N12/N14 model generation, CUDA model load, paid GPU, training, TTT/RL, new adapter, new model download or four-L4 deployment benchmark
- No competition submission or official score
- No confirmation-set evaluation
- No automatic shutdown of billing

The repository's historical aggregate baseline is separate and already had failures/errors before this additive suite. The main integrator rechecks that baseline and verifies existing tracked blobs are unchanged; this focused pass is not a claim that the entire historical repository is green.

## Reproduction

From this directory, run `python3 -m unittest discover -s tests -p 'test_*.py' -v`. Tests use only CPU and standard-library workers. When the optional full synthetic export is absent, the full-export test regenerates it safely in a temporary directory, taking a few minutes. The persisted tokenizer audit can be independently regenerated with the exact tokenizer assets/package versions described above. Run the notebook with its manual switch off first; no files or model resources should be touched.
