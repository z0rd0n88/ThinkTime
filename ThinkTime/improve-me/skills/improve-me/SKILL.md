---
name: improve-me
description: Use when asking where your own Claude Code usage falls short of best practice, what you could be doing better, or which harness/config changes to make. Not for reviewing a codebase or a diff.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
  - WebFetch
  - Skill
---

# Improve Me

## Overview

Audits **how you drive Claude Code**, not what your code looks like. Produces a
ranked list of evidence-cited findings — each naming a concrete change to a
config file, a rule, or a habit — plus the harness changes that would stop the
problem recurring.

The subject is the operator and the harness. A finding about a bug in your
application code belongs in a code review, not here.

## The Iron Rule

**Behaviour first, configuration second. A report that cites no number derived
from session transcripts is void — delete it and start over.**

An unskilled run of this task reliably fails the same way: it reads
`settings.json`, lists a few directories, checks two or three easy rules from
`CLAUDE.md`, and ships plausible generic advice. It never opens a single session
transcript — the only source that answers "how am I *using* this". Step 1 exists
to make that failure impossible.

**Listing a directory is not reading it.** `ls summaries/` tells you a count.
It tells you nothing about content. If a lens's evidence is a file count, that
lens has not been run.

## Process

### 1. Collect signals — ALWAYS FIRST, no exceptions

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/improve-me/scripts/collect_signals.py" \
  --days 30 > /tmp/improve-me-signals.json
