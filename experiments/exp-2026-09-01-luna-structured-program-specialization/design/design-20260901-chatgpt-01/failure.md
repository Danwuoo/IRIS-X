# H-P1a design attempt blocker

Status: **Incomplete — blocked before candidate formation**

Run `design-20260901-chatgpt-01` preserved 26 one-shot formal invocation
attempts under definition/code commit
`746932b070b9f76d85902d86a16d9845a6a680ad`:

- 24/24 Luna seed DEV attempts terminated with provider
  `invalid_json_schema` before output because the frozen shared schema used
  top-level `allOf`, which the active structured-output surface rejected;
- `opt-01-r01` and `opt-02-r01` each terminated once with provider
  `invalid_json_schema` because the frozen optimizer schema's
  `schema_version` property used `const` without an explicit `type`;
- no candidate output was returned or frozen;
- no optimizer-generated candidate was eligible;
- no validation call occurred;
- no tool attempt, retry, recovery, routing, escalation, subscription-limit
  event, API-key fallback, or billing-mode change occurred.

All 26 terminal records use canonical `failure` / `sufficient` semantics.
Raw JSON events and stderr are retained under their original invocation
identities. Provider monetary cost remains `Unknown`.

Under the controlling plan, the seed cannot substitute for C1, unused calls
cannot become replacement calls, and blind data cannot be generated. H-P1a
has no substantive result from this attempt and Phase 4 cannot close from it.
A corrected schema requires a new full definition/code commit and a separately
authorized new run/resource ceiling; this attempt must not be overwritten.
