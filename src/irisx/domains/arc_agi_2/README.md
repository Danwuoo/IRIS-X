# ARC mutable CLI facade

`register_parser` preserves the existing `irisx arc-agi-2` command tree.
`execute` loads the retained implementations only when an ARC command is selected.
Shared CLI supplies the original repository root for outbound construction.
There is one dispatch implementation and no copied solver.

Start with [ARC STATUS](../../../../docs/workstreams/arc-agi-2/STATUS.md),
[RESEARCH](../../../../docs/workstreams/arc-agi-2/RESEARCH.md), and the
[migration map](../../../../docs/verification/WSF-04/MIGRATION.md).
Static dependency exceptions are in
[dependencies.json](../../../../docs/workstreams/dependencies.json).

Run `python tools/dev.py verify --suite arc-unit` and
`python tools/dependency_check.py` from the checkout. These checks use synthetic
inputs and mocks; they do not attest authentic reconstruction or runtime/model
compatibility. The original flat legacy modules remain byte-bound at their paths.
