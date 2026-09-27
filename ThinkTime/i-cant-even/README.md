# I Can't Even

A design-decision advisor for when you've hit a non-trivial choice and need someone (or four someones) to grill you toward a defensible answer.

```
orient (read the repo)
  → grill (one question at a time, decision tree depth-first)
  → 4-persona panel (parallel)
  → synthesize into a one-screen memo
```

Advisory only. Output is a recommendation memo, not code. Hand off to your dev orchestrator (`tdd`, `feature-dev`, or a multi-agent dev skill) for implementation.

## The panel

Four personas, always all four, dispatched as parallel agent calls so they reason independently:

| Persona | Lean | One-liner |
|---|---|---|
| [Conservative](./skills/i-cant-even/personas/conservative.md) | Reliability + security | "Boring is good." |
| [Balanced](./skills/i-cant-even/personas/balanced.md) | Staff-architect craft | "Build it once, build it right." |
| [Aggressive](./skills/i-cant-even/personas/aggressive.md) | Pragmatic shipper | "Ship it, learn, refactor later." |
| [Critical Thinker](./skills/i-cant-even/personas/critical-thinker.md) | Off-spectrum | Attacks the assumptions the other three accept. |

The Critical Thinker exists because three positional personas (cautious / balanced / shipper) all share an axis — they disagree about pace, but they accept the *framing* of the question. The CT is allowed to say "you're solving the wrong problem." Without them, the panel can be unanimously confident and unanimously wrong.

## The two anti-bias guards

1. **Verbatim-quote rule.** Every panel entry in the memo must include one direct sentence quoted from that persona's output — not a paraphrase. Stops the orchestrator from softening dissent in summary.
2. **Forked-panel escape hatch.** If the panel is 3-1 *and* the Critical Thinker's objection attacks the framing (not just adds a risk), the skill **stops and refuses to synthesize**. It surfaces the CT's reframe to you and offers to re-run with the reframe as new orientation. The CT's "stop-the-presses risk" is the trigger — they get a veto.

These two rules are what makes the panel an actual stress test rather than a comfort-blanket. Most "multi-persona" patterns degrade to consensus-laundering.

## The memo format

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
<3-8 lines synthesizing the panel — name which posture you lean toward and why>

## Trade-offs
- For / Against / Alternatives ruled out

## Open risks
<unresolved items + any risk only one panelist flagged>

## Next step
<one action — test, spike, or hand to a TDD dev skill>
```

> If the memo doesn't fit on a screen, you grilled too long.

## When to use

You have a non-trivial design choice, the trade-offs aren't obvious, and you want **a real answer with a recommendation** — not a balanced list of bullet points.

Triggers: `/ThinkTime:i-cant-even`, or say "i cant even" in chat.

User-invoked only. The skill never auto-triggers on design-shaped questions — those get answered inline with at most a "want me to run `/ThinkTime:i-cant-even` on this?" suggestion. You stay in control of whether the full panel runs.

## Companion: `grill-me`

Matt Pocock's `grill-me` skill is interview-only — it stress-tests your plan via dialogue and stops there. `i-cant-even` wraps the same grilling instinct in a workflow with project orientation **before** (so the grill is specific to your codebase, not generic) and a synthesized recommendation **after** (so you leave with a memo, not just answered questions). Use `grill-me` when you only want the dialogue; use this skill when you want a deliverable.

## Install

```bash
claude plugin marketplace add z0rd0n88/ThinkTime
claude plugin install ThinkTime@thinktime
```

## Layout

```
i-cant-even/
├── .claude-plugin/plugin.json
├── README.md
├── commands/
│   └── i-cant-even.md
└── skills/
    └── i-cant-even/
        ├── SKILL.md
        └── personas/
            ├── conservative.md
            ├── balanced.md
            ├── aggressive.md
            └── critical-thinker.md
```

## License

[MIT](../../LICENSE).
