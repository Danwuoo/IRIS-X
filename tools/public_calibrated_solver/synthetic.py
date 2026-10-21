"""Explicit CPU mechanics fixture, never an alternate public-model backend.

It emits a fixed, source-independent set of colored grids and calculates actual
causal FP32 token NLL tensors. No fixture outcome estimates 2B-model capability.
"""
import time

from tools.public_demo_calibration import core
from tools.public_sft141_diagnostic import contract, model_worker as base


class SyntheticBackend:
    max_context = 8192

    def __init__(self, plan, deadline, fault="none"):
        import torch
        torch.set_num_threads(1)
        self.torch, self.deadline, self.fault = torch, deadline, fault
        self.calls, self.generations = 0, 0
        self.specs = {tuple(contract.prompt_ids(p["train"], q["input"], v)): v
                      for p in plan["parents"] for q in p["test"] for v in range(8)}
        self.loo = {tuple(prompt): spec["view"] for spec, prompt, answer in core.cases(plan)}
        self.metadata = {"backend": "synthetic-cpu-tensor-mechanics-only", "model_load_count": 1,
                         "real_model_executed": False, "torch_version": torch.__version__}
        if fault == "load-fail":
            raise RuntimeError("synthetic load failure")

    def score(self, prompt, answer, deadline):
        assert deadline is self.deadline
        self.calls += 1
        if self.fault == "calibration-fail" and self.calls == 3:
            raise RuntimeError("synthetic calibration forward failure")
        started = time.monotonic()
        torch = self.torch
        # Every full answer target, including EOS, is scored at p-1+j.
        logits = torch.zeros((1, len(prompt) + len(answer) - 1, 16), dtype=torch.float32)
        view = self.loo.get(tuple(prompt), 0)
        strength = 3.0 if view in (6, 7) else .2
        for j, token in enumerate(answer):
            logits[0, len(prompt) - 1 + j, token] = strength
        nll = base.full_answer_nll(logits, len(prompt), answer)
        return {"nll": nll, "seconds": time.monotonic() - started,
                "answer_tokens": len(answer), "input_tokens": len(prompt) + len(answer) - 1,
                "batch_size": 1, "use_cache": False}

    def generate(self, prompt, ceiling, deadline):
        assert deadline is self.deadline and ceiling == contract.MAX_NEW_TOKENS
        self.generations += 1
        if self.fault == "generation-hang":
            time.sleep(120)
        if self.fault == "generation-fail" and self.generations == 6:
            raise RuntimeError("synthetic generation forward failure")
        view = self.specs[tuple(prompt)]
        grid = [[1 if view < 4 else 2 if view < 6 else 3]]
        tokens = contract.answer_ids(contract.transform(grid, view))
        if self.fault == "invalid-pool":
            tokens = [contract.EOS_ID]
        return {"token_ids": tokens, "generated_tokens": len(tokens),
                "seconds": .0001, "termination": "eos"}


def fixture_plan():
    """12 independent parent IDs, three two-query parents, no gold labels."""
    parents = []
    for i in range(12):
        task = f"synthetic{i:02d}"
        parents.append({"task_id": task, "selection": {},
            "train": [{"input": [[0, 1], [2, 3]], "output": [[1, 2], [3, 4]]},
                      {"input": [[4, 5], [6, 7]], "output": [[5, 6], [7, 8]]}],
            "test": [{"input": [[i % 10, (i + 1) % 10], [(i + 2) % 10, (i + 3) % 10]],
                      "test_index": j, "query_id": f"{task}:{j}"} for j in range(2 if i < 3 else 1)]})
    return {"schema": "iris-public-sft141-plan-v1", "provenance": {}, "protocol": {}, "parents": parents}
