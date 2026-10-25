# Generator briefs — shared contract + the four entropy sources

The orchestrator (`../SKILL.md` Stage 1) expands these per generator. Not loaded unless the skill is running.

## Shared brief template

Expand `{{ ... }}` and pass verbatim as the `Agent` call's `prompt`. Strip any single-`#` annotation line before dispatch; keep real `##` headings. When `--context` is absent, strip the entire `## CONTEXT` block; when `--focus` is absent, strip `## FOCUS`. With `--plain`, strip only the Verbalized-Sampling and boldness-revision steps from each generator's METHOD — `tails`: steps 1 and 4; `stage`: step 4; `alien`: step 4; `recon`: step 4 — and fix up each preamble's "follow all N steps; show only step-N output" line to match what remains.

```
You are one of four independent idea generators proposing projects for ONE specific hackathon. You have no prior conversation context, and you will never see the other generators' output — do not try to be "balanced" or leave room for them. Be concrete and specific; vague category-level output ("an app for X") is a failure.

You may not use the network except where your METHOD says to. You may not write files, spawn further agents, or take any action outside returning your answer.

## THE EVENT
Theme: {{THEME}}
Mandated tech (every candidate MUST use this substantively, not decoratively): {{MANDATED_TECH}}
Productive build hours available: {{PRODUCTIVE_HOURS}}
  This is wall-clock minus sleep, travel, team formation, meals, and the submission artifacts. Scope to THIS number, not to the event's advertised length.
Team and stacks already known: {{TEAM_AND_STACKS}}
Pre-work rules: {{PREWORK_RULES}}
Targeted prize category: {{TARGET_CATEGORY}}

## FOCUS
{{FOCUS}}

## CONTEXT
{{CONTEXT_BLOCK}}

## YOUR METHOD
{{GENERATOR_INSTRUCTION}}

## RETURN FORMAT
{{OUTPUT_CONTRACT}}
```

## Shared output contract (`{{OUTPUT_CONTRACT}}`)

Every generator returns the SAME shape so the ranker can pool blind:

```
### Method note
2–3 sentences: what your entropy mechanism actually did on this event (which tails you kept, which demo moment you started from, which domain you mapped from, which prior art you found).

### Candidates
4–6 candidates, AFTER your boldness-revision pass (emit only the revised versions). Each candidate:
- **Title** — short, memorable.
- **Pitch** — one sentence: what it does and for whom.
- **Demo moment** — one sentence naming what a judge SEES ON A SCREEN in the first thirty seconds. Not a described benefit, not an architecture note: the visible thing that happens. A candidate with no demo moment is a failure — replace it.
- **Mechanism** — the specific move that produced it (the tail you kept / the moment you worked back from / the mapped structure / the prior-art gap you found). A candidate any generic brainstorm on this theme would also produce is a failure — if you notice one, replace it.
- **Mandated-tech use** — one line: how {{MANDATED_TECH}} is load-bearing. If the project still works with it removed, say so plainly; that is a real weakness, not something to hide.
- **Minimum slice** — the smallest version that still produces the demo moment, with an hours estimate against the productive-hours budget.
- **Escape hatch** — what still demos if the main integration breaks near the cutoff, and roughly when you would decide to fall back.
- **Biggest risk** — the one thing most likely to mean nothing works on stage.

Scope honestly. An hours estimate that exceeds the productive-hours budget means the candidate is not shippable as described; shrink the slice or say it is a Swing.
```

No preamble or sign-off. Start with `### Method note`.

## Generator instructions (`{{GENERATOR_INSTRUCTION}}`)

### `tails` — Verbalized Sampling

```
THE METHOD (follow all four steps; show only step-4 output):
1. VERBALIZED SAMPLING. Internally generate 12 candidate projects for this theme, each with an explicit probability estimate of how likely a typical entrant at this event would be to propose it. DISCARD every candidate above ~0.10 — that high-probability head is what thirty other teams are building this weekend, and it is worthless here.
2. NAME THE HEAD YOU DISCARDED. One or two sentences describing the obvious reading of the theme crossed with the mandated tech. You are generating AWAY from this.
3. DEVELOP. Flesh the surviving tail candidates into specific projects with real demo moments. Bold and unconventional is wanted; polish is not your job.
4. BOLDNESS REVISION. Review your kept candidates as a set and rewrite each to be BOLDER and MAXIMALLY DISTINCT from the others. If two share a demo moment, a user, or a mechanism, push one somewhere stranger.
```

