# Bounded NVIDIA CLI path repair

This overlay preserves the frozen code17 source. It appends `/opt/bin` to the
three existing trusted CLI directories, preserving their priority. The child
still requires the exact source-owned PATH and rejects selected executables
whose canonical target leaves those four roots. It never searches an ambient
PATH, scans directories recursively or reads rejected executable bodies.
The three original roots retain their canonical behavior, including `/bin`
linking into `/usr/bin`. The new `/opt/bin` root cannot introduce an arbitrary
canonical directory through a directory link; links into an original trusted
canonical root remain admissible.

The failed child receipt records four exact `nvidia-smi` leaf observations:
missing, nonregular, non-executable, executable, rejected link target or resolution
error. A resolved canonical target is limited to 512 characters with an explicit
truncation flag, including rejected targets. These diagnostics do not grant
admission. The five library roots, `libcuda.so.1`/`cuInit` check, bounded CLI query,
isolated Torch CUDA probe, original deadline and driver `580.178.04` remain
unchanged. All other model, scorer, process, physical-cost and closure code is
identical at the AST level.

NVIDIA documents `/opt/bin` among supported fixed `nvidia-smi` locations and
resolves links in its driver validator. This supports the narrow path addition;
it does not attest the actual path inside the pinned private Kaggle BYOD image.
[NVIDIA GPU Operator release notes](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/release-notes.html),
[NVIDIA implementation and tests](https://github.com/NVIDIA/gpu-operator/pull/2611/files).

NVIDIA distinguishes the `utility` capability required for `nvidia-smi` and NVML
from the `compute` capability. A visible GPU or CUDA installation alone therefore
does not establish the CLI location or availability.
[NVIDIA Container Toolkit documentation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html).
Kaggle's public Docker template documents its GPU image and library setup; it is
additional context, not an attestation of the private BYOD image digest.
[Kaggle Docker template](https://github.com/Kaggle/docker-python/blob/main/Dockerfile.tmpl).

The sibling `local_tests/test_driver_path_repair.py` authenticates and reconstructs
the frozen source, proves the complete allowed AST delta, and exercises synthetic
POSIX executables/links, real isolated CPU child failure persistence and native
failure gates. Run it in normal and `python -O` modes. Positive native responses
are mocks. These tests establish no GPU, model loading, fit, throughput or PUBLIC
score; the unchanged runtime gates must observe the actual pinned resource.
