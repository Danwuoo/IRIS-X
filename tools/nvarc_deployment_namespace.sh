#!/bin/sh
# Called inside a new user/mount/network namespace. Keep only the copied
# deployment visible through an alias, then hide the checkout before Python.
set -eu
probe=$1
runtime=$2
checkout=$3
alias_dir=$(mktemp -d /tmp/nvarc-wheel.XXXXXX)
mount --make-rprivate /
mount --bind "$probe" "$alias_dir"
mount -t tmpfs -o size=1m tmpfs "$checkout"
cd "$alias_dir"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
"$runtime" -I "$alias_dir/probe.py"
