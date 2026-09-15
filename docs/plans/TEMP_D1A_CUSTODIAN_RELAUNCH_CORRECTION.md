# TEMP — D1a Custodian Relaunch Correction

Status: **Owner-authorized / active**  
Date: **2026-09-15 Asia/Taipei**  
Starting repository SHA: **`8bafbe3c26c0b6ed9362906a8742fa005f6fa77a`**  
Frozen Task/Oracle SHA: **`2c8fe1cc4a34484e25f3f87907ec26d78bbc9c22`**

## Authority and scope

The owner explicitly authorized correction and continuation with exactly two
new `gpt-5.6-terra` / `high` custodian executions after TURN-B inspection found
that the first Authority-policy and Semantic-verifier processes exited without
producing bundles.

This correction authorizes only:

- one new Authority-policy custodian session (`b2`);
- one new Semantic-verifier custodian session (`c2`);
- fresh isolated external workspaces copied from the already sealed role
  disclosures;
- explicit Codex CLI `workspace-write` and `never` approval settings;
- `--ignore-rules` to prevent the local command policy from rejecting required
  deterministic SHA-256 and validation commands;
- exactly one immediate launch confirmation per process;
- a launch-only handoff and local repository commit.

The relaunch has zero additional retries, fallbacks, routes, escalations, model
judges, or subagents. Cumulative accounting must preserve the two failed first
attempts and add the two owner-authorized corrected executions.

## Preserved boundaries

The frozen Task/Oracle bundle, oracle labels, task contracts, disclosures, and
scientific interpretation remain unchanged. Each custodian receives only its
previously sealed disclosure set in a new external workspace. Neither session
may inspect the other workspace, launch another model, run D1b, perform D1
analysis, or author another custodian role.

This is a new owner-authorized correction scope. It does not retrospectively
reclassify the first failed executions as successful and does not establish
scientific qualification.

## Launch-only stop rule

After each corrected child receives one immediate launch confirmation, do not
poll, wait, inspect logs or output paths, validate child assets, or infer a
result. Record the factual corrected-launch metadata and stop. A later explicit
owner request is required for collection.
