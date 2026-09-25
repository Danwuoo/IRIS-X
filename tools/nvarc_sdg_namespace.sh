#!/bin/sh
# WSL2 Ubuntu isolated generated-program runner. Input is one JSON object on stdin.
set -eu
if [ "${1:-}" != inner ]; then
    exec unshare --user --map-root-user --mount --pid --net --fork sh "$0" inner
fi
root=$(mktemp -d /tmp/nvarc-sdg-root.XXXXXX)
mount -t tmpfs -o size=32m,nosuid,nodev tmpfs "$root"
cleanup() { umount -l "$root" 2>/dev/null || true; rmdir "$root" 2>/dev/null || true; }
trap cleanup EXIT HUP INT TERM
mkdir -p "$root/usr" "$root/dev" "$root/tmp"
mount --rbind /usr "$root/usr"
mount -o remount,bind,ro "$root/usr"
ln -s usr/lib "$root/lib"
ln -s usr/lib64 "$root/lib64"
ln -s usr/bin "$root/bin"
touch "$root/dev/null"
mount --bind /dev/null "$root/dev/null"
chmod 1777 "$root/tmp"
timeout -s KILL 6s chroot "$root" \
    /usr/bin/prlimit --as=805306368 --nproc=16 --cpu=4 -- \
    /usr/bin/setpriv --no-new-privs --bounding-set=-all \
    --inh-caps=-all --ambient-caps=-all /usr/bin/python3 -I -c '
import contextlib, io, json, sys
p = json.load(sys.stdin)
scope = {}
capture = io.StringIO()
with contextlib.redirect_stdout(capture):
    exec(p["code"], scope)
    if p["entry"] == "generate_puzzle_input":
        result = scope[p["entry"]](p["seed"])
    elif p["entry"] in ("generate_puzzle_output", "transform"):
        result = scope[p["entry"]](p["grid"])
    else:
        raise ValueError("unknown SDG entry")
if hasattr(result, "tolist"):
    result = result.tolist()
sys.stdout.write(json.dumps(result))
'
