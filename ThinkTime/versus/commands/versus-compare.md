---
description: "Benchmark two skills or two agents head-to-head on one fixture task and report a paired comparison"
argument-hint: "<candidate-a> <candidate-b> --fixture <id-or-path> [flags]"
---

Invoke the `versus` skill and follow it exactly.

Arguments forwarded: `$ARGUMENTS`

Before spending anything, run the same invocation with `--dry-run` appended and
show the user what it would do. A real comparison spawns N pairs of model runs.

If the user has not named a fixture, the shipped options are
`readonly-reviewer-diff-audit` (agent mode) and `spec-from-vague-issue` (skill
mode). Both resolve by id.

When reporting the outcome, state the verdict state by name and do not describe
`INCONCLUSIVE`, `DIRECTIONAL_HINT`, `TASK_TOO_HARD`, or `HARNESS_INVALID` as a
win. Note that neither shipped fixture has a `pass` calibration record yet, so
the overall verdict is downgraded to `INCONCLUSIVE` by design.
