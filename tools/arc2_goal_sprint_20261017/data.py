"""Truth-free training/public inputs and reversible ARC grid representations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import re

from src.irisx.arc_nvarc_data import known_variant_group


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def valid_grid(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 30:
        return False
    width = len(value[0]) if isinstance(value[0], list) else 0
    return 1 <= width <= 30 and all(isinstance(row, list) and len(row) == width and
        all(type(x) is int and 0 <= x <= 9 for x in row) for row in value)


def transform(grid, rotation=0, transpose=False, colors=None, inverse=False):
    colors = list(range(10)) if colors is None else colors
    if sorted(colors) != list(range(10)):
        raise ValueError("color permutation required")
    result = [list(row) for row in grid]
    if inverse:
        rev = {x: i for i, x in enumerate(colors)}
        result = [[rev[x] for x in row] for row in result]
        for _ in range((-rotation) % 4):
            result = [list(row) for row in zip(*result[::-1])]
        if transpose:
            result = [list(row) for row in zip(*result)]
    else:
        if transpose:
            result = [list(row) for row in zip(*result)]
        for _ in range(rotation % 4):
            result = [list(row) for row in zip(*result[::-1])]
        result = [[colors[x] for x in row] for row in result]
    return result


def random_view(rng):
    colors = list(range(10))
    rng.shuffle(colors)
    return {"rotation": rng.randrange(4), "transpose": bool(rng.randrange(2)), "colors": colors}


IDENTITY = {"rotation": 0, "transpose": False, "colors": list(range(10))}
SECOND_VIEW = {"rotation": 1, "transpose": False, "colors": [0, 7, 2, 9, 4, 1, 6, 3, 8, 5]}


def grid_text(grid):
    return "\n".join(" ".join(map(str, row)) for row in grid)


def answer_text(grid):
    return "<grid>\n" + grid_text(grid) + "\n</grid>"


def parse_grid(text):
    """Parse a bounded complete grid, never silently crop or repair its cells."""
    matches = re.findall(r"<grid>\s*(.*?)\s*</grid>", text, flags=re.S)
    if matches:
        text = matches[-1]
    else:
        text = text.strip()
        if text.startswith("["):
            try:
                grid = json.loads(text)
                return grid if valid_grid(grid) else None
            except (ValueError, TypeError):
                return None
    rows = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not re.fullmatch(r"[0-9](?:\s*[0-9])*", line):
            return None
        rows.append([int(x) for x in re.findall(r"[0-9]", line)])
    return rows if valid_grid(rows) else None


def render_prompt_spans(demos, query):
    """Return the unchanged prompt and exact character spans of demo outputs."""
    parts = ["Infer the grid transformation from the examples. Apply the same rule to the final input. "
             "Return only the output grid in <grid> and </grid> tags, with one row per line and digits separated by spaces."]
    spans = []
    for i, pair in enumerate(demos):
        parts.append(f"Example {i + 1} input:\n" + grid_text(pair["input"]))
        start = len("\n\n".join(parts)) + len("\n\nOutput:\n")
        answer = answer_text(pair["output"])
        spans.append((start, start + len(answer)))
        parts.append("Output:\n" + answer)
    parts.append("Final input:\n" + grid_text(query) + "\nOutput:")
    return "\n\n".join(parts), spans


def render_prompt(demos, query):
    return render_prompt_spans(demos, query)[0]


def causal_output_mask(tokenizer, text, content, spans, ids, completion):
    """Supervise only whole tokens inside answer spans after the first answer.

    Chat rendering must embed the exact content once. Fast-tokenizer offsets
    must agree with the actual model IDs. Boundary-crossing tokens are excluded,
    never approximated by tokenizing a substring or silently using another mask.
    """
    if not getattr(tokenizer, "is_fast", False):
        raise ValueError("causal_outputs requires a Fast tokenizer with offsets")
    if not spans:
        raise ValueError("causal_outputs requires a retained causal demonstration; exceeds context")
    if text.count(content) != 1:
        raise ValueError("chat template must preserve the exact prompt content once")
    shift = text.index(content)
    ranges = [(a + shift, b + shift) for a, b in spans[1:]]
    encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = encoded["offset_mapping"]
    if encoded["input_ids"] != ids or len(offsets) != len(ids):
        raise ValueError("tokenizer offset IDs differ from actual prompt IDs")
    previous_start = 0
    mask = []
    for index, pair in enumerate(offsets):
        if (len(pair) != 2 or any(type(v) is not int for v in pair)
                or not 0 <= pair[0] <= pair[1] <= len(text)
                or pair[0] < previous_start):
            raise ValueError("invalid tokenizer character offsets")
        a, b = pair
        previous_start = a
        mask.append(int(index > 0 and a < b and any(left <= a < b <= right for left, right in ranges)))
    return mask + [1] * len(completion)


def encode_example(tokenizer, demos, query, target=None, *, context=8192, generation=2048, loss_mode="final"):
    """Drop whole demonstrations only; never truncate a query or target grid."""
    if loss_mode not in {"final", "causal_outputs"} or (target is None and loss_mode != "final"):
        raise ValueError("invalid supervised loss mode")
    kept = list(demos)
    completion = [] if target is None else tokenizer.encode(answer_text(target), add_special_tokens=False)
    if target is not None and tokenizer.eos_token_id is not None:
        completion.append(tokenizer.eos_token_id)
    reserve = len(completion) if target is not None else generation
    while True:
        content, spans = render_prompt_spans(kept, query)
        text = tokenizer.apply_chat_template([{"role": "user", "content": content}],
                                            tokenize=False, add_generation_prompt=True, enable_thinking=False)
        ids = tokenizer.encode(text, add_special_tokens=False)
        if len(ids) + reserve <= context:
            result = {"prompt_ids": ids, "completion_ids": completion, "demos_used": len(kept),
                      "demos_dropped": len(demos) - len(kept)}
            if loss_mode == "causal_outputs":
                result["loss_mask"] = causal_output_mask(tokenizer, text, content, spans, ids, completion)
                result["loss_mode"] = loss_mode
            return result
        if not kept:
            raise ValueError("complete query/target exceeds context; truncation forbidden")
        # Preserve as many examples as possible by dropping the largest one.
        index = max(range(len(kept)), key=lambda i: sum(len(grid_text(v)) for v in kept[i].values()))
        kept.pop(index)


def inference_views(count, *, seed, task_id, demo_count):
    """Frozen D4/color/demo-order views; independent of global RNG and answers."""
    if type(count) is not int or count not in (2, 8, 16):
        raise ValueError("candidate_views must be 2, 8, or 16")
    order = list(range(demo_count))
    if count == 2:
        return [{"transform": spec, "demo_order": list(order)} for spec in (IDENTITY, SECOND_VIEW)]
    views = []
    for index in range(count):
        rng = random.Random(hashlib.sha256(canonical([seed, task_id, index, "candidate-views-v1"])).digest())
        colors, shuffled = list(range(10)), list(order)
        if index:
            rng.shuffle(colors)
            rng.shuffle(shuffled)
        views.append({"transform": {"rotation": index % 4, "transpose": bool((index // 4) % 2),
                                     "colors": colors}, "demo_order": shuffled})
    return views


def view_inputs(task, query, view):
    spec = view["transform"]
    demos = [{k: transform(task["train"][i][k], **spec) for k in ("input", "output")}
             for i in view["demo_order"]]
    return demos, transform(query, **spec)


def sample_sft_parent(tasks, rng, bundles_by_parent=None):
    """Uniform original parents, then 50/50 original/generated when available."""
    key = rng.choice(sorted(tasks))
    bundles = (bundles_by_parent or {}).get(key, [])
    if bundles and rng.random() < .5:
        bundle = rng.choice(bundles)
        return key, bundle, {"source": "curriculum", "bundle_id": bundle["task_id"]}
    return key, tasks[key], {"source": "original", "bundle_id": None}


def loo_example(task, rng, *, augment=True, held_index=None):
    pairs = task["train"]
    index = rng.randrange(len(pairs)) if held_index is None else held_index
    spec = random_view(rng) if augment else IDENTITY
    demos = [{key: transform(pair[key], **spec) for key in ("input", "output")}
             for i, pair in enumerate(pairs) if i != index]
    if augment:
        rng.shuffle(demos)
    return demos, transform(pairs[index]["input"], **spec), transform(pairs[index]["output"], **spec)


def load_data(training_root, manifest_path, public_path, *, expected_manifest_sha256=None):
    body = Path(manifest_path).read_bytes()
    sha = hashlib.sha256(body).hexdigest()
    if expected_manifest_sha256 is not None and sha != expected_manifest_sha256:
        raise ValueError("training manifest identity differs")
    manifest = json.loads(body)
    public = json.loads(Path(public_path).read_bytes())
    if len(public) != 120 or sum(len(t["test"]) for t in public.values()) != 167:
        raise ValueError("complete PUBLIC120/167 challenge inventory required")
    for task in public.values():
        if set(task) != {"train", "test"} or any(set(t) != {"input"} for t in task["test"]):
            raise ValueError("public test answers forbidden")
        if not all(valid_grid(p[k]) for p in task["train"] for k in ("input", "output")):
            raise ValueError("invalid public demonstration")
        if not all(valid_grid(p["input"]) for p in task["test"]):
            raise ValueError("invalid public query")
    protected = set(manifest["protected_ids"]) | set(public)
    public_variants = {known_variant_group({"train": t["train"], "test": []}) for t in public.values()}
    tasks, excluded, groups = {}, [], {}
    root = Path(training_root)
    inventory = manifest["files"]
    expected = {Path(name).name for name in inventory if name.startswith("data/training/") and name.endswith(".json")}
    if {p.name for p in root.glob("*.json")} != expected or len(expected) != 1000:
        raise ValueError("complete pinned training inventory required")
    for name in sorted(expected):
        path = root / name
        if path.is_symlink():
            raise ValueError("training symlink forbidden")
        raw = path.read_bytes()
        row = inventory["data/training/" + name]
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("training source digest differs")
        task_id = path.stem
        original = json.loads(raw)
        # Original training-file test fields may exist but are NEVER training examples.
        pairs = original["train"]
        if not pairs or not all(set(p) == {"input", "output"} and all(valid_grid(p[k]) for k in p) for p in pairs):
            raise ValueError("invalid training demonstrations")
        task = {"train": pairs}
        variant = known_variant_group({**task, "test": []})
        if task_id in protected or variant in public_variants:
            excluded.append(task_id)
            continue
        tasks[task_id] = task
        groups.setdefault(variant, []).append(task_id)
    fixed = manifest["upstream"]["fixed_splits"]
    if set(fixed["train"]) & set(fixed["dev"]) or set(fixed["train"]) | set(fixed["dev"]) != {Path(x).stem for x in expected}:
        raise ValueError("invalid historical train/dev partition")
    dev_ids = set(fixed["dev"])
    # Known duplicates touching historical dev are all demoted, never moved to train.
    for ids in groups.values():
        if set(ids) & dev_ids:
            dev_ids.update(ids)
    training = {k: v for k, v in tasks.items() if k not in dev_ids}
    dev = {k: v for k, v in tasks.items() if k in dev_ids}
    if not training or not dev:
        raise ValueError("nonempty disjoint training/development required")
    receipt = {"training_manifest_sha256": sha, "training_tasks": len(training), "dev_tasks": len(dev),
               "excluded_task_ids": excluded, "train_ids_digest": digest(sorted(training)),
               "dev_ids_digest": digest(sorted(dev)), "public_digest": digest(public),
               "training_test_fields_used": False, "deduplication": "known D4/color-renaming/demo-shuffle only"}
    return training, dev, public, receipt
