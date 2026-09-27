# Local semantic continuation

Date: 2026-09-27. Local development on main, beginning at `5d3e0fd`.
No external execution authority is created. Frozen combined 003, raw replies,
packages, approved thresholds and consumed ledgers remain unchanged.

## M3 implementation and actual offline evidence

`arc_nvarc_semantics.py` supplies a distinct **proposed**
`qwen-rule-contract-v3`. Summary rules are executable ordered operations,
checked against **every** supplied public demonstration. Unsupported prose or
operations fail closed. The five supported operations are identity,
row-major boundary-pair swap, 180-degree rotation, row flip and column flip.
This deliberately restricted language is not a general ARC rule verifier or
full upstream SDG parity. Demo agreement does not establish rule uniqueness.

Composition is derived by applying the validated operations to one-hot color
probes, rather than hardcoding the expected nine-index answer. Rectangular,
double-rotation, alternate-parent and noncommuting-order tests provide
independent controls. V3 requires context at the stage gate; programs remain
`program-contract-pending-sandbox` after EOS/AST acceptance. A rejected stage
retains raw text, reason and digest, consumes its reservation and is not retried.
Both standalone and internal historical teacher entrances reject v3 before
model imports or material access; it cannot reuse an old execution envelope.

The complete record gate verifies summary and mix before accepting any pair.
It permits only the concrete isolated executor, checks ndarray/integer/shape/
color contracts, seed repeatability and variation, obvious correlated cell
traces, output repeatability, nine one-hot and three offset-color challenges,
then the hash-checked upstream pair filter. Accepted pairs retain **measured**
outputs, parent binding, raw-reply/program/spec digests, seeds and dependency
identity. No generated code is evaluated on the host. Finite probes cannot
prove arbitrary program equivalence or distributional independence; bounded
acceptance explicitly records these limitations.

The existing Linux cp312 NumPy 2.2.6 wheel is extracted locally into an
inventory-bound directory and mounted read-only inside a separate namespace
runner. No download/install, fake NumPy, host path exposure or relaxed resource
limit is used. User/mount/PID/network namespaces, chroot, capability drop,
read-only mounts, 768 MiB address space, 16 processes, four CPU seconds,
six-second inner timeout and bounded output remain enforced. The strict suite
actually checks filesystem, second-chroot, dependency-write, network, memory,
process and timeout canaries with NumPy present. Missing isolation refuses
execution; missing pinned source/filter dependencies fail before probes.
The wheel SHA-256 is
`fd83c01228a688733f1ded5201c678f0c53ecc1006ffbc404db9f7a899ac6249`;
the 871-file inventory digest is
`sha256:d2e0186fe8ea6e3f8189f09ea47b9a8456736e1c242927fd90ff082a5e295ff0`.
Rehashed or symlinked replacement dependencies are rejected.

The retained negative fixture preserves all four complete raw replies and
their original response and ledger digests from archive
`937a6091143a4bfe997f53fb3f1635fc90b0ee467ddc4536886825ddd069c3de`.
The replay verifies all 44 local archive-member hashes and fixture equality.

| Retained stage | Local disposition |
| --- | --- |
| summary | `summary_demo_mismatch:puzzle1:0`; the limited negative-replay prose adapter interprets only the retained explicit rotation claim. V3 accepts executable rules, never this prose adapter |
| mix | `mix_composition_mismatch` against operations derived from demonstration-checked rules |
| input | Seeds 0/2/3 return a dictionary; seeds 1/4 raise ValueError. All reject the fixed-grid contract |
| output | A real ndarray argument produces IndexError: the function expects dictionary fields |

The independently authored NumPy control produces five bounded-contract pairs
after 44 isolated calls. A separate 2x3 rotation control passes. Float arrays,
wrong shape/colors, constant inputs, correlated cells and index-only answers
are meaningful negative controls. These are authored engineering fixtures:
**retained teacher yield remains zero**, and no teacher/model call or ARC
scoring occurs during replay.

## M2 engineering audit and candidate implementation

Source differential checks cover native/compact row identities, role/newline/
EOS tokens, assistant masks in SFT/TTT, source augmentation/inverses, sorted
DFS siblings, cumulative NLL including EOS, source likelihood sums, duplicate
votes, missing outputs and deterministic ranking. Tiny actual Qwen3.5 checks
exercise compact save/reload, gradients/reset, hybrid full-prefix branch
isolation and model-backed source solve. The export boundary requires a trained
artifact to bind its pinned compact base and training identity. These checks
found no demonstrated representation, mask or score-accounting cause of the
observed 4B zero candidates; the Editor archive itself omits model weights.

Root arithmetic from the retained four calls is separate from counterfactual
generation. Legal mass exceeds 99%, conditional maxima remain below .2 and
all four current roots are pruned. Extra expansion/token allowance cannot
create a root edge. At .1, the retained roots have 5/4/6/6 surviving digit
edges; at .02 all ten digits survive. **Deeper logits, complete candidates and
answer quality are unknown.** A controlled diffuse-logit case opens the root
at .02 but still exhausts all branches without a completion.

The source runtime now honors an explicit candidate-only
`cumulative_probability_threshold`; the absent-field historical default is
still .2. A separate tiny source configuration confirms identical forwarded
root logits/query tails after the same checkpoint and adaptation seed, with
only the requested bound changing reachable expansions.
`arc_nvarc_threshold_trial.py` implements the reviewed three-arm comparison:
adapt once, hold that model across arms, clear prefix caches/counters per arm,
retain arm-tagged reservations and actual costs, detect in-place parameter
mutation/replacement, bind the exact adapter tensor bytes and query digests,
and reset the adapter on success or failure. This is a
mutation guard, not a replacement for the experiment's material digests.

