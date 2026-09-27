# versus — head-to-head benchmarking for Claude Code skills and agents

`versus` runs two candidates (skills or agents) against the same task, N times
each, in isolated git worktrees, and produces a paired-comparison report: who
did the task correctly, who stayed inside its declared constraints, who was
faster/cheaper, and which one a blind LLM judge preferred — with honest
statistics (Wilson intervals, a sign test) and no invented composite score.

**Status: migrated from ClaudesMods v1.22.0.** Phases 0–6 are included — isolation,
grading, blind judging, statistics/reporting, `verify-fixture`, A-vs-A
calibration and two fixtures. The plugin registers
[`skills/versus/SKILL.md`](skills/versus/SKILL.md) plus
[`commands/versus-compare.md`](commands/versus-compare.md), both listed in
`ThinkTime/.claude-plugin/plugin.json`. `/ThinkTime:versus-compare` is the slash
command; the CLI below is still the execution surface and the skill drives it.

The original design spec (`docs/design/2026-07-26-versus-compare-spec.md`) is
**not in this repository** — nothing at that path, in any branch or in history.
The `FR-*` / `SM*` / `DR-*` identifiers below are preserved as written but
cannot be followed to a source here; this README is the authoritative surviving
description.

## Quick start

```bash
cd ThinkTime/versus
python3 scripts/cli.py run \
  path/to/candidate-a.md path/to/candidate-b.md \
  --fixture readonly-reviewer-diff-audit \
  --quick \
  --workspace /tmp/my-versus-run
```

This runs 3 pairs (`--quick`), prints progress to stderr, and on success
writes `report.json`/`report.md` into a new comparison directory under
`/tmp/my-versus-run/`. Read `report.md` first — it's the human-readable
summary; `report.json` is the same data in machine-readable form. Both
shipped fixtures (`readonly-reviewer-diff-audit`, `spec-from-vague-issue`)
resolve by id — no `--unverified-fixture` needed. See "Fixtures" below for
what each expects from a candidate.

Run the test suite from the same directory:

```bash
python3 -m pytest tests/ -q      # 590 tests, no external deps
ruff check scripts/ tests/       # lint
```

## What a candidate looks like

A candidate is either an **agent** or a **skill**, resolved automatically
from the path you pass:

- **Agent** — a single `.md` file with frontmatter: `name`, `description`,
  `prompt`, optionally `tools: [...]` / `disallowedTools: [...]` (validated
  against the known Claude Code tool surface) and `model`. This is the same
  shape `--agents` expects.
- **Skill** — a directory containing either `SKILL.md` or
  `.claude-plugin/plugin.json`. The whole directory is wrapped and launched
  via `--plugin-dir`.

You always compare **two of the same kind** — skill-vs-skill or
agent-vs-agent. Skill-vs-agent is out of scope for this design (see DR-6 in
the spec).

## The `versus` CLI

Four subcommands, invoked as `python3 scripts/cli.py <subcommand> ...`:

### `run` — the main comparison

```
run <candidate-a> <candidate-b> --fixture <path-or-id> [options]
```

| Flag | Meaning |
|---|---|
| `--fixture PATH` | required. A fixture directory (see below) |
| `--runs N` | pairs to run. Default 5, or 3 under `--quick`. Minimum 3 |
| `--quick` | N=3, and caps the verdict at `DIRECTIONAL_HINT` (never a full win) — a fast, cheap check that never over-claims |
| `--parallel N` | how many pairs run concurrently (default 3) |
| `--model NAME` | executor model for both candidates (default `haiku`) |
| `--effort LEVEL` | executor effort level |
| `--respect-candidate-model` | let an agent's own frontmatter `model` override `--model` |
| `--double-judge` | judge each pair twice with swapped A/B slots, at 2× the comparator cost — catches positional bias |
| `--self-calibrate` | takes **one** candidate, runs it against itself (A-vs-A), evaluates SM1's predicate, and appends a `pass`/`fail`/`fail_unconfirmed`/`inconclusive`/`underpowered` record to the fixture's `calibration.jsonl`. Requires `--runs 9` minimum (the floor is refused, not clamped). A subsequent normal comparison against that fixture reads the latest record: only a `pass` at the current `fixture_version` lifts the `INCONCLUSIVE` downgrade FR-52 otherwise applies |
| `--max-budget-usd N` | per-run dollar ceiling |
| `--keep-worktrees {on-failure,always,never}` | worktree retention policy (default `on-failure`) |
| `--dry-run` | print exactly what would run — every worktree, every command line, every env key — and spawn nothing |
| `--isolation {worktree,clone}` | how each run is isolated. Default `worktree` |
| `--unverified-fixture` | skip the discrimination gate. **Not registered at all** unless `VERSUS_DEV=1` is set *and* the plugin version string contains `-dev`, so it is absent from `--help` in a normal install. Neither shipped fixture needs it |
| `--workspace PATH` | where comparisons are written (default `~/.versus`) |

