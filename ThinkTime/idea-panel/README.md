# Idea Panel

A parallel panel of thinking-skills mental-model lenses that *generates* candidate ideas for a topic, then a synthesizer clusters, ranks, and de-duplicates them into one shortlist.

Generative sibling of [`multi-agent-review`](https://github.com/z0rd0n88/ClaudesMods/tree/main/ClaudesMods/multi-agent-review): instead of a panel of reviewers finding faults in an existing artifact, this panel of lenses attacks a topic from distinct cognitive frames (first-principles, jobs-to-be-done, inversion, effectuation, …) so the same problem space gets explored from angles a single pass would collapse into one.

## The skill

| Skill | What it does | Command |
|---|---|---|
| [`idea-panel`](./skills/idea-panel/SKILL.md) | Spawns N lens agents in parallel over a topic, each generating candidate ideas from a distinct mental model, then a synthesizer merges them into one ranked, deduped report. Read-only. | `/ThinkTime:idea-panel` |

## Default lens roster

1. `thinking-first-principles` — strip the topic to irreducible truths; rebuild ideas from base truths, not inherited convention.
2. `thinking-jobs-to-be-done` — reframe from "what to build" to "what progress is someone trying to make."
3. `thinking-inversion` — enumerate failure/neglect modes, then invert each into an opportunity.
4. `thinking-effectuation` — start from available means (skills, networks, assets), not goals.

Any `thinking-<name>` slug can be swapped in via `--lenses`, and named specialist agents (e.g. `market-researcher`, `product-strategist`) can join the panel for domain grounding the mental-model lenses structurally lack. An optional `critical-thinking` carve-out lens interrogates the topic's unstated assumptions instead of generating ideas — opt in with `--lenses ...,critical-thinking`.

## Install

```bash
claude plugin marketplace add z0rd0n88/ThinkTime
claude plugin install ThinkTime@thinktime
```

## Use

```bash
/ThinkTime:idea-panel genetic security — new project/product directions
/ThinkTime:idea-panel loyalty rewards for indie coffee shops --panel-size 3
/ThinkTime:idea-panel developer tooling --lenses thinking-triz,thinking-second-order,thinking-jobs-to-be-done
/ThinkTime:idea-panel authentication UX --context docs/research/ --write-to docs/ideas/auth-panel.md
```

The shortlist is written to `docs/ideas/<YYYY-MM-DD>-<topic-slug>.md` by default; `--write-to` only overrides the path, and `--no-write` opts out.

## Composition with other skills

The natural follow-on pipeline once a shortlist exists:

| Step | Skill | Where it lives |
|---|---|---|
| Generate ideas | **`idea-panel`** | this plugin |
| Sharpen the chosen idea | `idea-autopsy:iterate-to-v2` | [sibling plugin in ClaudesMods](https://github.com/z0rd0n88/ClaudesMods/tree/main/ClaudesMods/idea-autopsy) |
| Formalize into a spec | `product-management:write-spec` / `to-prd` | separate skills |
| Pressure-test before committing | `idea-autopsy:evaluate-proposal-harsh` | [sibling plugin in ClaudesMods](https://github.com/z0rd0n88/ClaudesMods/tree/main/ClaudesMods/idea-autopsy) |

## Layout

```
idea-panel/
├── .claude-plugin/plugin.json
├── README.md
├── commands/
│   └── idea-panel.md
└── skills/
    └── idea-panel/
        ├── SKILL.md
        └── references/
            ├── lens-briefs.md
            └── synthesizer-brief.md
```

## License

[MIT](../../LICENSE).
