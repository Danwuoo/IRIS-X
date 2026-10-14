# Mutable ARC entry boundary

Read root AGENTS and docs/workstreams/arc-agi-2/STATUS.md and RESEARCH.md.
This package owns mutable parser/dispatch only. Shared CLI registers its parser
and passes the original repository root explicitly. Keep public names, arguments,
errors and exit codes compatible. Implementation imports occur only on dispatch.

Call the explicitly registered frozen flat ARC/Kaggle modules; do not create a
second solver, replace old paths with shims, move byte-bound files or edit their
manifests. See docs/verification/WSF-04/MIGRATION.md for consumers and limits.
New imports must pass tools/dependency_check.py. No direct line-b dependency.

This task permits synthetic/public CPU checks only. No model, evaluator inputs,
transfer archive, provider calls, training or new experiment. Preserve the
existing research question, results, limitations and current experiment. Keep
developer acceptance at review_ready until sourced independent review.
