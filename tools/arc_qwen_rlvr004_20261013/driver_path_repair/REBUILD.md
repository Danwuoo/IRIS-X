# Rebuild the exact run005 runtime source

The compact source map reuses the 257 unchanged code17 members from Git and
points the other two members to this repair overlay and `release_run005.py`.
All 200 inherited baseline members, the scorer and measured policy remain
byte-identical. The environment changes only its three source material paths
from source004 to source005. The generated release file binds that environment
and the normalized source digest; it grants no publication authority.

From the repository root, use a fresh output directory:

```sh
python3 -B tools/arc_qwen_rlvr004_20261013/prepare_successor_release.py --mode source --repository-root . --parent-overlay tools/arc_qwen_rlvr004_20261013/driver_path_repair/parent_scoring.py --parent-overlay-sha 0ccdeecc8398098c0240d919c8ff9f4f51e5455ee96debd35c8c7c8ce10bb24b --output-root .irisx/code18-source-rebuild-001
```

This deterministic stage needs only Git source and the overlay. It does not
require provider observations, original evidence, authentication, reviews,
weights or evaluator data, and calls no model or provider. It reconstructs all
259 members and the canonical stored ZIP. Expected bindings are:

| Artifact | SHA256 |
| --- | --- |
| Logical runtime source | `4050616ed0ed34d19501be416650a09ae5cc9c86c875b349a056baec9308f3e3` |
| Canonical source ZIP | `22fc93ae1dfbc4d4a7c90cf9907668af5d697dece28cb9211dea82c776d7dc9e` |
| Environment005 | `0f7133bdb22d8cba124537622ab09a98e9450e1649df1b07d4e6661d48e33e28` |
| Generated release pin file | `88f97c9d0c3ad6d999cba410d8929d07bbfa53372e0b19da51130de30fb7a16c` |

The generated freeze, environment, map and release pin file must match their
retained counterparts here exactly. Source reconstruction does not establish
GPU admission, inference completion, public scoring or successful closure.

The separate `proposal` and `final` stages require the authenticated original
code17 assembly and retained v33 terminal evidence outside Git. They bind code18,
inactive v34 and active v35 with fresh run005/state/review identities. Their
source proposal cannot approve itself: final assembly requires independently
hash-bound runtime, material and target-free dataset path reviews. Provider
publication additionally requires exact local operator and collector review.

The target-free solver descriptor's two escrow reference paths also change to
run005. That changes its raw file hash while preserving its records, semantic
content, escrow hashes and denominators. The old code17 expected descriptor is
a deterministic path projection from the authenticated v31 solver member; it
is not claimed to have been produced by v33, which failed before data admission.
Original archives and descriptor bodies remain outside Git. No escrow answer
body is read to make this path projection.

The focused driver, assembler and operator tests run in local WSL/POSIX in normal
and `-O` modes. The full-shape CPU simulations are explicitly synthetic and
use only the authentic solver-side fixtures. Native tensor/GPU gates still
require the actual unchanged pinned resource and model environment.
