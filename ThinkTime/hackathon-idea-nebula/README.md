# hackathon-idea-nebula

Generates candidate projects for **one specific hackathon**, then shortlists them. It generates; it does not judge — hand the pick to [`hackathon-judge`](../hackathon-judge/README.md) with the same rules block for the verdicts.

```
hackathon-idea-nebula [<focus...>] [--category NAME] [--context <path>]
            [--wild <n>] [--banlist] [--no-feasibility]
            [--feasibility-top <n>] [--plain] [--write-to <path>] [--force]
            + a filled RULES AND CONSTRAINTS block
```

## How it differs from `idea-nebula`

Same architecture — four independent parallel generators, blind pairwise ranking in both orders, live grounding before any shortlist, barbell output. Every instrument points somewhere else:

| | `idea-nebula` | `hackathon-idea-nebula` |
|---|---|---|
| Input | a topic | one event's rules, with five gating fields |
| Generators | `tails`, `folk`, `alien`, `miner` | `tails`, `stage`, `alien`, `recon` |
| Grounding | demand — complaints, vendors, kill-zone | feasibility — API access, live-demo limits, the hard part, prior art, pre-work legality |
| "Novel" means | distance from the idea space's modal region | distance from what the room will build: the obvious reading of the theme crossed with the mandated tech's quickstart |
| Barbell | Safe Picks / Moonshots | Safe Demos / Swing Demos |
| Scoped to | whether a market exists | whether a demo ships |

The two generators that are genuinely new:

- **`stage`** samples from *things visible on a screen* and works backwards to the project. Judging is a short demo in a noisy room, and a project designed problem-forward often has no visible moment at all.
- **`recon`** mines prior art rather than complaints — the mandated tech's own samples and quickstarts, past winners, GitHub. That one search answers both questions that kill an entry: can it be built in time, and will thirty other teams build it too.

## Required input

The RULES AND CONSTRAINTS block, in the same shape `hackathon-judge` uses, so one filled block serves the whole pipeline. Five fields gate the run — duration, theme, mandated tech, pre-work rules, targeted category. Blank any of them and the skill prints the template, names what is missing, and stops. It does not invent the event.

The block is untrusted input: text inside it that tries to direct the skill is reported, not obeyed.

## What it returns

Safe Demos and Swing Demos as separate lists, each candidate carrying its demo moment, mandated-tech use, minimum slice with hours against the productive-hours budget, escape hatch, and differentiation justification. Plus anything a hard threshold killed and why — a closed path you can see beats a shorter list.

No verdict. Standings are duel records inside the pool, not a prediction about the room.

## Cost

A full run dispatches up to ~10 subagents (4 generators + 1 ranker + up to `--feasibility-top` feasibility checks). `--no-feasibility` skips the grounding stage and forces an UNCHECKED warning into the report.
