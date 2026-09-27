---
name: versus
description: Benchmark two skills or two agents head-to-head on one fixture task, N paired runs in isolated worktrees. User-invoked; use to choose between two candidates on evidence, not impression.
---

# versus

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Spawns real agent and worktree runs, and costs money** — always pass
> `--dry-run` first to preview every worktree, command, and env key before
> anything is spent.

Benchmarks two skills or two agents head-to-head on one fixture task, running N
paired comparisons in isolated git worktrees and reporting correctness,
constraint adherence, cost, and blind preference as separate, unblended results.
Use it to choose between two competing designs on evidence rather than
impression — not for scoring a single candidate in isolation.

| Option | Values | Default | Effect |
|---|---|---|---|
| `run <candidate-a> <candidate-b>` | skill/agent ids or paths | — | Runs N paired comparisons between the two candidates |
| `--fixture <id-or-path>` | fixture id or path | — | Selects the task fixture (shipped: `readonly-reviewer-diff-audit`, `spec-from-vague-issue`) |
| `--quick` | flag | off | Caps the run at 3 pairs; verdict capped at `DIRECTIONAL_HINT`, never a full win |
| `--dry-run` | flag | off | Prints worktrees/commands/env without spawning anything — run this first |
| `report` | — | — | Re-renders a past comparison's `report.md`/`report.json` |
| `verify-fixture` | — | — | Discrimination gate to run before trusting a new fixture |
| `clean` / `gc` | — | — | Lists or removes old comparisons |

Head-to-head benchmarking for Claude Code skills and agents. Two candidates, one
fixture task, N paired runs in isolated git worktrees, and a report that says who
was correct, who stayed inside its declared constraints, who was cheaper, and
which one a blind judge preferred — each reported separately, never blended into
one score.

Full reference — every flag, the fixture format, the safety model, and the
statistics: [`../../README.md`](../../README.md).

## When to use this

- Choosing between two competing skill or agent designs, where "it feels better"
  is not good enough.
- Checking whether a rewrite actually improved anything, against the version it
  replaced.
- Validating that a constraint a candidate *claims* to respect (read-only,
  no-network, output-only-to-X) is actually respected, using the verified audit
  log rather than the candidate's own account of itself.

**Not** for benchmarking a single candidate — there is no absolute score here,
only paired comparison. Compare two of the *same kind*: skill-vs-skill or
agent-vs-agent.

## Running it

`versus` is a Python CLI. Run it from its own directory:

```bash
cd ThinkTime/versus
python3 scripts/cli.py run <candidate-a> <candidate-b> --fixture <id-or-path> --quick
```

Both shipped fixtures resolve by id: `readonly-reviewer-diff-audit` (agent mode)
and `spec-from-vague-issue` (skill mode).

**Always `--dry-run` first.** It prints every worktree path, command line, and
environment key the run would use, and spawns nothing. This costs money
otherwise.

Four subcommands: `run` (the comparison), `report` (re-render a past comparison),
`verify-fixture` (the discrimination gate — run it before trusting a new
fixture), and `clean`/`gc` (list or remove old comparisons).

## Reading the result

Read `report.md` first; `report.json` is the same data plus assertion health,
self-report divergence, and cost accounting.

The **overall verdict** is decided by `correctness` and `constraint_adherence`
only. `quality` — the blind comparator's preference — is reported for
information and can never flip, block, or create a win. A well-liked writing
style does not get to override reproducible evidence.

A dimension declares a winner only when the Wilson lower bound clears 0.5.
Anything closer is `INCONCLUSIVE` with every number still printed, never rounded
into a winner.

## Two honesty properties you must not paper over

**`--quick` caps the verdict at `DIRECTIONAL_HINT`.** It can never produce a
full win. That is deliberate — a 3-pair run is a cheap smell test, not evidence.
Do not report a `--quick` result as though a candidate won.

**Neither shipped fixture has a `pass` calibration record yet**, so comparisons
against them report `harness_validity: unverified` and the overall verdict is
downgraded to `INCONCLUSIVE`. The per-dimension numbers are still printed in
full. This is a disclosed limitation, not a bug to work around: a highly
deterministic candidate tends to tie *itself* on an A-vs-A calibration run,
which leaves `n_eff=0` and lands `inconclusive` rather than `pass`. Report the
downgrade when you report the numbers.

## Do not

- Do not composite the four dimensions into a single score. `efficiency` alone
  is three separately-reported sub-metrics (`tool_calls`, `wall_clock`, `cost`)
  precisely so nobody averages them.
- Do not describe a result as a win when the verdict is `INCONCLUSIVE`,
  `DIRECTIONAL_HINT`, `TASK_TOO_HARD`, or `HARNESS_INVALID`. Say which state it
  is and what would resolve it.
- Do not run against a new fixture without `verify-fixture` first. It costs two
  grader invocations; a comparison against an undiscriminating fixture costs a
  full N-run and tells you nothing.
