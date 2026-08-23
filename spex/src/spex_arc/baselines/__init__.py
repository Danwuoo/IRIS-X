"""Development-only ARC-AGI-1 G0/S1 configuration and comparison helpers."""

from .arc_a1 import (
    BaselineConfiguration,
    BaselineSolverFactory,
    BudgetTierMultipliers,
    CalibrationObservation,
    PairedTaskComparison,
    derive_budget_proposal,
    load_calibration_observation,
    paired_precondition_failures,
    run_baseline,
    summarize_paired_task_comparison,
)

__all__ = [
    "BaselineConfiguration",
    "BaselineSolverFactory",
    "BudgetTierMultipliers",
    "CalibrationObservation",
    "PairedTaskComparison",
    "derive_budget_proposal",
    "load_calibration_observation",
    "paired_precondition_failures",
    "run_baseline",
    "summarize_paired_task_comparison",
]
