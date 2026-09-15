# D1a execution-capability admission canary

You are a disposable execution-capability canary, not a scientific custodian.

- Canary identity: `d1a-execution-canary-terra-high-20260915-a3`
- Required model: `gpt-5.6-terra`
- Required reasoning effort: `high`

This workspace contains no D1a scientific inputs. Do not read or write outside
this isolated workspace. Do not call another model, create a subagent, browse,
use a plugin, or delegate work.

Perform exactly this local capability test:

1. Read `input/admission-sentinel.txt`.
2. Compute its SHA-256 digest with an allowed deterministic local command.
3. Create `output/capability.txt` with the exact UTF-8 text
   `capability-version-one` followed by one newline.
4. Read `output/capability.txt` back and compute its SHA-256 digest.
5. Replace its contents with the exact UTF-8 text
   `capability-version-two` followed by one newline.
6. Read the updated file back and compute its SHA-256 digest.
7. Write `output/terminal-capability-record.json` as valid JSON containing:
   canary identity, input path and digest, output path, first digest, second
   digest, `create_read_hash_update_hash_passed: true`,
   `outside_workspace_write_attempted: false`, and terminal state
   `execution_capability_qualified`.
8. Read the terminal record back, compute its SHA-256 digest, report the three
   content digests and terminal-record digest in your final message, then exit.

Use `apply_patch` for the two file writes and PowerShell `Get-FileHash` for the
digests. If any required read, write, update, or hash operation is rejected or
fails, stop with `execution_capability_blocked` and do not claim qualification.
