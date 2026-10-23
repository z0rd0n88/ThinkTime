# Rubric, duels, judge panel, verdicts, report

The orchestrator (`../SKILL.md` Stages 1, 4, 6, 7) uses this reference. Not loaded unless the skill is running.

## Why this protocol exists

- Position bias flips roughly 1/3 of LLM-judge pairwise verdicts on order swap (MT-Bench, arXiv 2306.05685) → every duel is judged in BOTH orders; only order-consistent wins count.
- Claude-class judges self-prefer by up to +25% → ideas are ranked BLIND, with neutral IDs and no generator attribution.
- Pointwise 1–10 self-scores are assigned arbitrarily → banned for ranking. The judge panel scores criteria (Stage 6) because the event's own rubric demands numbers, but those are per-criterion with written reasoning, never a self-asserted overall quality score.
- "Worth building" and "would win" are different questions with different answers → two separate rankings, never averaged.
- Averaging a panel destroys the signal a panel exists to produce → disagreements are reported as findings.

## Rubric provenance (Stage 1)

State which of these applied, in the report, in one line:

1. **Published rubric** → criteria and weights verbatim. No additions, no substitutions, no reweighting. If the event publishes criteria without weights, say so and weight them equally.
2. **No published rubric** → the fallback below, labelled as this skill's defaults.

### Fallback rubric

| Criterion | Weight | What it measures |
|---|---|---|
| Demoability | 25% | A 3-minute live demo with a visible wow moment, on venue wifi, without a code walkthrough. |
| Buildability | 25% | A shippable slice inside the stated duration, in a stack the team already knows. No time to learn one. |
| Differentiation | 15% | How many other teams build this same thing this weekend. Saturation is scored here. |
| Judge legibility | 15% | A non-expert grasps the value in 30 seconds, without domain context. |
| Scope escape hatch | 10% | What still demos at 6 hours to deadline with the hardest integration broken. Absent hatch scores 0 and is reported as a finding. |
| Rule compliance | 10% | Mandated sponsor tech used non-trivially; pre-work rules respected; submission requirements satisfiable. |

**Prize-category reshaping.** Score against the targeted category, not "best overall": a sponsor-API prize raises Rule compliance and the non-trivial-use test; a social-impact prize raises Judge legibility; a technical prize raises the hard-part test inside Demoability and discounts wrappers. State the reshaping applied.

## Duel protocol (Stage 4 — run twice, once per ranking)

Pool all generator ideas, assign neutral IDs (`I1`, `I2`, …) in shuffled order (do NOT group by generator), strip every trace of which generator produced what. Pass the pooled ideas with full contract fields into the template below, once with the buildability duel question and once with the winnability one. `subagent_type: general-purpose`.

```
You are ranking a pool of candidate hackathon projects. You have no prior conversation context. You did not generate these and must not add new ones.

## THEME
{{TOPIC}}

## RULES AND CONSTRAINTS
{{RULES_BLOCK}}

## TEAM AND STACK
{{TEAM}} builder(s), senior level, stack: {{STACK}}. There is no time to learn anything new; an idea requiring that is a failed idea.

## RUBRIC IN FORCE
{{RUBRIC}}

## IDEA POOL
{{POOLED_IDEAS}}

## THE ONE QUESTION YOU ARE RANKING ON
{{DUEL_QUESTION}}

## PROTOCOL — follow in order

1. DEDUPE. Merge near-duplicates into one entry, noting the merge ("I3+I7"). Independent convergence is signal — flag merged entries CONVERGENT.
2. NAME THE MODAL REGION. In 2–4 sentences, describe the cluster any generic hackathon brainstorm on this theme would produce. Flag every pool idea inside it MODAL.
3. PRUNE to at most 8 finalists. Drop an idea only if dominated: another is at least as strong on your ranking question AND at least as rule-compliant AND at least as reachable for this team. One line per pruned idea.
4. DUELS. Round-robin over the finalists. For each pair, judge your one ranking question TWICE: once as (A vs B), once as (B vs A) — re-derive the verdict fresh the second time, do not copy it. Order-consistent verdict = win; inconsistent = draw. Record standings as W-D-L.
5. JUSTIFY. One line per finalist: for the buildability question, the specific thing that could leave them with nothing on stage; for the winnability question, its distance from the modal region you named and why that distance earns points under the rubric. No bare numbers.
6. SPLIT. Divide the finalists into SAFE DEMOS (strong record, plausibly shippable, nearer the modal region acceptable) and TROPHY SWINGS (high variance, far from the modal region, kept BECAUSE they are non-obvious). Neither list may be empty unless the pool genuinely lacks one side — say so if so.

Return exactly:

### Modal region
### Pruned
### Standings
(table: ID | Title | W-D-L | justification)
### Safe demos
### Trophy swings

No preamble.
```

## Judge panel (Stage 6)

Four agents, in parallel, each scoring EVERY finalist against EVERY rubric criterion with one line of reasoning per criterion. No judge sees another's output. `subagent_type: general-purpose`.

```
You are one judge on a hackathon panel. You have no prior conversation context and you will not see the other judges' scores. Score independently — do not hedge toward a consensus you cannot see.

## YOUR SEAT AND INCENTIVES
{{JUDGE_PERSONA}}

## RULES AND CONSTRAINTS
{{RULES_BLOCK}}

## RUBRIC — score against these criteria and weights exactly
{{RUBRIC}}

## FINALISTS
{{FINALISTS}}

## TASK
For each finalist, score every rubric criterion on that criterion's own scale, with ONE line of reasoning per criterion written in your seat's voice. Then give the finalist a weighted total using the stated weights. Finally, name the one finalist you would vote for and the one you would eliminate first, in one line each.

Return exactly:

### Scorecard: <finalist title>
(table: Criterion | Score | Weight | One-line reasoning)
**Weighted total**: <n>
(repeat per finalist)
### My vote
### First elimination

No preamble.
```

