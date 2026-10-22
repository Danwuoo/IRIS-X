"""Offline check with the already-available public Base tokenizer, no weights."""
from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path

from .contract import build_row, token_ledger

TOKENIZER_SHA256 = "fe000e3ed39ed12b8d2481d527d44f93c65d37e87645d2dcc80d1bf9d50d2927"
CONFIG_SHA256 = "3891e840d7dc5fca0af33d3a25083a735e36fe06214e3f707024820cb6b9f89c"
EOS = 248044
VOCAB = 248320
TEXTS = (
    "Grid input:\n0 1 0\n2 0 2\nGrid output:\n0 1 0\n2 0 2\n",
    "def reflect(row):\n    return row[::-1]\n",
    "規則：保留空白與換行。\n輸入 0 1 2\n輸出 2 1 0\n",
    "Spaces  stay\tand tabs stay.\n\n",
    "input=[[0,1],[2,3]]\noutput=[[2,3],[0,1]]\n",
    "Café is NFC; a != b; 1e-6 != 0.\n",
)


def checked_file(path, digest):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected regular local tokenizer file")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("Public Base tokenizer pin mismatch")
    return body


def encode_with_policy(tokenizer, text, *, policy="require_exact", content_kind="text"):
    """Keep native tokenizer behavior; an explicit text policy may allow NFC.

    This reports transformation, not semantic equivalence. Programs, exact-match
    targets and similar fields need an independent semantic policy, so this
    bounded reference only allows automatic NFC acceptance for ordinary text.
    Original strings are never replaced; hashes identify both representations.
    """
    if policy not in {"require_exact", "native_nfc_with_receipt"}:
        raise ValueError("Unknown normalization policy")
    if content_kind not in {"text", "code", "exact_target"} or not isinstance(text, str):
        raise ValueError("Invalid content kind or text")
    normalized = unicodedata.normalize("NFC", text)
    changed = normalized != text
    if changed and (policy == "require_exact" or content_kind != "text"):
        raise ValueError("Non-NFC input requires an explicit semantic normalization policy")
    ids = tokenizer.encode(text, add_special_tokens=False).ids
    expected = normalized if policy == "native_nfc_with_receipt" else text
    if tokenizer.decode(ids, skip_special_tokens=False) != expected:
        raise ValueError("Tokenizer changed manufactured input text")
    return ids, {"policy": policy, "content_kind": content_kind, "changed": changed,
                 "raw_utf8_sha256": hashlib.sha256(text.encode()).hexdigest(),
                 "normalized_utf8_sha256": hashlib.sha256(normalized.encode()).hexdigest()}


def encode_without_silent_normalization(tokenizer, text):
    return encode_with_policy(tokenizer, text)[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    tokenizer_body = checked_file(args.tokenizer_root / "tokenizer.json", TOKENIZER_SHA256)
    if json.loads(tokenizer_body).get("normalizer") != {"type": "NFC"}:
        raise ValueError("Unexpected native tokenizer normalization")
    config = json.loads(checked_file(args.tokenizer_root / "tokenizer_config.json", CONFIG_SHA256))
    if config["eos_token"] != config["pad_token"] or config.get("bos_token") is not None:
        raise ValueError("Expected exact public Base EOS/PAD and no BOS")
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(args.tokenizer_root / "tokenizer.json"))
    if tokenizer.token_to_id(config["eos_token"]) != EOS:
        raise ValueError("Unexpected EOS mapping")
    receipts, rows = [], []
    for i, text in enumerate(TEXTS):
        encoded = encode_without_silent_normalization(tokenizer, text)
        ids = encoded + [EOS]
        row = build_row(ids, [True] * len(ids), length=128, eos_id=EOS,
                        vocab_size=VOCAB, objective="cpt")
        naive_count = sum(x != EOS for x in row["targets"])
        if row["loss_positions"] - naive_count != 1:
            raise ValueError("EOS/PAD counterexample did not reproduce")
        receipts.append({"manufactured_document": i, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                         "ids": ids, "naive_id_mask_loss_positions": naive_count,
                         "length_mask_loss_positions": row["loss_positions"],
                         "true_eos_target_position": row["true_eos_target_position"]})
        rows.append(row)
    special_ids = tokenizer.encode("literal <|endoftext|> inside", add_special_tokens=False).ids + [EOS]
    try:
        build_row(special_ids, [True] * len(special_ids), length=128, eos_id=EOS,
                  vocab_size=VOCAB, objective="cpt")
    except ValueError:
        literal_special_rejected = True
    else:
        raise ValueError("Internal EOS injection was not rejected")
    decomposed = "é versus e\u0301 are not the same raw bytes.\n"
    native_decode = tokenizer.decode(tokenizer.encode(decomposed, add_special_tokens=False).ids,
                                     skip_special_tokens=False)
    if native_decode == decomposed or native_decode != unicodedata.normalize("NFC", decomposed):
        raise ValueError("Native NFC normalization counterexample did not reproduce")
    try:
        encode_without_silent_normalization(tokenizer, decomposed)
    except ValueError:
        non_nfc_rejected = True
    else:
        raise ValueError("Non-NFC source was silently rewritten")
    admitted_ids, normalization_receipt = encode_with_policy(
        tokenizer, decomposed, policy="native_nfc_with_receipt", content_kind="text")
    if tokenizer.decode(admitted_ids, skip_special_tokens=False) != native_decode:
        raise ValueError("Explicit native NFC policy changed tokenizer semantics")
    report = {"format": "irisx/public-base-token-probe-v1", "status": "PASS",
              "hf_repository": "Qwen/Qwen3.5-35B-A3B-Base",
              "revision": "0f0813072d2358973511097385626f21fcb6d422",
              "tokenizer_sha256": TOKENIZER_SHA256, "config_sha256": CONFIG_SHA256,
              "ledger": token_ledger(rows), "documents": receipts,
              "literal_internal_eos_rejected": literal_special_rejected,
              "native_normalizer": "NFC", "non_nfc_input_rejected": non_nfc_rejected,
              "native_unicode_change_reproduced": True,
              "explicit_text_normalization_receipt": normalization_receipt,
              "limits": ["Manufactured text, not admitted real training corpus",
                         "No weights, forward, optimizer, or MaxText adapter executed",
                         "No packing, no truncation; SFT boundary must be independently validated"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as out:
        json.dump(report, out, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        out.write("\n")
    print(json.dumps({"status": "PASS", "ledger": report["ledger"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
