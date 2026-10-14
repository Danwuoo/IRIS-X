# line-b synthetic engineering loop

The real second-line domain is unassigned. This six-case label workload is
synthetic, engineering-only and non-deployable. It demonstrates specification,
baseline/candidate evaluation, selection and package verification using the
unchanged P1 qualification profile, with no model or external calls.

```sh
python -m irisx.domains.line_b.flow --output .irisx/line-b/example-001
python -m irisx.domains.line_b.flow --output .irisx/line-b/example-unmet --variant unmet
python -m irisx.domains.line_b.flow --output .irisx/line-b/example-missing --variant missing
```

Use the installed product or an explicitly selected source checkout. Every
output must be new. `prepare(output, variant='candidate')` creates the independent
contract graph; `run(output, variant='candidate')` completes the whole loop under
`fixture/`, `run/` and, only after an eligible decision, `package/`.

Six independent cases use accept/reject/defer labels, two segments and two
critical cases. The reject-all baseline has accuracy 2/6 and one critical miss;
the bounded candidate table has 6/6. The synthetic requirements are accuracy
at least 5/6 and no critical failures. These are scaffold requirements, not a
customer-domain acceptance standard. The `unmet` variant records an infeasible
decision and creates no package. `missing` omits its own generated candidate
component and fails closed. CLI exit 0 means the engineering operation closed;
inspect `outcome` and `package_created`. Missing evidence returns exit 2.

Domain, source collection, cases, evaluator, requirements, configurations,
trial, result, decision, verdicts, run summary and manifest IDs are line-b-owned.
The adapter directly uses common contract constructors, `fixture.run_trial`,
`engine.select_configuration`, and `package.build_package/verify_package`.
It supplies a new six-case workload; it does not rename or import an ARC solver.

The shared P1 verifier requires the exact logical IDs
`qualification-deployment-placeholder` and `qualification-known-limitations`.
Those two IDs remain fixed profile exceptions. Their payload/digests bind the
line-b configuration and limitations; the scaffold changes no public contract.
The placeholder continues to declare `deployable: false`. The new line-b
manifest retains that profile and has its own ID.

Focused source tests are `python -B tests/line_b/test_flow.py` and the same
command with `-O`. They include negative evidence/package controls, byte
reproduction, blocked ARC/ML imports and simultaneous core/line-b processes.
These CPU results establish engineering behavior only; they establish no
domain efficacy, ARC/GPU success or independent acceptance.
