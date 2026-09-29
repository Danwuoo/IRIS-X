# Compact ABC 002 isolated public development score

This is a local, solver-isolated score of the frozen owner-Editor 002 result,
not a Kaggle score or a locked holdout. The result ZIP SHA-256 is
`965ac0622546efe2d2e996e925ab376f4e219e5657d705cbe45685e8e060f37e`.
The evaluator uses only `00576224`, `c9e6f938` and `0d3d703e` from the public
`arc-agi_training2_solutions.json` at NVARC source commit
`846d0198efa752534594e321fc3289fc0a06c657`, file SHA-256
`9f07a38bd25af5e83aa5bf85c5cb1a1fefdb30f6a755256fa65429e697ca97f9`.
Its paired challenge file SHA-256
`779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5`
equals the approved plan source binding. For each selected task, the solver
ZIP's exact public demonstrations and one visible test input equal that source;
the solver-visible test has no output field. Each selected source task has
exactly one test output. The solution file was read only by
`tools/score_nvarc_abc_002_dev.py`, never by the notebook or solver.

| Arm | pass@1 | pass@2 | Candidate-pool oracle coverage | Calls | Verifications |
| --- | ---: | ---: | ---: | ---: | ---: |
| A, compact base | 1/3 | 1/3 | 1/3 | 6 | 11 |
| B, eight-step SFT pilot | 0/3 | 0/3 | 0/3 | 6 | 12 |
| C, SFT plus one-step TTT | 0/3 | 0/3 | 0/3 | 6 | 12 |

Only A's top candidate for `00576224` is correct. Its other two task pools
miss the answer. All six B/C task pools miss the answer despite legal output
shape and 3–4 retained candidates each. Thus this tiny diagnostic exposes a
candidate-content/coverage problem; it does not show an instance where the
right candidate was present but misranked. The three parents have been
repeatedly examined, including `00576224` before 002. They are tuning data,
not a fresh generalization test. The observed 1/3 versus 0/3 differences are
too small and selected to establish a general SFT or TTT effect. The SFT
export is only an eight-step, 2,578-token pilot.

The exact local machine-readable score is retained at
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-002-dev-score.json`.
That output contains metrics and source hashes, without answer grids.
