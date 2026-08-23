# ARC Dataset and Toolkit Status v0

- **Version:** v0.1
- **Status:** Current operational snapshot
- **Snapshot date:** 2026-08-02
- **Scope:** Local ARC-AGI-1/2 datasets and ARC-AGI-3 Toolkit availability
- **Document role:** Record installation, inventory, configuration behavior, and smoke-test results. This is not a canonical data manifest, evaluator snapshot, formal run record, score record, or empirical adjudication.
- **Related evaluation specification:** [ARC Evaluation Definition v0](./ARC-Eval-Definition-v0.md)

---

## 1. Status summary

The local public ARC datasets and the ARC-AGI-3 Toolkit are usable for implementation work.

| Component | Operational status | Verified result |
|---|---|---|
| ARC-AGI-1 public data | Available | 400 training JSON files and 400 evaluation JSON files |
| ARC-AGI-2 public data | Available | 1,000 training JSON files and 120 evaluation JSON files |
| ARC-AGI-3 root Toolkit | Available | `uv sync`, `import arc_agi`, and `import arcengine` passed |
| ARC-AGI-3 local/offline mode | Available for bundled test environments | Two local test environments were discovered; reset and one legal action passed |
| ARC-AGI-3 remote environment discovery | Available with the configured root Toolkit `.env` | 25 environments returned on 2026-08-02 |
| ARC-AGI-3 Agents reference project | Available | `uv sync` and `import agents` passed |
| ARC-AGI-3 benchmarking reference project | Installed; remote authentication is configuration-scoped | Official `--list-games` exists; a child-project test without valid child authentication returned HTTP 401 |

This availability does **not** establish any `A1-*`, `A2-*`, or `A3-*` stage achievement. No formal benchmark, scorer validation, sealed/private evaluation, or model run was performed.

---

## 2. Local topology and inventory

All paths are repository-relative.

```text
data/
└── arc-datasets/
    ├── ARC-AGI-1/
    │   └── data/
    │       ├── training/       # 400 JSON files
    │       └── evaluation/     # 400 JSON files
    ├── ARC-AGI-2/
    │   └── data/
    │       ├── training/       # 1,000 JSON files
    │       └── evaluation/     # 120 JSON files
    └── ARC-AGI-3-toolkit/
        ├── arc_agi/
        ├── test_environment_files/
        ├── ARC-AGI-3-Agents/
        └── arc-agi-3-benchmarking/
```

The counts above are direct, non-recursive counts of `*.json` files in the four dataset directories. They match the public counts stated in ARC Evaluation Definition v0 for ARC-AGI-1 and the public portion of ARC-AGI-2.

### 2.1 What is not yet frozen

The checkout currently provides usable data, but the following formal substrate records are still absent or not evidenced:

- canonical repository commit or release pin for each dataset;
- file manifest and hashes;
- official parser/scorer/evaluator snapshot;
- contamination and development-query log;
- sealed-validation split and custodian;
- private or semi-private access record.

Therefore the correct state is **local data available; formal evaluation substrate not yet frozen**.

---

## 3. Tool and Python environment

Versions observed on 2026-08-01:

| Tool | Version |
|---|---|
| Git | `2.52.0.windows.1` |
| Python (`python`) | `3.12.10` |
| Python launcher (`py`) | `3.12.10` |
| uv | `0.11.3` |

### 3.1 Root Toolkit

The root `pyproject.toml` declares:

- distribution name: `arc-agi`;
- version: `0.9.9`;
- import package: `arc_agi`;
- required Python: `>=3.12`;
- required runtime dependency: `arcengine>=0.9.3`.

Executed successfully from `data/arc-datasets/ARC-AGI-3-toolkit`:

```powershell
uv sync
uv run python -c "import arc_agi; print('arc_agi import OK')"
uv run python -c "import arcengine; print('arcengine import OK')"
uv lock --check
```

`uv sync` updated the root `uv.lock` metadata from the stale local `arc-agi 0.9.8` entry to `0.9.9`, matching `pyproject.toml`.

### 3.2 Reference subprojects

`ARC-AGI-3-Agents`:

- project version `0.1.0`;
- `uv sync` passed;
- `import agents` passed;
- no `--list-games` or `--list-environments` CLI is implemented in the current `main.py`;
- normal agent execution can call model APIs and was not run during setup validation.

`arc-agi-3-benchmarking`:

- project version `0.1.0`;
- `uv sync` passed;
- official read-only list command: `uv run main.py --list-games`;
- a direct child-project test returned HTTP 401 when that process lacked valid ARC authentication;
- model benchmarks were not run.

---

## 4. Configuration and operation modes

The current root Toolkit source supports these operation modes:

