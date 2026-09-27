---
name: i-cant-even
description: 'User-invoked only; run when the user types `/ThinkTime:i-cant-even` or says "i cant even". Evaluates a design choice in project context and gives a recommendation with trade-offs.'
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
  - Write
  - Edit
---

# i-cant-even

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

Evaluates a non-trivial software design decision: orients on the codebase, grills
the user through the open questions one at a time, then runs a 4-persona panel
to synthesize a recommendation memo with trade-offs. It's advisory only — the
output is a memo, not code — and hands off implementation to a TDD dev skill.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<design question>` (free text after `/ThinkTime:i-cant-even`) | any text describing the design decision to evaluate | none — required | Sets the decision that orientation, grilling, and the persona panel run against |

Produce a grounded design recommendation for a non-trivial software decision. Advisory only — output is a memo, not code. Hand off to your TDD dev orchestrator (`tdd`, `feature-dev`, or a multi-agent dev skill if you have one) for implementation.

**vs. `grill-me`:** grill-me is interview-only (no deliverable). This skill adds project orientation before, and a synthesized recommendation after.

## Workflow

### 1. Orient

- Read repo `ARCH.md`, `CONTEXT.md`, `docs/adr/` if they exist.
- Note hard constraints in the user's request (deadline, "must work with X", "can't touch Y").
- For multi-file scope, dispatch `Explore` with a narrow question.
- Restate scope + constraints back to the user in 2–4 lines before grilling.

### 2. Grill

Walk the design decision tree one question at a time, resolving dependencies between decisions in order.

- **One question per turn**, always paired with your recommended answer ("I'd lean X because Y — agree?").
- **Read the code, don't ask.** Questions the repo can answer get answered by grep/read. Only ask about intent, constraints, taste.
- **Stay specific.** Questions must reference what you found in Phase 1 — no template questions.
- **Stop early.** When remaining branches are low-impact or stylistic, move on and list them under Open risks.

### 3. Recommend — bundled persona panel

Don't write the recommendation yourself. Run a **4-persona panel** using the persona definitions bundled in `personas/`. No external agents — the personas live inside this skill.

**The panel (always all four):**

1. **Conservative** — `personas/conservative.md`. Reliability/security lean. "Boring is good."
2. **Balanced** — `personas/balanced.md`. Staff-architect lean. "Build it once, build it right."
3. **Aggressive** — `personas/aggressive.md`. Pragmatic shipper. "Ship it, learn, refactor later."
4. **Critical Thinker** — `personas/critical-thinker.md`. Off-spectrum. Attacks assumptions the other three accept.

**How to run the panel:**

For each persona, in a single assistant turn (parallel) dispatch one `Agent` call with `subagent_type: general-purpose`. The prompt MUST contain:

1. The full text of `personas/<name>.md` (read it and inline it — that IS the persona instruction).
2. **Orientation summary** from Phase 1 (scope, constraints, the codebase facts that matter).
3. **Decisions resolved** from Phase 2.
4. **Open risks** you already know about.
5. The literal task: *"Follow the output contract in your persona. Do not deviate."*

Each persona returns only what its output contract specifies — keep responses tight.

**Synthesis rules (guard against orchestrator bias):**

- **Verbatim quote rule** — each Panel entry must include one direct sentence quoted from that persona's output, not a paraphrase. Prevents softening dissent in summary.
- **Forked-panel escape hatch** — if the panel is 3-1 *and* the Critical Thinker's objection attacks the Phase 1/2 framing (not just flags an additional risk), STOP. Do not synthesize. Surface the CT's reframe to the user and offer a re-run with the reframe as new orientation. The CT's "stop-the-presses risk" is the trigger.

**Synthesize into the memo:**

```md
# Design: <title>

## Context
<2-4 lines: what, scope, constraints>

## Decisions resolved
- <Q>: <answer>

## Panel
- **Conservative**: <1-2 lines — their pick + key trade-off>
- **Balanced**: <1-2 lines>
- **Aggressive**: <1-2 lines>
- **Critical Thinker**: <1-2 lines — strongest objection + stop-the-presses risk if any>

## Recommended approach
<3-8 lines synthesizing the panel — name which posture you lean toward and why. Where the three positional panelists agree, that's the spine. Where they disagree, you pick and justify. Address the Critical Thinker's objection explicitly: refute it, accept it, or note it as a known risk.>

## Trade-offs
- **For / Against / Alternatives ruled out**

## Open risks
<unresolved items + any risk only one panelist flagged>

## Next step
<one action — test, spike, or hand to a TDD dev skill (`tdd` / `feature-dev` / etc.)>
```

If the memo doesn't fit on a screen, you grilled too long.

### 4. Persist

The memo is a one-shot advisory output with no fixed home — don't assume where it belongs. Ask
the user (`AskUserQuestion` or inline) whether to save it: append to an existing doc/ADR
(`docs/adr/`), write a new file (e.g. `docs/decisions/<slug>.md`), or leave it in chat only. Save
via `Write`/`Edit` per their answer.

## Invocation

User-triggered only. Valid triggers: `/ThinkTime:i-cant-even`, "i-cant-even", "i cant even".

For unprompted design-shaped questions, answer inline. You may suggest the skill in one sentence and wait — do not start the workflow until the user agrees.

## Discipline

- Don't skip orientation — generic advice is useless advice.
- Don't implement here — memo only.
- Cite file paths for any referenced code.
