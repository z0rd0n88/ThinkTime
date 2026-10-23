# hackathon-idea-nebula

Hackathon project generation that answers two separate questions: **is this worth spending the event on**, and **would it win**. An idea can be a great weekend and lose; an idea can win and be miserable to build. They are scored and reported separately.

## Executive summary

`idea-nebula` generates products; this skill generates *entries*. It inherits the generation architecture — four independent parallel entropy sources, mandatory boldness revision, blind pairwise duels judged in both orders, modal-region naming, barbell output — and retargets every judgment at the event's own rules:

| Inherited from `idea-nebula` | Retargeted to |
|---|---|
| 4 parallel entropy-source generators, no debate | `tails`, `stage` (reverse-engineered from the on-stage wow moment), `alien`, `scout` (live prior-art + capability mining) |
| Live demand mining with hard thresholds | Live **build-feasibility** mining: credential availability, rate limits, library coverage of the hard part, data existence, prior-art saturation |
| One blind ranking | **Two** blind rankings — buildability and winnability — never merged |
| Barbell: Safe Picks / Moonshots | Safe Demos / Trophy Swings |
| Novelty as distance from the modal region | Differentiation as distance from what 15 other teams submit this weekend |

From `idea-refine` it takes the hard input gate (stop and ask, never guess), the minimum-slice discipline and the explicit **Not Doing** list. From the hackathon reality it adds a simulated panel of four conflicting judges and an hour-by-hour plan with a scope-cut checkpoint at T-6h.

## Requires a RULES AND CONSTRAINTS block

The skill will not guess the event. Supply duration and schedule, theme, mandated sponsor tech, team size cap, pre-work rules, submission requirements, the event's published rubric and weights, and the prize categories. Missing fields are reported as evidence gaps; a missing rubric falls back to a stated default; a missing block stops the run.

## Usage

```
/ThinkTime:hackathon-idea-nebula <theme...> --rules <path> [--stack <desc>] [--team <n>]
      [--prize <category>] [--wild <n>] [--banlist] [--no-feasibility]
      [--feasibility-top <n>] [--plain] [--write-to <path>] [--force]
```

## Pipeline

```
GATE      RULES block required — no rules, no run
RUBRIC    event's published criteria + weights verbatim, else a stated
          default (demoability · buildability · differentiation ·
          judge legibility · escape hatch · rule compliance),
          reshaped for the targeted prize category
DIVERGE   4 generators in parallel, blind to each other:
          tails (VS tail ideas) · stage (wow moment first) ·
          alien (far-domain mapping) · scout (live prior art + capability)
          each: draft -> boldness revision -> wow moment, hard part,
          rule compliance, escape hatch
RANK      two blind rankings: "will it ship" and "will it score",
          round-robin duels judged in BOTH orders, never merged
GROUND    per-finalist feasibility: credentials, rate limits, library
          coverage, data existence, saturation, rule compliance
JUDGE     4 conflicting judges score the rubric independently;
          splits reported as fragility, not averaged away
REPORT    both verdicts first (BUILD IT / BUILD WITH SCOPE CUTS /
          SAME DOMAIN DIFFERENT DEMO / PICK SOMETHING ELSE), rubric
          provenance, scorecards, disagreements, ALL findings and
          evidence gaps, minimum slice + Not Doing, hour-by-hour plan
SAVE      offers to write the report (default
          docs/ideas/<topic-slug>-hackathon.md)
```

> ⚠️ A full run dispatches up to ~13 subagents. `--no-feasibility` and `--feasibility-top` reduce that.

## Relationship to other ThinkTime skills

- **idea-nebula** — same architecture, no event, no rules, no judges. Use it when there is no deadline.
- **idea-refine** — sharpen the chosen entry after this skill picks it.
- Downstream: `idea-autopsy:stress-test-idea` to attack the pick before the clock starts.

## Install

```
claude plugin marketplace add z0rd0n88/ThinkTime
claude plugin install ThinkTime@thinktime
```
