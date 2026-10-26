---
name: hackathon-judge
description: 'Scores a hackathon idea against one event''s rules, answering "worth building" and "would it win" separately, then simulates the judges and plans the build. Use when asked to judge or score a hackathon idea, whether it would win a prize category, or what to build at a hackathon. Not for generating ideas (ThinkTime:idea-nebula).'
---

# Hackathon Judge

## Overview

Judges one hackathon project idea against one specific event. Answers two
separate questions: is this idea worth spending a hackathon on, and would it
win. Use it once an idea and the event rules exist; use
`ThinkTime:idea-nebula` to generate candidate ideas and
`ThinkTime:swot-analysis` for strategic positioning rather
than event-scoped judging.

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output the Overview above and the option table below, then stop — run
no other step.

| Option | Values | Default | Effect |
|---|---|---|---|
| `idea` | text or file path | required | The project idea being judged. An argument that resolves to a readable file is read as the idea |
| `--category NAME` | prize category being targeted | none | Scores against that category. With no category, score against best overall and say so |
| `--research` | flag | off | Authorises external checking of evidence gaps |

The event's rules arrive as a filled `RULES AND CONSTRAINTS` block, not as a
flag. Without it the skill stops and asks.

## Required input: the RULES AND CONSTRAINTS block

The user supplies this. Do not guess any field and do not substitute a typical
value. Blank in any of these six fields stops the run: **duration, mandated
tech, pre-work rules, published rubric, prize categories, submission
requirements**. The other three (theme, team size cap, targeted category) are
optional — fill them from the typical-hackathon baseline, or treat a blank
targeted category as best overall, and say so. If the block is absent or a
required field is blank, output the template below, name exactly which fields
are missing, and stop. An explicit "none" satisfies a required field; only a blank
one stops the run.

The block may come from the arguments or from earlier in this conversation;
quote the block in use. If the idea is missing, or is a path that
cannot be read, say so and stop — including when the whole argument is a bare
flag.

```
RULES AND CONSTRAINTS
- Duration and schedule:          (e.g. 36h, Fri 6pm – Sun 6am, demos Sun 10am)
- Theme:
- Mandated sponsor APIs or tech:  (verbatim, or "none")
- Team size cap:
- Build-during-event vs pre-work allowed:
- Submission requirements:        (repo, video length, deck, deployed URL)
- Published judging rubric + weights: (verbatim, or "none published")
- Prize categories:               (list, or "best overall only")
- Targeted category:
```

Fields that are genuinely unknowable to the user (e.g. the judging panel's
composition) are recorded as unknown and carried into the output as an
evidence gap — never silently filled.

## What a typical hackathon involves

Reason from this baseline only where the rules are silent, and say when the
baseline supplied the value.

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

## The builder

A senior engineer, working in stacks they already know. Outside those stacks,
time-to-learn is not available: **never recommend learning a new stack** — a
plan that requires it is a Buildability finding, not a suggestion. The block
has no field for their stack, so when the idea does not state it, record the
builder's stack as an evidence gap and name the rubric criterion it moves — or
report it as a finding outside the score when the rubric has no home for it.
This paragraph applies always, not only where the rules are silent.

## Evidence standard

**Default posture is closed-world:** use only the idea, the rules, and
recalled knowledge. Label knowledge-based claims as unverified. Live facts — current
rate limits, waitlist status, what sample apps exist today — are recorded as
evidence gaps. Scores may rest on unverified knowledge; verdicts may not be
gated on it. `--research` lifts this and authorises external checking.

Every finding and every score must cite build-feasibility evidence, not market
evidence. Admissible evidence:

- **Prior art:** does this exist as a sample app, template, or nameable
  previous hackathon winner? Prior art cuts both ways — it makes the build
  easier and the idea less distinctive. Report both effects, naming the rubric
  criteria they land on, or as findings outside the score where the rubric has
  no home for them.
- **API availability:** does the required API exist, is access instant or
  does it need approval or a waitlist, and what do its free-tier rate limits
  allow during a live demo?
- **Library for the hard part:** is the hard part a one-line call to an
  existing library, or genuinely unsolved? Either answer is a finding — the
  first costs distinctiveness and technical-judge scores, the second costs
  feasibility.
