# Active Tools

`repository_check.py` is the single handoff-validation entry point. Run
`python tools\repository_check.py --all` to execute its helper self-tests,
deterministic repository checks, the complete unit suite, and `git diff
--check`. Focused modes remain available while iterating. The repository check
validates the active layout, product authority, forbidden runtime integrations,
immutable historical evidence, archive recovery, and archive separation.

`irisx_build_backend.py` is the dependency-free PEP 517/660 backend used for
offline editable installs and pure-Python wheels. It is intentionally limited to
the single `src/irisx` package and the declared `irisx` console entry point.

`trial_001_layout.py` is the read-only Decision-0009 audit for the retained
ARC-AGI-2 `run-001` bytes. It verifies the frozen outbound, manifest, notebook,
runner, and repository identities; inventories known aliases and superseded
packages; and accepts either complete verified result/evaluation evidence or
the exact accepted Decision-0012 `inconclusive-no-promotion` closure record as
a terminal normalization gate. It never moves or deletes files.

Historical tools are recoverable from the cold-archive tag and are not active
commands.

`nvarc_original_corpus.py` prepares the distinct Decision-0050 original
reproduction corpus under `.irisx/nvarc-original/`. It copies published
HF bytes unchanged, retains all six training sources and separate validation,
and freezes row-aligned Arrow lineage/exposure and compact projection counts.
The verifier checks every row, independent encoder samples, actual upstream
concatenation and the complete seed-24 shuffle. Original tokenizer and NeMo
packing parity remain separate prerequisites. It never starts training,
scoring, acquisition or provider work; see the
[original material report](../trials/arc-agi-2-qwen35-nvarc/original-corpus-20261001.md).

`nvarc_datasets.py` inventories and safely extracts downloaded ZIPs, builds
public parent catalogs with frozen development/locked exclusions, prepares
filtered HF material with ordered multi-parent lineage, and independently
verifies digests and real upstream-loader samples. It is offline and never
executes downloaded programs or starts training. Decision 0049 covers the
separate fixed-version Kaggle acquisition; see the
[dataset report](../trials/arc-agi-2-qwen35-nvarc/dataset-acquisition-20261001.md).

`stage_nvarc_source_continuation.py` and
`preflight_nvarc_source_continuation.py` prepare and check a local, inert
post-SFT source solve from the retained M2 export. They perform no upload,
model invocation or provider call. `verify_nvarc_deployment.py` exercises
the installed wheel with tiny CPU model work in an offline WSL mount/network
namespace. See the [continuation plan](../docs/plan/2026-09-26-nvarc-source-teacher-continuation.md)
for prerequisites, evidence limits and separate external authorization.

`nvarc_continuation_authorization.py` binds Decision 0033 to the unchanged
reviewed drafts; the staging tools accept an explicit authorization file and
their preflights require `--approved` for runnable packages.
`materialize_nvarc_teacher_tokenizer.py --fetch` deliberately acquires only
the six pinned tokenizer/configuration files. Run this separately from the
offline `preflight_nvarc_teacher_tokenizer.py`; neither tool invokes a model.
`verify_nvarc_continuation.py` checks the retrieved M2 training/export/source
chain or M3 dependent response ledgers, hardware, counters and artifact hashes
without model calls. Complete teacher programs still require separate sandbox
replay and pair validation.
