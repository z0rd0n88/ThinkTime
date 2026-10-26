# Ranking & synthesis: blind duels, barbell report

The orchestrator (`../SKILL.md` Stages 3 & 5) uses this reference. Not loaded unless the skill is running.

## Why this protocol exists

- Position bias flips roughly 1/3 of GPT-4-class pairwise verdicts on order swap, and far more for weaker judges (MT-Bench: 33.8% to 76.2% inconsistency by model) → every duel is judged in BOTH orders; only order-consistent wins count. The same paper prescribes exactly this remedy and calling an inconsistency a tie.
- LLM judges have been reported to self-prefer by up to +25% win rate (MT-Bench, which disclaims being able to attribute that to self-enhancement; the causal account in arXiv 2404.13076 runs through self-recognition of the text, not the label) → candidates are presented with no generator attribution and neutral IDs.
- LLMs assign pointwise 1 to 10 scores arbitrarily and self-evaluate unreliably → pointwise scoring is banned; differentiation must be justified as distance from a named modal region.
- Averaging a ranking destroys the sharp edges a shortlist exists to find → the output is a barbell (Safe Demos + Swing Demos), never one merged list.

What differs from `idea-nebula`: the modal region here *can* be checkable
rather than a guess about an idea space, because `recon` goes and looks. It is
the obvious reading of the theme, the mandated tech's own quickstart path, and
what `recon` found prior entrants already built. That third part is what makes
it evidence; where `recon` supplied nothing, the region is a guess like any
other and the report says so.

## Building the ranker prompt

Pool all generator candidates. Assign each a neutral ID (`C1`, `C2`, …) in shuffled order (do NOT group by generator). Strip every trace of which generator produced what. Keep the attribution map to yourself for the final report.

Attribution-stripping is not information-theoretic blinding: the `Mechanism`
field's vocabulary identifies its generator to a reader who knows the roster.
The brief therefore instructs the ranker not to use mechanism provenance, and
the report calls the standings attribution-stripped rather than blind.

Pass the pooled candidates (full contract fields each) into the template below. One `Agent` call, `subagent_type: general-purpose`.

## Ranker brief template

````
You are ranking candidate projects for ONE specific hackathon. You have no prior conversation context. You did not generate these candidates and must not add new ones. You may not use the network, write files, or spawn agents.

{{UNTRUSTED_DATA_PARAGRAPH}}

## THE EVENT
```
Event: {{EVENT_NAME}}
Theme: {{THEME}}
Mandated tech: {{MANDATED_TECH}}
Productive build hours available: {{PRODUCTIVE_HOURS}} PERSON-hours (includes the submission artifacts inside each candidate's own estimate)
Team and stacks already known: {{TEAM_AND_STACKS}}
Pre-work rules: {{PREWORK_RULES}}
Submission requirements: {{SUBMISSION_REQUIREMENTS}}
Published judging rubric and weights: {{RUBRIC}}
Prize categories: {{PRIZE_CATEGORIES}}
Targeted prize category: {{TARGET_CATEGORY}}
```

## CROWDED GROUND FOUND BY RECON
```
{{RECON_CROWDED_GROUND}}
```
(If empty, say so in step 2 and name the modal region from the theme and the mandated tech alone, marking it unverified.)

## CANDIDATE POOL
```
{{POOLED_CANDIDATES}}
```

## PROTOCOL: follow in order

1. DEDUPE. Merge near-duplicate candidates into one entry, noting the merge ("C3+C7"). Flag merged entries MERGED. For a merge, keep the fuller set of contract fields; where two disagreed, keep the larger hours estimate and the narrower minimum slice, and say which you kept. Do not infer or use which process produced any candidate; mechanism wording is evidence about the idea, not about its author.

2. NAME THE MODAL REGION. In 2 to 4 sentences, describe what a large share of entrants will ship: the obvious reading of this theme, crossed with the mandated tech's quickstart path, plus the crowded ground above. Any pool candidate inside it gets flagged MODAL. MODAL is a report flag, not a prune criterion.

