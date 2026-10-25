---
name: hackathon-judge
description: 'Use when deciding whether to build an idea at a specific hackathon — scores "worth building" and "would it win" separately against the event rules, simulates the judging panel, and plans the build'
---

# Hackathon Judge

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — run no other step.

Judges one hackathon project idea against one specific event. Answers two
separate questions: is this idea worth spending a hackathon on, and would it
win. Use it after you have an idea and the event rules; use `idea-nebula` to
generate candidate ideas and `swot-analysis` for strategic positioning rather
than event-scoped judging.

| Option | Values | Default | Effect |
|---|---|---|---|
| `idea` | text or file path | required | The project idea being judged |
| `RULES AND CONSTRAINTS` | a filled block (see below) | required | The event's rules; without it the skill stops and asks |
| `--category NAME` | prize category being targeted | best overall | Reshapes the rubric toward that category |

## Required input: the RULES AND CONSTRAINTS block

The user supplies this. Do not guess any field, do not substitute a typical
value, and do not proceed on a partially filled block for fields that change
the rubric (duration, mandated tech, pre-work rules, published rubric, prize
category). If the block is absent or those fields are blank, output the
template below, name exactly which fields are missing, and stop.

```
RULES AND CONSTRAINTS
- Duration and schedule:          (e.g. 36h, Fri 6pm – Sun 6am, demos Sun 10am)
- Theme:
- Mandated sponsor APIs or tech:
- Team size cap:
- Build-during-event vs pre-work allowed:
- Submission requirements:        (repo, video length, deck, deployed URL)
- Published judging rubric + weights: (verbatim, or "none published")
- Prize categories:
- Targeted category:
```

Fields that are genuinely unknowable to the user (e.g. the judging panel's
composition) are recorded as unknown and carried into the output as an
evidence gap — never silently filled.

## What a typical hackathon involves

Reason from this baseline only where the rules are silent, and say when you
are doing so.

- **Duration:** 24–48 hours of wall clock, of which 12–20 are productive
  build time after travel, team formation, meals, and sleep.
- **Team:** 1–4 people. Assume the stated team only; no reinforcements.
- **Judging format:** a 2–5 minute live demo plus Q&A, or a science-fair
  table round where judges spend 2–3 minutes per project. Judges see 20–60
  projects and remember a handful.
- **"Done" on stage:** a working path through one scenario, run live or from
  a recorded fallback, that a non-expert recognises as valuable within 30
  seconds.
- **Standard failure modes:** over-scoping (the whole product instead of one
  path); integration hell (an unfamiliar API, auth, or deploy step eating a
  third of the clock); demo-day flakiness (venue wifi, rate limits, cold
  starts, a live model call); pre-work disqualification (committing code
  before the start, or reusing an existing project beyond what the rules
  allow); and submission misses (no video, late repo, missing sponsor tech).

The builder is a senior engineer and can build anything technically
reasonable inside the time budget. **Never recommend learning a new stack** —
a plan that requires it is a Buildability finding, not a suggestion.

## Evidence standard

Every finding and every score must cite build-feasibility evidence, not market
evidence. Admissible evidence:

- **Prior art:** does this exist as a sample app, template, or previous
  hackathon winner you can name? Prior art raises Buildability and lowers
  Differentiation at the same time — report both effects.
- **API availability:** does the required API exist, is access instant or
  does it need approval or a waitlist, and what do its free-tier rate limits
  allow during a live demo?
- **Library for the hard part:** is the hard part a one-line call to an
  existing library, or genuinely unsolved? Either answer is a finding — the
  first threatens Differentiation and technical-judge scores, the second
  threatens Buildability.
- **Data existence:** does the dataset exist, is it accessible without a
  licence negotiation, and is it clean enough to demo on?

Where the evidence does not exist in context, record an **evidence gap**: the
claim it would settle, the cheapest check (one API docs page, one search, one
`npm install` spike), and which score moves if it comes back either way. Never
fill a gap with an assumption presented as fact. If the caller has authorised
external checking, verify gaps and label each result as verified or
unverified.

## Rubric construction

Build the rubric before scoring and state where it came from.

1. **If the event publishes a rubric**, use its criteria and weights
   verbatim, say so, and do not add, rename, or reweight criteria. If a
   concern below has no home in the published rubric, report it as a finding
   outside the score rather than bending the weights.
2. **If it does not**, build one from the six criteria below, state the
   weights you chose and why, and keep them visible in the output.

