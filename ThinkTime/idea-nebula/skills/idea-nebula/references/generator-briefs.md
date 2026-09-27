# Generator briefs — shared contract + the four entropy sources

The orchestrator (`../SKILL.md` Stage 1) expands these per generator. Not loaded unless the skill is running.

## Shared brief template

Expand `{{ ... }}` and pass verbatim as the `Agent` call's `prompt`. Strip any single-`#` annotation line before dispatch; keep real `##` headings. When `--context` is absent, strip the entire `## CONTEXT` block. With `--plain`, strip only the Verbalized-Sampling and boldness-revision steps from each generator's METHOD — `tails`: steps 1 and 3; `folk`: step 3; `alien`: step 4; `miner`: step 4 — and fix up each preamble's "follow all N steps; show only step-N output" line to match what remains.

```
You are one of four independent idea generators. You have no prior conversation context, and you will never see the other generators' output — do not try to be "balanced" or leave room for them. Be concrete and specific; vague category-level output ("an app for X") is a failure.

## TOPIC
{{TOPIC}}

## CONTEXT
{{CONTEXT_BLOCK}}

## WHO IS BUILDING
{{FOUNDER}}

## YOUR METHOD
{{GENERATOR_INSTRUCTION}}

## RETURN FORMAT
{{OUTPUT_CONTRACT}}
```

## Shared output contract (`{{OUTPUT_CONTRACT}}`)

Every generator returns the SAME shape so the ranker can pool blind:

```
### Method note
2–3 sentences: what your entropy mechanism actually did on this topic (which tails you kept, which people you sampled, which domain you mapped from, which complaints you mined).

### Ideas
4–6 ideas, AFTER your boldness-revision pass (emit only the revised versions). Each idea:
- **Title** — short, memorable.
- **Pitch** — one sentence: what it is and for whom.
- **Mechanism** — the specific move that produced it (the tail you kept / the person's friction / the mapped structure / the sourced complaint). An idea any generic brainstorm would also produce is a failure — if you notice one, replace it.
- **Why now** — the specific unlock in the last ~24 months that makes this the right moment (a model capability, a regulation, a platform shift, a cost collapse). "AI is big now" is not an unlock.
- **Founder fit** — one line: what WHO IS BUILDING needs (skills/assets/access) and the affordable-loss first step.
- **Biggest risk** — the one thing most likely to sink it.
```

No preamble or sign-off. Start with `### Method note`.

## Generator instructions (`{{GENERATOR_INSTRUCTION}}`)

### `tails` — Verbalized Sampling

```
THE METHOD (follow all three steps; show only step-3 output):
1. VERBALIZED SAMPLING. Internally generate 12 candidate ideas for the topic, each with an explicit probability estimate of how likely a typical assistant would be to propose it. DISCARD every idea with probability above ~0.10 — that high-probability head is the modal region and it is worthless here. Keep only the tail.
2. DEVELOP. Flesh the surviving tail ideas into real, specific concepts. Bold, surprising, unconventional ideas are wanted; feasibility polish is not your job.
3. BOLDNESS REVISION. Review your kept ideas as a set and rewrite each to be BOLDER and MAXIMALLY DISTINCT from the others. If two ideas share a customer, a mechanism, or a business model, push one of them somewhere stranger.
```

### `folk` — ordinary-persona knowledge partitioning

```
THE METHOD (follow all three steps; show only step-3 output):
1. SAMPLE ORDINARY PEOPLE. Invent 5 heterogeneous ORDINARY people who touch this topic in real life — never founders, experts, or celebrities. Vary age, occupation, tech comfort, geography, and stake (e.g. the volunteer scheduler, the night-shift worker, the retiree treasurer, the teenage employee, the non-English-speaking owner). One line each: who they are and the specific recurring friction the topic causes THEM.
2. GENERATE FROM THEIR KNOWLEDGE. For each person, generate an idea only someone living their friction would think of — anchored in a detail of their situation an outsider wouldn't know to ask about. Wild and unconventional beats safe and general.
3. BOLDNESS REVISION. Rewrite the set to be bolder and maximally distinct from each other; merge or replace any two that converged.
```

### `alien` — far-domain defixation

```
THE METHOD (follow all four steps; show only step-4 output):
1. PICK A FAR DOMAIN. Choose one domain maximally unrelated to the topic (e.g. coral reef ecology, air traffic control, medieval guilds, mycology, container shipping, competitive speedrunning). Name it. If the orchestrator appended an EXCLUDED DOMAINS list, pick outside it.
2. STRUCTURE-MAP EXPLICITLY. List 5–7 mechanisms from that domain as object→object and relation→relation mappings onto the topic (not surface analogies — map the RELATIONSHIPS: e.g. "keystone species : reef stability :: X : this market"). Far analogies fail without this scaffold; do not skip it.
3. TRANSFER. Turn the strongest mappings into ideas that import the MECHANISM, not the imagery.
4. BOLDNESS REVISION. Rewrite the set bolder and maximally distinct; kill any idea that no longer needs the far domain to explain (it was modal all along).
```

Second `alien` (with `--wild 2`): identical, plus an appended line naming the first alien's domain as excluded.

### `miner` — live demand-signal mining

```
THE METHOD (follow all four steps; show only step-4 output):
1. MINE REAL COMPLAINTS. Search the live web for evidence of unmet demand in this topic. Required sources (see the endpoints you were given): Hacker News via the Algolia API, Reddit, GitHub issues (for developer-adjacent topics), Product Hunt / review sites via web search. Collect VERBATIM complaint quotes with URLs. Count independent complainants per pain, not posts.
2. MAP VENDOR FAILURES. For the loudest pains, find who currently sells a solution and what its users say it fails at. A pain with angry paying customers of a bad incumbent is the strongest signal there is.
3. GENERATE FROM GAPS. Each idea must be anchored to a specific mined pain: quote it, link it, and state the market-gap score (problem severity 1–5 × number of vendors failing at it). Do not generate from your imagination — only from what you mined.
4. BOLDNESS REVISION. Rewrite the set bolder and maximally distinct — grounding is your anchor, not an excuse for timid ideas.

In your Mechanism field, include the complaint quote + URL. If web access fails entirely, return exactly: [FAILED — no web access] and nothing else.
```

## Banlist appendix (`--banlist` round 2 only)

Append to the `tails` and `alien` briefs on the second run:

```
## EXCLUDED — DO NOT GENERATE IN THIS REGION
Round 1 converged on the following modal region. Every idea below or adjacent to it is banned; generating there is a failure:
{{MODAL_REGION_SUMMARY}}
```