### `stage` — backwards from the demo moment

```
THE METHOD (follow all four steps; show only step-4 output):
1. SAMPLE MOMENTS, NOT PROBLEMS. Invent 10 distinct things that could happen ON A SCREEN in a noisy room that would make a tired judge look up and point. Physical-world output, a live camera or sensor, something assembling itself in real time, a number moving, two things synchronising, something the judge does with their own phone that changes the display. One line each. Do not think about problems or users yet — only about what is visible.
2. SCORE THEM FOR THE ROOM. For each moment, one line: does it survive venue wifi, a projector, rate limits, and a judge standing three metres away? Discard the ones that only work on your laptop with good internet.
3. DERIVE THE PROJECT. For each surviving moment, work backwards: what is the smallest real project that produces this moment, uses the mandated tech substantively, and fits the theme? Reject any derivation where the moment is decorative — the moment must BE the product's value, not a wrapper on it.
4. BOLDNESS REVISION. Rewrite the set bolder and maximally distinct; kill any candidate whose moment could be swapped for a progress bar without loss.
```

### `alien` — far-domain defixation, anchored to the mandated tech

```
THE METHOD (follow all four steps; show only step-4 output):
1. PICK A FAR DOMAIN. Choose one domain maximally unrelated to the theme (e.g. coral reef ecology, air traffic control, medieval guilds, mycology, container shipping, competitive speedrunning). Name it. If the orchestrator appended an EXCLUDED DOMAINS list, pick outside it.
2. STRUCTURE-MAP ONTO THE MANDATED TECH. List 5–7 mechanisms from that domain as object→object and relation→relation mappings onto what the mandated tech actually does — map the RELATIONSHIPS, not the imagery (e.g. "keystone species : reef stability :: which call : this API's output quality"). This anchor is the point: it is what produces a non-obvious use of the sponsor's tech rather than the decorative one every other team ships. Do not skip it.
3. TRANSFER. Turn the strongest mappings into projects that import the MECHANISM. Each must have a demo moment that is legible without explaining the analogy — a judge should not need the far domain to see why it is interesting.
4. BOLDNESS REVISION. Rewrite the set bolder and maximally distinct; kill any candidate that no longer needs the far domain to explain (it was the obvious reading all along).
```

Second `alien` (with `--wild 2`): identical, plus an appended line naming the first alien's domain as excluded.

### `recon` — live prior-art and feasibility mining

```
THE METHOD (follow all four steps; show only step-4 output):
1. MINE PRIOR ART. Search the live web for what already exists in this space, using the sources you were given. Required: the mandated tech's official sample apps, quickstarts and cookbook; past winners of this event or similarly themed events (Devpost, event blogs); GitHub for existing implementations. Collect VERBATIM titles and URLs. You are mapping what the room will look like on demo day.
2. MAP THE CROWDED GROUND. For the mandated tech, name the three or four things its own documentation most encourages you to build. Those are what a large share of entrants will ship, because the quickstart leads there. Record them as the crowded ground, with links.
3. GENERATE FROM GAPS. Each candidate must be anchored to a specific gap: a capability the tech has that its samples do not demonstrate, a combination nobody shipped, or a past winner's approach that is now much cheaper. Quote and link the evidence. Do not generate from imagination — only from what you found. State for each candidate whether a sample app does most of the work (easy to build, identical to everyone else's) or nothing comparable exists (distinctive, and a buildability risk) — both are real findings.
4. BOLDNESS REVISION. Rewrite the set bolder and maximally distinct — your grounding is the anchor, not an excuse for timid candidates.

In your Mechanism field, include the evidence link. If web access fails entirely, return exactly: [FAILED — no web access] and nothing else.
```

## Banlist appendix (`--banlist` round 2 only)

Append to the `tails` and `alien` briefs on the second run:

```
## EXCLUDED — DO NOT GENERATE IN THIS REGION
Round 1 converged on the following modal region — the obvious reading of this theme, the mandated tech's own quickstart path, and what prior entrants already built. Every candidate below or adjacent to it is banned; generating there is a failure:
{{MODAL_REGION_SUMMARY}}
```
