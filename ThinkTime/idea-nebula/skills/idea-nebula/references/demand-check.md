# Demand-check — sources, thresholds, gap scoring

Used by the `miner` generator (Stage 1) and the per-finalist demand-check agents (Stage 4). Not loaded unless the skill is running.

## Why this stage is non-negotiable

The ideation–execution gap (Stanford RCT, arXiv 2506.20803): AI ideas that scored significantly *more novel* pre-execution lost the entire advantage once built — the ranking flipped below human ideas, and pre-execution scores were weak-to-negative predictors of executed quality. Novelty that isn't validated is a liability. This stage converts "sounds great" into evidence or a flag.

## Sources a subagent can actually hit (2026)

| Source | How | Notes |
|---|---|---|
| Hacker News | `curl "https://hn.algolia.com/api/v1/search?query=<q>&tags=story"` (also `search_by_date` for trend direction) | No key, full historical archive. Best for dev/B2B pain; for consumer/local-service verticals expect a dead end — skip fast and say so, don't force it. |
| Reddit | WebSearch `site:reddit.com "<pain phrase>"`, or `https://www.reddit.com/search.json?q=<q>` | Complaints lead search-volume trends by months. |
| GitHub issues | `gh search issues "<q>" --limit 30` or label-mining a category's popular repos | For developer-adjacent topics: open feature-requests = priced demand. |
| Product Hunt / G2 / Capterra / app stores | WebSearch (`site:producthunt.com`, `"<incumbent>" review "frustrating"`) | Direct API/scrape access is constrained — go through search snippets; treat as indicative. |
| Google Trends | WebSearch summary only | VALIDATION ONLY. Search volume is interest, not pain; it lags Reddit complaints by months. Never a discovery source. |

Count **independent complainants** (distinct people/threads), not posts. Always capture verbatim quote + URL.

## Per-finalist demand-check brief

One agent per finalist, spawned in parallel. `subagent_type: general-purpose`.

```
You are demand-checking ONE product idea. You have no prior conversation context. Use live web sources (endpoints in your instructions) — your own opinions about the market are inadmissible; only what you can quote and link counts.

## IDEA
{{TITLE}} — {{PITCH}} (why-now claim: {{WHY_NOW}})

## CHECKS — run all four

1. COMPLAINT DENSITY. Find independent people complaining about the pain this idea solves. Target ≥20 independent complainants across sources. Record: count, the 2–3 strongest verbatim quotes with URLs.
2. VENDOR CHECK. Who already sells a solution (or close substitute)? What do their users say they fail at? NO existing paid vendor or substitute is a RED flag (usually means no budget exists), not a green one.
3. KILL-ZONE CHECK. Could a user get ≥80% of the core value by pasting their problem into free ChatGPT/Claude today? If yes, does the idea have a moat an LLM cannot fabricate (proprietary data, community, network effects, physical-world integration)? No moat → KILL-ZONE.
4. WHY-NOW CHECK. Does live evidence support the claimed ≤24-month unlock, or is the timing claim decorative?

## RETURN FORMAT

### Verdict
One of: GROUNDED / WEAK / DOWNGRADE / KILL-ZONE (a KILL-ZONE flag overrides the others).

### Evidence
- **Complaints**: <count> independent — quotes + URLs (or "under 20 found: <count>" → this alone forces DOWNGRADE)
- **Vendors**: who + what users say they fail at (or "none found" → DOWNGRADE)
- **Kill-zone**: yes/no + the moat, if any
- **Why-now**: supported / decorative + one line

### Gap score
Problem severity (1–5) × vendors failing at it (count) = score, with one line of justification.

No preamble. If web access fails, return exactly: [FAILED — no web access].
```

## Hard thresholds (applied by the orchestrator, not the agent)

| Signal | Action |
|---|---|
| <20 independent complaints | DOWNGRADE regardless of novelty score — say so in the report. |
| No existing paid vendor or substitute | DOWNGRADE (no budget exists to capture). |
| Free LLM covers ≥80% of core function, no data/community/network moat | KILL-ZONE flag — require a moat before pursuing. |
| Demand-check agent failed | Mark `demand: UNVERIFIED`; never silently omit or guess. |

## What this stage cannot do (route to the human)

Fake-door / landing-page tests (healthy cold-traffic email capture ~5–15%, "Buy" CTR ~0.5–3%), pre-sales/deposits, and B2B LOIs (target 3–5) are the only non-lying validation — they require the human to run them. The report's "Validate Next" section points there; this stage only gathers the passive-demand layer.
