# First Real-Domain P2 Admission Package

Status: **admission-blocked**

This directory is the owner decision package required by Decision 0003. It is
not an Engineering Trial, contains no real workload or result, and authorizes no
execution.

## Readiness finding

Repository authority permits P2 admission preparation, but no current artifact
selects or approves the following inputs. Each remains `Unknown` in
[`admission.json`](admission.json):

1. a bounded real domain and representative frozen workload;
2. source provenance, ownership, permitted uses, retention, and sensitivity;
3. the baseline configuration;
4. the candidate specialization intervention;
5. the evaluator, hard requirements, acceptance thresholds, and resource
   measures;
6. whether external execution is needed and authorized;
7. any provider/model and maximum budget; and
8. the deployment target and operational constraints.

Because these are inputs to the product question rather than implementation
details, the repository must not infer them. The P1 synthetic fixture does not
resolve any gate.

## One owner choice

Choose exactly one path:

1. **Local/offline real domain.** Supply or approve the real domain/workload,
   rights and provenance, baseline, intervention, evaluator and thresholds, and
   deployment target. Provider/model and external-execution gates are then
   explicitly marked not required; paid budget is exactly USD 0.
2. **Authorized external provider.** Supply everything above plus the exact
   provider/model, permitted data classes, maximum USD budget, retention
   behavior, credentials boundary, and external-execution stop conditions.
3. **Defer P2.** Keep the admission block and do not create or run a real trial.

These options are mutually exclusive for the first trial. Selecting the local
path does not implicitly approve later external execution; selecting the
external path does not approve any unnamed provider, model, data class, or
spend.

## Draft trial contract and intended directory

The `trial_draft` in `admission.json` maps every field needed by the existing
`irisx/engineering-trial` contract. It sets `qualification_fixture` to false,
requires real evidence, reserves `trials/first-real-domain/`, and marks every
unresolved artifact reference as `Unknown` rather than inventing a digest.

Once separately admitted, the real trial directory is expected to contain at
least:

```text
trials/first-real-domain/
├── README.md
├── specification.json
├── workload.json
├── requirements.json
├── evaluator.json
├── cases.json or authorized source bindings
├── baseline.json
├── candidate.json
├── components/
├── trial.json
├── results/
├── decision.json
└── package/ or an exact retained package reference
```

The actual source-material layout, retention, and package form must follow the
later authorization and the data policy; this draft tree is not permission to
commit sensitive or erasable data.

## Acceptance and falsification

Promotion requires real authorized evidence, baseline and candidate results on
the same frozen workload and evaluator, satisfaction of every hard requirement,
complete resource-use accounting, deterministic selection, and independent
Domain Package verification.

The trial is falsified or stopped by an unrepresentative workload, missing
rights/provenance, synthetic evidence presented as real, unauthorized external
activity, an unnamed or unapproved provider/model/budget, stale references,
failure of any hard requirement, or non-reproducible selection/package output.
Failures are retained as decision evidence; they are not rewritten into a
promotion.

## Validation

From the repository root:

```powershell
python -m irisx admission validate trials/p2-admission/admission.json
```

Success means the blocked snapshot is internally consistent and bound to the
current authority files. It does not make P2 execution, promotion, or a Domain
Package eligible.
