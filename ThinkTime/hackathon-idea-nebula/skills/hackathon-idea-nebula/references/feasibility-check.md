# Feasibility check — sources, checks, hard thresholds

Used by the `scout` generator (Stage 2) and the per-finalist feasibility agents (Stage 5). Not loaded unless the skill is running.

## Why this stage is non-negotiable

Hackathons are not lost to bad ideas; they are lost to the integration nobody checked. The credential that needs a sales call, the free tier that rate-limits at 20 requests an hour, the "simple" hard part with no library in your language, the dataset that does not exist publicly — each converts a 24-hour plan into a 3am rewrite. Evidence here means **build-feasibility evidence**, not market evidence: prior art, API availability and limits, whether a library owns the hard part, whether the data exists. Your opinion about whether something is doable is inadmissible; only what you can quote and link counts.

## Sources a subagent can actually hit (2026)

| Source | How | Notes |
|---|---|---|
| Prior art / saturation | WebSearch `site:devpost.com "<theme>"`, the event's own past-winner pages, hackathon recap posts | Two reads: what saturates submissions (avoid) and what the panel rewarded (learn). Quote titles + URLs. |
| Vendor/API docs | WebFetch the quickstart and pricing/limits pages directly | The only authority on credential flow, free tier, rate limits, documented latency. Quote the limit numbers. |
| Credential reality | The signup page itself: instant key vs. waitlist vs. "contact sales" vs. card required | A gated credential is a hard DOWNGRADE — you cannot build on it this weekend. |
| Library coverage | `gh search repos "<hard part>" --limit 20`, package registries (npm/PyPI/crates.io), GitHub issues for known breakage | The question is whether a library in the team's stack owns the hard part, maintained and installable today. |
| Data existence | WebSearch for the dataset/API that supplies the demo's data; HuggingFace datasets, public APIs | A demo whose data does not exist is a demo that does not exist. |
| Model/API status | Status pages, recent issue threads | Known outages and deprecations inside the event window. |

## Per-finalist feasibility brief

One agent per finalist, spawned in parallel. `subagent_type: general-purpose`.

```
You are feasibility-checking ONE candidate hackathon project. You have no prior conversation context. Use live sources (endpoints in your instructions) — your own impressions of what is doable are inadmissible; only what you can quote and link counts.

## CANDIDATE
{{TITLE}} — {{PITCH}}
Hard part as claimed: {{HARD_PART}}
Wow moment: {{WOW_MOMENT}}

## CONSTRAINTS
Duration: {{DURATION}} | Team: {{TEAM}} | Stack: {{STACK}} (no time to learn anything new)
Mandated technology: {{MANDATED_TECH}} | Pre-work rules: {{PREWORK_RULES}}

## CHECKS — run all six

1. PRIOR ART AND SATURATION. Has this been built and submitted at comparable events? How many times, and did any win? Record counts, titles, URLs. A project that appears repeatedly in submission galleries is SATURATED — differentiation is already lost.
2. CREDENTIAL AND AVAILABILITY. For every external service this needs: does a usable credential issue instantly and free? Quote the signup/pricing page. Waitlist, sales call, or card-required → say so explicitly.
3. LIMITS AND LATENCY. Quote the documented rate limits, quotas and latency. Decide and state: do these survive a live demo (repeated calls, a judge's own input, a cold start)?
4. LIBRARY COVERAGE OF THE HARD PART. Does a maintained library in the stated stack own the claimed hard part? Name it, link it, note last release. If nothing owns it, say what would have to be written and roughly how much of the duration that consumes. If a single API call owns it, say so — the hard part is a wrapper.
5. DATA EXISTENCE. Does the data the demo needs exist, publicly, in a form that can be loaded this weekend? Link it. If it must be generated or hand-made, say how much.
6. RULE COMPLIANCE. Is the mandated technology used non-trivially (not swappable for any competitor without changing the project)? Does anything in the build sketch require pre-work the rules forbid? Can the submission requirements be met in the remaining time?

## RETURN FORMAT

### Verdict
One of: FEASIBLE / TIGHT / DOWNGRADE / BLOCK (a rule violation is BLOCK and overrides everything else).

### Evidence
- **Prior art**: count + titles + URLs (or "none found")
- **Credentials**: per service — instant/free, gated, or paid — with the quoted page + link
- **Limits & latency**: quoted numbers + whether they survive a live demo
- **Hard part**: the library that owns it (+ link, last release), or what must be written, or "wrapper — one API call"
- **Data**: link + form, or what must be fabricated
- **Rule compliance**: mandated tech used non-trivially (yes/no + how); pre-work risk; submission feasibility

### Time estimate
The hard part's realistic cost in hours for this team and stack, with one line of justification, and what fraction of the usable duration that is.

No preamble. If web access fails, return exactly: [FAILED — no web access].
```

## Hard thresholds (applied by the orchestrator, not the agent)

| Signal | Action |
|---|---|
| Credential gated behind waitlist, sales contact, or paid-only | DOWNGRADE — cannot be built on this weekend. |
| Rate limits or latency that break a repeated live demo | DOWNGRADE, and the report names the limit. |
| Hard part has no library in the stated stack and is not shippable in the window | DOWNGRADE with the hour estimate quoted. |
| Hard part is one API call | WRAPPER flag — the technical judge discounts it; say so in the scorecard section. |
| Project appears repeatedly in comparable submission galleries | SATURATED — differentiation scores near zero. |
| Required data does not exist publicly | DOWNGRADE unless fabricating it is itself inside the slice. |
| Mandated tech unused or trivially used, or pre-work rules violated | **RULE-RISK BLOCK** — forces PICK SOMETHING ELSE regardless of score. |
| Feasibility agent failed | Mark `feasibility: UNVERIFIED`; never silently omit, never guess. |

## What this stage cannot do (route to the human)

It cannot confirm the venue wifi, the laptop, the sponsor's booth support, or how the panel behaves on the day. It also cannot run the code. The one thing that converts a plan into evidence is a 30-minute spike before committing: issue the credential, make one real call, confirm the limit. The report's hour-by-hour plan puts that spike first for exactly this reason.
