# Ranking & synthesis — prune, three axis judges, rating matrix

The orchestrator (`../SKILL.md` Stages 3 & 5) uses this reference. Not loaded unless the skill is running.

## Why this protocol exists

- Position bias flips roughly 1/3 of LLM-judge pairwise verdicts on order swap (MT-Bench) → every duel is judged in BOTH orders; only order-consistent wins count.
- Claude-class judges self-prefer by up to +25% win rate → ideas are presented BLIND (no generator attribution) with neutral IDs.
- LLMs assign pointwise 1–10 scores arbitrarily and self-evaluate unreliably → pointwise scoring is banned; every cell of the rating matrix is a duel record (W-D-L).
- A judge rating several criteria at once lets its overall impression bleed into each one (halo effect) → each axis gets its own judge, which sees only its own question.

## Stage 3a — prune brief

Pool all generator ideas. Assign each a neutral ID (`I1`, `I2`, …) in shuffled order (do NOT group by generator). Strip every trace of which generator produced what — keep the attribution map to yourself for the final report. One `Agent` call, `subagent_type: general-purpose`, `description: "idea-nebula-product: prune"`.

```
You are pruning a pool of product ideas from an idea-generation pipeline. You have no prior conversation context. You did not generate these ideas and must not add new ones. Ideas are judged on usability, originality, and usefulness to the end user — not on revenue, market size, or how hard they are to build.

## TOPIC
{{TOPIC}}

## IDEA POOL
{{POOLED_IDEAS}}

## PROTOCOL — follow in order

1. DEDUPE. Merge near-duplicate ideas into one entry, noting the merge ("I3+I7"). Independent convergence is signal — flag merged entries as CONVERGENT.
2. NAME THE MODAL REGION. In 2–4 sentences, describe the idea-space cluster that any generic single-pass brainstorm on this topic would produce (the obvious tracker/marketplace/dashboard/"AI assistant for X" tropes for this space). Any pool idea inside it gets flagged MODAL.
3. OFF-TOPIC. Drop any idea whose end user is not someone the topic names (e.g. a tool for the businesses that serve those people, when the topic is the people themselves). List each as OFF-TOPIC with one line.
4. PRUNE to at most 8 finalists. If 8 or fewer remain after step 3, keep them all and write "none" under Pruned. Otherwise drop an idea only if it is dominated: another idea is at least as easy to use AND at least as original AND at least as useful to its end user. Decide each dominance by comparing the two ideas directly, axis by axis, in words — never by giving ideas numeric scores. List what you pruned in one line each, naming the idea that dominates it.

Return exactly:

### Modal region
### Pruned
### Finalists
(each finalist with its ID, CONVERGENT/MODAL flags, and every field from the pool copied unchanged)

No preamble.
```

## Stage 3b — axis judge brief

Three `Agent` calls in ONE message, one per axis, `subagent_type: general-purpose`, `description: "idea-nebula-product: judge <axis>"`. Each gets the same finalists (as returned by the prune step, IDs unchanged) and only its own axis question.

| `{{AXIS}}` | `{{AXIS_QUESTION}}` |
|---|---|
| Usability | Which would its end user find easier to start and keep using? Weigh: steps and setup before the first useful moment, how much there is to learn, how well it fits what the user already does, and whether it works in the user's real conditions (hands full, noisy room, low vision, poor connection, low tech comfort). |
| Originality | Which is more original? Weigh: distance from the modal region below, and how different it is from what the end user can already get today. A re-skin (an existing product with a new noun) is not original; strangeness that adds nothing for the user is not original either. |
| Usefulness | Which would matter more to its end user? Weigh: how painful the problem it removes is, how often that problem hits, and how much better off the user is after each use. |

