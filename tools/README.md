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
