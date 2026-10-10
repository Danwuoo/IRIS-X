# Prerequisite discovery scope repair

Revision: `evidence-inputs-fix2-20261010`.

## Observed failure

The owner’s N9 v3 launch stopped with `prior-discovery-limit`, `limit: depth`, at `/kaggle/input/competitions/arc-prize-2026-arc-agi-3/ARC-AGI-3-Agents/.git/logs/refs/remotes/origin`. This was an input-discovery scope bug: the search entered an unrelated competition repository. The bounded limit correctly stopped it before installation/model execution; generation and training counters were both zero. Increasing the depth limit would not fix the scope error.

## Narrow change

Discovery now excludes the typed `/kaggle/input/competitions` namespace, its descendants and the already-associated direct legacy `/kaggle/input/arc-prize-2026-arc-agi-3` mount before descending. Exact VCS metadata directories `.git`, `.hg` and `.svn` are pruned. The search receipt records excluded paths.

This is not a global `competitions` basename filter. An ordinary Dataset wrapper named `competitions` is still searched. Ordinary repository working trees, including `repo/results/N6`, remain in scope and can cause the existing ambiguity failure; only their VCS metadata is excluded. A `.git` member inside a claimed closed evidence root is still rejected by full evidence integrity validation.

Depth, entry, candidate, metadata and byte caps are unchanged. ZIP/auto-extracted compatibility, duplicate-copy deduplication, full run/source/seal/inventory/ledger validation, N6/N7 exact evidence pins, explicit overrides and fail-closed ambiguity remain unchanged. No competition content is opened by this repair’s tests; the failing directory layout is reproduced with synthetic empty directories.

## Retry and remaining notebooks

The old zero-call terminal BLOCKED receipt remains valid retry evidence. The next manually started attempt uses a fresh attempt namespace and preserves every old file/archive. Complete, partial, model-attempted or uncertain runs are not automatically resumed. The same helper correction is embedded into N9–N14; N13 still performs no prior/model scan and N14 still requires genuine N9–N11 results and a qualifying policy.

All scientific `src/` bytes are preserved; the source lock remains `29172a035efc7704cd3f60e663a714a7570c18f636fdca32304be94d02689d50`. The five solver assets and existing private prerequisite Dataset version are unchanged. No GPU/model/training execution, paid spend, competition data use or Git write is part of this repair.

## Verification

The regression suite covers the exact reported competition/.git layout without any `scandir` inside that namespace; direct legacy competition aliases; explicit search roots inside the excluded namespace; ordinary Dataset wrappers named competitions; differing valid evidence in ordinary repository working trees; unchanged limits on unrelated ordinary input trees; source/evidence integrity; all six actual generated notebook entrypoints using verified provider-returned N6/N7 evidence; and recovery from a reproduced zero-call depth-limit BLOCKED receipt.

Actual-input notebook tests stop at a mocked CPU backend boundary after real evidence and gate validation. They do not establish live GPU behavior. The exact final acceptance and independent review are retained under `evidence/input-scopefix/`.
