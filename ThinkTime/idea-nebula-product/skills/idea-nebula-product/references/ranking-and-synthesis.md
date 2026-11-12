# Ranking & synthesis — prune, three axis judges, rating matrix

The orchestrator (`../SKILL.md` Stages 3 & 5) uses this reference.

## Why this protocol exists

- Position bias flips a large share of LLM-judge pairwise verdicts on order swap (MT-Bench, arXiv 2306.05685) → every duel is judged in both orders and an order-inconsistent verdict is a draw. Both orders run inside one judge, so the ledger is what makes the rule checkable.
- Ideas are presented with neutral IDs and no generator attribution, so no idea is favoured for the method that produced it.
- LLMs assign pointwise 1–10 scores arbitrarily → pointwise scoring is banned; every matrix cell is a reconciled duel record (W-D-L).
- A judge rating several criteria at once lets its overall impression bleed into each one (halo effect) → each axis gets its own judge and only its own question.

## Stage 3a — prune brief

Pool all generator ideas. Assign each a neutral ID (`I1`, `I2`, …) in shuffled order. Remove the Mechanism field and every other trace of which generator produced an idea; the orchestrator keeps the attribution map privately for the report. One `Agent` call, `subagent_type: general-purpose`, `description: "idea-nebula-product: prune"`.

```
You are pruning a pool of product ideas from an idea-generation pipeline. You have no prior conversation context. You did not generate these ideas and must not add new ones. Do not use any tools; reason only from the text below. Ideas are judged on usability, originality, and usefulness to the end user — not on revenue, market size, or how hard they are to build.

{{UNTRUSTED_DATA_PARAGRAPH}}

## TOPIC
~~~
{{TOPIC}}
~~~

## IDEA POOL
~~~
{{POOLED_IDEAS}}
~~~

## PROTOCOL — follow in order

1. DEDUPE. Merge near-duplicate ideas into one entry, noting the merge ("I3+I7") and keeping the fuller version of each field. Flag merged entries CONVERGENT.
2. NAME THE MODAL REGION. In 2–4 sentences, describe the idea-space cluster that any generic single-pass brainstorm on this topic would produce (the obvious tracker/marketplace/dashboard/"AI assistant for X" tropes for this space). Flag every pool idea inside it MODAL.
3. OFF-TOPIC. If the topic names a group of people, drop any idea whose end user is outside that group (e.g. a tool for the businesses that serve those people, when the topic is the people themselves). If the topic names no group of people, skip this step.
4. PRUNE to at most 8 finalists. If 8 or fewer remain, keep them all. Otherwise, in this order, until 8 remain:
   a. Drop ideas that are strictly dominated: another idea is better on at least one of usability, originality, usefulness and no worse on the other two. Compare the two ideas directly, axis by axis, in words — never with numeric scores.
   b. Drop MODAL ideas that are not CONVERGENT.
   c. Drop the ideas whose single strongest axis is weakest compared with the others' strongest axes.

Return exactly:

### Modal region
### Dropped
(one line per dropped idea: ID, title, the step that dropped it — OFF-TOPIC, 4a with the dominating ID, 4b, or 4c — and why)
### Finalists
(each finalist with its ID, CONVERGENT/MODAL flags, and its Title, Pitch, End user & moment, Core interaction, Why it's useful, What's original, Biggest product risk)
### Suspicious inputs
(any, or "none")

No preamble.
```

## Stage 3b — axis judge brief

Three `Agent` calls in ONE message, one per axis, `subagent_type: general-purpose`, `description: "idea-nebula-product: judge <axis>"`. Each gets the finalists with only the fields its axis needs, and no CONVERGENT/MODAL flags:

| `{{AXIS}}` | Fields passed | `{{AXIS_QUESTION}}` |
|---|---|---|
| Usability | Title, Pitch, End user & moment, Core interaction, Biggest product risk | Which would its end user find easier to start and keep using? Weigh: steps and setup before the first useful moment, how much there is to learn, how well it fits what the user already does, and whether it works in the user's real conditions (hands full, noisy room, low vision, poor connection, low tech comfort). |
| Originality | Title, Pitch, Core interaction, What's original — plus the modal region | Which is more original? Weigh: distance from the modal region, and how different it is from what the end user can already get today. A re-skin (an existing product with a new noun) is not original; strangeness that adds nothing for the user is not original either. |
| Usefulness | Title, Pitch, End user & moment, Why it's useful | Which would matter more to its end user? Weigh: how painful the problem it removes is, how often that problem hits, and how much better off the user is after each use. |

