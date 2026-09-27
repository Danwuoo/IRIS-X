"""Arithmetic on RETAINED root logits, no model or counterfactual completion."""

import math

from .errors import ValidationError


def audit_root(observation, thresholds=(0.2, 0.1, 0.02)):
    root = observation["diagnostics"]["root"]
    log_probs = root["log_probs"]
    if (len(log_probs) != 16 or any(not math.isfinite(x) or x > 0 for x in log_probs) or
            not math.isclose(sum(math.exp(x) for x in log_probs), 1.0, abs_tol=1e-5)):
        raise ValidationError("retained_root_log_probs_invalid")
    if root["allowed_token_ids"] != list(range(10)):
        raise ValidationError("retained_root_grammar_differs")
    if any(not 0 < threshold < 1 for threshold in thresholds):
        raise ValidationError("root_threshold_invalid")
    best = max(range(10), key=lambda i: log_probs[i])
    mass = sum(math.exp(log_probs[i]) for i in range(10))
    return {"best_legal_token": best, "best_legal_probability": math.exp(log_probs[best]),
            "best_legal_nll": -log_probs[best], "legal_probability_mass": mass,
            "best_conditional_probability": math.exp(log_probs[best]) / mass,
            "thresholds": [{"cumulative_probability": threshold,
                            "max_nll": -math.log(threshold),
                            "root_survivors": [i for i in range(10) if -log_probs[i] < -math.log(threshold)]}
                           for threshold in thresholds],
            "claim": "root-edge arithmetic only; deeper logits and completion unknown"}