| Criterion | Scores (1–5) |
|---|---|
| Demoability | A 3-minute live demo with a visible wow moment — something that happens on screen, not a described benefit |
| Buildability | A shippable slice in the stated duration, on stacks the builder already knows; assume zero time to learn one |
| Differentiation | How many of the other teams build this same thing; obvious-idea-plus-obvious-API scores low |
| Judge legibility | A non-expert grasps the value in 30 seconds without the builder explaining the architecture |
| Scope escape hatch | What still demos with 6 hours left and the main integration broken. **An absent hatch is a finding, not a footnote** |
| Rule compliance | Mandated sponsor tech used non-trivially, pre-work rules respected, every submission requirement met |

Suggested default weights when none are published: Demoability 25, Judge
legibility 20, Buildability 20, Differentiation 15, Scope escape hatch 10,
Rule compliance 10. Say that these are this skill's defaults, not the event's.

**Prize categories reshape the rubric.** Score against the specific targeted
category, not a generic best-overall. A sponsor-API prize raises Rule
compliance and the sponsor judge's weight; a technical prize raises the hard
part and lowers Judge legibility; a social-impact prize raises legibility and
problem realism. State the reshaping explicitly.

## The judging panel

Simulate the panel the rules imply as four separate scorers, dispatched in
fresh parallel contexts so they do not see each other's output. Prohibit
writes, further agents, and — unless external checking was authorised —
network access. If a judge's role is blocked, report incomplete panel
coverage rather than averaging over the gap.

| Judge | Incentive | Asks |
|---|---|---|
| Sponsor engineer | Their API shown used well | Is our API load-bearing or a decorative one-line call? |
| VC / business judge | A legible pitch and a real problem | Who has this problem, would they use it, is the pitch 30 seconds or 3 minutes? |
| Technical judge | Respect for the engineering | Is the hard part actually hard, or a wrapper around someone else's model? |
| Time-pressured generalist | Sees 40 demos, remembers 5 | Did anything on screen surprise me? Will I still recall this at deliberation? |

Each judge scores every rubric criterion independently and writes **one line
of reasoning per criterion**. Then:

- **Report the disagreements.** Where judges split on a criterion is where the
  project is fragile — name the split, the cause, and what would close it.
  Do not average a split away before reporting it.
- **Aggregate** to a panel score using the event's weights (or the stated
  defaults), showing the arithmetic.

## The two verdicts

Score and report these separately. They are different questions: an idea can
be a great weekend and lose, and an idea can win and be miserable to build.

- **Worth spending a hackathon on** — driven by Buildability, Scope escape
  hatch, Rule compliance, and what the builder keeps afterwards (skills,
  reusable code, a thing they wanted to exist).
- **Would it win** — driven by the panel score against the targeted category:
  Demoability, Judge legibility, Differentiation, and the sponsor judge where
  a sponsor prize is targeted.

Each verdict uses the same ladder, and **every verdict cites the single
criterion that decided it**:

| Verdict | Means |
|---|---|
| **BUILD IT** | No supported Critical finding and the deciding criterion scores well |
| **BUILD WITH SCOPE CUTS** | Viable once named cuts land — list the exact cuts |
| **SAME DOMAIN, DIFFERENT DEMO** | The domain holds, this demo does not — name the replacement demo |
| **PICK SOMETHING ELSE** | An unresolvable Critical, or several distinct supported Criticals |

A missing required rules field, or a blocked judge role, yields
`incomplete_coverage` and no verdict — say what is needed.

## Findings

Findings are causal, each with a source location in the idea or rules, a
consequence, an evidence basis from the standard above, and a severity
(Critical / High / Medium / Low). **Report the complete list, never
pre-filtered by severity**, then prioritise up to five substantive changes
with their expected consequence, dependency, and cost in hours. Repeated
mentions of one cause are one finding. A finding without evidence is an
evidence gap, not a failure.

## Output contract

In this order:

1. **The two verdicts** — worth building, and would it win — each with the
   criterion that decided it.
2. **The rubric**, its weights, and where they came from (published verbatim,
   or this skill's defaults), including any category reshaping.
3. **Each judge's scorecard** — per-criterion score and its one line.
4. **The disagreements** — every criterion where judges split, with cause.
5. **The full findings list and evidence gaps** — complete, unfiltered, each
   gap naming its cheapest check and which score it moves.
6. **The minimum demoable slice** — the smallest thing that survives on stage.
7. **An hour-by-hour build plan** fitted to the stated duration, with the
   escape-hatch decision point marked at the 6-hours-remaining mark and the
   submission requirements as their own blocks.

Do not soften a finding to approve an idea or sharpen one to look decisive.
Where the rules were silent and the typical-hackathon baseline was used
instead, say so at the point of use.