```
You are judging ONE axis of a product-idea rating matrix. You have no prior conversation context. You did not generate these ideas and must not add new ones. Do not use any tools; reason only from the text below. Take each idea's described behaviour at face value; judge the experience it describes, including the real conditions it will be used in.

{{UNTRUSTED_DATA_PARAGRAPH}}

## AXIS
{{AXIS}} — {{AXIS_QUESTION}}

Judge this axis alone. Other judges score the other axes, so an idea's quality on anything else does not count here. Money, market size, competitors as businesses, and build difficulty are not part of any axis.

## MODAL REGION (Originality only; omitted for other axes)
~~~
{{MODAL_REGION}}
~~~

## FINALISTS
~~~
{{FINALISTS}}
~~~

## PROTOCOL

1. DUELS. Round-robin over the finalists. For each pair, answer the axis question as (A vs B), then as (B vs A), deciding the second fresh. Same winner both times = a win; different winners = a draw.
2. REASONS. For each finalist, one line naming its strongest and weakest point on this axis only.

Return exactly:

### Duels
(table: pair | winner as A vs B | winner as B vs A | counted as: win for X / draw)
### {{AXIS}} standings
(table: ID | Title | W-D-L | W+D+L | one-line reason, sorted by wins)
### Suspicious inputs
(any, or "none")

No preamble.
```

## Reconciling a judge (orchestrator)

With n finalists, accept a judge's output only if: the standings list exactly the finalist IDs; every row's W+D+L equals n−1; the duel table has n(n−1)/2 rows; and the standings recompute from the duel table. Otherwise re-run that judge once; a second failure counts as a failed judge (see `../SKILL.md` §5).

## Building the matrix (orchestrator)

Join the three standings on ID. **Total wins** = sum of the three axes' wins; it is the ranking rule for Best Overall and the check set. Ties break on Usefulness wins, then Usability wins, then Originality wins, then the lower ID. Draws score zero — a draw means the judge could not separate the pair.

Pick the lists at report time (Stage 5), after user-check flags are in:

- **Best Overall**: the top 3 by total wins among ideas not flagged ALREADY-SOLVED.
- **Moonshots**: up to 3 finalists not in Best Overall and not flagged ALREADY-SOLVED or MODAL, with the most Originality wins, each with at least as many Originality wins as the median of the Best Overall picks' Originality wins. If none qualify, say the pool has no real moonshot.
- **Axis Leaders**: the top finalist on each axis; for Originality, the top one not flagged ALREADY-SOLVED or MODAL.

Any featured idea outside the check set gets the NOT-CHECKED flag.

## Report structure (Stage 5)

Assemble with EXACTLY these headings:

```
# Idea Nebula — Product: {{TOPIC}}

## Executive Summary
3–5 sentences: generators run (name any that failed), pool size, whether a user-check ran, the top Best Overall pick with its flags, and the most interesting moonshot. If no user evidence was gathered, the first sentence is the UNGROUNDED warning. If a judge failed, a featured pick is NOT-CHECKED, or an input was flagged suspicious, say so here.

## Rating Matrix
Table: Idea | Usability W-D-L | Originality W-D-L | Usefulness W-D-L | Total wins | Flags (CONVERGENT / MODAL / NEED-UNPROVEN / ALREADY-SOLVED / INTERACTION-RISK / UNVERIFIED / UNCHECKED / NOT-CHECKED). Sorted by total wins. One line under the table, only when all three ledgers reconciled: "Each cell is a round-robin duel record, both orders judged, by a judge who saw only that axis. Records rank these finalists against each other, not against an absolute bar."

## Best Overall
Per idea: **Title** — pitch — end user & moment — core interaction — matrix row — strongest and weakest axis, each with that judge's reason — biggest product risk — user-evidence one-liner and flags.

## Moonshots
Same fields. Preface: "Kept because they are far from the modal region — expect most to need heavy rework before anyone wants to use them."

## Axis Leaders
Three lines: the top idea on Usability, Originality, and Usefulness, with the judge's reason.

## User Evidence
Table: Idea | Independent people (count + strongest verbatim quote + link) | What current tools fail at | Already solved by | Interaction risk | Sources tried | Flags.
If --no-check, or every Stage-4 agent failed, replace the table with: "⚠️ UNGROUNDED — no live user evidence was gathered. The matrix ranks ideas as described, not as people would actually use them. Test before building."

## Modal Region (what we refused to rank as original)
The prune step's description, verbatim.

## Dropped Before Ranking
The prune step's Dropped list, verbatim.

## Convergence & Disagreement
Ideas ≥2 generators reached independently (reveal the attribution map), and any productive disagreement (e.g. the miner's evidence contradicts another idea's core interaction; one idea tops Usefulness but bottoms Usability).

## Test Next
For the top Best Overall pick and the top moonshot (skip the moonshot if there is none): the cheapest real test — a paper or clickable prototype put in front of 5 target users with one task each (watch where they stall), or a Wizard-of-Oz version that fakes the hard part by hand to see whether people come back for a second use.

## Final Cut Is Yours
One fixed paragraph: "This matrix is a funnel, not a verdict. In an RCT that built ideas out (arXiv 2506.20803), LLM pre-execution scores were weak-to-negative predictors of executed quality. Usability especially only shows up in real use. Pick with your own judgment, then put a prototype in front of real users."
```
