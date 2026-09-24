# Compact 4B small complete pilot 003: verified terminal record

Status: **bounded synthetic 4B compact flow verified; candidate yield partial**.
Decision 0027 authorized this distinct program-error repair attempt. Kaggle
accepted the exact private, Internet-disabled
[`danielwuu/iris-x-4b-compact-complete-003`](https://www.kaggle.com/code/danielwuu/iris-x-4b-compact-complete-003)
as version 1 and reported `KernelWorkerStatus.COMPLETE`. The notebook's worker
exited 0, and its own material/result verification succeeded. The full
material and result were then independently verified locally with
`python -m irisx.arc_nvarc_compact_pilot verify`. The staged package, ledger,
terminal log snapshot, retrieved files and local verification report are under
ignored `.irisx/arc-agi-2/qwen35-nvarc/compact-complete-launch-003/`.

## Identity and material

The run ID is `nvarc-4b-compact-complete-003`. The approved plan, runtime
wheel, notebook and metadata SHA-256 values are respectively
`9eee16e3976a485fcb54c7de093dd844681aea0d04d673f5980a7b9ab189c41b`,
`7ec36a949d1745965e220289ce1789c5544e9b755e7f8a9915195b9ff101bae8`,
`77c0d2becfdb98b3d6068ca5537906cf5d4319b764571a0c79a0e753676f74d0`,
and `1219b4ca2b9d40753f5c801a85a1cec8b8f83f56a40de712db483cd38429f461`.
The five returned plan/source/manifest/wheel files matched their staged
SHA-256 values. The official competition challenge mount was checked for
presence only; no challenge contents or evaluator truth entered the package.

The Dataset v2 root and exact retained legacy tree passed the closed inventory
gate. Qwen3.5-4B source material was rehashed, 16 pinned tokenizer rows were
selected, and a distinct four-shard compact model was saved, reloaded and
verified. Its material digest is
`sha256:1a8eebd70d811e58c35dc5b1ee27dc18bd73a1066c3ab33adf96ed8427d4c982`.
The truth-free `result.zip` digest is
`sha256:085db1e03d9d673701cabccb85db029b9a016b021f7fd4674c08df1f29eb6130`.
Local verification returned both exact digests. The phase and checkpoint file
SHA-256 values are
`f60a911e27a2643b809dd034b881683de5f0b4ce55df87448c6aa4f08145c8d2`
and `2dffbc5153e1b49404e97ccf656191e6ae9483ff28bf59a46975506fe3e28d11`.
The terminal log snapshot and local verification report SHA-256 values are
`c5829f783aacaf15ebe6f1c9b625dd1579a4ca26c42d6e6eb4d223c11f17dc0a`
and `fe018fc8d78153cecac16c5f409f9951ec4554f72470bff3ac2d17b001e2a482`.

## Observed work and limits

Kaggle exposed four distinct NVIDIA L4 devices, each with 22,563 MiB visible
to PyTorch; only device 0 was used. Its compact-model load peak was 7,558 MiB.
The two task peaks were 8,257 and 8,265 MiB. Phase records show source
inventory at 2.27 seconds, compact reload at 173.53 seconds, and terminal
result at 247.18 seconds of application runtime, below the 2,400-second
session limit.

Both synthetic tasks completed one task-local LoRA optimizer step, using 10
training tokens each. The checkpoint is complete and records **two steps,
20 training tokens, four generation calls, four observed sequences, 43 explicit
forward calls, four likelihood verification calls and zero teacher calls**.
The two tests of `synthetic-rect-b` each have two valid complete-grid attempts.
The two tests of `synthetic-rect-a` produced no complete candidate and are
explicitly marked `missing-candidate`; no answer was filled in. The complete
grid requirement for this small flow is met, while candidate yield is 2/4
tests. No ARC accuracy or pass@2 claim follows from these synthetic outputs.

## Retrieval and boundary

The first full output transfer broke with `IncompleteRead` on shard four after
three weight shards were retained. Targeted continuation recovered the small
phase/result files and the fourth shard from the **same immutable version**.
The two targeted CLI invocations returned a Windows `charmap` error while
printing the Unicode log, after their selected files had landed. File sizes,
the complete model inventory digest and result ZIP were independently checked
locally. These were transport continuations only; they caused no new kernel
version, training step or generation. The terminal log was retained separately
through the read-only log endpoint.

This establishes a bounded 4B compact conversion, reload, short task-local
adaptation, actual model generation, complete-grid parsing, verification and
truth-free result path on one L4. It does not establish ARC quality, full
NVARC rank 256 / 8,192-token viability, full SFT, TRM, SDG or four-worker
performance. Decision 0027's session debugging authority ends with this
verified small flow; no further kernel is needed under it.
