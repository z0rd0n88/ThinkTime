---
description: "Evaluate a design choice: orient on the codebase, grill, run a 4-persona panel, deliver a memo"
argument-hint: "[brief description of the design question]"
---

Invoke the `i-cant-even` skill and follow it exactly.

Arguments forwarded: `$ARGUMENTS`

The skill produces a grounded design recommendation for a non-trivial software decision. **Advisory only — output is a memo, not code.**

Three phases:

1. **Orient.** Reads `ARCH.md`, `CONTEXT.md`, `docs/adr/`, and any other architectural docs. Notes hard constraints in your request. Restates scope back to you in 2–4 lines.

2. **Grill.** Walks the design decision tree one question at a time, each question paired with the recommended answer ("I'd lean X because Y — agree?"). Reads code to answer what the repo can answer; only asks you about intent, constraints, taste. Stops early when remaining branches are stylistic.

3. **4-persona panel + synthesis.** Dispatches four parallel persona agents (conservative / balanced / aggressive / critical-thinker), each constrained by a bundled persona file. Verbatim-quote rule prevents softening dissent in synthesis. Stop-the-presses escape hatch fires when the critical thinker reframes the question rather than just adding a risk. Synthesizes into a one-screen memo: Context / Decisions resolved / Panel / Recommended approach / Trade-offs / Open risks / Next step.

**User-invoked only.** Does not auto-trigger. For unprompted design-shaped questions in conversation, the skill answers inline and may suggest running `/ThinkTime:i-cant-even` — but only starts the workflow if you explicitly ask.

**Companion:** `grill-me` is interview-only (no deliverable). This skill adds project orientation before and a synthesized recommendation after.
