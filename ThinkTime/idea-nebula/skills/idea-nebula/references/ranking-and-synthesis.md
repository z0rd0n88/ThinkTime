# Ranking & synthesis — blind duels, barbell report

The orchestrator (`../SKILL.md` Stages 3 & 5) uses this reference. Not loaded unless the skill is running.

## Why this protocol exists

- Position bias flips roughly 1/3 of LLM-judge pairwise verdicts on order swap (MT-Bench) → every duel is judged in BOTH orders; only order-consistent wins count.
- Claude-class judges self-prefer by up to +25% win rate → ideas are presented BLIND (no generator attribution) with neutral IDs.
- LLMs assign pointwise 1–10 scores arbitrarily and self-evaluate unreliably → pointwise scoring is banned; novelty must be justified as distance from a named modal region.
- Averaging a ranking destroys the sharp edges a panel exists to find → the output is a barbell (Safe Picks + Moonshots), never one merged list.

## Building the ranker prompt

Pool all generator ideas. Assign each a neutral ID (`I1`, `I2`, …) in shuffled order (do NOT group by generator). Strip every trace of which generator produced what — keep the attribution map to yourself for the final report. Pass the pooled ideas (full contract fields per idea) into the template below. One `Agent` call, `subagent_type: general-purpose`.

## Ranker brief template

```
You are ranking a pool of ideas from an idea-generation pipeline. You have no prior conversation context. You did not generate these ideas and must not add new ones.

## TOPIC
{{TOPIC}}

## IDEA POOL
{{POOLED_IDEAS}}

## PROTOCOL — follow in order

1. DEDUPE. Merge near-duplicate ideas into one entry, noting the merge ("I3+I7"). Independent convergence is signal — flag merged entries as CONVERGENT.

2. NAME THE MODAL REGION. In 2–4 sentences, describe the idea-space cluster that any generic single-pass brainstorm on this topic would produce (the obvious scheduling/CRM/marketplace/dashboard tropes for this vertical). Any pool idea inside it gets flagged MODAL.

3. PRUNE to at most 8 finalists. Drop an idea only if it is dominated: another idea is at least as novel AND at least as plausible AND at least as reachable for the stated founder. List what you pruned in one line each.

4. DUELS. Round-robin over the finalists. For each pair, judge "which is the stronger candidate to actually pursue (novelty beyond the modal region × plausibility × founder reachability × strength of its why-now)" TWICE: once as (A vs B), once as (B vs A) — re-derive the verdict fresh the second time, do not copy it. Order-consistent verdict = win; inconsistent = draw. Record standings as W-D-L.

5. NOVELTY JUSTIFICATION. For each finalist, one line: its distance from the modal region you named in step 2, and why. No bare numbers.

6. BARBELL SPLIT. Divide the finalists: SAFE PICKS (strong duel record, plausibly reachable, nearer the modal region is acceptable here) and MOONSHOTS (high distance from modal region, high variance, weaker plausibility — kept BECAUSE they are non-obvious). Do not force a fixed split, but neither list may be empty unless the pool genuinely lacks one side (say so if so).

Return exactly:

### Modal region
### Pruned
### Duel standings
(table: ID | Title | W-D-L | one-line novelty justification)
### Safe picks
### Moonshots

No preamble.
```

## Report structure (Stage 5)

Assemble (you, the orchestrator — no extra agent needed) with EXACTLY these headings:

```
# Idea Nebula: {{TOPIC}}

## Executive Summary
3–5 sentences: generators run, pool size, whether a demand-check ran, the single most promising safe pick and the single most interesting moonshot.

## Safe Picks
Ranked by duel standings. Per idea: **Title** — pitch — W-D-L — novelty justification — why-now — founder fit — biggest risk — demand evidence one-liner (or UNVERIFIED / flags).

## Moonshots
Same fields. Preface: "High-variance bets kept because they are far from the modal region — expect most to die under validation."

## Demand Evidence
Table: Idea | Independent complaints (count + strongest verbatim quote + link) | Existing paid vendors | Gap score | Flags (DOWNGRADE / KILL-ZONE / UNVERIFIED).
If --no-demand, or no demand evidence was actually gathered (every Stage-4 demand-check agent failed or lacked web access), replace the table with: "⚠️ UNGROUNDED — no live demand evidence was gathered. Novelty ranking without demand grounding is actively misleading (pre-execution scores are weak-to-negative predictors of executed quality). Validate before acting."

## Modal Region (what we refused to rank as novel)
The ranker's step-2 description, verbatim — this documents what every generic brainstorm would have handed you.

## Convergence & Disagreement
Ideas ≥2 generators reached independently (now attributed — reveal the map), and any productive disagreement (e.g. the miner's evidence contradicts a tails idea's premise).

## Validate Next
For the top safe pick and top moonshot: the concrete next validation step — fake-door/landing page (healthy cold-traffic email capture is ~5–15%, "Buy" CTR ~0.5–3%), or 3–5 LOIs for B2B. Money and LOIs are validation; search volume is only interest.

## Final Cut Is Yours
One fixed paragraph: "This ranking is a funnel, not a verdict. In the only RCT that built ideas out (~100 expert-hours each), LLM pre-execution scores were weak-to-negative predictors of executed quality, and novelty advantages evaporated in execution. Pick with your own judgment — especially between the barbell's two ends."
```

Then suggest the follow-on pipeline: `idea-autopsy:iterate-to-v2` → `product-management:write-spec` / `to-prd` → `idea-autopsy:evaluate-proposal-harsh`.