3. PRUNE to at most 8 finalists, in this order:
   a. Drop any candidate with no demo moment, or whose minimum slice plainly exceeds the productive-hours budget with no smaller version, or whose only build path breaks the pre-work rules above.
   b. Drop a candidate that is dominated: another is at least as demoable AND at least as shippable in the hours budget AND at least as distant from the modal region.
   c. If more than 8 remain, keep the 8 with the strongest demo moments, breaking ties toward distance from the modal region. This is the only step that cuts a candidate no rule condemned, and it must be labelled as such.
   Say which candidates went at which step, one line each, naming the step.

4. DUELS. Round-robin over the finalists. For each pair, judge "which is the stronger entry for THIS event in the targeted category: demo moment that lands in a noisy room × shippability inside the productive-hours budget × distance from the modal region × substantive use of the mandated tech" TWICE: once as (A vs B), once as (B vs A). Re-derive the verdict fresh the second time, do not copy it. Order-consistent verdict = win; inconsistent = draw. Record both verdicts for every pair.
   Where a published rubric and weights are given above, weight those four factors toward it: a rubric that puts most of its weight on sponsor-tech use and technical depth makes distance from the modal region a tie-breaker rather than a co-equal term. Say in one line how you weighted them.
   Where the event mandates no tech, drop the fourth factor and run on the remaining three.
   Standings are W-D-L. Draws are expected to be common, so rank by wins, then by fewest draws, then by the smaller hours estimate; state the tie-break you used wherever it decided an order.

5. DIFFERENTIATION JUSTIFICATION. For each finalist, one line: its distance from the modal region you named in step 2, and why. No bare numbers.

6. BARBELL SPLIT. Divide the finalists:
   - SAFE DEMOS: strong duel record, the slice fits the hours budget with room, the escape hatch is real. Nearer the modal region is acceptable here; shipping something is the point.
   - SWING DEMOS: high distance from the modal region, higher ceiling, real risk of nothing working on stage. Kept BECAUSE they are non-obvious.
   A candidate whose hours exceed the budget can only be a Swing, never Safe. A candidate flagged MODAL that also has a weak duel record is still assigned to an arm: MODAL alone does not exclude it from Safe, where being near the region is acceptable.
   Do not force a fixed split, but neither list may be empty unless the pool genuinely lacks one side (say so if so). This split is provisional: Stage-4 feasibility flags can move a candidate between arms, and the orchestrator owns that re-split.

7. STAGE RISK. For each finalist, one line naming the single most likely way it shows nothing on demo day, and whether its stated escape hatch covers that.

Return exactly:

### Modal region
### Pruned
(one line per dropped candidate, naming which prune step dropped it)
### Duels
(table: pair | verdict as A vs B | verdict as B vs A | counted as win/draw)
### Duel standings
(table: ID | Title | W-D-L | W+D+L total | one-line differentiation justification)
### Safe demos
### Swing demos
### Stage risk
(table: ID | most likely stage failure | hatch covers it? yes/no/partial)

No preamble.
````

The orchestrator checks that every finalist's `W+D+L` equals `n-1`. A mismatch
means the duel table was truncated; re-run rather than reporting partial
standings.

## Report structure (Stage 5)

Assemble (you, the orchestrator. No extra agent needed) with EXACTLY these headings, in this order:

```
# Hackathon Idea Nebula: {{EVENT_OR_THEME}}

## Executive Summary
3 to 5 sentences: the event as recorded (duration, mandated tech, targeted category), generators run and how many candidates each returned, pool size, whether a feasibility check ran and over how many finalists, the single strongest Safe Demo and the single most interesting Swing Demo. State the productive-hours budget, its unit, and its arithmetic. Name any gating-adjacent field left blank and anything marked UNANCHORED.

## Safe Demos
Ranked by duel standings. Per candidate: **Title**, pitch, W-D-L, demo moment, mandated-tech use, minimum slice + hours vs budget (the feasibility agent's estimate where one exists, with the generator's alongside), escape hatch, differentiation justification, feasibility verdict one-liner (or UNVERIFIED / NOT CHECKED / flags).

## Swing Demos
Same fields. Preface: "Higher ceiling, real risk of nothing working on stage. Kept because they are far from what the room will build. Expect some to die in the first six hours."
If either arm was emptied by KILLs, say so in that arm's place and do not back-fill from the other.

## Killed
Any candidate a hard threshold removed, with its reason and link. This is the only place a KILLed candidate is written out; the evidence table carries its flag and points here. Never drop one silently. A closed path the user can see is worth more than a shorter list.

## Feasibility Evidence
If --no-feasibility, or every Stage-4 agent failed or lacked web access, print this banner FIRST: "⚠️ UNCHECKED: no live feasibility evidence was gathered. Ranking candidates on demoability and distinctiveness without checking API access, rate limits and prior art is actively misleading: the two things that kill a hackathon entry are that it could not be built in time and that thirty other teams built it too, and neither was checked. Verify before committing a weekend." With --no-feasibility, add: "Every KILL threshold was skipped, so a candidate that cannot legally be entered may appear above."
If only some agents failed, or `recon` failed while Stage 4 ran, print instead: "⚠️ PARTIAL: <which> could not be checked." Then print the table either way, so an UNCHECKED run still shows what was and was not attempted.
Table: Candidate | Access (obtainable before the clock? + link) | Live-demo limits | Hard part (library/sample/unsolved + link) | Prior art & crowding score | Submittability | Hours vs budget | Flags (KILL / DOWNGRADE / TIGHT / UNVERIFIED / NOT CHECKED / UNANCHORED / MODAL / CONTRACT GAP).

## The Room (what we refused to rank as distinctive)
The ranker's step-2 modal region, verbatim, attributed as derived from pages `recon` fetched rather than as this skill's own finding — and marked unverified where `recon` supplied no crowded ground. Where --banlist ran, also print the round-1 region used for the exclusion and note that the two were named by different agents. This documents what a large share of entrants will ship, and what every candidate here was ranked against.

## Convergence & Disagreement
Candidates ≥2 generators reached independently, using the attribution map (the ranker's MERGED flag cannot tell cross-generator convergence from two near-duplicates out of one generator; only the map can, so state which kind each merge was). Reveal the map here. Add any productive disagreement, e.g. recon's prior art contradicts a tails candidate's distinctiveness claim. Note that convergence between generators is weak evidence that other entrants will converge there too.

## Validate Next
For the top Safe Demo and the top Swing Demo: the cheapest real check before committing: a thirty-minute spike against the actual API to confirm access and limits, or one `npm install`/`pip install` and a hello-world against the hard part. A spike beats every link in this report. Where any access row is UNVERIFIED, the first check is one question to the organisers.

## Next: Judge It
One line: run `hackathon-judge` on your pick with the SAME rules block for the worth-entering and would-it-win verdicts, one idea per run. This report deliberately contains neither.

## Final Cut Is Yours
One fixed paragraph: "This shortlist is a funnel, not a verdict. In the RCT that actually built the ideas out, LLM pre-execution scores were weak-to-negative predictors of executed quality, and novelty advantages evaporated in execution. At a hackathon that reckoning arrives in 36 hours, in public. The hours estimates here are estimates, not measurements. Pick with your own judgment, and between the barbell's two ends use the rule you can live with on Sunday morning: take a Safe Demo if finishing something matters more to you than placing, take a Swing if a near-miss is acceptable and you would rather have built the interesting one. Either way, spike the hard part before you commit the weekend, and set a time on Saturday at which you fall back to the escape hatch."
```

The report states no verdict and never says a candidate will win. Naming the
top-ranked Safe and Swing Demo is a report of duel standings inside this pool,
not a prediction about the room, and the report says so where it names them.
Standings are attribution-stripped, not blind.