- **Data existence:** does the dataset exist, is it accessible without a
  licence negotiation, and is it clean enough to demo on?

Where the evidence does not exist in context, record an **evidence gap**: the
claim it would settle, the cheapest check (one API docs page, one search, one
`npm install` spike), and which score moves if it comes back either way. Never
fill a gap with an assumption presented as fact. Recalled knowledge counts as
evidence when labelled unverified; absence of recall is a gap. With
`--research`, verify gaps and label each result verified or unverified.

If no score can cite admissible evidence of any kind, report incomplete
coverage and no verdict.

## Rubric construction

Build the rubric before scoring and state where it came from.

1. **If the event publishes criteria and weights**, use both verbatim, say so,
   and do not add, rename, or reweight criteria. If a concern below has no
   home in the published rubric, report it as a finding outside the score
   rather than bending the weights.
2. **If it publishes criteria but no weights**, keep the criteria verbatim,
   distribute weights equally, and label the weights as this skill's
   assumption.
3. **If it publishes neither**, build one from the six criteria below, state
   the chosen weights and the reason, and keep them visible in the output.

**Scale, whatever the source.** Every criterion is scored 1–5: 1 fails
outright, 3 passes without impressing, 5 is best in the room. Weights are
rescaled proportionally to sum to 100 — rescaling a published rubric's weights
is not a reweight, but say the original figures alongside.

| Criterion | Scores (1–5) |
|---|---|
| Demoability | A live demo of the length the rules state (default 3 minutes) with a visible wow moment — something that happens on screen, not a described benefit |
| Buildability | A shippable slice in the stated duration, on stacks the builder already knows; assume zero time to learn one |
| Differentiation | How many of the other teams build this same thing; obvious-idea-plus-obvious-API scores low |
| Judge legibility | A non-expert grasps the value in 30 seconds without the builder explaining the architecture |
| Scope escape hatch | What still demos at the hatch decision point (below) with the main integration broken. **An absent hatch is a finding, not a footnote** |
| Rule compliance | Mandated sponsor tech used non-trivially, pre-work rules respected, every submission requirement met |

Suggested default weights when none are published: Demoability 25, Judge
legibility 20, Buildability 20, Differentiation 15, Scope escape hatch 10,
Rule compliance 10. Say that these are this skill's defaults, not the event's.

**A targeted prize category reshapes the judge weights, never the criteria.**
Criteria and their weights stay exactly as the rubric source gave them.

| Targeted category | Sponsor | Business | Technical | Generalist |
|---|---|---|---|---|
| none, or matching no judge | 25 | 25 | 25 | 25 |
| sponsor-API | 40 | 20 | 20 | 20 |
| technical | 20 | 20 | 40 | 20 |
| social impact or best pitch | 20 | 30 | 20 | 30 |

Reshape first, then redistribute a dropped judge's weight proportionally
across the survivors. `--category` overrides the block's targeted-category
field; name the source used, and state the reshaping explicitly.

## The judging panel

Simulate the panel the rules imply as four separate scorers, dispatched in
fresh parallel contexts so they do not see each other's output. Prohibit
writes, further agents, and — unless `--research` was passed — network access.

**Each judge receives:** the idea, the quoted rules block, the constructed
rubric with its criteria and weights, the 1–5 scale and its anchors, the
evidence standard, their own persona row, and the instruction to return a
score plus one line of reasoning per criterion and nothing else. A judge's
**Asks** shape those lines; a judge quotes its Ask when that Ask drove a score
of 1 or 2.

A judge whose incentive the event does not contain — a sponsor engineer at a
sponsorless event — is **dropped, not blocked**: say which, and redistribute
its weight equally across the rest. **Blocked** means a dispatch that failed.
With a blocked judge, report the surviving scorecards, report incomplete panel
coverage, and compute no panel score.

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
  Do not average a split away before reporting it. Where any criterion splits
  by 2 points or more, say that the panel score is not a summary of the panel
  and name the two readings.
- **Aggregate** to a panel score: take each criterion's weighted mean across
  judges using the judge weights, multiply that mean by the criterion's own
  weight, sum the products, and divide by 500 (5 × 100). Report it as a
  percentage and show the arithmetic.