```
You are judging ONE axis of a product-idea rating matrix. You have no prior conversation context. You did not generate these ideas and must not add new ones. Assume each idea is built as described and works.

## AXIS
{{AXIS}} — {{AXIS_QUESTION}}

Judge this axis alone. The other axes are scored by other judges, so an idea's quality on anything else does not count here. Money, market size, competition, and build difficulty are not part of any axis.

## MODAL REGION
{{MODAL_REGION}}

## FINALISTS
{{FINALISTS}}

## PROTOCOL

1. DUELS. Round-robin over the finalists. For each pair, answer the axis question TWICE: once as (A vs B), once as (B vs A) — re-derive the verdict fresh the second time, do not copy it. Order-consistent verdict = win; inconsistent = draw. Record standings as W-D-L.
2. REASONS. For each finalist, one line naming its strongest and weakest point on this axis only.

Return exactly:

### {{AXIS}} standings
(table: ID | Title | W-D-L | one-line reason, sorted by wins)

No preamble.
```

## Building the matrix (orchestrator, no agent)

Join the three standings tables on ID. Total wins = sum of the three axes' order-consistent wins; ties break on Usefulness wins, then Usability wins. Sorting by total is for reading order only — the three columns are the result, and the report must show them side by side.

Pick the lists below at report time (Stage 5), after the user-check flags are in:

- **Best Overall**: the top 3 by total wins among ideas not flagged ALREADY-SOLVED. An ALREADY-SOLVED idea stays in the matrix with its flag; the next idea moves up.
- **Moonshots**: up to 3 finalists with the most Originality wins that are not already in Best Overall. If none of them has at least as many Originality wins as the median Best Overall pick, say the pool has no real moonshot.
- **Axis Leaders**: the top finalist on each axis (may repeat Best Overall).

## Report structure (Stage 5)

Assemble (you, the orchestrator) with EXACTLY these headings:

```
# Idea Nebula — Product: {{TOPIC}}

## Executive Summary
3–5 sentences: generators run, pool size, whether a user-check ran, the top Best Overall pick and why, and the most interesting moonshot.

## Rating Matrix
Table: Idea | Usability W-D-L | Originality W-D-L | Usefulness W-D-L | Total wins | Flags (CONVERGENT / MODAL / NEED-UNPROVEN / ALREADY-SOLVED / INTERACTION-RISK / UNCHECKED). Sorted by total wins. One line under the table: "Each cell is a round-robin duel record judged in both orders by a judge who saw only that axis."

## Best Overall
Per idea: **Title** — pitch — end user & moment — core interaction — matrix row — strongest axis and weakest axis, each with that judge's one-line reason — biggest product risk — user-evidence one-liner (or UNCHECKED / flags).

## Moonshots
Same fields. Preface: "Kept because they are far from the modal region — expect most to need heavy rework before anyone wants to use them."

## Axis Leaders
Three lines: the top idea on Usability, Originality, and Usefulness, with the judge's reason. For readers who care about one axis most.

## User Evidence
Table: Idea | Independent people (count + strongest verbatim quote + link) | What current tools fail at | Need score | Flags.
If --no-check, or no user evidence was actually gathered (every Stage-4 agent failed or lacked web access), replace the table with: "⚠️ UNGROUNDED — no live user evidence was gathered. The matrix ranks ideas as described, not as people would actually use them. Test before building."

## Modal Region (what we refused to rank as original)
The prune step's description, verbatim.

## Convergence & Disagreement
Ideas ≥2 generators reached independently (now attributed — reveal the map), and any productive disagreement (e.g. the miner's evidence contradicts another idea's core interaction; one idea tops Usefulness but bottoms Usability).

## Test Next
For the top Best Overall pick and the top moonshot: the cheapest real test — a paper or clickable prototype put in front of 5 target users with one task each (watch where they stall), or a Wizard-of-Oz version that fakes the hard part by hand to see whether people come back for a second use.

## Final Cut Is Yours
One fixed paragraph: "This matrix is a funnel, not a verdict. In the only RCT that built ideas out (~100 expert-hours each), LLM pre-execution scores were weak-to-negative predictors of executed quality. Usability especially only shows up in real use. Pick with your own judgment, then put a prototype in front of real users."
```
