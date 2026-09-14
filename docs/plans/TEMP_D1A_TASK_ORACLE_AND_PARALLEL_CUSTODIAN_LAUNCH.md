# TEMP — D1a Task/Oracle Authoring and Parallel Independent Custodian Launch

Status: **Owner-authorized / not started**  
Date: **2026-09-14 Asia/Taipei**  
Repository: **Danwuoo/IRIS-X**  
Required scientific baseline `main`: **`8fc21d5190b5f2ee8d6f2d60d10b69050ccb490e`**  
Primary coordinating session: **one continuous GPT-5.6 Sol / High reasoning session**  
Follow-on independent custodian sessions: **exactly two Codex CLI background sessions, each `gpt-5.6-terra` / `high`, only after Task/Oracle admission**  
Follow-on model-session ceiling: **maximum 2 total; 0 retries; 0 fallback; 0 escalation**  
Phase authority: **none; this plan does not create Phase 7**  
D1b authority: **none**  
Hard terminal boundary: **after each child launch receives exactly one immediate launch confirmation and the launch handoff is recorded, STOP; do not monitor, wait, tail, collect, inspect, or interpret either child session**

---

## 1. Purpose

The D1a qualification substrate is now implementation-ready and correctly reports
`ready_for_independent_custodians`. The next useful work is not another substrate
review. It is to create the first real sealed independent assets while preserving
the information barriers required for D1 identification.

This plan authorizes one Sol High session to:

1. act as the **Task/Oracle custodian** and author the first real sealed
   `task_oracle` bundle;
2. freeze that bundle before any authority-policy or semantic-verifier output
   exists;
3. create role-specific, minimum-necessary disclosure workspaces for two new
   independent custodians;
4. launch exactly two new Codex CLI sessions in the background:
   - one **Authority-policy custodian**;
   - one **Semantic-verifier custodian**;
5. perform exactly one immediate launch confirmation for each process;
6. record only factual launch metadata and **STOP**.

This turn does not collect either child result. Collection is a separate
owner-requested turn.

The governing principle is:

> **Author and seal Task/Oracle first; disclose only role-permitted frozen
> surfaces; launch the two independent custodians; then stop without observing
> their work.**

---

## 2. Current scientific state that must remain unchanged

The task starts from the D1a substrate state recorded at
`8fc21d5190b5f2ee8d6f2d60d10b69050ccb490e`.

Preserve all of the following:

- F1-A is supported only within bounded prior fixtures.
- F1-B incremental decision value remains `inferred` / independently
  `Not established`.
- F1-C, F1-D, and F1-E remain `Not established`.
- wider novelty remains `novelty_not_established`.
- D1a meta-qualification is instrument behavior only, not empirical evidence.
- D1b is not specified, frozen, launched, or authorized.
- historical Phase 6 evidence and zero direct capability-gate triggers remain
  unchanged.
- no child-custodian output may be interpreted in this turn.

The known minor substrate-hardening observations from later review are
**non-blocking**. Do not spend this task renaming states, redesigning schemas, or
adding general infrastructure unless a concrete defect prevents a valid
Task/Oracle bundle or safe child launch. If such a defect is material, stop with
`needs_revision` rather than widening scope.

---

## 3. Required starting checks

Before substantive work:

1. read every applicable `AGENTS.md`;
2. inspect:
   - `git status --short`;
   - `git rev-parse HEAD`;
   - `git rev-parse origin/main`;
   - `git rev-list --left-right --count origin/main...main`;
3. verify the starting repository is exactly, or is a clean descendant of,
   `8fc21d5190b5f2ee8d6f2d60d10b69050ccb490e`;
4. verify no unrelated owner work will be overwritten;
5. read only the Task/Oracle-relevant scientific and contract surfaces needed
   before authoring:
   - `experiments/AGENTS.md`;
   - `research/AGENTS.md`;
   - `docs/d1a-independent-asset-preparation-handoff.md`;
   - `experiments/d1a-warrant-discrimination-v0/README.md`;
   - `experiments/d1a-warrant-discrimination-v0/custodian-packets/task-oracle-custodian.md`;
   - `experiments/d1a-warrant-discrimination-v0/submission-schemas/task-oracle-bundle.schema.json`;
   - `experiments/d1a-warrant-discrimination-v0/submission-schemas/custodian-attestation.schema.json`;
   - `experiments/d1a-warrant-discrimination-v0/definition/provenance-contract.json`;
   - Task/Oracle-relevant portions of `definition/role-boundaries.json`;