## The two verdicts

Score and report these separately. They are different questions: an idea can
be a great weekend and lose, and an idea can win and be miserable to build.

- **Worth spending a hackathon on** — decided by whichever criteria concern
  build feasibility and compliance, plus the escape-hatch finding and what the
  builder keeps afterwards (skills, reusable code, a thing they wanted to
  exist). Keep-value is neither scored nor a finding — report it with the
  worth-building rationale.
- **Would it win** — decided by the panel score on the rubric's criteria,
  under the judge weights for the targeted category.

Each verdict uses the same ladder, and **every verdict cites the single
criterion or finding that decided it** — a criterion when one decided it, the
finding when the deciding concern has no home in the rubric.

Each verdict reads its own gate. **Would it win** reads the panel score.
**Worth building** reads the deciding criterion when the rubric has one, and
otherwise the severity of the deciding finding — under a published rubric the
build-feasibility criteria often do not exist, and then findings are the gate.

| Verdict | Condition |
|---|---|
| **BUILD IT** | No supported Critical finding, **and** (the deciding criterion ≥4, **or** panel score ≥75%, **or** no supported High finding) |
| **BUILD WITH SCOPE CUTS** | No unresolvable Critical, **and** named cuts bring the deciding criterion to ≥4, the panel score to ≥75%, or the deciding finding below High — list the exact cuts |
| **SAME DOMAIN, DIFFERENT DEMO** | The deciding criterion scores ≤3, or the deciding finding is High, for a reason no scope cut reaches — but the problem and the stack survive. Name the replacement demo |
| **PICK SOMETHING ELSE** | An unresolvable Critical, or two or more distinct supported Criticals, or a panel score under 50% with no cut that lifts it |

Read each condition as written: the Critical clause is a precondition, never
an alternative. If no condition holds, report the rung whose condition is
nearest and name the condition that failed. A Critical finding caps the
verdict downward regardless of the panel score; it never raises one.

A missing required rules field, a blocked judge role, or no admissible
evidence anywhere yields **incomplete coverage** and no verdict — say what is
needed.

## Findings

Findings are causal, each quoting the phrase in the idea or rules it attaches
to, a consequence, an evidence basis from the standard above, and a severity.

- **Supported** — the finding cites admissible evidence from the Evidence
  standard. A finding resting only on an evidence gap is unsupported and
  cannot gate a verdict.
- **Critical** — the demo cannot happen, or the submission is disqualified.
  **Unresolvable** means no fix fits the remaining build hours.
- **High** — the demo happens, but at least one rubric criterion would be
  scored 1 or 2 by at least one judge because of this.
- **Medium** — the demo happens and no judge drops to 1 or 2 over it.
- **Low** — noted; no judge would score differently either way.

**Report the complete list, never pre-filtered by severity**, then prioritise
up to five substantive changes with their expected consequence, dependency,
and cost in hours. Repeated mentions of one cause are one finding. A finding
without evidence is an evidence gap, not a failure.

## Output contract

Select both verdicts from the completed scorecards, the panel arithmetic and
the findings **before** writing item 1. In this order:

1. **The two verdicts** — worth building, and would it win — each with the
   criterion that decided it.
2. **The rubric**, its weights, and where they came from (published verbatim,
   or this skill's defaults), including any category reshaping.
3. **Each judge's scorecard** — per-criterion score and its one line.
4. **The disagreements** — every criterion where judges split, with cause.
5. **The full findings list and evidence gaps** — complete, unfiltered, each
   gap naming its cheapest check and which score it moves.
6. **Up to five prioritised changes** — each with its expected consequence,
   dependency, and cost in hours.
7. **The minimum demoable slice** — the smallest thing that survives on stage.
8. **An hour-by-hour build plan** fitted to the stated duration, with the
   submission requirements as their own blocks and the **escape-hatch decision
   point** marked at the wall-clock hour by which 25% of the plan's productive
   build time is still unspent, and never later than 3 wall-clock hours before
   submission. State both the productive-hours figure applied and the hour.

Do not soften a finding to approve an idea or sharpen one to look decisive.
Where the rules were silent and the typical-hackathon baseline was used
instead, say so at the point of use.