## Concrete inert proposals

Both JSON configurations have distinct identities, `approved=false`, no owner
decision and zero external allowances. They are local proposals, not outbound
Kaggle packages. The preflight command emits configuration/prompts/seed review
bundles with source and file hashes; it exposes no execution option.

| Proposal | Hypothesis and fixed comparison | Proposed upper bounds and acceptance |
| --- | --- | --- |
| [M3 rule contract](configs/m3-rule-contract-proposal-001.json) | A restricted executable summary with dependent semantic rejection yields usable code rather than schema-only completion; same public parents, pinned full-vocabulary teacher, greedy/direct mode, old token reservations | Four dependent teacher calls, 28,160 reserved tokens, one L4, 1,800 seconds, USD 0. First rejected stage stops; no retry. Success requires all semantic/sandbox/source gates and retained measured pairs, not four complete calls |
| [M2 root threshold](configs/m2-root-threshold-proposal-001.json) | Uncertain initial digits explain candidate unavailability under source cumulative pruning. Compare .2 control with .1 and .02, same export/task/four views, one shared TTT state, no masking renormalization | One TTT step/512 training tokens; 12 generation calls, <=24 sequences, <=1,536 DFS forwards plus <=192 verification forwards, 64 suffix positions/returned sequence (<=1,536 returned positions), one L4, 1,800 seconds, USD 0. Record availability/cost only; no ARC scoring |

For M2, save post-TTT/material/query/view bindings before inference. All arms
must share them. Run fixed control/candidate arms without selecting tasks from
answers. A complete legal inverse-mapped candidate with finite source ranking
is an availability observation; it is not a correct answer. If all arms fail,
retain failure and stop. For either proposal, identity/state/hardware mismatch,
nonfinite values, OOM/crash/deadline or quota excess stops without replacement.
Reserve 30 seconds for terminal evidence; generation/verification forwards and
TTT work are separate counters. No warm-up, teacher addition or scoring follows.

The next proposed external step is M3's four-call restricted profile, with a
new exact owner envelope and separately staged notebook. M2's scientific
threshold choice requires its own decision. Neither proposal changes an
accepted threshold or authorizes Dataset mutation, submission/QUICK_SAVE,
queries/retrieval, monitoring, publication or promotion. Full SFT quality, real
v3 teacher yield, real threshold-arm availability and full TRM/joint ARC quality
remain unverified. The full NVARC goal remains open.

## Reproduction and coverage

From repository root, using the existing optional ML environment (no install):

```powershell
$env:PYTHONPATH = 'src'
.irisx/nvarc-ml-venv/Scripts/python.exe -m unittest tests.nvarc_source_differential tests.test_arc_nvarc_ml tests.test_arc_nvarc_distributed -v
.irisx/nvarc-ml-venv/Scripts/python.exe -m unittest tests.nvarc_semantic_strict tests.nvarc_threshold_strict -v
.irisx/nvarc-ml-venv/Scripts/python.exe tools/replay_nvarc_semantics.py --output .irisx/NEW-semantic-replay --sandbox
.irisx/nvarc-ml-venv/Scripts/python.exe tools/preflight_nvarc_local_proposals.py --output .irisx/NEW-semantic-proposals --tokenizer
python tools/repository_check.py --all
```

New output directories are required. Run isolated program suites sequentially.
Default Python can run static replay without `--sandbox`; it refuses generated
program execution. The default interpreter lacks host NumPy for the trusted
source filter; use the existing ML environment for isolated replay. An initial
default-Python replay reached that dependency failure before this early check
was added. Concurrent isolated follow-up probes failed without usable stderr;
the runner now retains bounded stderr in its failure message. These failures
are not teacher-semantic observations. Sequential final results are recorded
below; no resource limit was relaxed.

The first preflight counted a default tokenizer BatchEncoding's fields instead
of tokens. It is superseded: the corrected explicit token-tensor gate measures
343/132/155/180 input tokens for the four authored prompts, below unchanged
stage caps. This does not guarantee caps for arbitrary future teacher replies.

Default repository validation covers lightweight contracts and governance.
Its four optional skips are torch SFT resume, distributed torch, the ML class,
and saved TRM tensor normalization. The separately invoked strict source,
tiny-Qwen, collective, semantic and threshold suites fail on missing materials;
they are not skipped/default substitutes. Original-scale TRM and real 4B or
teacher calls remain outside these tests. No new provider request, paid usage,
ARC score or real 4B/teacher generation was made.

Final focused checks: 24 tests pass. Strict source/tiny model/distributed checks:
19 pass, followed by the changed source/threshold comparison suite's 14 passing
tests (13 source and one paired tiny-model test). The five actual isolated NumPy
tests pass sequentially; the final pinned/rehashed dependency check also passes.
The two remaining default optional tests (torch resume and TRM tensor fixture)
pass in the ML environment. These counts overlap and must not be added as
unique-test coverage. Logs are under `.irisx/nvarc-semantic-*.txt` and
`.irisx/nvarc-threshold-*.txt`.

`python tools/repository_check.py --all` passes: 267 tests, four optional skips.
The log is `.irisx/nvarc-semantic-repository-final.txt`. The two default skipped
individual fixtures and the skipped ML/distributed paths are separately
exercised as above; this does not add original-scale GPU or teacher evidence.
The digest-bound replay report is
`.irisx/nvarc-semantic-replay-isolated-002/report.json`; it retains zero accepted
teacher pairs and five authored controls. Final review bundles and their
packaged guard/source hashes are under
`.irisx/nvarc-local-semantic-proposals-release-001/`.
