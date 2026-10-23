# Generator briefs — shared contract + the four entropy sources

The orchestrator (`../SKILL.md` Stage 2) expands these per generator. Not loaded unless the skill is running.

## Shared brief template

Expand `{{ ... }}` and pass verbatim as the `Agent` call's `prompt`. Strip any single-`#` annotation line before dispatch; keep real `##` headings. With `--plain`, strip only the Verbalized-Sampling and boldness-revision steps from each generator's METHOD — `tails`: steps 1 and 3; `stage`: step 3; `alien`: step 4; `scout`: step 4 — and fix up each preamble's "follow all N steps; show only step-N output" line to match what remains.

```
You are one of four independent idea generators for a hackathon project. You have no prior conversation context, and you will never see the other generators' output — do not try to be "balanced" or leave room for them. Be concrete and specific; vague category-level output ("an AI app for X") is a failure.

## THEME / TOPIC
{{TOPIC}}

## RULES AND CONSTRAINTS (binding — an idea that breaks these is a failed idea)
{{RULES_BLOCK}}

## WHO IS BUILDING
{{TEAM}} builder(s), senior engineer skill level, shipping in: {{STACK}}
HARD CONSTRAINT: there is no time to learn a new stack, language, or platform. Every idea must be buildable in the stack above using libraries that team can `install` and use the same hour. An idea that requires learning something new is a failed idea, not an ambitious one.

## WHAT WINS HERE
{{RUBRIC}}

## YOUR METHOD
{{GENERATOR_INSTRUCTION}}

## RETURN FORMAT
{{OUTPUT_CONTRACT}}
```

## Shared output contract (`{{OUTPUT_CONTRACT}}`)

Every generator returns the SAME shape so the rankers can pool blind:

```
### Method note
2–3 sentences: what your entropy mechanism actually did on this theme (which tails you kept, which stage moments you reverse-engineered, which domain you mapped from, what you found in the live sources).

### Ideas
4–6 ideas, AFTER your boldness-revision pass (emit only the revised versions). Each idea:
- **Title** — short, memorable, says what it is.
- **Pitch** — one sentence a non-expert judge understands in 30 seconds.
- **Wow moment** — the single visible beat in the live demo that makes a tired judge look up. Name what physically happens on screen or in the room. "It shows a dashboard" is not a wow moment.
- **Hard part** — the technically hard component, and whether an off-the-shelf library or API already owns it. If the hard part IS one API call, say so plainly — do not dress it up.
- **Mechanism** — the specific move that produced this idea (the tail you kept / the stage moment you worked back from / the mapped structure / the source you found). An idea any generic hackathon brainstorm would also produce is a failure — if you notice one, replace it.
- **Rule compliance** — which mandated technology it uses and how that use is non-trivial; whether it stays inside the pre-work rules; what the submission requires that is not just code.
- **Escape hatch** — what still demos at 6 hours to deadline with the hardest integration broken. If there is no hatch, write "NONE" — do not invent one.
- **Build sketch** — the minimum slice that demos, as 3–5 bullets, each one a thing that exists at the end of it.
- **Biggest risk** — the one thing most likely to leave you with nothing on stage.
```

No preamble or sign-off. Start with `### Method note`.

## Generator instructions (`{{GENERATOR_INSTRUCTION}}`)

### `tails` — Verbalized Sampling

```
THE METHOD (follow all three steps; show only step-3 output):
1. VERBALIZED SAMPLING. Internally generate 12 candidate hackathon projects for this theme, each with an explicit probability estimate of how likely a typical assistant would be to propose it. DISCARD every idea with probability above ~0.10 — that high-probability head is the modal region (chatbot over your docs, RAG on a PDF, sentiment dashboard, "Uber for X", a wrapper with a chat box) and it is worthless here: 15 other teams are building it this weekend. Keep only the tail.
2. DEVELOP. Flesh the surviving tail ideas into real, specific projects that fit the duration and the stack. Bold and surprising is wanted; polish is not your job.
3. BOLDNESS REVISION. Review your kept ideas as a set and rewrite each to be BOLDER and MAXIMALLY DISTINCT from the others. If two share a customer, a mechanism, or a wow moment, push one somewhere stranger.
```

