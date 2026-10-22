"""Offline numerical/reference tests, deliberately not a model-training gate."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from tests.platform_requirements import requires_linux

import numpy as np

from tools.bf16_numeric_prerequisites_20261021 import reference as r


def f32(bits):
    return np.array(bits, dtype=np.uint32).view(np.float32)


class RoundingTests(unittest.TestCase):
    def test_every_finite_bf16_exact_identity(self):
        bits = np.arange(65536, dtype=np.uint16)
        bits = bits[(bits & 0x7F80) != 0x7F80]
        values = r.decode(bits)
        np.testing.assert_array_equal(r.nearest(values), bits)
        for random in (0, 32768, 65535):
            np.testing.assert_array_equal(r.stochastic(values, np.full(bits.shape, random, np.uint16)), bits)

    def test_signed_zero(self):
        values = f32([0, 0x80000000, 1, 0x80000001])
        np.testing.assert_array_equal(r.nearest(values), [0, 0x8000, 0, 0x8000])
        np.testing.assert_array_equal(r.stochastic(values, np.zeros(4, np.uint16)), [0, 0x8000, 1, 0x8001])
        np.testing.assert_array_equal(r.stochastic(values, np.ones(4, np.uint16)), [0, 0x8000, 0, 0x8000])
        self.assertTrue(np.signbit(r.decode(np.array([0x8000], np.uint16)))[0])

    def test_ties_to_even_positive_negative_normal_subnormal_boundary(self):
        values = f32([0x3F808000, 0x3F818000, 0xBF808000, 0xBF818000,
                      0x00008000, 0x00018000, 0x007F8000, 0x3FFF8000])
        np.testing.assert_array_equal(r.nearest(values),
                                      [0x3F80, 0x3F82, 0xBF80, 0xBF82, 0, 2, 0x80, 0x4000])

    def test_probability_exhaustive_and_signed_unbiasedness(self):
        # Every possible U16, not an approximation; negative numeric upper probability reverses.
        random = np.arange(65536, dtype=np.uint16)
        cases = [0x3F800001, 0x3F804000, 0x3F808000, 0x3F80FFFF,
                 0xBF804000, 0xBF80FFFF, 0x00000001, 0x00008000,
                 0x80008000, 0x007FFFFF, 0x3FFFFFFF, 0x7F7EFFFF]
        for word in cases:
            with self.subTest(word=hex(word)):
                value = f32([word])[0]
                out = r.stochastic(np.full(65536, value, np.float32), random)
                toward = word >> 16
                away = toward + 1
                rem = word & 0xFFFF
                self.assertEqual(int(np.count_nonzero(out == away)), rem)
                self.assertEqual(set(np.unique(out).tolist()), {toward, away})
                y = r.decode(out).astype(np.float64)
                # All BF16 intervals and FP32 values are exact powers-of-two multiples.
                self.assertEqual(float(y.mean()), float(value))
                a, b = sorted(r.decode(np.array([toward, away], np.uint16)).astype(np.float64))
                var = (float(value) - a) * (b - float(value))
                self.assertAlmostEqual(float(np.var((y - float(value)) / (b - a))), var / (b - a)**2, places=14)

    def test_nonfinite_and_overflow_rejected(self):
        for value in [np.nan, np.inf, -np.inf, np.finfo(np.float32).max, -np.finfo(np.float32).max]:
            for fn in [lambda x: r.nearest(x), lambda x: r.stochastic(x, np.zeros(1, np.uint16))]:
                with self.assertRaises(ValueError):
                    fn(np.array([value], np.float32))
        np.testing.assert_array_equal(r.nearest(np.array([r.MAX_BF16, -r.MAX_BF16], np.float32)), [0x7F7F, 0xFF7F])
        with self.assertRaises(ValueError):
            r.decode(np.array([0x7F80], np.uint16))

    def test_dtype_shape_and_bounded_inputs(self):
        with self.assertRaises(TypeError):
            r.nearest(np.array([1.0], np.float64))
        with self.assertRaises(TypeError):
            r.stochastic(np.ones(2, np.float32), np.zeros((2, 1), np.uint16))
        with self.assertRaises(TypeError):
            r.stochastic(np.ones(2, np.float32), np.zeros(2, np.uint32))
        with self.assertRaises(ValueError):
            r.nearest(np.zeros(r.MAX_ELEMENTS + 1, np.float32))

    def test_no_early_bf16_cast(self):
        original = np.array([1.0], np.float32)
        candidate = original + np.float32(1e-5)
        self.assertNotEqual(float(candidate[0]), float(original[0]))
        self.assertEqual(r.nearest(candidate)[0], r.nearest(original)[0])
        self.assertGreater(r.decode(r.stochastic(candidate, np.array([0], np.uint16)))[0], 1)
        # Casting candidate before SR destroys the discarded bits permanently.
        early = r.decode(r.nearest(candidate))
        self.assertEqual(r.decode(r.stochastic(early, np.array([0], np.uint16)))[0], 1)

    def test_fp32_candidate_can_erase_update_before_sr(self):
        weight = np.array([1.0], np.float32)
        delta = np.array([-1e-8], np.float32)
        candidate = np.add(weight, delta, dtype=np.float32)
        self.assertEqual(float(candidate[0]), 1.0)
        self.assertLess(float(weight[0]) + float(delta[0]), 1.0)
        random = np.arange(65536, dtype=np.uint16)
        np.testing.assert_array_equal(r.stochastic(np.full(65536, candidate[0], np.float32), random),
                                      np.full(65536, 0x3F80, np.uint16))

    def test_cumulative_error_accounting_and_low_lr_stagnation(self):
        initial = np.array([0.5, 1.0, -1.0], np.float32)
        delta = np.array([1e-6, -1e-6, 1e-6], np.float32)
        bits = r.nearest(initial)
        intended = initial.astype(np.float64).copy()
        round_error = np.zeros(3, np.float64)
        add_error = np.zeros(3, np.float64)
        for _ in range(256):
            old = r.decode(bits)
            candidate = np.add(old, delta, dtype=np.float32)
            bits = r.nearest(candidate)
            round_error += r.decode(bits).astype(np.float64) - candidate.astype(np.float64)
            add_error += candidate.astype(np.float64) - (old.astype(np.float64) + delta.astype(np.float64))
            intended += delta.astype(np.float64)
        np.testing.assert_array_equal(r.decode(bits), initial)
        np.testing.assert_allclose(r.decode(bits).astype(np.float64) - intended,
                                   round_error + add_error, rtol=0, atol=1e-14)

    def test_sampled_prng_probabilities_predeclared(self):
        cases = [0x3F804000, 0xBF804000, 0x00008000, 0x3F80C000]
        n_per_seed = 4096
        seeds = tuple(range(8))
        alpha_family = 1e-6
        n = n_per_seed * len(seeds)
        tolerance = np.sqrt(np.log(2 * len(cases) / alpha_family) / (2 * n))
        random = np.concatenate([r.indexed_bits(seed, "probability-test", 0,
                    np.arange(n_per_seed, dtype=np.uint64)) for seed in seeds])
        for word in cases:
            x = np.full(n, f32([word])[0], np.float32)
            out = r.stochastic(x, random)
            observed_away = np.mean(out == ((word >> 16) + 1))
            self.assertLessEqual(abs(observed_away - (word & 0xFFFF)/65536), tolerance)


class RandomAndCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.values = np.linspace(-1.1, 1.1, 113, dtype=np.float32)
        self.context = (42, "decoder/0/expert/weight", 19, self.values.size)
        self.digest = r.input_digest(self.values)

    def stream(self):
        return r.RoundingStream(*self.context)

    def test_indexed_shard_permutation_replica_semantics(self):
        indices = np.arange(113, dtype=np.uint64)
        full = r.indexed_bits(*self.context[:3], indices)
        shards = np.concatenate([r.indexed_bits(*self.context[:3], indices[:7]),
                                 r.indexed_bits(*self.context[:3], indices[7:41]),
                                 r.indexed_bits(*self.context[:3], indices[41:])])
        np.testing.assert_array_equal(shards, full)
        permutation = np.arange(112, -1, -1)
        np.testing.assert_array_equal(r.indexed_bits(*self.context[:3], indices[permutation]), full[permutation])
        np.testing.assert_array_equal(r.indexed_bits(*self.context[:3], indices), full)
        self.assertFalse(np.array_equal(r.indexed_bits(42, self.context[1], 20, indices), full))
        self.assertFalse(np.array_equal(r.indexed_bits(42, "other-leaf", 19, indices), full))
        self.assertFalse(np.array_equal(r.indexed_bits(43, self.context[1], 19, indices), full))
        # Resetting shard-local indices repeats noise; it is not valid resharding.
        np.testing.assert_array_equal(r.indexed_bits(*self.context[:3], indices[:7]), full[:7])
        self.assertFalse(np.array_equal(r.indexed_bits(*self.context[:3], indices[:7]), full[7:14]))

    def test_fixed_known_answer_prng(self):
        prefix = b"iris-bf16-sr\x00v1\x00" + (42).to_bytes(8, "little") + (19).to_bytes(8, "little")
        leaf = self.context[1].encode("ascii")
        prefix += len(leaf).to_bytes(2, "little") + leaf
        expected = [int.from_bytes(hashlib.sha256(prefix + i.to_bytes(8, "little")).digest()[:2], "little") for i in [0, 2**32, 2**64-1]]
        np.testing.assert_array_equal(r.indexed_bits(*self.context[:3], np.array([0, 2**32, 2**64-1], np.uint64)), expected)

    @requires_linux("POSIX directory fsync for durable atomic checkpoint replacement")
    def test_interrupted_chunked_resume_exact(self):
        whole = np.zeros(self.values.size, np.uint16)
        self.stream().round_next(self.values, whole)
        for split in [0, 1, 37, 112, 113]:
            with self.subTest(split=split), tempfile.TemporaryDirectory() as tmp:
                bits = np.zeros(self.values.size, np.uint16)
                state = self.stream()
                state.round_next(self.values[:split], bits)
                path = Path(tmp) / "state.json"
                r.save_checkpoint(path, state, bits, input_sha256=self.digest)
                restored, result = r.load_checkpoint(path, expected_input_sha256=self.digest, expected_context=self.context)
                for start in range(split, self.values.size, 11):
                    restored.round_next(self.values[start:start+11], result)
                np.testing.assert_array_equal(result, whole)
                self.assertEqual(restored.next_index, self.values.size)
                self.assertEqual(state.next_index, split)

    def test_failure_preserves_cursor_and_destination(self):
        state = self.stream()
        bits = np.zeros(self.values.size, np.uint16)
        for invalid in [np.array([np.nan], np.float32), np.zeros(114, np.float32), np.ones((1, 1), np.float32)]:
            with self.assertRaises(ValueError):
                state.round_next(invalid, bits)
            self.assertEqual(state.next_index, 0)
            self.assertTrue(np.all(bits == 0))

    def test_overlapping_or_strided_destination_rejected_atomically(self):
        backing = np.zeros(2*self.values.size, np.uint16)
        destinations = [np.lib.stride_tricks.as_strided(backing[:1], shape=(self.values.size,),
                        strides=(0,), writeable=True), backing[::2]]
        for destination in destinations:
            state = self.stream()
            with self.assertRaisesRegex(ValueError, "contiguous"):
                state.round_next(self.values, destination)
            self.assertEqual(state.next_index, 0)
            self.assertTrue(np.all(backing == 0))
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "state.json"
                with self.assertRaisesRegex(ValueError, "contiguous"):
                    r.save_checkpoint(path, state, destination, input_sha256=self.digest)
                self.assertFalse(path.exists())

    def test_experiment_receipt_refuses_overwrite_before_computation(self):
        from tools.bf16_numeric_prerequisites_20261021 import experiments
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "numerical-receipt.json"
            path.write_text("existing receipt")
            with mock.patch("sys.argv", ["experiments", "--output", tmp]):
                with mock.patch.object(experiments, "random_cube") as compute:
                    with self.assertRaises(SystemExit) as raised:
                        experiments.main()
                    self.assertEqual(raised.exception.code, 2)
                    compute.assert_not_called()
            self.assertEqual(path.read_text(), "existing receipt")

    @requires_linux("POSIX directory fsync for durable atomic checkpoint replacement")
    def test_atomic_save_failure_preserves_prior_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            bits = np.zeros(self.values.size, np.uint16)
            state = self.stream()
            r.save_checkpoint(path, state, bits, input_sha256=self.digest)
            old = path.read_bytes()
            state.round_next(self.values[:3], bits)
            with mock.patch.object(r.os, "replace", side_effect=OSError("simulated interruption before atomic commit")):
                with self.assertRaises(OSError):
                    r.save_checkpoint(path, state, bits, input_sha256=self.digest)
            self.assertEqual(path.read_bytes(), old)
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)

    @requires_linux("POSIX directory fsync for durable atomic checkpoint replacement")
    def test_all_corrupt_and_missing_contract_fields_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            bits = np.zeros(self.values.size, np.uint16)
            state = self.stream()
            r.save_checkpoint(path, state, bits, input_sha256=self.digest)
            valid = json.loads(path.read_bytes())
            changes = [lambda p: p.pop("version"), lambda p: p.update(schema="v0"),
                       lambda p: p["rng"].pop("next_index"), lambda p: p["rng"].update(algorithm="other"),
                       lambda p: p["rng"].update(bits=32), lambda p: p["rng"].update(seed=True),
                       lambda p: p["rng"].update(next_index=114), lambda p: p["rng"].update(next_index=-1),
                       lambda p: p["rng"].update(ordering="rank-local"),
                       lambda p: p["state"].update(dtype="pickle"), lambda p: p["state"].update(shape=[112]),
                       lambda p: p["state"].update(data_hex="807f" + p["state"]["data_hex"][4:]),
                       lambda p: p.update(input_sha256="0"*64)]
            for change in changes:
                env = copy.deepcopy(valid)
                change(env["payload"])
                env["sha256"] = hashlib.sha256(r._canonical(env["payload"])).hexdigest()
                path.write_bytes(r._canonical(env))
                with self.assertRaises(ValueError):
                    r.load_checkpoint(path, expected_input_sha256=self.digest, expected_context=self.context)
                self.assertEqual(state.next_index, 0)
                self.assertTrue(np.all(bits == 0))
            bad = copy.deepcopy(valid)
            bad["payload"]["rng"]["seed"] = 1
            path.write_bytes(r._canonical(bad))
            with self.assertRaisesRegex(ValueError, "integrity"):
                r.load_checkpoint(path, expected_input_sha256=self.digest, expected_context=self.context)
            path.write_text('{"payload":{},"payload":{},"sha256":"' + '0'*64 + '"}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                r.load_checkpoint(path, expected_input_sha256=self.digest, expected_context=self.context)
            path.write_bytes(r._canonical(valid))
            with self.assertRaisesRegex(ValueError, "identity"):
                r.load_checkpoint(path, expected_input_sha256=self.digest, expected_context=(43, *self.context[1:]))

    def test_candidate_digest_binds_shape_sign_and_bits(self):
        self.assertNotEqual(r.input_digest(np.array([0], np.float32)), r.input_digest(np.array([-0.0], np.float32)))
        self.assertNotEqual(r.input_digest(np.ones(4, np.float32)), r.input_digest(np.ones((2, 2), np.float32)))

    def test_rng_contract_rejects_invalid_identity(self):
        for args in [(True, "leaf", 0, 1), (-1, "leaf", 0, 1), (0, "", 0, 1),
                     (0, "leaf", -1, 1), (0, "leaf", 0, r.MAX_ELEMENTS+1)]:
            with self.assertRaises(ValueError):
                r.RoundingStream(*args)
        with self.assertRaises(TypeError):
            r.indexed_bits(0, "leaf", 0, np.array([-1], np.int64))


if __name__ == "__main__":
    unittest.main()
