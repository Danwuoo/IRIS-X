# Local reconstruction of launcher diagnostic tests

`test_launch_diagnostics.py` is newly reconstructed local source. The rescue ZIP
does not contain the original final version of this test file, so this version
must not be described as hash-matched recovered final bytes or covered by an old
review receipt.

The reconstruction starts from `earlier-versions/test_launch_diagnostics.py`
(SHA-256 `dc443d13384477996e2fd1b83f1f9b8c7fd1a426ab33429f142c22056db5c6b2`)
and incorporates the separately marked
`incomplete-literal-fragments/test_launch_diagnostics.final-lines123-148.txt`
(SHA-256 `5a8b0594b64b7cac993c95254d950059a28596b2d0191a2872c2d27a3c344a3e`).
The fragment supplies complete replacement methods for FIFO and oversized-leaf
tests; it is not installed as an executable module. These methods allow actual
directory acquisition while detecting any attempted unsafe leaf open.

Local additions verify preservation of binary stdout/stderr after a real
nonzero child exit, propagation of the current Python optimization mode to that
child, and original deadline timeout plus genuine owned-tree closure. Temporary
files remain below the ignored `.irisx/run006-local/diagnostics-tests` directory.
The fixed source/request marker strings are explicitly synthetic unit fixtures;
they do not authorize a release, closure, scoring, cost, or provider action.

Use the normal and `python -O` commands in `README.md` with Python 3.12 on Linux.
Installer and preparation suites execute stdlib-only CPU fixtures. The bundle
integration authenticates a genuine 259-member frozen source reconstruction and
fails at an empty synthetic Dataset mount, before installation/model/GPU work.
These tests cannot verify the unidentified manual run005 failure's cause, real
offline installation, CUDA/model execution, or PUBLIC120 scoring.
