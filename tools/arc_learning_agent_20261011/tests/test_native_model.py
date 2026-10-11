import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from tools.arc_learning_agent_20261011.native_model import (
    ContextLimitError, NativeGridConstraint, NativeModel, NativeModelError, TinyByteTokenizer,
)


class NativeGridTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = TinyByteTokenizer()
        self.constraint = NativeGridConstraint(self.tokenizer, [128], tiny_cpu=True)

    def test_entire_grid_language_not_solution_list(self):
        for height in range(1, 31):
            for width in range(1, 31):
                text = "\n".join("".join(str((r + c) % 10) for c in range(width)) for r in range(height))
                ids = self.tokenizer.encode(text)
                self.assertEqual(self.constraint.validate_completion(ids + [128]), text)
        self.assertFalse(self.constraint.receipt["finite_solution_inventory"])

    def test_eos_and_prefix_fail_closed(self):
        self.assertNotIn(128, self.constraint.allowed_tokens([]))
        self.assertIn(128, self.constraint.allowed_tokens([49]))
        for ids in ([128], [49], [49, 128, 128], [49, 10, 128], [49, 10, 49, 49, 128], [49, 32, 128]):
            with self.subTest(ids=ids), self.assertRaises(NativeModelError):
                self.constraint.validate_completion(ids)
        for ids in ([49, 10, 10], [49] * 31, [49, 10] * 30, [128]):
            with self.subTest(ids=ids), self.assertRaises(NativeModelError):
                self.constraint.allowed_tokens(ids)
        self.assertEqual(self.constraint.allowed_tokens([49, 10] * 29 + [49]), [128])

    def test_unknown_decoder_and_synthetic_production_refused(self):
        with self.assertRaisesRegex(NativeModelError, "proven native"):
            NativeGridConstraint(TinyByteTokenizer(), [128], tiny_cpu=False)
        class Unproved:
            all_special_ids = [128]
            def get_vocab(self):
                return TinyByteTokenizer().get_vocab()
            class backend_tokenizer:
                @staticmethod
                def to_str():
                    return json.dumps({"decoder": {"type": "WordPiece"}})
        with self.assertRaisesRegex(NativeModelError, "unproven"):
            NativeGridConstraint(Unproved(), [128])

    def test_runtime_contextual_change_rejected(self):
        original = self.tokenizer.decode
        self.tokenizer.decode = lambda ids, **kwargs: "wrong" if ids == [49, 50] else original(ids, **kwargs)
        with self.assertRaisesRegex(NativeModelError, "contextual"):
            self.constraint.allowed_tokens([49, 50])


    def test_synthetic_tokenizer_export_roundtrip_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.tokenizer.save_pretrained(directory)
            self.assertEqual(len(paths), 1)
            path = Path(paths[0])
            fixture = json.loads(path.read_text())
            self.assertTrue(fixture["synthetic_only"])
            self.assertFalse(fixture["production_compatible"])
            self.assertEqual(path.name, "tiny-byte-tokenizer.json")
            self.assertFalse((Path(directory) / "tokenizer.json").exists())
            restored = TinyByteTokenizer.from_pretrained(directory)
            self.assertEqual(restored.get_vocab(), self.tokenizer.get_vocab())
            text = "".join(chr(i) for i in range(128))
            self.assertEqual(restored.decode(restored.encode(text)), text)
            self.assertEqual(self.tokenizer.save_pretrained(directory), paths)
            fixture["eos_token_id"] = 1
            path.write_text(json.dumps(fixture))
            with self.assertRaisesRegex(NativeModelError, "policy or bytes changed"):
                TinyByteTokenizer.from_pretrained(directory)
            with self.assertRaisesRegex(NativeModelError, "replace"):
                self.tokenizer.save_pretrained(directory)


class NativePromptTests(unittest.TestCase):
    def setUp(self):
        self.model = object.__new__(NativeModel)
        self.model.model = object()
        self.model.closed = False
        self.model.tokenizer = TinyByteTokenizer()
        self.model.vocab_size = 130
        self.model.context_limit = 8192
        self.model.prompt_cap = 6144
        self.model.output_cap = 2048
        self.model.eos_ids = (128,)
        self.messages = [{"role": "user", "content": "0"}]

    def test_exact_completion_mask_and_eos(self):
        row = self.model.prepare_completion(self.messages, "12\n34")
        n = row["prompt_tokens"]
        self.assertEqual(row["labels"][:n], [-100] * n)
        self.assertEqual(row["labels"][n:], [49, 50, 10, 51, 52, 128])
        self.assertEqual(row["completion_tokens"], 6)
        self.assertEqual(row["input_ids"][n:], row["labels"][n:])
        self.assertEqual(row["input_tokens"], len(row["input_ids"]))

    def test_native_boundary_merge_never_guessed(self):
        original = self.model.tokenizer.encode
        self.model.tokenizer.encode = lambda text, **kwargs: ([7] + original(text)[1:]) if text.endswith("1") else original(text)
        with self.assertRaisesRegex(NativeModelError, "boundary merge"):
            self.model.prepare_completion(self.messages, "1")

    def test_whole_prompt_context_exclusion_and_close(self):
        self.model.prompt_cap = 2
        with self.assertRaises(ContextLimitError):
            self.model.prepare_completion(self.messages, "1")
        self.model.close()
        with self.assertRaisesRegex(NativeModelError, "closed"):
            self.model.prepare_completion(self.messages, "1")

    def test_default_inert_and_lazy_import(self):
        with self.assertRaisesRegex(NativeModelError, "default-inert"):
            NativeModel.from_config({})
        command = "import sys; import tools.arc_learning_agent_20261011.native_model; assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules"
        subprocess.run([sys.executable, "-c", command], check=True)


if __name__ == "__main__":
    unittest.main()