6. do **not** inspect `meta-fixtures/`, real future perturbation assignments,
   comparator outputs, authority-policy outputs, or semantic-verifier outputs
   while authoring the Task/Oracle bundle.

The coordinating session may know that later custodians exist. It may not use
future authority/verifier content to shape held-out truth or oracle rules.

If the starting authority is materially inconsistent, stop with
`authority_drift_blocked`.

---

## 4. Task/Oracle authorship requirements

The primary Sol High session is the sole Task/Oracle authoring session for this
turn. It must create a real bundle under a new directory outside `meta-fixtures/`
and conform to the frozen Task/Oracle schema.

At minimum, the bundle must contain two bounded task families with:

- stable task-family and instance IDs;
- explicit task contracts;
- permitted initial-state observations;
- deterministic or independently adjudicable `actual_outcome` rules;
- explicit post-state rules;
- stable content digests;
- task truth separate from any later authorization judgment;
- no dependency on evidence/authority perturbation assignment;
- no dependency on future comparator policy decisions;
- no dependency on held-out producer outputs.

One family should be a bounded semantic-result task suitable for independent
semantic verification.

One family should expose a **reversible but consequential action boundary** so a
later study can test bounded F1-D without making authority itself the factual
oracle. The Task/Oracle author defines factual preconditions and post-state
success/failure only. It must not define who is authorized to act.

Do not optimize tasks to make R4/F1 win. The Task/Oracle author must not read or
instantiate future evidence/authority perturbation assignments.

---

## 5. Task/Oracle sealing and admission gate

Before any child model launch:

1. validate the Task/Oracle bundle with the existing D1a submission validator;
2. verify all asset digests;
3. freeze and seal the canonical manifest;
4. verify no post-seal mutation;
5. run focused deterministic tests relevant to the new bundle;
6. commit the sealed Task/Oracle assets and all disclosure manifests described
   below;
7. record the freeze commit SHA.

Child launch is permitted only when the bundle is not `rejected` and the seal,
schema, provenance, and information-boundary checks needed for use as a frozen
input pass.

Do not require this turn to prove universal scientific independence. Preserve
any distinction between admission evidence and final D1 scientific adjudication.

After the Task/Oracle seal, **never modify its task contracts, oracle rules,
held-out instances, or post-state truth because of anything the child sessions
later produce**. Any future change requires a new version and restarts the
relevant independence chain.

---

## 6. Role-specific disclosure manifests

Before launching children, create two immutable disclosure manifests that list
**exactly** what each child may read.

### 6.1 Authority-policy disclosure

The Authority custodian may receive only material needed to define an ex ante
policy, including as applicable:

- public task/institutional rules;
- legitimate principal/role vocabulary;
- proposition classes;
- action classes;
- public task contract portions needed to know what may be authorized;
- its own custodian packet, schema, base attestation schema, and provenance
  contract.

It must not receive:

- realized task correctness;
- held-out oracle labels;
- post-state outcome labels not required to understand action classes;
- semantic-verifier implementation or outputs;
- perturbation assignments;
- policy scores;
- comparator decisions;
- analysis outputs.

### 6.2 Semantic-verifier disclosure

The Semantic-verifier custodian may receive only:

- public task semantics;
- input/output contracts;
- permitted task observations;
- enough non-held-out development material for verifier development, or
  permission to create its own disjoint development material from the public
  contract;
- its own custodian packet, schema, base attestation schema, and provenance
  contract.

It must not receive:

- held-out oracle labels;
- authority maps or authority-policy outputs;
- evidence/authority perturbation assignments;
- comparator outputs;
- analysis outputs.

Both manifests must contain paths/digests and must be frozen before launch.

---

## 7. Isolated child workspaces

The two child sessions must not share a writable workspace and must not be
launched in the full IRIS-X repository tree.

Create two separate external working directories outside the repository, for
example under a session-specific temporary or owner-local run root:

```text
<external-root>/authority-custodian/
<external-root>/semantic-verifier-custodian/
```

Populate each workspace only with:

- the role's frozen disclosure-manifest files;
- the role's custodian packet;
- the role-specific submission schema;
- the shared base attestation/provenance material required to construct a valid
  bundle;
- a minimal local validation helper or copied validator subset if needed;
- the child prompt frozen before launch.

Do not include the other child's workspace or output path in the readable input
set.

Do not include the full repository merely for convenience.

Child outputs are written only inside that child's external workspace during
TURN A. They are not imported into the repository in this turn.

---

## 8. Child-session identities and model configuration

This plan authorizes exactly two follow-on model sessions, both through Codex
CLI:

### Child B — Authority-policy custodian

```text
model: gpt-5.6-terra
reasoning_effort: high
role: authority_policy
session: new independent Codex CLI process
retries: 0
fallback: 0
network/web research: not required; keep disabled unless unavoidable for local CLI operation
```

### Child C — Semantic-verifier custodian

```text
model: gpt-5.6-terra
reasoning_effort: high
role: semantic_verifier
session: separate new independent Codex CLI process
retries: 0
fallback: 0
network/web research: not required; keep disabled unless unavoidable for local CLI operation
```

The repository accepted Codex baseline identifies `gpt-5.6-terra` as the strong
role. This task overrides its default reasoning effort from `medium` to `high`
for these two bounded custodian sessions. The exact local CLI command and config
must be preflighted before launch; do not silently substitute another model,
provider, reasoning effort, or execution surface.

Using the same model family does not establish statistical independence of model
failure modes. The scientific independence claim here is limited to separate
authoring sessions, separated visible inputs, separate workspaces, and frozen
provenance. Record same-model correlated-failure risk as a limitation for later
analysis.

---

## 9. Child prompt contract

The primary session must create two compact child prompts from the frozen role
contracts. The prompts must not contain the parent session's chain of thought,
research interpretation, expected answer, or a summary of the other role.

Each child prompt must state:

- exact role;
- exact allowed input manifest;
- exact prohibited information;
- exact output schema/bundle requirements;
- requirement to seal its bundle;
- prohibition on editing upstream Task/Oracle assets;
- prohibition on authoring the other role;
- prohibition on D1 interpretation;
- prohibition on model/provider subcalls or follow-on sessions;
- required terminal handoff inside its own isolated workspace.

The Authority prompt must not describe expected semantic-verifier behavior.
The Verifier prompt must not describe the authority policy or expected authority
cases.

Freeze and hash both prompts before launch.

---

## 10. Codex CLI preflight

Before either child launch, perform only deterministic/local preflight:

- resolve the Codex CLI executable;
- record `codex --version`;
- verify the accepted provider/model baseline identity;
- verify the intended model is exactly `gpt-5.6-terra`;
- verify `model_reasoning_effort="high"` is accepted by the current local
  admission/config path;
- verify authentication/billing mode without sending a test prompt if the
  existing admission tooling allows it;
- freeze sandbox/approval settings;
- verify each child has a distinct authoring-session ID;
- verify prompt digest, workspace path, stdout path, stderr path, and output
  bundle target path;
- verify the main repository tree is clean at the freeze SHA.

A provider reachability prompt is not authorized as a preflight call.

If exact configuration cannot be admitted locally, return `launch_blocked`.
Do not fall back to Luna, another Terra setting, another provider, or retry.

---

## 11. TURN A — launch-only protocol

After all admission gates pass, launch the child processes in the background via
Codex CLI using the frozen prompts and isolated workspaces.

For each child:

1. redirect stdout and stderr to fixed external paths outside the repository;
2. launch exactly once;
3. record:
   - role;
   - model/provider identity;
   - reasoning effort;
   - Codex CLI version/path;
   - prompt path/digest;
   - workspace path;
   - expected output bundle path;
   - freeze SHA;
   - Task/Oracle bundle ID/digest;
   - launch timestamp;
   - PID if available;
   - stdout/stderr paths;
4. perform exactly **one immediate launch confirmation** solely to determine
   whether process creation was attempted and whether it had already exited at
   that immediate observation;
5. do not read stdout, stderr, bundle files, or terminal result.

Launch the two children as separate processes. They may run concurrently.

The parent may launch Child C after Child B without checking Child B again.
Launching the second child is not permission to monitor the first.

---

