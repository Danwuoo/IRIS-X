# Task record template

Copy this shape into a newly named JSON file under docs/management/tasks/;
replace each example value with the actual bounded task. This Markdown template
is not itself an executable task record. Register the actual plan document
before referring to its catalog ID. Acceptance IDs must exist in that plan.

```json
{
  "format": "irisx.task.v1",
  "id": "EXAMPLE-01",
  "title": "One concrete engineering outcome",
  "workstream": "line-b",
  "state": "planned",
  "depends_on": [],
  "owner_role": "developer",
  "plan_ref": "example-plan",
  "scope_paths": ["src/irisx/domains/line_b/example.py", "tests/line_b/test_example.py"],
  "base_branch": "refactor/workstream-pr3-validation",
  "head_branch": "example/local-task",
  "base_commit": null,
  "implementation_commit": null,
  "acceptance": ["EX1-1"],
  "blockers": [],
  "handoff_ref": null,
  "verification_refs": [],
  "review_refs": [],
  "concurrency_group": null
}
```

Use full 40-character Git SHAs when known and null while not yet created. Put
commands and test observations in a named report, not executable task fields.
Document references use catalog IDs. Concurrent in_progress tasks in the same
non-null concurrency_group must have non-overlapping writable scopes. A blocked
task requires concrete blockers. review_ready requires the previously committed
implementation SHA and registered handoff. verified additionally requires an
independent review bound to that implementation SHA.
