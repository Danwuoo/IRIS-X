"""TRAIN-only LODO length metadata; no model, token arrays, answers or corpus output.

Grid16 source contract: user header=3 IDs, user EOS=1, assistant
header=3, assistant EOS=1; every digit/newline in a rectangular grid is
one ID. Source/raw-tokenizer parity is pre-existing evidence, not rerun here.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re

PINS = {
    "documents": "017b4f6fb60d0e80cb71426533ce3cf827feac76a6952fbea7af1ac758e9d37c",
    "index": "022be83469311ef64642616b5f0cda7b1e359d657f5c5e0fc5eb90e1972c3f24",
    "prior_metadata": "001911ff69d88ae26789ae986ae818a2773bc934656340609d047cfe5b7be214",
}


def require(value, why):
    if not value:
        raise ValueError(why)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def pair_lengths(text):
    """Validate canonical complete demonstrations, retaining dimensions only."""
    require(type(text) is str and text.isascii() and "\r" not in text
            and text.endswith("\n"), "canonical ASCII episode")
    lines = text.splitlines()
    require(lines and lines[0] == "ARC demonstration episode", "episode header")
    at, result = 1, []
    while at < len(lines):
        require(lines[at] == f"Example {len(result)}", "ordered TRAIN examples only")
        at += 1
        lengths = []
        for role in ("Input", "Output"):
            require(at < len(lines), "missing grid header")
            match = re.fullmatch(role + r" ([1-9][0-9]?) ([1-9][0-9]?)", lines[at])
            require(match is not None, "grid header")
            h, w = map(int, match.groups())
            require(1 <= h <= 30 and 1 <= w <= 30, "grid dimensions")
            at += 1
            grid = lines[at:at + h]
            require(len(grid) == h and all(len(row) == w and
                    all("0" <= c <= "9" for c in row) for row in grid),
                    "grid body / reserved-token injection")
            at += h
            lengths.append(h * w + h - 1)
        result.append(tuple(lengths))
    require(at == len(lines) and len(result) >= 2, "complete TRAIN demonstrations")
    return result


def episode_metadata(parent, text):
    lengths = pair_lengths(text)
    full = sum(i + o + 8 for i, o in lengths)
    views = []
    for q, (inp, out) in enumerate(lengths):
        target = out + 1  # Real assistant EOS, never padding.
        prompt = sum(i + o + 8 for n, (i, o) in enumerate(lengths) if n != q) + inp + 7
        require(prompt + target == full, "LODO complete-token accounting")
        views.append({"query_demo_ordinal": q, "prompt_ids": prompt,
                      "target_ids_including_eos": target})
    return {"parent_id": parent, "source_text_sha256": sha(text.encode()),
            "demonstration_pairs": len(lengths), "full_episode_ids": full,
            "views": views}


def pinned_jsonl(path, key):
    require(path.is_file() and not path.is_symlink(), "regular pinned input")
    body = path.read_bytes()
    require(sha(body) == PINS[key], "input SHA mismatch: " + key)
    return [json.loads(line) for line in body.splitlines()]


def run(documents, index, prior):
    require(len(documents) == len(index) == 800, "800-parent denominator")
    metadata = [x for x in prior if x.get("source") == "official800"]
    require(len(metadata) == 800, "prior grid16 800-parent denominator")
    rows, seen = [], set()
    for d, ix, old in zip(documents, index, metadata):
        parent = d["record_id"]
        require(parent not in seen and parent == ix["record_id"] == old["parent_id"], "parent/order binding")
        require(ix["source_field"] == "train", "TRAIN-only input")
        require(sha(d["text"].encode()) == ix["text_utf8_sha256"] == old["source_text_sha256"], "text binding")
        seen.add(parent)
        row = episode_metadata(parent, d["text"])
        require(row["full_episode_ids"] == old["ids"] and
                row["demonstration_pairs"] == old["pairs"] and
                sum(v["target_ids_including_eos"] for v in row["views"]) == old["supervised_targets"],
                "independent lengths versus prior real-tokenizer metadata")
        rows.append(row)
    views = [v for row in rows for v in row["views"]]
    summary = {"parents": len(rows), "views": len(views), "new_parents": 0,
               "full_episode_ids_total": sum(row["full_episode_ids"] for row in rows),
               "query_target_ids_total": sum(v["target_ids_including_eos"] for v in views),
               "lodo_prompt_ids_total": sum(v["prompt_ids"] for v in views),
               "length_metadata_only": True, "native_or_model_test": False,
               "nontrain_or_task_test_reads": False, "truncation": False,
               "generation_caps": {}, "input_pins": PINS}
    for cap in (160, 320, 512, 930):
        eligible = lambda v: v["prompt_ids"] + cap <= 3072 and v["target_ids_including_eos"] <= cap
        summary["generation_caps"][str(cap)] = {
            "views_prompt_plus_reserve_fits": sum(v["prompt_ids"] + cap <= 3072 for v in views),
            "views_known_train_target_fits_cap": sum(v["target_ids_including_eos"] <= cap for v in views),
            "views_both_conditions": sum(eligible(v) for v in views),
            "parents_any_view": sum(any(eligible(v) for v in row["views"]) for row in rows),
            "parents_all_views": sum(all(eligible(v) for v in row["views"]) for row in rows),
            "known_train_target_tokens_eligible": sum(v["target_ids_including_eos"] for v in views if eligible(v)),
        }
    summary["limits"] = [
        "All views reuse known TRAIN demonstrations; no original task.test query is present.",
        "Length is not mechanism diversity, difficulty, nonexposure or semantic deduplication proof.",
        "Known TRAIN answer lengths are disclosed engineering eligibility metadata, never final-holdout selection.",
        "A target fitting the cap does not guarantee the model emits EOS or a correct answer within it.",
        "Parent/ancestor split precedes views; no different-view holdout claim.",
        "No panel adoption, sampling, training or provider action is performed.",
    ]
    return rows, summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--documents", required=True, type=Path)
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--prior-metadata", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    require(not args.output.exists(), "new metadata output only")
    rows, summary = run(pinned_jsonl(args.documents, "documents"),
                        pinned_jsonl(args.index, "index"),
                        pinned_jsonl(args.prior_metadata, "prior_metadata"))
    args.output.mkdir(parents=True)
    data = b"".join(json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n" for row in rows)
    require(len(data) <= 1024 * 1024, "small metadata-only output")
    (args.output / "lengths.jsonl").write_bytes(data)
    summary["metadata_sha256"] = sha(data)
    summary["source_sha256"] = sha(Path(__file__).read_bytes())
    (args.output / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