### `stage` — demo-first reverse engineering

```
THE METHOD (follow all three steps; show only step-3 output):
1. START FROM THE STAGE, NOT THE PRODUCT. Invent 6 visceral things that could happen during a 3-minute live demo and make a judge who has seen 40 demos put their phone down — something physical moves; a judge's own data or face appears in it; a real phone rings; it runs on the judge's laptop in 5 seconds; something is deliberately destroyed; the latency is so low it feels fake; the room participates. One line each: the moment, and why it survives being the 41st demo.
2. WORK BACKWARDS. For each moment, derive the MINIMUM system that produces it inside the stated duration and stack. The product is whatever is left once the moment is guaranteed — not the reverse.
3. BOLDNESS REVISION. Rewrite the set bolder and maximally distinct; kill any idea whose wow moment would survive removing the project (it was theatre, not a demo).
```

### `alien` — far-domain defixation

```
THE METHOD (follow all four steps; show only step-4 output):
1. PICK A FAR DOMAIN. Choose one domain maximally unrelated to the theme (e.g. coral reef ecology, air traffic control, medieval guilds, mycology, container shipping, competitive speedrunning). Name it. If the orchestrator appended an EXCLUDED DOMAINS list, pick outside it.
2. STRUCTURE-MAP EXPLICITLY. List 5–7 mechanisms from that domain as object→object and relation→relation mappings onto the theme (not surface analogies — map the RELATIONSHIPS: e.g. "keystone species : reef stability :: X : this system"). Far analogies fail without this scaffold; do not skip it.
3. TRANSFER. Turn the strongest mappings into projects that import the MECHANISM, not the imagery — and that still fit the duration and stack.
4. BOLDNESS REVISION. Rewrite the set bolder and maximally distinct; kill any idea that no longer needs the far domain to explain (it was modal all along).
```

### `scout` — live prior-art and capability mining

```
THE METHOD (follow all four steps; show only step-4 output):
1. MINE WHAT ACTUALLY WON. Search the live web for winners and submissions at comparable events on this theme (Devpost project galleries, the event's own past winners, hackathon recaps, sponsor blog posts). Record VERBATIM titles and URLs. You are looking for two things: the saturated region (what dozens of teams submit — avoid it) and the shape of what wins (what the panel rewarded — learn from it).
2. MAP AVAILABLE CAPABILITY. For the mandated technologies and any API an idea would need, find the live facts: is there a free tier, does the credential issue instantly or gate behind a waitlist/sales call, what are the rate limits, what is the documented latency, is there a quickstart in the team's stack. Quote and link. A capability you cannot confirm exists is not a capability.
3. GENERATE FROM THE GAP. Each idea must be anchored to something you actually found: a saturated region you are deliberately stepping outside, a sponsor capability with an instant credential and a quickstart, or a hard part a library already owns. Quote it and link it. Do not generate from imagination — only from what you found.
4. BOLDNESS REVISION. Rewrite the set bolder and maximally distinct — grounding is your anchor, not an excuse for timid ideas.

In your Mechanism field, include the source quote + URL. If web access fails entirely, return exactly: [FAILED — no web access] and nothing else.
```

Second `alien` (with `--wild 2`): identical, plus an appended line naming the first alien's domain as excluded.

## Banlist appendix (`--banlist` round 2 only)

Append to the `tails` and `alien` briefs on the second run:

```
## EXCLUDED — DO NOT GENERATE IN THIS REGION
Round 1 converged on the following modal region. Every idea below or adjacent to it is banned; generating there is a failure:
{{MODAL_REGION_SUMMARY}}
```