| Mode | Behavior |
|---|---|
| `normal` | Discover local environments and query the ARC API |
| `online` | Use the ARC API only |
| `offline` | Use local environments only; no API discovery |
| `competition` | API/competition behavior and competition scoring restrictions |

The current root Toolkit reads these configuration fields:

- `ARC_API_KEY`
- `ARC_BASE_URL`
- `OPERATION_MODE`
- `ENVIRONMENTS_DIR`
- `RECORDINGS_DIR`

Constructor arguments take precedence in the documented cases. The root package loads `.env` and `.env.example` relative to the process working directory. Configuration files in the root Toolkit and its two child projects are therefore **working-directory scoped**; updating the root `.env` does not automatically configure a child process launched with a child directory as its working directory.

No API key value is recorded in this document. On 2026-08-02, a root Toolkit `Arcade()` call successfully loaded the root `.env` and returned the remote environment catalogue. This verifies effective configuration without disclosing the credential.

---

## 5. Available environments

### 5.1 Bundled local test environments

The default `environment_files` directory is absent in the root Toolkit checkout. The bundled `test_environment_files` directory contains:

- `bt11-fd9df0622a1a` — BT11
- `bt33-a7c3f9d18b4e` — BT33

These are local test fixtures, not a claim that the official public ARC-AGI-3 catalogue has been downloaded for offline competition use.

### 5.2 Remote catalogue snapshot

The configured root Toolkit returned 25 environments on 2026-08-02:

```text
g50t-5849a774  r11l-495a7899  sb26-7fbdac44  ar25-0c556536  su15-1944f8ab
cd82-fb555c5d  lf52-271a04aa  sk48-d8078629  ft09-0d8bbf25  dc22-fdcac232
ka59-38d34dbb  ls20-9607627b  bp35-0a0ad940  re86-8af5384d  lp85-305b61c3
tr87-cd924810  sc25-635fd71a  s5i5-18d95033  sp80-589a99af  tu93-0768757b
m0r0-492f87ba  vc33-5430563c  cn04-2fe56bfb  tn36-ef4dde99  wa30-ee6fef47
```

This is a time-indexed API discovery result. Availability, versions, and access scope may change. It is not an immutable competition snapshot.

---

## 6. Offline smoke test

The smoke test used explicit offline mode and the relative directory `test_environment_files`; it did not call an ARC API or a model API.

| Step | Result |
|---|---|
| Discover local environments | PASS — two environments |
| Create environment | PASS — `bt11-fd9df0622a1a` |
| Explicit reset | PASS — state `NOT_FINISHED` |
| Initial observation | PASS — two legal actions exposed |
| Execute at most one action | PASS — `ACTION3`, state remained `NOT_FINISHED` |
| Close | PASS with API limitation — `EnvironmentWrapper` exposes no `close()`; the local scorecard was closed successfully |

The test used `save_recording=False`. It did not modify ARC-AGI-1/2 data or run a benchmark.

---

## 7. Reproduction

From the repository root, the reusable Windows PowerShell check is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_arc_setup.ps1
```

The script:

- derives the project root from `$PSScriptRoot`;
- uses no machine-specific absolute path;
- does not print API keys;
- checks directories, JSON counts, tool versions, `uv sync`, imports, local environment discovery, reset, one action, and closure behavior;
- returns a non-zero exit code when a required check fails;
- passed under Windows PowerShell 5.1;
- was not executed under PowerShell 7 because `pwsh` was not installed on the test machine.

To verify remote discovery without printing credentials, run from the root Toolkit directory:

```powershell
uv run python -c "import logging; logging.disable(logging.CRITICAL); from arc_agi import Arcade; print([e.game_id for e in Arcade().get_environments()])"
```

---

## 8. Interpretation and status impact

### Source-stated

- Package names, version, dependencies, configuration variables, operation modes, and APIs are taken from the cloned root Toolkit README, `pyproject.toml`, `.env.example`, and source code.
- The expected ARC-AGI-1/2 public task counts are stated in ARC Evaluation Definition v0.

### Directly observed

- Directory presence and JSON counts;
- tool versions;
- environment synchronization and imports;
- local environment discovery and smoke-test behavior;
- remote environment catalogue returned after root `.env` configuration.

### Not established

- Dataset canonicality, integrity hashes, contamination status, or sealed/private status;
- evaluator correctness or scorer parity;
- any ARC score, baseline, superiority result, stage achievement, SOTA status, or winning hypothesis.

- **Empirical claim impact:** none.
- **ARC stage-status impact:** none.
- **Winning-hypothesis impact:** none.

---

## 9. Change log

| Date | Version | Change | Status impact |
|---|---|---|---|
| 2026-08-02 | v0.1 | Recorded local ARC-AGI-1/2 inventories, Toolkit installation, configuration behavior, local smoke test, and remote environment discovery. | Operational readiness only; no empirical or ARC stage-status change. |
