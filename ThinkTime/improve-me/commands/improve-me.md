---
description: "Audit how you actually use Claude Code — own-rule conformance, harness friction, dead capability — from session-log evidence"
argument-hint: "[--days N]"
---

Invoke the `improve-me` skill from this plugin.

Pass through any `--days N` window the user supplied (default 30). The skill runs its
bundled signal collector first, then reasons over the derived numbers — it must not
produce findings from `settings.json` and directory listings alone.

Diagnostic only: it writes a dated report to `~/Improvements/<date>/report.md` and
proposes harness changes, but never edits config, rules, or hooks.
