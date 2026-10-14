# WSF-R5 bounded startup correction

Append ordinary commits to `fix/workstream-review-r1-r4-20261014` / Draft PR9,
based on reviewed delivery `1a08648603e1af2fe66998a0e53b11d02abf5c6b`
and code `15c1209c88ee54738595b92cf9d35c2f0d4a3177`. Base remains PR4.
The independent PR9 review passed the original R1–R4 within 31 normal and
31 optimized constant-only regressions; its sole new blocker is startup seed.

- WSF-R5: make seed0 effective at child interpreter startup while preserving
  source snapshot/binding, source-drift rejection, owning roots, no-user-site,
  unsafe-path protection and protected-before-import/no-training controls.
  Remove inherited PYTHON* settings, restore only explicit fixed allowlists,
  and test actual flags/hash against a fresh same-interpreter seed0 reference.
  Prove repeated child hashes, normal/-O and polluted PYTHONHOME/PYTHONPATH
  isolation; never hardcode a portable hash or log the whole environment.

Only necessary suite/distribution/onboarding callers and constant-only tests
change. Preserve original review/failed receipts and historical denials.
Revalidate seven public suites and formal non-editable wheel. Original audit
and aggregate remain BLOCKED/non-success and unexecuted. No training including
synthetic SGD, providers/Kaggle, model/evaluator/transfer downloads, frozen
runtime edits, research changes, merges, main/run008 updates or history/tag moves.
Stop at review_ready with new code/delivery SHA and a named handoff.
