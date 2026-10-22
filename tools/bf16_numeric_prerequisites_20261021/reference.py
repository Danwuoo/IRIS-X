"""Portable, bounded FP32 -> BF16 reference and safe rounding-stream checkpoint.

No JAX, accelerator, model, pickle, installation, or network dependency. The
uint16 storage encodes BF16; only small arithmetic candidates widen to FP32.
The scalar SHA-256 PRNG is a reference, not TPU hardware/Threefry compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile

import numpy as np

VERSION = "bf16-cpu-reference-v1"
SCHEMA = "iris-bf16-rounding-checkpoint-v1"
ALGORITHM = "sha256-indexed-u16-le-v1"
POLICY = "reject-nonfinite-and-abs-above-bf16-max"
ORDERING = "canonical-leaf-step-global-c-flat-index-v1"
MAX_ELEMENTS = 1_048_576
MAX_CHECKPOINT_BYTES = 8 * MAX_ELEMENTS
MAX_BF16 = np.array([0x7F7F0000], dtype=np.uint32).view(np.float32)[0]
UINT64_MAX = (1 << 64) - 1


def _integer(value, name, maximum=UINT64_MAX):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [0, {maximum}]")
    return value


def _leaf(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,255}", value):
        raise ValueError("canonical leaf ID must be 1..256 ASCII identifier characters")
    return value


def _digest(value, name):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def fp32_input(values):
    """Require FP32, rejecting rather than coercing nonfinite/out-of-range inputs."""
    arr = np.asarray(values)
    if arr.dtype != np.dtype(np.float32):
        raise TypeError("input must have native float32 dtype, with conversion explicit upstream")
    if arr.size > MAX_ELEMENTS:
        raise ValueError("bounded reference element limit exceeded")
    if not np.all(np.isfinite(arr)):
        raise ValueError("NaN and infinity are rejected")
    if np.any(np.abs(arr) > MAX_BF16):
        raise ValueError("finite overflow rejected: no unbiased finite BF16 bracket exists")
    return arr


def bf16_input(bits):
    arr = np.asarray(bits)
    if arr.dtype != np.dtype(np.uint16) or arr.size > MAX_ELEMENTS:
        raise TypeError("BF16 storage must be bounded native uint16")
    if np.any((arr & np.uint16(0x7F80)) == np.uint16(0x7F80)):
        raise ValueError("nonfinite BF16 storage is rejected")
    return arr


def decode(bits):
    """Exact widening, including signed zero and BF16 subnormals (no flush)."""
    arr = bf16_input(bits)
    return (arr.astype(np.uint32) << np.uint32(16)).view(np.float32)


def nearest(values):
    """IEEE round-to-nearest, ties-to-even, under the strict finite-domain policy."""
    arr = fp32_input(values)
    u = arr.view(np.uint32)
    return ((u + np.uint32(0x7FFF) + ((u >> 16) & 1)) >> 16).astype(np.uint16)


def stochastic(values, random_bits):
    """Exact discrete SR using uniform 16-bit integers and the FP32 low 16 bits.

    Magnitude rounds away from zero iff U < discarded_bits. For negative values,
    this is rounding toward the numeric lower neighbor, not numeric upper.
    Exact values and signed zero survive unchanged. No float addition is used.
    """
    arr = fp32_input(values)
    rnd = np.asarray(random_bits)
    if rnd.dtype != np.dtype(np.uint16) or rnd.shape != arr.shape:
        raise TypeError("random_bits must be uint16 and have exactly the input shape")
    u = arr.view(np.uint32)
    return ((u >> 16) + (rnd.astype(np.uint32) < (u & 0xFFFF))).astype(np.uint16)


def indexed_bits(seed, leaf_id, step, global_indices):
    """Order/shard invariant PRNG keyed by logical identity, never device rank.

    Every coordinate is encoded explicitly with fixed width/little endian;
    the UTF-8 leaf has a length prefix. Replicas share identities and therefore
    bits. Shards must supply nonoverlapping *global* indices. Duplicate indices
    deliberately repeat bits; callers own duplicate/coverage validation.
    """
    seed = _integer(seed, "seed")
    step = _integer(step, "step")
    leaf = _leaf(leaf_id).encode("ascii")
    indices = np.asarray(global_indices)
    if indices.dtype != np.dtype(np.uint64) or indices.size > MAX_ELEMENTS:
        raise TypeError("global_indices must be bounded uint64")
    prefix = b"iris-bf16-sr\x00v1\x00" + struct.pack("<QQH", seed, step, len(leaf)) + leaf
    out = np.empty(indices.size, dtype=np.uint16)
    for position, index in enumerate(indices.flat):
        digest = hashlib.sha256(prefix + struct.pack("<Q", int(index))).digest()
        out[position] = int.from_bytes(digest[:2], "little")
    return out.reshape(indices.shape)


def input_digest(values):
    arr = fp32_input(values)
    h = hashlib.sha256()
    h.update(b"float32-le-c-order\x00")
    h.update(json.dumps(list(arr.shape), separators=(",", ":")).encode("ascii"))
    h.update(arr.astype("<f4", copy=False).tobytes(order="C"))
    return h.hexdigest()


@dataclass
class RoundingStream:
    """Single-owner contiguous C-order stream; failed chunks do not advance.

    Checkpoint data binds the external FP32 candidate digest. The caller must
    regenerate those identical bounded candidates on reload; they are not a
    persistent FP32 weight master. To change step/leaf start a new stream.
    """
    seed: int
    leaf_id: str
    step: int
    global_size: int
    next_index: int = 0

    def __post_init__(self):
        _integer(self.seed, "seed")
        _leaf(self.leaf_id)
        _integer(self.step, "step")
        _integer(self.global_size, "global_size", MAX_ELEMENTS)
        _integer(self.next_index, "next_index", self.global_size)

    def round_next(self, values, destination):
        self.__post_init__()
        arr = fp32_input(values)
        dest = bf16_input(destination)
        if (arr.ndim != 1 or dest.shape != (self.global_size,) or not dest.flags.writeable
                or not dest.flags.c_contiguous):
            raise ValueError("stream requires 1D candidate and writable contiguous global destination")
        end = self.next_index + arr.size
        if end > self.global_size:
            raise ValueError("chunk exceeds global stream size")
        indices = np.arange(self.next_index, end, dtype=np.uint64)
        rounded = stochastic(arr, indexed_bits(self.seed, self.leaf_id, self.step, indices))
        # All validation and random generation precede either mutation.
        dest[self.next_index:end] = rounded
        self.next_index = end
        return rounded.copy()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact_keys(value, required, name):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError(f"unexpected or missing {name} fields")


def _parse_checkpoint(raw, *, expected_input_sha256, expected_context):
    if len(raw) > MAX_CHECKPOINT_BYTES:
        raise ValueError("checkpoint exceeds byte limit")
    try:
        envelope = json.loads(raw, object_pairs_hook=_pairs_no_duplicates,
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid checkpoint JSON") from exc
    _exact_keys(envelope, {"payload", "sha256"}, "envelope")
    payload = envelope["payload"]
    _digest(envelope["sha256"], "payload digest")
    if hashlib.sha256(_canonical(payload)).hexdigest() != envelope["sha256"]:
        raise ValueError("checkpoint integrity digest mismatch")
    _exact_keys(payload, {"schema", "version", "rng", "overflow_policy", "input_sha256", "state"}, "payload")
    if payload["schema"] != SCHEMA or payload["version"] != VERSION or payload["overflow_policy"] != POLICY:
        raise ValueError("unsupported schema, implementation, or overflow policy")
    rng = payload["rng"]
    _exact_keys(rng, {"algorithm", "bits", "byte_order", "ordering", "seed", "leaf_id", "step", "global_size", "next_index"}, "RNG")
    if (rng["algorithm"], rng["bits"], rng["byte_order"], rng["ordering"]) != (ALGORITHM, 16, "little", ORDERING):
        raise ValueError("unsupported RNG contract")
    _integer(rng["bits"], "bits", 16)
    stream = RoundingStream(**{k: rng[k] for k in ("seed", "leaf_id", "step", "global_size", "next_index")})
    _digest(payload["input_sha256"], "input digest")
    if payload["input_sha256"] != _digest(expected_input_sha256, "expected input digest"):
        raise ValueError("external candidate input binding differs")
    context = (stream.seed, stream.leaf_id, stream.step, stream.global_size)
    if context != expected_context:
        raise ValueError("expected logical stream identity differs")
    state = payload["state"]
    _exact_keys(state, {"dtype", "shape", "byte_order", "data_hex"}, "state")
    if state["dtype"] != "bf16-uint16" or state["byte_order"] != "little" or state["shape"] != [stream.global_size]:
        raise ValueError("unsupported checkpoint state representation")
    if type(state["shape"][0]) is not int:
        raise ValueError("shape must use integer dimensions")
    encoded = state["data_hex"]
    if not isinstance(encoded, str) or len(encoded) != 4 * stream.global_size or not re.fullmatch("[0-9a-f]*", encoded):
        raise ValueError("invalid BF16 state bytes")
    bits = np.frombuffer(bytes.fromhex(encoded), dtype="<u2").astype(np.uint16, copy=True)
    bf16_input(bits)
    # Return fresh objects only after *all* validation. Existing live state is untouched.
    return stream, bits


def save_checkpoint(path, stream, destination, *, input_sha256):
    """Single-file JSON + hash, validate first, fsync and atomic same-dir replace.

    Hash detects accidental corruption, not an attacker capable of replacing
    both data and hash. This is single-process/single-owner, not a distributed
    transactional checkpoint or a crash-resume implementation for an optimizer.
    """
    stream.__post_init__()
    bits = bf16_input(destination)
    if bits.shape != (stream.global_size,) or not bits.flags.c_contiguous:
        raise ValueError("destination must have the contiguous global shape")
    payload = {
        "schema": SCHEMA, "version": VERSION, "overflow_policy": POLICY,
        "input_sha256": _digest(input_sha256, "input digest"),
        "rng": {"algorithm": ALGORITHM, "bits": 16, "byte_order": "little", "ordering": ORDERING,
                "seed": stream.seed, "leaf_id": stream.leaf_id, "step": stream.step,
                "global_size": stream.global_size, "next_index": stream.next_index},
        "state": {"dtype": "bf16-uint16", "shape": [stream.global_size], "byte_order": "little",
                  "data_hex": bits.astype("<u2", copy=False).tobytes().hex()},
    }
    raw = _canonical({"payload": payload, "sha256": hashlib.sha256(_canonical(payload)).hexdigest()}) + b"\n"
    context = (stream.seed, stream.leaf_id, stream.step, stream.global_size)
    _parse_checkpoint(raw, expected_input_sha256=input_sha256, expected_context=context)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as handle:
            temp_name = handle.name
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
        temp_name = None
        dir_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if temp_name is not None:
            os.unlink(temp_name)


def load_checkpoint(path, *, expected_input_sha256, expected_context):
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_CHECKPOINT_BYTES + 1)
    return _parse_checkpoint(raw, expected_input_sha256=expected_input_sha256,
                             expected_context=expected_context)
