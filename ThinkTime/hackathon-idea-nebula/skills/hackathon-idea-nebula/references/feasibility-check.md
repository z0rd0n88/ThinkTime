# Feasibility-check — sources, thresholds, prior-art scoring

Used by the `recon` generator (Stage 1) and the per-finalist feasibility agents (Stage 4). Not loaded unless the skill is running.

## Why this stage is non-negotiable

The ideation–execution gap (Stanford RCT, arXiv 2506.20803) found that ideas scoring *more novel* pre-execution lost the whole advantage once built. At a hackathon the gap closes in 36 hours instead of months, and it closes in public. The two ways a candidate dies are **it could not be built in time** and **thirty other teams built it too** — and both are checkable before anyone writes code, from the same sources. This stage converts "sounds great" into evidence or a flag.

`idea-nebula`'s demand-check asks whether anyone would pay. That question is out of scope here: a hackathon entry is judged on what happens on stage, not on a market. Do not import demand thresholds; do not score market size.

## Sources a subagent can actually hit (2026)

| Source | How | Notes |
|---|---|---|
| The mandated tech's own docs | WebFetch the quickstart, cookbook, samples and pricing/limits pages | The single most valuable source. Its quickstart path *is* the crowded ground, and its rate-limit page decides whether a live demo survives. |
| Devpost | WebSearch `site:devpost.com "<theme or tech>"`, and the event's own page if it is hosted there | Past winners and submission counts. Shows what a themed room actually produces. |
| GitHub | `gh search repos "<q>" --limit 30`, `gh search code` for API usage patterns | Is the hard part an existing library, a sample, or genuinely unsolved? Stars and recency matter more than count. |
| Hacker News | `curl "https://hn.algolia.com/api/v1/search?query=<q>&tags=story"` | Best for "does this API actually work" reports and recent limit changes. No key. |
| Package registries | WebSearch or `curl` npm/PyPI | Confirms a library exists, is maintained, and installs without a toolchain fight. |
| Status and limits pages | WebFetch the provider's status/limits/waitlist page | Whether access is instant or gated is the difference between a project and a KILL. |

Capture verbatim titles, quotes and URLs. A claim with no link is an unverified claim and must be labelled as one.

## Per-finalist feasibility brief

One agent per finalist, spawned in parallel. `subagent_type: general-purpose`.

```
You are feasibility-checking ONE hackathon project candidate. You have no prior conversation context. Use live web sources (endpoints in your instructions) — your own opinions about difficulty are inadmissible; only what you can quote and link counts. You may not write files, spawn further agents, or take any action beyond returning your answer.

## THE CANDIDATE
{{TITLE}} — {{PITCH}}
Demo moment: {{DEMO_MOMENT}}
Mandated-tech use: {{MANDATED_TECH_USE}}
Minimum slice and hours estimate: {{MINIMUM_SLICE}}

## THE EVENT
Productive build hours available: {{PRODUCTIVE_HOURS}}
Team and stacks already known: {{TEAM_AND_STACKS}}
Pre-work rules: {{PREWORK_RULES}}
Mandated tech: {{MANDATED_TECH}}

## CHECKS — run all six

1. ACCESS. Can every required API, model, dataset and service be obtained BEFORE the clock starts, by this team, at a cost they can cover? Look for waitlists, approval queues, enterprise-only tiers, KYC, and regional limits. Quote the page. Access that cannot be obtained in time is fatal, not inconvenient.
2. LIVE-DEMO LIMITS. Find the free or starter tier's rate limits, cold-start behaviour and latency. Can the demo moment survive being run three times in a row, in front of judges, on venue wifi? Name the specific limit and its URL.
3. THE HARD PART. Identify the single hardest technical step. Is it a maintained library or an official sample (name it, link it), a known-hard problem with partial solutions, or unsolved? Estimate the hours for this step alone and say what the estimate rests on.
4. PRIOR ART AND CROWDING. What already exists that does most of this? Check the mandated tech's own samples first — anything its quickstart leads to will be built by many entrants. Then past winners and GitHub. Report both effects: prior art makes the build easier AND makes the entry less distinctive.
5. PRE-WORK LEGALITY. Does the minimum slice depend on anything that would already exist before the clock starts — an existing repo, a trained model, a scraped dataset, a deployed service? Check that against the stated pre-work rules. A path that only works by breaking them is fatal.
6. STACK MATCH. Does the slice sit on stacks the team already knows? Where it does not, estimate the learning cost for the specific unfamiliar piece and say what that estimate rests on. Do not assume a productivity rate, and do not treat unfamiliar tech as automatically disqualifying — price it.

## RETURN FORMAT

### Verdict
One of: SHIPPABLE / TIGHT / DOWNGRADE / KILL (a KILL overrides the others).

### Evidence
- **Access**: obtainable before the clock? + quote/URL (gated access → KILL)
- **Live-demo limits**: the specific limit + URL, and whether the demo survives three runs
- **Hard part**: what it is, library/sample/unsolved + link, hours for this step
- **Prior art**: what exists + links, and whether an official sample does most of it
- **Pre-work legality**: clean / depends on pre-existing work (name it) + the rule it meets or breaks
- **Stack match**: known / unfamiliar piece + priced learning cost

### Hours
Your own estimate for the minimum slice, broken into the hard part, integration, the demo path, and the submission artifacts. Compare it to the productive-hours budget and say whether it fits.

### Crowding score
Expected-overlap (1–5: how many entrants plausibly ship something similar) with one line of justification from your links, not from intuition.

No preamble. If web access fails, return exactly: [FAILED — no web access].
```

## Hard thresholds (applied by the orchestrator, not the agent)

| Signal | Action |
|---|---|
| Required access needs a waitlist, approval, or a tier the team cannot get before the clock starts | **KILL** — the candidate cannot be entered, not merely risky. |
| The minimum slice only works by breaking the stated pre-work rules | **KILL** — a disqualified entry scores nothing. |
| No dataset, model or API exists for a load-bearing step | **KILL**. |
| Free-tier rate limits or cold starts cannot survive three consecutive live runs | DOWNGRADE, and require the escape hatch to name a recorded or cached fallback. |
| Hours for the minimum slice exceed the productive-hours budget | DOWNGRADE to Swing at best; never report as shippable. |
| The hard part is unsolved and is more than a third of the budget | DOWNGRADE. |
| An official sample app or quickstart does most of the project | DOWNGRADE for crowding — easy to build and identical to many entries. Say both. |
| Mandated tech is removable without breaking the project | DOWNGRADE — the sponsor judge scores this directly. |
| Crowding score 4–5 | DOWNGRADE unless the candidate's differentiation is a named, linked gap. |
| Feasibility agent failed | Mark `feasibility: UNVERIFIED`; never silently omit or guess. |

A KILL removes a candidate from both shortlists; report it in the evidence table with its reason rather than dropping it silently, so the user can see the path was considered and why it closed.

## What this stage cannot do (route to the human)

It cannot tell you the project will place — that needs the panel, and it is `hackathon-judge`'s job with the same rules block. It cannot confirm a limit that is only documented as "contact us", and it cannot measure venue wifi. A thirty-minute spike against the real API is worth more than every check here; the report's handoff says so.
