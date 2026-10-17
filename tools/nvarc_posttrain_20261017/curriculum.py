"""Train-only exact-success allocation and bounded verified positive replay.

No new generator or ReArc model is used. Difficulty allocation changes only
which admitted training parent supplies the next reversible augmented LOO task.
"""
from __future__ import annotations

from collections import deque
import copy
import hashlib
import math
import random

from tools.arc2_goal_sprint_20261017.data import canonical


def exact_reward(predicted, target):
    from tools.arc2_goal_sprint_20261017.data import valid_grid
    if not valid_grid(target):
        raise ValueError("valid train-only target required")
    return float(valid_grid(predicted) and predicted == target)


class ExactCurriculum:
    """Half uniform exploration, half smoothed mixed-success prioritization."""
    def __init__(self, parent_ids, *, seed):
        self.ids = tuple(sorted(parent_ids))
        if not self.ids or len(set(self.ids)) != len(self.ids):
            raise ValueError("unique admitted training parents required")
        self.rng = random.Random(seed)
        self.stats = {key: [0, 0, 0] for key in self.ids}  # successes, samples, groups
        self.selections = 0

    def choose(self):
        self.selections += 1
        if self.selections % 2:
            return self.rng.choice(self.ids), "uniform-exploration"
        weights = []
        for key in self.ids:
            successes, samples, groups = self.stats[key]
            p = (successes + 1) / (samples + 2)
            weights.append(0.05 + 4 * p * (1 - p) + 1 / math.sqrt(groups + 1))
        return self.rng.choices(self.ids, weights=weights, k=1)[0], "exact-mixed-priority"

    def observe(self, parent_id, rewards):
        if (parent_id not in self.stats or not rewards
                or any(type(r) not in (int, float) or r not in (0, 1) for r in rewards)):
            raise ValueError("complete binary exact training rewards required")
        row = self.stats[parent_id]
        row[0] += sum(rewards)
        row[1] += len(rewards)
        row[2] += 1

    def report(self):
        return {"strategy": "half-uniform-half-smoothed-exact-mixed-v1", "selections": self.selections,
                "parents": len(self.ids), "parents_observed": sum(bool(s[2]) for s in self.stats.values()),
                "groups": sum(s[2] for s in self.stats.values()), "samples": sum(s[1] for s in self.stats.values()),
                "exact": sum(s[0] for s in self.stats.values()), "public_or_dev_feedback": False}


class PositiveReplay:
    """Parent-balanced verified token trajectories, never on-policy relabeling."""
    def __init__(self, parent_ids, *, per_parent=4, seed=0):
        if type(per_parent) is not int or not 1 <= per_parent <= 16:
            raise ValueError("bounded positive replay capacity required")
        self.allowed = frozenset(parent_ids)
        self.rows = {p: deque(maxlen=per_parent) for p in self.allowed}
        self.rng = random.Random(seed)
        self.admitted = self.rejected = 0

    def add(self, parent_id, trajectory, *, target, policy_digest, model_identity):
        from .codec import parse_completion
        if parent_id not in self.allowed:
            raise ValueError("positive replay parent is not admitted training")
        prompt_length = trajectory.get("prompt_length")
        ids = trajectory.get("input_ids", [])
        if type(prompt_length) is not int or not 0 < prompt_length < len(ids):
            raise ValueError("original prompt/completion boundary required")
        completion = ids[prompt_length:]
        if exact_reward(parse_completion(completion), target) != 1:
            self.rejected += 1
            return False
        if not isinstance(policy_digest, str) or not policy_digest or not model_identity:
            raise ValueError("verified positive policy/model lineage required")
        key = hashlib.sha256(canonical(ids)).hexdigest()
        if any(row["tokens_sha256"] == key for row in self.rows[parent_id]):
            return False
        self.rows[parent_id].append({"prompt_ids": list(ids[:prompt_length]), "completion_ids": list(completion),
            "demos_dropped": 0, "tokens_sha256": key, "parent_id": parent_id,
            "policy_digest": policy_digest, "model_identity": copy.deepcopy(model_identity),
            "verified_exact": True, "use": "separate-off-policy-supervised-replay"})
        self.admitted += 1
        return True

    def sample(self):
        available = sorted(p for p, rows in self.rows.items() if rows)
        return None if not available else copy.deepcopy(self.rng.choice(self.rows[self.rng.choice(available)]))

    def __len__(self):
        return sum(map(len, self.rows.values()))