### The four seats (`{{JUDGE_PERSONA}}`)

| Seat | Incentive | Scores harshly when |
|---|---|---|
| **Sponsor engineer** | Their API must be used in a way that makes it look good. | The mandated tech is a decorative call, swappable for any competitor, or used below its interesting surface. |
| **Business judge** | Is the problem real and is the pitch legible to someone who writes checks. | There is no identifiable user, the pitch needs a diagram, or the value takes 90 seconds to state. |
| **Technical judge** | Is the hard part actually hard, or a wrapper. | A library or one API call owns the whole difficulty, and the team's own contribution is glue. |
| **Time-pressured generalist** | Sees 40 demos, remembers 5. | Nothing visible happens in the first 20 seconds, or the demo looks like the three before it. |

### Aggregation and disagreement

Aggregate the four weighted totals using the event's weights to a panel score per finalist. Then extract, per finalist, every criterion where the judges' scores span more than a third of the scale, and report it as a fragility: name the two seats that split and the one line each wrote. **Do not smooth a split into an average and move on.** A project the technical judge loves and the generalist forgets is a specific, fixable problem.

## Verdict ladder

Each candidate gets one verdict on each of the two questions, and every verdict cites the criterion that decided it.

| Verdict | Means |
|---|---|
| **BUILD IT** | Ships in the window and scores top of the panel. |
| **BUILD WITH SCOPE CUTS** | Viable only smaller — **name the cuts**, as specific removals. |
| **SAME DOMAIN, DIFFERENT DEMO** | The space is right, the demo is wrong — **name the replacement demo**. |
| **PICK SOMETHING ELSE** | The deciding criterion cannot be fixed inside the duration or the rules. |

A RULE-RISK BLOCK flag from Stage 5 forces **PICK SOMETHING ELSE** regardless of score, and the report says which rule.

## Report structure (Stage 7)

Assemble it yourself — no extra agent — with EXACTLY these headings, in this order.

```
# Hackathon Idea Nebula: {{TOPIC}}

## Verdict 1 — Worth spending the event on?
Top candidates with their buildability verdict from the ladder, each citing the criterion that decided it. 3–5 sentences of summary, then the per-candidate lines.

## Verdict 2 — Would it win?
The same candidates with their winnability verdict and panel score, each citing the deciding criterion. State plainly where the two verdicts disagree — a great weekend that loses, or a winner that is miserable to build — because that disagreement is the decision the human actually has to make.

## Rubric In Force
The criteria and weights, and one line of provenance: published-verbatim, or this skill's defaults. Note the prize-category reshaping applied.

## Judge Scorecards
Each seat's table, verbatim, per finalist. Four seats; a failed seat shows as [NO SCORE].

## Where The Judges Split
Per finalist: every criterion with a span over a third of the scale, the two seats, their two lines. Fragility, not noise.

## Safe Demos
Ranked by the buildability standings. Per candidate: pitch — wow moment — hard part — W-D-L on both rankings — panel score — escape hatch — feasibility flags.

## Trophy Swings
Same fields. Preface: "High-variance bets kept because they are far from the modal region — expect most to die under the duration."

## Feasibility Evidence
Table: Idea | Credential/availability (quoted + link) | Rate limits & latency | Library owning the hard part | Prior-art saturation | Flags (DOWNGRADE / WRAPPER / SATURATED / RULE-RISK / UNVERIFIED).
If --no-feasibility, or every Stage-5 check failed, replace the table with: "⚠️ UNGROUNDED — no live feasibility evidence was gathered. A hackathon plan without confirmed API availability, rate limits and library coverage is a guess; the integration you have not checked is the one that eats the night. Verify before committing."

## Modal Region (what we refused to score as differentiated)
The rankers' step-2 descriptions — this is what 15 other teams are building.

## All Findings
Every finding from every stage, complete and unfiltered, most severe first. Never trimmed to the important ones, never replaced with a count. An absent escape hatch is a finding. A trivial mandated-tech use is a finding. A wrapper hard part is a finding.

## Evidence Gaps
Every unsupplied RULES field, every capability that could not be confirmed live, every judge seat that failed, every UNVERIFIED feasibility check. Say what would close each gap.

## Minimum Demoable Slice
For the recommended pick: the smallest thing that demos end to end, as a bulleted list where each bullet is a thing that exists when it is done. Then a **Not Doing** list with a reason per line — the trade-offs made explicit.

## Hour-By-Hour Plan
A table fitted to the stated duration, in real clock hours from the stated start, with sleep and ceremonies subtracted: Hour | Goal | Done when. Include a hard scope-cut checkpoint at T-6h that names what gets dropped, and a demo rehearsal block before the submission deadline.

## Final Cut Is Yours
One fixed paragraph: "This is a funnel, not a verdict. Simulated judges are a model of a panel, not the panel; pre-build scores are weak predictors of what survives contact with the venue wifi. Pick with your own judgment — especially where the two verdicts disagree."
```

Then suggest the follow-ons: `ThinkTime:idea-refine` to sharpen the chosen pick, and `idea-autopsy:stress-test-idea` to attack it before the clock starts.