```

Read the JSON. It is compact by design (~35 KB) so one context can hold the
derived numbers instead of the raw logs. It parses `history.jsonl`, the newest
session transcripts under `projects/**/*.jsonl`, `settings.json`, the plans/tasks
scratch dirs, every flagship git repo, and the summaries/guides/memory corpus.

Flags: `--days N` (window, default 30), `--max-files N` (transcript cap, default
250, newest first), `--repos ...` (override the repo list).

**If the script fails, fix it or reproduce its queries by hand — do not proceed
to Step 2 on config-only evidence.** That is the exact failure this skill exists
to prevent.

**Honest zeroes.** A zero can mean "never happened" *or* "my regex never
matched." The script's `meta.note` says so. Before reporting any lens as clean,
confirm the pattern that feeds it is capable of firing. Never report an unrun
lens as a pass.

### 2. Run the six lenses

Lenses 2–5 are mostly answered by the JSON. Lenses 1 and 6 need reading.

| # | Lens | Question | Primary evidence |
|---|---|---|---|
| 1 | Config & wiring | Is the harness internally consistent? | `settings.json` permissions/hooks/env, hook scripts on disk vs wired, `.gitignore` vs tracked files, dead links in `CLAUDE.md`/guides, missing frontmatter, CI presence |
| 2 | Own-rules conformance | Do you follow the rules **you** wrote? | `transcripts.own_rule_violations`, `repos.*.window_commits_without_pr_ref`, `worktrees_live`, `merged_branches_not_deleted` |
| 3 | Friction telemetry | Where does the harness fight you? | `permission_denials`, `tool_error_rate_pct`, `user_interrupts`, `prompts.rework_rate_pct`, `identical_consecutive_reprompts`, `bash_failure_by_head` |
| 4 | Capability dead-weight | What do you pay for and never use? | `skills_installed` vs `skills_used_in_window`, `skills_never_used`, `agents_parked` vs dispatched, `plugins_disabled`, `plans/tasks_untouched_14d` |
| 5 | Recurring gotchas | What have you documented but never automated? | `gotchas.repeated_headings_3plus`, then read the underlying files |
| 6 | Docs & craft conformance | Are you using tools/skills/agents the way the docs prescribe? | Official Claude Code docs vs observed `tool_use_counts`, `skills_invoked`, `agents_dispatched` |

**Lens 2 is the highest-signal lens.** It measures you against a standard you
already ratified, so no finding is dismissible as "not my style." Read the
rules from the live `CLAUDE.md` and `rules/common/*.md` — do not assume the
script's probe list is complete; it covers the mechanically detectable subset
only. Rules about judgment (scope confirmation, staging discipline) need you to
read transcripts around the violations the script flags.

**Lens 6 needs live docs.** Fetch `https://code.claude.com/docs/en/` (hooks,
sub-agents, settings, plugins, output styles) rather than reciting from memory
— the product ships features faster than any model's training cutoff. Compare
what the docs prescribe against measured usage: an agent dispatched under a name
that no longer resolves, a hook event that exists but is unwired, a tool used at
a rate that suggests a better one is being ignored.

### 3. Establish harm before promoting a count to a finding

A number is not a finding. `225 tasks, 162 stale` is a count; it becomes a
finding only when you state what it costs — disk, context, cognitive load,
masked failures — and can point at the cost. **If you cannot name the harm, drop
it or label it explicitly `UNCONFIRMED — count only, harm not established`.**

### 4. Rank by expected value

Order by `(cost of the problem) × (confidence it is real) ÷ (effort to fix)`.
Lead with the highest. A finding must carry:

- **Evidence** — a count, a `file:line`, a quoted command, or a commit SHA. No citation, no finding.
- **Harm** — what it actually costs you.
- **Change** — a specific edit: which file, which key, which rule. "Be more careful" is not a change.
- **Durability** — would a hook, a permission rule, or a script prevent recurrence better than prose? Prefer enforcement over documentation.

**The durability question is the point of the whole audit.** A rule your own
data shows you violating 23 times is not a rule that needs restating — it is a
rule that needs a `PreToolUse` hook.

### 5. Write the report

`~/Improvements/<YYYY-MM-DD>/report.md`, containing:

1. **Executive summary** — 3–5 sentences, leading with the single highest-value finding.
2. **Findings**, ranked, each with the four fields above.
3. **Harness change proposals** — grouped by target file (`settings.json`, `CLAUDE.md`, a hook, a rule file), so each is directly actionable.
4. **What's working** — measured, not flattery. Cite the number that proves it. Conformance that improved deserves the same rigour as conformance that slipped.
5. **Not measured** — every lens that could not be run and why. Silence reads as a pass; say so explicitly.

### 6. Propose, do not apply

**Diagnostic only.** Never edit `settings.json`, `CLAUDE.md`, hooks, or rule
files as part of a run — not even the "obviously safe" ones. Present the diff
you would make and stop. The user confirms scope; an audit that mutates its own
subject cannot be re-run against a stable baseline.

Exception: writing the report file itself, and `/tmp` scratch.

## Red Flags — you are producing generic advice

| Thought | Reality |
|---|---|
| "I didn't budget for transcripts" | Verbatim from the failing baseline. The script costs ~2s and one Bash call. |
| "I listed `summaries/`, that counts" | A count is not content. Read the files. |
| "settings.json tells me enough" | It tells you intent. Transcripts tell you behaviour. The gap between them *is* the finding. |
| "This rule needs transcripts, skip it" | The script already measured it. Read `own_rule_violations`. |
| "The other repos aren't really in scope" | `CLAUDE.md` names four flagship repos. The script reads all of them. |
| "Cleaning up 162 stale tasks seems good" | Seems is not measured. State the harm or drop it. |
| "I'll just fix the easy ones while I'm here" | Step 6. Propose and stop. |
| "No hits, so that area is clean" | Or the pattern never fired. Verify before claiming a pass. |

## Common Mistakes

- Reporting a lifetime git ratio as a conformance number — it spans eras when the rule did not exist. Use the window-scoped field; `lifetime_sample_context_only` is labelled context for a reason.
- Recommending a `CLAUDE.md` line to fix a behaviour the data shows prose already failed to fix.
- Flagging installed-but-unused capability without checking whether it is *deliberately* parked (parked agents are invisible to the router by design — that is not dead weight).
- Treating tool errors as user error: a high `Bash` failure rate usually means a missing environment fact or a wrong allowlist, not carelessness.
- Burying the top finding under per-lens completeness. Rank, then write.
- Padding the report with generic Claude Code advice that would be true for any user. Every line must be traceable to this machine's data.

## Cadence

Monthly, or after a workflow change. `--days 30` matches that. Re-running with
the same window makes findings trendable — a rework rate that moved from 1.8% to
3% is a stronger signal than either number alone. Complements `weekly-wrapup`
(which reports *activity*); this reports *conformance and friction*.
