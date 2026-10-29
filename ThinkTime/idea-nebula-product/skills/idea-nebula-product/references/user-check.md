# User-check — sources, thresholds, need scoring

Used by the `miner` generator (Stage 1) and the per-finalist user-check agents (Stage 4). Not loaded unless the skill is running.

## Why this stage exists

The ideation–execution gap (Stanford RCT, arXiv 2506.20803): AI ideas that scored significantly *more novel* pre-execution lost the entire advantage once built, and pre-execution scores were weak-to-negative predictors of executed quality. An original idea nobody needs is not a good product. This stage asks two questions only: do real people have this problem, and does something already solve it well for them?

Business signals — pricing, paid competitors, market size, moats, willingness to pay — are out of scope here. A problem that no one sells a fix for counts the same as one with ten vendors; free tools, open-source projects, and workarounds all count as "current tools".

## Sources a subagent can actually hit (2026)

| Source | How | Notes |
|---|---|---|
| Hacker News | `curl "https://hn.algolia.com/api/v1/search?query=<q>&tags=story"` (also `tags=comment`) | No key, full historical archive. Best for dev/technical pain; for consumer topics expect a dead end — skip fast and say so. |
| Reddit | WebSearch `site:reddit.com "<problem phrase>"`, or `https://www.reddit.com/search.json?q=<q>` | Richest source of people describing problems in their own words. |
| GitHub issues | `gh search issues "<q>" --limit 30` or label-mining a category's popular repos | For developer-adjacent topics: feature requests and UX bug reports. |
| App stores / review sites / forums | WebSearch (`"<tool>" review "confusing"`, `"<tool>" "too many steps"`) | Best source of usability complaints about current tools. Treat snippets as indicative. |

Count **independent people** (distinct authors/threads), not posts. Always capture verbatim quote + URL.

## Per-finalist user-check brief

One agent per finalist, spawned in parallel. `subagent_type: general-purpose`.

```
You are checking ONE product idea against what real people say. You have no prior conversation context. Use live web sources (endpoints in your instructions) — your own opinions are inadmissible; only what you can quote and link counts. Ignore business questions (pricing, market size, competitors as businesses); judge only the user's side.

## IDEA
{{TITLE}} — {{PITCH}}
End user & moment: {{END_USER}}
Core interaction: {{CORE_INTERACTION}}

## CHECKS — run all four

1. REAL NEED. Find independent people describing the problem this idea removes, in their own words. Target ≥10 independent people across sources. Record: count, the 2–3 strongest verbatim quotes with URLs.
2. CURRENT TOOLS. What do these people use today (apps, workarounds, paper, general AI assistants)? What do they say it fails at — especially usability (confusing, slow, too many steps, breaks in their real conditions)? Quotes + URLs.
3. ALREADY SOLVED. Does an existing product — free or paid, including a general AI assistant — already do this well, with users praising it for exactly this and no more effort than the idea promises? Name it and quote the praise.
4. INTERACTION RISK. Is there evidence that the core interaction this idea depends on (e.g. voice in a noisy room, wearing a headset, logging every day) fails or gets abandoned in real use? Supported / contradicted + one quote.

## RETURN FORMAT

### Verdict
One of (ALREADY-SOLVED overrides the others):
- GROUNDED — ≥10 independent people have the need, and no evidence contradicts the core interaction.
- WEAK — ≥10 people have the need, but the core interaction is contradicted, or current tools already cover most of it.
- NEED-UNPROVEN — fewer than 10 independent people found.
- ALREADY-SOLVED — an existing product does it well and users praise it for exactly this.

### Evidence
- **Need**: <count> independent — quotes + URLs (or "under 10 found: <count>" → this alone forces NEED-UNPROVEN)
- **Current tools**: what people use + what they say it fails at
- **Already solved**: no / yes — <product> + quote
- **Interaction risk**: none found / contradicted + quote

### Need score
Severity (1–5) × frequency (daily=3, weekly=2, rarer=1) = score, with one line of justification.

No preamble. If web access fails, return exactly: [FAILED — no web access].
```

## Hard thresholds (applied by the orchestrator, not the agent)

| Signal | Action |
|---|---|
| <10 independent people describing the problem | NEED-UNPROVEN flag — say so in the report, whatever the matrix says. |
| An existing product already does this well | ALREADY-SOLVED flag — the idea's originality claim is void until it names what it does better. |
| Evidence contradicts the core interaction | INTERACTION-RISK flag — the usability column is optimistic; say so. |
| User-check agent failed | Mark `user-check: UNCHECKED`; never silently omit or guess. |

## What this stage cannot do (route to the human)

Only real use tells you whether a product is usable and useful. The report's "Test Next" section points to tests the human must run: a hallway usability test of a paper or clickable prototype with 5 target users (five users surface most of the serious usability problems — Nielsen), a Wizard-of-Oz or concierge version that fakes the hard part by hand to see whether people keep coming back, and a one-week diary of when they reached for it. This stage only gathers what people have already said in public.
