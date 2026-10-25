# Ranking & synthesis — blind duels, barbell report

The orchestrator (`../SKILL.md` Stages 3 & 5) uses this reference. Not loaded unless the skill is running.

## Why this protocol exists

- Position bias flips roughly 1/3 of LLM-judge pairwise verdicts on order swap (MT-Bench) → every duel is judged in BOTH orders; only order-consistent wins count.
- Claude-class judges self-prefer by up to +25% win rate → candidates are presented BLIND (no generator attribution) with neutral IDs.
- LLMs assign pointwise 1–10 scores arbitrarily and self-evaluate unreliably → pointwise scoring is banned; differentiation must be justified as distance from a named modal region.
- Averaging a ranking destroys the sharp edges a shortlist exists to find → the output is a barbell (Safe Demos + Swing Demos), never one merged list.

The one thing that differs from `idea-nebula`: the modal region here is not a guess about an idea space. It is concrete and checkable — the obvious reading of the theme, the mandated tech's own quickstart path, and what `recon` found prior entrants already built. Name it from evidence where `recon` supplied any.

## Building the ranker prompt

Pool all generator candidates. Assign each a neutral ID (`C1`, `C2`, …) in shuffled order (do NOT group by generator). Strip every trace of which generator produced what — keep the attribution map to yourself for the final report. Pass the pooled candidates (full contract fields each) into the template below. One `Agent` call, `subagent_type: general-purpose`.

## Ranker brief template

```
You are ranking candidate projects for ONE specific hackathon. You have no prior conversation context. You did not generate these candidates and must not add new ones. You may not use the network, write files, or spawn agents.

## THE EVENT
Theme: {{THEME}}
Mandated tech: {{MANDATED_TECH}}
Productive build hours available: {{PRODUCTIVE_HOURS}}
Team and stacks already known: {{TEAM_AND_STACKS}}
Targeted prize category: {{TARGET_CATEGORY}}

## CROWDED GROUND FOUND BY RECON
{{RECON_CROWDED_GROUND}}
(If empty, say so in step 2 and name the modal region from the theme and the mandated tech alone, marking it unverified.)

## CANDIDATE POOL
{{POOLED_CANDIDATES}}

## PROTOCOL — follow in order

1. DEDUPE. Merge near-duplicate candidates into one entry, noting the merge ("C3+C7"). Independent convergence is signal — flag merged entries as CONVERGENT. Note that convergence here cuts both ways: if two independent generators reached it, other entrants may too.

2. NAME THE MODAL REGION. In 2–4 sentences, describe what a large share of entrants will ship: the obvious reading of this theme, crossed with the mandated tech's quickstart path, plus the crowded ground above. Any pool candidate inside it gets flagged MODAL.

3. PRUNE to at most 8 finalists. Drop a candidate only if it is dominated: another is at least as demoable AND at least as shippable in the hours budget AND at least as distant from the modal region. Also drop any candidate with no demo moment, or whose minimum slice plainly exceeds the productive-hours budget with no smaller version — say which in one line each.

4. DUELS. Round-robin over the finalists. For each pair, judge "which is the stronger entry for THIS event in the targeted category — demo moment that lands in a noisy room × shippability inside the productive-hours budget × distance from the modal region × substantive use of the mandated tech" TWICE: once as (A vs B), once as (B vs A) — re-derive the verdict fresh the second time, do not copy it. Order-consistent verdict = win; inconsistent = draw. Record standings as W-D-L.

5. DIFFERENTIATION JUSTIFICATION. For each finalist, one line: its distance from the modal region you named in step 2, and why. No bare numbers.

6. BARBELL SPLIT. Divide the finalists:
   - SAFE DEMOS — strong duel record, the slice fits the hours budget with room, the escape hatch is real. Nearer the modal region is acceptable here; shipping something is the point.
   - SWING DEMOS — high distance from the modal region, higher ceiling, real risk of nothing working on stage. Kept BECAUSE they are non-obvious.
   Do not force a fixed split, but neither list may be empty unless the pool genuinely lacks one side (say so if so). A candidate whose hours exceed the budget can only be a Swing, never Safe.

7. STAGE RISK. For each finalist, one line naming the single most likely way it shows nothing on demo day, and whether its stated escape hatch covers that.

Return exactly:

### Modal region
### Pruned
### Duel standings
(table: ID | Title | W-D-L | one-line differentiation justification)
### Safe demos
### Swing demos
### Stage risk
(table: ID | most likely stage failure | hatch covers it? yes/no/partial)

No preamble.
```

## Report structure (Stage 5)

Assemble (you, the orchestrator — no extra agent needed) with EXACTLY these headings:

```
# Hackathon Idea Nebula: {{EVENT_OR_THEME}}

## Executive Summary
3–5 sentences: the event as recorded (duration, mandated tech, targeted category), generators run, pool size, whether a feasibility check ran, the single strongest Safe Demo and the single most interesting Swing Demo. State the productive-hours budget and its arithmetic.

## Safe Demos
Ranked by duel standings. Per candidate: **Title** — pitch — W-D-L — demo moment — mandated-tech use — minimum slice + hours vs budget — escape hatch — differentiation justification — feasibility verdict one-liner (or UNVERIFIED / flags).

## Swing Demos
Same fields. Preface: "Higher ceiling, real risk of nothing working on stage — kept because they are far from what the room will build. Expect some to die in the first six hours."

## Killed
Any candidate a hard threshold removed, with its reason and link. Never drop one silently — a closed path the user can see is worth more than a shorter list.

## Feasibility Evidence
Table: Candidate | Access (obtainable before the clock? + link) | Live-demo limits | Hard part (library/sample/unsolved + link) | Prior art & crowding score | Hours vs budget | Flags (KILL / DOWNGRADE / TIGHT / UNVERIFIED).
If --no-feasibility, or no feasibility evidence was actually gathered (every Stage-4 agent failed or lacked web access), replace the table with: "⚠️ UNCHECKED — no live feasibility evidence was gathered. Ranking candidates on demoability and distinctiveness without checking API access, rate limits and prior art is actively misleading: the two things that kill a hackathon entry are that it could not be built in time and that thirty other teams built it too, and neither was checked. Verify before committing a weekend."

## The Room (what we refused to rank as distinctive)
The ranker's step-2 modal region, verbatim — this documents what a large share of entrants will ship, and what every candidate here was ranked against.

## Convergence & Disagreement
Candidates ≥2 generators reached independently (now attributed — reveal the map), and any productive disagreement (e.g. recon's prior art contradicts a tails candidate's distinctiveness claim). Note that convergence between generators is weak evidence that other entrants will converge there too.

## Validate Next
For the top Safe Demo and the top Swing Demo: the cheapest real check before committing — a thirty-minute spike against the actual API to confirm access and limits, or one `npm install`/`pip install` and a hello-world against the hard part. A spike beats every link in this report.

## Next: Judge It
One line: run `hackathon-judge` on your pick with the SAME rules block for the worth-entering and would-it-win verdicts. This report deliberately contains neither.

## Final Cut Is Yours
One fixed paragraph: "This shortlist is a funnel, not a verdict. In the only RCT that built ideas out, LLM pre-execution scores were weak-to-negative predictors of executed quality, and novelty advantages evaporated in execution — at a hackathon that reckoning arrives in 36 hours, in public. The hours estimates here are estimates, not measurements. Pick with your own judgment, especially between the barbell's two ends, and spike the hard part before you commit the weekend."
```

The report states no verdict and never says a candidate will win. Standings are duel records inside this pool, not a prediction about the room.
