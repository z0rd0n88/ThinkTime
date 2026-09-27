# improve-me

> **Created by:** z0rd0n88

Audit **how you drive Claude Code** — not what your code looks like.

Produces a ranked, evidence-cited list of where your actual behaviour diverges from
best practice, from the rules you wrote yourself, and from what the harness could be
doing for you.

## Invocation

`/ThinkTime:improve-me [--days N]`, or ask directly ("where am I not following best practices?",
"what harness changes should I make?"). Default window is 30 days.

## Why it needs a script

A naive run of this task reads `settings.json`, lists a few directories, and ships
generic advice — it never opens a session transcript, the only source that records
what you actually *did*. But 2,000+ transcripts don't fit in a context.

`scripts/collect_signals.py` resolves that: it parses the logs and emits ~35 KB of
derived numbers, so one reasoning context works from measurements instead of vibes.
Read-only, no network, ~2s.

```bash
python3 ThinkTime/improve-me/scripts/collect_signals.py --days 30 > signals.json
```

| Flag | Default | Meaning |
|---|---|---|
| `--days N` | 30 | analysis window |
| `--max-files N` | 250 | transcript cap, newest first |
| `--repos ...` | flagship repos | override repos scanned |

## The six lenses

| Lens | Finds |
|---|---|
| Config & wiring | Hooks on disk but unwired, dead doc links, `.gitignore` vs tracked reality, missing CI |
| **Own-rules conformance** | Measured violations of your own `CLAUDE.md` — `git add -A`, hook bypasses, force pushes, direct-to-main commits, uncleaned worktrees |
| Friction telemetry | Permission denials, per-tool error rates, interrupts, rework prompts, re-prompt loops |
| Capability dead-weight | Installed-and-never-invoked skills/agents/plugins, abandoned plans and tasks |
| Recurring gotchas | Themes documented 3+ times across summaries, memory, and guides — a fix you never automated |
| Docs & craft conformance | Observed tool/skill/agent usage against the current official docs |

Own-rules conformance is the highest-signal lens: it measures you against a standard
you already ratified, so no finding is dismissible as "not my style."

## Guarantees

- **No finding without a citation** — a count, a `file:line`, a quoted command, or a SHA.
- **No count without established harm** — unproven costs are labelled `UNCONFIRMED`, not shipped as findings.
- **Window-scoped conformance** — lifetime git ratios span eras when a rule didn't exist yet; those are reported as context only, never as a conformance score.
- **Honest zeroes** — an unmatched pattern is reported as unrun, never as a pass.
- **Diagnostic only** — proposes config/hook/rule diffs and stops. Never edits its own subject.

## Tuning

`REWORK_PATTERNS` in the collector encodes what counts as evidence of *your* friction.
The default is generic. Edit it to match how you actually phrase corrections — a
pattern that never fires yields a silently empty lens; one that over-fires turns the
rework rate into noise.

## Related

`weekly-wrapup` reports activity; this reports conformance and friction.
`drift-status-check` audits a project against its plan; this audits the operator
against their own rules. For reviewing a diff, see `multi-agent-review` or
`total-review`.
