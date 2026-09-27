#!/bin/sh
# Same namespace/chroot boundary as the retained runner; cached NumPy only.
set -eu
deps=$1
if [ "${2:-}" != inner ]; then
    exec unshare --user --map-root-user --mount --pid --net --fork sh "$0" "$deps" inner
fi
root=$(mktemp -d /tmp/nvarc-sdg-semantic.XXXXXX)
mount -t tmpfs -o size=32m,nosuid,nodev tmpfs "$root"
cleanup() { umount -l "$root" 2>/dev/null || true; rmdir "$root" 2>/dev/null || true; }
trap cleanup EXIT HUP INT TERM
mkdir -p "$root/usr" "$root/dev" "$root/tmp" "$root/opt/numpy"
mount --rbind /usr "$root/usr"
mount -o remount,bind,ro "$root/usr"
mount --bind "$deps" "$root/opt/numpy"
mount -o remount,bind,ro "$root/opt/numpy"
ln -s usr/lib "$root/lib"
ln -s usr/lib64 "$root/lib64"
ln -s usr/bin "$root/bin"
touch "$root/dev/null"
mount --bind /dev/null "$root/dev/null"
chmod 1777 "$root/tmp"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 timeout -s KILL 6s chroot "$root" \
    /usr/bin/prlimit --as=805306368 --nproc=16 --cpu=4 -- \
    /usr/bin/setpriv --no-new-privs --bounding-set=-all \
    --inh-caps=-all --ambient-caps=-all /usr/bin/python3 -I -c '
import contextlib, io, json, sys
sys.path.insert(0, "/opt/numpy")
import numpy as np
p = json.load(sys.stdin)
scope = {}
capture = io.StringIO()
try:
    with contextlib.redirect_stdout(capture):
        exec(p["code"], scope)
        if p["entry"] == "generate_puzzle_input":
            result = scope[p["entry"]](p["seed"])
        elif p["entry"] == "generate_puzzle_output":
            result = scope[p["entry"]](np.asarray(p["grid"], dtype=np.int64))
        else:
            raise ValueError("unknown semantic entry")
    if isinstance(result, np.ndarray):
        observation = {"kind":"ndarray", "dtype_kind":result.dtype.kind,
                       "shape":list(result.shape), "value":result.tolist()}
    else:
        observation = {"kind":type(result).__name__}
except Exception as error:
    observation = {"error":type(error).__name__}
sys.stdout.write(json.dumps(observation))
'
