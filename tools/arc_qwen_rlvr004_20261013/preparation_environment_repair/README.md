# Model-free preparation environment repair

Two deployment-only successor overlays fix the ordering failure observed in
v41. The notebook interpreter called the production worker environment before
the offline interpreter existed; its cuDNN distribution lookup succeeded but
the exact version check failed. The ambient version and loaded backend are
unknown. The same premature lookup after installation was a second, unexecuted
static risk because preparation still runs in the outer interpreter.

`launch_notebook.py` defines one stdlib-only `preparation_environment`, used by
both deployment callers. It retains the production device visibility/order
validation, closed offline/thread settings, and fixed driver executable/library
roots. It ignores inherited paths, credentials and interpreter injection. It
does not resolve cuDNN, use fixture mode, import a model, or admit a worker.

The installed parent still enters through the unchanged installed
`python_command` and parent entry. Its source-bound bootstrap/runner computes
the real worker environment under that interpreter, authenticates complete
vendor bytes before exec, and the child repeats the installation/environment
checks before native imports and exact loaded-byte admission afterward.

An exact-guard CPU replay also reproduced a second ordering consequence: the
pinned offline startup guard adds six fixed keys, while the prior worker policy
omitted them and therefore rejected the actual whole child environment. The new
`parent_scoring.py` is a one-file runtime successor to the original loader
overlay. Its sole behavioral delta adds those six fixed values to the production
environment before exec. It never inherits their ambient values, alters fixture
mode, removes the offline guard, or relaxes whole-environment equality.

All historical files, remaining loader/runtime bytes, scientific policy,
scorer, original clocks and guards stay unchanged. The successor runtime source
identity/archive and deployment descriptors require fresh binding and review.
The inherited run005 spellings are assembly inputs, never permission
to reuse that consumed run. The admission assembler must bind fresh deployment
descriptors and a separately reviewed successor identity.

## Offline CPU checks

From the repository root, with workspace-backed scratch space:

    mkdir -p .irisx/preparation-environment-repair/tmp
    export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1
    export TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
    export TMPDIR="$PWD/.irisx/preparation-environment-repair/tmp"
    python -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/preparation_environment_repair -p 'test_*.py' -v
    python -O -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/preparation_environment_repair -p 'test_*.py' -v

The tests exercise both real caller functions with wrong ambient metadata,
closed-environment parity, invalid device controls, the exact narrow source
delta, unchanged historical runtime-overlay hashes/order, and retained diagnostic
tests. Runtime AST comparison proves only six fixed production values changed.
Linux/gcc integration uses a real isolated stdlib venv with real dist-info and
tiny synthetic wheel/ELF files, through the actual bounded preparation-to-parent
process guard. Its exact pinned offline launcher/guard/.pth flow reproduces the
predecessor failure and passes with the successor. Successful owned-first
selection passes; wrong installed metadata, parent/child byte tampering, a
foreign already-loaded backend, altered guard-owned values, and extra environment
keys reject. The guard's whole-environment rejection remains before native load.
Both normal and optimized test modes propagate to the synthetic installed child.

The material resolution/installer and full parent bootstrap are explicitly
mocked; `cpu_parent_worker.py` is a test harness, not a deployment entry. Only
synthetic wheel/hash/driver inputs and a tiny Torch API wrapper are substituted
inside the real loader checks. Actual installed prefix and distribution lookup
are not mocked in those processes. No package is downloaded or installed, and
no real cuDNN/GPU/model/scorer work or production-success claim follows.
