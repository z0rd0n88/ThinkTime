# Ranking & synthesis — blind duels, barbell report

The orchestrator (`../SKILL.md` Stages 3 & 5) uses this reference.

## Why this protocol exists

- Position bias flips a large share of LLM-judge pairwise verdicts on order swap (MT-Bench, arXiv 2306.05685) → every duel is judged in both orders and an order-inconsistent verdict is a draw. Both orders run inside one ranker, so the duel ledger is what makes the rule checkable.
- Ideas are presented with neutral IDs and no generator attribution, so no idea is favoured for the method that produced it.
- LLMs assign pointwise 1–10 scores arbitrarily and self-evaluate unreliably → pointwise scoring is banned; novelty must be justified as distance from a named modal region.
- Averaging a ranking destroys the sharp edges a panel exists to find → the output is a barbell (Safe Picks + Moonshots), never one merged list.

## Building the ranker prompt

Pool all generator ideas. Assign each a neutral ID (`I1`, `I2`, …) in shuffled order (do not group by generator). Remove the Mechanism field and every other trace of which generator produced what; the orchestrator keeps the attribution map privately for the report. Pass the remaining contract fields into the template below. One `Agent` call, `subagent_type: general-purpose`.

## Ranker brief template

```
You are ranking a pool of ideas from an idea-generation pipeline. You have no prior conversation context. You did not generate these ideas and must not add new ones. Do not use any tools; reason only from the text below.

{{UNTRUSTED_DATA_PARAGRAPH}}

## TOPIC
~~~
{{TOPIC}}
~~~

## WHO IS BUILDING
~~~
{{FOUNDER}}
~~~

## IDEA POOL
~~~
{{POOLED_IDEAS}}
~~~

## PROTOCOL — follow in order

1. DEDUPE. Merge near-duplicate ideas into one entry, noting the merge ("I3+I7"). Independent convergence is signal — flag merged entries as CONVERGENT.

2. NAME THE MODAL REGION. In 2–4 sentences, describe the idea-space cluster that any generic single-pass brainstorm on this topic would produce (the obvious scheduling/CRM/marketplace/dashboard tropes for this vertical). Any pool idea inside it gets flagged MODAL.

3. PRUNE to at most 8 finalists. If 8 or fewer remain, keep them all. Otherwise, in this order, until 8 remain:
   a. Drop ideas that are strictly dominated: another idea is better on at least one of novelty, plausibility, reachability for the stated founder, and no worse on the other two. Compare the two directly, in words — never with numeric scores.
   b. Drop MODAL ideas that are not CONVERGENT.
   c. Drop the least reachable ideas for the stated founder.

4. DUELS. Round-robin over the finalists. For each pair, judge "which is the stronger candidate to actually pursue (novelty beyond the modal region × plausibility × founder reachability × strength of its why-now)" as (A vs B), then as (B vs A), deciding the second fresh. Same winner both times = a win; different winners = a draw. Record standings as W-D-L.

5. NOVELTY JUSTIFICATION. For each finalist, one line: its distance from the modal region you named in step 2, and why. No bare numbers.

6. BARBELL SPLIT. Divide the finalists: SAFE PICKS (strong duel record, plausibly reachable, nearer the modal region is acceptable here) and MOONSHOTS (high distance from modal region, high variance, weaker plausibility — kept BECAUSE they are non-obvious). Do not force a fixed split, but neither list may be empty unless the pool genuinely lacks one side (say so if so).

Return exactly:

### Modal region
### Pruned
(one line per dropped idea: ID, title, the step that dropped it — 3a with the dominating ID, 3b, or 3c — and why)
### Duels
(table: pair | winner as A vs B | winner as B vs A | counted as: win for X / draw)
### Duel standings
(table: ID | Title | W-D-L | W+D+L | one-line novelty justification)
### Safe picks
### Moonshots
### Suspicious inputs
(any, or "none")

No preamble.
```

## Reconciling the ranker (orchestrator)

With n finalists, accept the ranker's output only if: every row's W+D+L equals n−1; the duel table has n(n−1)/2 rows; and the standings recompute from the duel table. Otherwise re-run the ranker once; a second failure is a ranker failure (see `../SKILL.md` §5).

## Report structure (Stage 5)

Assemble (you, the orchestrator — no extra agent needed) with EXACTLY these headings:

```
# Idea Nebula: {{TOPIC}}

## Executive Summary
3–5 sentences: generators run (name any that failed), pool size, whether a demand-check ran, the single most promising safe pick with its flags, and the single most interesting moonshot. If no demand evidence was gathered, the first sentence is the UNGROUNDED warning. If a featured pick is NOT-CHECKED or an input was flagged suspicious, say so here.

## Safe Picks
Ranked by duel standings. Per idea: **Title** — pitch — W-D-L — novelty justification — why-now — founder fit — biggest risk — demand evidence one-liner and flags (DOWNGRADE / KILL-ZONE / UNVERIFIED / UNCHECKED / NOT-CHECKED).

## Moonshots
Same fields. Preface: "High-variance bets kept because they are far from the modal region — expect most to die under validation."

## Demand Evidence
Table: Idea | Independent complaints (count + strongest verbatim quote + link) | Existing paid vendors | Gap score | Sources tried | Flags (DOWNGRADE / KILL-ZONE / UNVERIFIED / UNCHECKED).
If --no-demand, or no demand evidence was actually gathered (every Stage-4 demand-check agent failed or lacked web access), replace the table with: "⚠️ UNGROUNDED — no live demand evidence was gathered. Novelty ranking without demand grounding is actively misleading (pre-execution scores are weak-to-negative predictors of executed quality). Validate before acting."

## Modal Region (what we refused to rank as novel)
The ranker's step-2 description, verbatim — what any generic brainstorm would have produced.

## Dropped Before Ranking
The ranker's Pruned list, verbatim.

## Convergence & Disagreement
Ideas ≥2 generators reached independently (now attributed — reveal the map), and any productive disagreement (e.g. the miner's evidence contradicts a tails idea's premise).

## Validate Next
For the top safe pick and top moonshot: the concrete next validation step — fake-door/landing page (healthy cold-traffic email capture is ~5–15%, "Buy" CTR ~0.5–3%), or 3–5 LOIs for B2B. Money and LOIs are validation; search volume is only interest.

## Final Cut Is Yours
One fixed paragraph: "This ranking is a funnel, not a verdict. In an RCT that built ideas out (arXiv 2506.20803), LLM pre-execution scores were weak-to-negative predictors of executed quality, and novelty advantages evaporated in execution. Pick with your own judgment — especially between the barbell's two ends."
```

Then suggest the follow-on pipeline where installed: `idea-autopsy:iterate-to-v2` → a spec/PRD skill → `idea-autopsy:evaluate-proposal-harsh`.
