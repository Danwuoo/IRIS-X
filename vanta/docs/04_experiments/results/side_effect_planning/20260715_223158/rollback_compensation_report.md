# Rollback And Compensation Report

Positive-control declaration rate: 1.0 (2/2)
Missing-declaration rejection rate: 1.0 (1/1)
Runtime `COMMITTABLE` execution count: 0
Runtime `IRREVERSIBLE` execution count: 0
Memory-write count: 0

The positive controls cover both `fixture_commit_restore` and
`fixture_commit_supersede`. Supersession is compensation, not strict
rollback. Neither path is executable in this pilot.