## 12. Absolute no-monitoring rule after launch

After the one immediate confirmation for a child, the parent session must not:

- poll that process;
- call process-status APIs again;
- wait on it;
- sleep and recheck;
- tail stdout or stderr;
- read partial or complete child output;
- inspect the child's output directory for completion;
- watch file sizes or timestamps;
- infer success from filesystem changes;
- run validation against child output;
- collect the bundle;
- summarize or interpret child content;
- restart or retry the child.

This remains true even if the child appears to have exited immediately.

If one child launch succeeds and the other launch is blocked or fails at the
single immediate observation, record `partial_launch_stop`; do not inspect the
successful child's output and do not retry either side.

---

## 13. Launch handoff

After both launch attempts and their one allowed immediate confirmations, create
a compact durable handoff:

`docs/d1a-parallel-custodian-launch-handoff.md`

It may contain only:

- starting SHA and freeze SHA;
- Task/Oracle bundle ID/digest and validation status;
- disclosure-manifest IDs/digests;
- child role, model, reasoning effort, authoring-session ID;
- external workspace and log paths;
- child prompt digests;
- launch timestamp and PID if available;
- immediate launch state only;
- exact call count;
- explicit statement that outputs were not monitored or collected;
- next required owner action: explicit TURN-B collection authorization.

The handoff must not contain child results.

Commit the launch handoff if doing so does not require reading child output.
Then STOP.

---

## 14. Execution ceilings

This plan authorizes:

```text
primary Sol High coordinating session: 1 (the current owner-started session)
follow-on Codex CLI child sessions: maximum 2
child Authority model: gpt-5.6-terra / high
child Semantic-Verifier model: gpt-5.6-terra / high
child retries: 0
child fallbacks: 0
child routes: 0
child escalations: 0
child model judges: 0
child subagents/follow-on model tasks: 0
D1b producer executions: 0
```

The two child launches are the only repository-initiated model executions
allowed by this plan.

---

## 15. Prohibited scope expansion

Do not:

- create Phase 7;
- create or launch D1b;
- modify F1-B/C/D/E status;
- revise the D1 interpretation matrix;
- redesign the D1a substrate for convenience;
- author the Authority policy in the parent session;
- author the Semantic verifier in the parent session;
- let either child author the other child's bundle;
- import child results during TURN A;
- run calibration or analysis;
- generate producer held-out outputs;
- use child results to edit the sealed Task/Oracle bundle;
- start a third model session to review or repair the children.

---

## 16. Terminal states

End with exactly one primary terminal state.

### `custodians_launched_stop`

Use when:

- Task/Oracle bundle is sealed and admissible for frozen use;
- both child prompts/disclosures are frozen;
- both Codex CLI child launches were attempted exactly once;
- each received exactly one immediate confirmation;
- no child output was inspected;
- launch handoff was recorded.

Then STOP.

### `partial_launch_stop`

Use when Task/Oracle is sealed but only one child could be launched under the
frozen exact configuration. Record facts and STOP. No retry.

### `task_oracle_needs_revision`

Use when a valid sealed Task/Oracle bundle cannot be produced without violating
its information boundary.

No child launch is allowed.

### `launch_blocked`

Use when Task/Oracle is frozen but exact child Codex/model/config admission cannot
be established before launch.

No fallback is allowed.

### `authority_drift_blocked`

Use when repository authority drift prevents safe continuation.

---

## 17. TURN B is explicitly outside this plan's active turn

A later owner-requested collection task may:

- inspect whether child processes completed;
- collect stdout/stderr and sealed child bundles;
- validate provenance and boundaries;
- import admitted bundles into the repository;
- decide whether calibration/analysis can proceed.

None of that is authorized in TURN A.

The child processes may continue after this session ends.

---

## 18. Final response format

The primary session final response must be factual and short:

- terminal state;
- Task/Oracle bundle ID/digest;
- freeze commit SHA;
- Authority child: model/effort/PID/immediate launch state;
- Verifier child: model/effort/PID/immediate launch state;
- repository-initiated child call count;
- confirmation that no monitoring or collection occurred;
- path to `docs/d1a-parallel-custodian-launch-handoff.md`;
- explicit next action: owner must initiate a separate TURN-B collection task.

Do not report child results because they must not have been observed.