### `report` — regenerate a report from a past comparison

```
report <comparison-id> [--format json|md|both]
```

Re-runs the aggregation/redaction pipeline against an already-completed
comparison directory and prints the result. Useful if you want to re-render
`report.md` without re-running the candidates. One real limitation: a fresh
`report` invocation has no memory of the original run's credentials, so its
credential sweep is pattern-based only (catches `ghp_...`/`sk-...`-shaped
secrets and `SOMETHING_TOKEN=`/`SOMETHING_KEY=`-labelled values) — the
exact-value sweep only runs once, automatically, inside the original `run`.

### `clean` (alias `gc`) — list or remove old comparisons

```
clean [--comparison-id ID | --all] [--dry-run]
```

With no target, just lists what's in the workspace. Removal always goes
through `git worktree remove --force` + `git worktree prune`, never a bare
`rm -rf`.

### `verify-fixture` — the discrimination gate (FR-44)

```
verify-fixture <fixture-id> [--fixture-dir <dir>]
```

Applies `reference/`, `broken/`, and `broken_hard/` to fresh clones, runs
the deterministic gate against each, grades `reference/` and `broken/`
against `assertions.json`, and writes the `discrimination` block into
`fixture.json`. A comparison refuses a fixture whose `reference_pass_rate <
0.9` or `broken_pass_rate > 0.2` (or whose gate results don't match) unless
`--unverified-fixture` is used. Both shipped fixtures pass this cleanly
(`reference_pass_rate: 1.0`, `broken_pass_rate: 0.0`).

## Fixtures

A fixture is a git-bundled task: a repo state, a prompt, deterministic
checks, and known-good/known-bad reference solutions.

Three real, shipped fixtures exist under `fixtures/`:

| Fixture | Mode | Task |
|---|---|---|
| `readonly-reviewer-diff-audit` | agent | Review a pinned diff that introduces a subtle numeric bug (a dropped `/ 100`); write findings only to `.vc-out/` — everything else is read-only, enforced via `constraint_adherence` |
| `spec-from-vague-issue` | skill | Turn an underspecified feature request into a structured spec with goals, non-goals, requirements, and an explicit decision on an interaction the request never mentions |
| `review-round2-carryforward` | skill | Round 2 of a review loop: suppress the two findings round 1 deferred with reasons, while still raising the one round 1 fixed *badly* and the new defect its fix introduced. Discriminates carry-forward from blanket suppression; see the fixture's own `README.md` for the planted defects and its stated bias |

`dev/fixtures/dev-noop` remains a throwaway, one-line-output task for
exercising the harness itself — never shipped, still needs
`--unverified-fixture` with `VERSUS_DEV=1` set. `dev/fixtures/dev-noop/`'s
own `README.md` documents the fixture-authoring layout
(`fixture.json`, `prompt.md`, `checks.sh`, `assertions.json`,
`reference/`/`broken/`/`broken_hard/` patches, `repo.bundle`) if you want to
author your own.

**Calibration status, stated honestly.** Neither shipped fixture has a
`pass` calibration record yet. `readonly-reviewer-diff-audit` was
calibrated once at N=9 (2026-08-04) and came back `inconclusive`: the
reviewer agent used tied on `correctness` and `constraint_adherence` on
all 9 pairs (a deterministic, well-behaved candidate has no reason to
sometimes fail or sometimes violate a constraint), leaving `n_eff=0` on
both — below FR-52's floor, so the attempt is neither `pass` nor `fail`.
A second consecutive `inconclusive` would formalize this as
`underpowered` rather than resolve it, since the same candidate would
almost certainly tie the same way again. This is a disclosed limitation
of self-calibrating a highly deterministic candidate against a fixture
built to be highly discriminating (SM3 wants reference/broken solutions
to score at the extremes, which correlates with a *capable* candidate
also scoring at the extremes, i.e. tying itself). Until a `pass` record
exists, comparisons against these fixtures report `harness_validity:
unverified` and the overall verdict is downgraded to `INCONCLUSIVE` —
the per-dimension numbers are still printed in full (FR-52).

## What gets measured

Four dimensions, reported with a **95% Wilson score interval** on the paired
win rate — never a single blended score:

| Dimension | Decided by | Model call? |
|---|---|---|
| `correctness` | the deterministic gate + a grader model's `pass_rate` against the fixture's declared assertions | Yes (the grader) |
| `constraint_adherence` | the verified, tamper-evident audit log of tool calls — fewer/no violations wins | No |
| `efficiency` | three separately-reported sub-metrics: `tool_calls`, `wall_clock`, `cost` — **never composited into one number** | No |
| `quality` | a blind comparator model, shown both outputs with all identifying information scrubbed, picks a winner or a tie | Yes (the comparator) |

A dimension only declares a winner if the Wilson lower bound clears 0.5 — a
close result is reported as `INCONCLUSIVE` with every number still printed,
never silently rounded to a winner. The **overall verdict** is one of six
states — `A_WINS`, `B_WINS`, `INCONCLUSIVE`, `TASK_TOO_HARD`,
`HARNESS_INVALID`, `DIRECTIONAL_HINT` — and is decided by `correctness` and
`constraint_adherence` alone. `quality` is reported for information and can
**never** flip, block, or create a win — a well-liked writing style doesn't
get to override reproducible evidence.

`report.json` additionally carries: an assertion-health breakdown (which
fixture assertions actually discriminate between the two arms, and which
ones pass or fail regardless of the candidate and should be removed), a
self-report-divergence check (did a candidate under- or over-report its own
tool usage relative to the verified audit log?), a credential-redaction
sweep over every retained artifact, and a full cost/invocation accounting.

## Safety properties worth knowing about

- Every run happens in its own git worktree with a **stripped-and-rebuilt**
  environment (allowlist, not denylist — an unknown env var is absent by
  construction, not filtered out after the fact).
- A `PreToolUse` deny hook blocks writes outside the worktree, network
  access, and reads of the harness's own control files.
- The blind comparator never sees a candidate name, file path, or denylisted
  identity term — inputs are staged into a scrubbed copy with all of that
  removed before the comparator ever launches.
- Every retained artifact (transcripts, audit logs, `outputs/`, the report
  itself) is swept for credential-shaped strings before the comparison is
  considered complete.

None of this is a sandbox in the OS-namespace sense — see the spec's own
Risks & Mitigations section for what's out of scope in v1.

## Things worth trying

1. **The smoke test** — run the quick-start command above verbatim with two
   trivially different agent `.md` files (e.g. one that writes a terse
   review, one that writes a verbose one) against `readonly-reviewer-diff-audit`.
   Read the resulting `report.md`; both should clear the deterministic gate
   identically, so the interesting numbers are `efficiency` and `quality`.
2. **`--dry-run` first** — before spending any money, run the exact same
   command with `--dry-run` appended. It prints every worktree path, command
   line, and environment key it *would* use, with zero spawns.
3. **`verify-fixture` on your own fixture** — run it before ever comparing
   candidates against a new fixture; it's what actually decides whether
   `reference_pass_rate`/`broken_pass_rate` clear SM3's bar, and it costs
   only 2 grader invocations (not a full N-run comparison).
4. **`--self-calibrate` as a sanity check** — point it at one candidate,
   `--runs 9` (the floor), and read the appended `calibration.jsonl`
   record. `pass` means no dimension showed a consistent winner; see
   "Fixtures" above for what `inconclusive`/`underpowered` mean and why a
   very reliable candidate can land there rather than `pass`.
5. **`--double-judge`** on a pair where `quality` came back close — see
   whether the blind judge's opinion holds up when A/B slots are swapped.
6. **Author your own fixture** — copy `readonly-reviewer-diff-audit/`'s
   shape for a real task you care about, run `verify-fixture` against it,
   then compare two real candidates. Keep the task prompt from spelling
   out the exact rubric your assertions check for — see the
   `dev-sm2-convention-rig` fixture note in `dev/fixtures/` for why that
   matters if you ever want a rigged-candidate self-test to actually show
   a difference.
7. **Read `report.json`'s `assertion_health` block** after a real multi-run
   comparison — it tells you which of your fixture's assertions are actually
   pulling weight versus which ones pass or fail no matter what you feed
   them.
