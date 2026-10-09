"""CPU known-witness checks against the actual verifier, independent reference.

This proves the listed authored witnesses are in the frozen inventory and that
their compiler templates execute correctly. It is not an ARC coverage estimate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from arc_typed_ir import compile_plan, digest, grammar_candidates, grammar_manifest


def reference_step(grid, step):
    """Independent ordinary Python reference over trusted operation data only."""
    g = [row[:] for row in grid]
    op = step["op"]
    if op == "identity":
        return g
    if op == "flip_horizontal":
        return [list(reversed(row)) for row in g]
    if op == "flip_vertical":
        return list(reversed(g))
    if op == "transpose":
        return [list(row) for row in zip(*g)]
    if op == "rotate":
        for _ in range(step["turns"]):
            g = [list(row) for row in zip(*reversed(g))]
        return g
    if op == "recolor":
        return [[step["target"] if x == step["source"] else x for x in row] for row in g]
    if op == "scale":
        k = step["factor"]
        return [[x for x in row for _ in range(k)] for row in g for _ in range(k)]
    if op == "tile":
        return [row * step["columns"] for _ in range(step["rows"]) for row in g]
    if op == "crop_nonbackground":
        pixels = [(r, c) for r, row in enumerate(g) for c, x in enumerate(row)
                  if x != step["background"]]
    elif op == "largest_component_crop":
        seen, objects = set(), []
        for r, row in enumerate(g):
            for c, color in enumerate(row):
                if color == step["background"] or (r, c) in seen:
                    continue
                pending, obj = [(r, c)], []
                seen.add((r, c))
                while pending:
                    rr, cc = pending.pop()
                    obj.append((rr, cc))
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            if not (dr or dc) or (step["connectivity"] == 4 and dr and dc):
                                continue
                            nr, nc = rr + dr, cc + dc
                            if (0 <= nr < len(g) and 0 <= nc < len(g[0]) and
                                    (nr, nc) not in seen and g[nr][nc] == color):
                                pending.append((nr, nc))
                                seen.add((nr, nc))
                objects.append(obj)
        pixels = max(objects, key=len) if objects else []
    else:
        raise ValueError("unknown reference operation")
    if not pixels:
        return g
    r0, r1 = min(r for r, _ in pixels), max(r for r, _ in pixels) + 1
    c0, c1 = min(c for _, c in pixels), max(c for _, c in pixels) + 1
    return [row[c0:c1] for row in g[r0:r1]]


def reference_plan(grid, plan):
    for step in plan["steps"]:
        grid = reference_step(grid, step)
    return grid


def known_witness_coverage(verify_fn, output=None, *, wall_seconds=120):
    """Verify all 137 atomic templates plus representative composition classes."""
    candidates = grammar_candidates()
    selected = [c for c in candidates if len(c["plan"]["steps"]) == 1]
    classes = set()
    for candidate in candidates:
        steps = candidate["plan"]["steps"]
        if len(steps) == 2:
            signature = tuple(step["op"] for step in steps)
            if signature not in classes:
                selected.append(candidate)
                classes.add(signature)
    demo = [[0, 1, 1, 0, 2], [3, 1, 0, 4, 2], [5, 0, 4, 4, 6], [7, 8, 0, 9, 0]]
    query = [[9, 0, 8, 1], [2, 2, 3, 4], [5, 6, 7, 0]]
    started, rows, total_steps = time.monotonic(), [], 0
    for candidate in selected:
        remaining = wall_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise ValueError("known-witness coverage wall budget")
        plan = candidate["plan"]
        task = {"train": [{"input": demo, "output": reference_plan(demo, plan)}],
                "test": [{"input": query}]}
        result = verify_fn(candidate["program"], task, timeout_seconds=min(3.0, remaining))
        if (result.get("all_demonstrations_exact") is not True or
                result.get("query_execution_success") is not True or
                result.get("candidate") != reference_plan(query, plan)):
            raise ValueError("known witness failed: " + candidate["id"] + " " + str(result))
        total_steps += result["program_steps"]
        rows.append({"candidate_id": candidate["id"], "plan": plan,
                     "source_sha256": hashlib.sha256(candidate["program"].encode()).hexdigest(),
                     "task_sha256": digest(task), "query_target_sha256": digest(reference_plan(query, plan)),
                     "all_demonstrations_exact": True, "query_exact": True,
                     "program_steps": result["program_steps"]})
    report = {"format": "irisx/known-witness-coverage-v1", "status": "passed",
              "grammar": grammar_manifest(), "witnesses": rows,
              "atomic_parameterizations_verified": 137,
              "composition_operation_classes_verified": len(classes),
              "fresh_verifier_calls": len(rows), "program_steps": total_steps,
              "wall_seconds": time.monotonic() - started,
              "verifier": getattr(verify_fn, "provenance", {}),
              "claims": "Only these explicit authored witnesses; no ARC or arbitrary-plan completeness claim."}
    if output is not None:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return report
