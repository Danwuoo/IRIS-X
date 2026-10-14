# ARC2 offline continuation: paused development checkpoint

Source baseline: `cc14bd1a79aac1fe6135017c9e09d4834300675d` on
`feat/run008-native-research-20261013`. Work belongs only to
`feat/arc2-sft-rl-continuation-20261014`; the engineering/management branch and
main are separate. All pre-existing tracked source bytes remain unchanged.

## Status: incomplete, not accepted for operational use

Development was paused on 2026-10-14 for a research-first review of methods,
agent architectures and RL alternatives. These new modules are preserved as
unfinished work, not a finished handoff or an execution-ready release.

- `prepare.py` reads five pinned public source files as bytes/data and constructs
  an inert description of the existing SFT256 / fixed-batch RL / whole-wall
  matched extra-SFT experiment. It performs no model, provider or Git operation.
- `analysis.py` interprets existing compact consumer reports as untrusted JSON.
  It never authenticates collection, reads evaluator targets, creates a score,
  establishes method efficacy or authorizes another run. Conditional hitset
  differences do not prove a common full case universe. The compact report also
  does not prove the 120-task PUBLIC universe merely by declaring 167 queries.
- `io.py` and `cli.py` are incomplete integration scaffolding. Do not use their
  output as a release or admission artifact.

Independent checkpoint review found a parent-directory race in `write_new_json`:
replacing an ancestor between its path check and publication can redirect output
and leak a temporary file. Descriptor-relative no-follow publication and an
adversarial regression test are pending. Input path race coverage and full
integration review are also pending. A huge-integer analysis overflow was fixed
by the analysis author and covered by a focused test, but independent final
retest is pending. Preparation's portable-platform test handling and explicit
JSON float-overflow rejection remain follow-ups; preparation currently requires
POSIX descriptor-relative no-follow file operations.

Focused author checks at this pause: preparation 28 normal / 28 optimized;
analysis 38 normal / 38 optimized; I/O 17 normal / 17 optimized (independently
rerun). These synthetic tests do not establish real GPU, scoring, secure output
publication or full integration success. Do not treat them as a release pass.
A public-source baseline full suite had 1583 tests, 6 failures, 41 errors and
74 skips in this fresh environment. Repository layout separately reports the
same seven README findings. These unrelated failures are not repaired here;
no final matched full-suite comparison has yet run.

No Kaggle access, authentication, dataset/notebook mutation, training launch,
new clock, paid resource or competition submission is performed or authorized
by these tools. Publication/execution remains a separate local-executor role.
Never import these modules into the frozen producer or change a frozen pin to
make an observed failure pass. Resume implementation only after the research
priority and scope are reconciled.
