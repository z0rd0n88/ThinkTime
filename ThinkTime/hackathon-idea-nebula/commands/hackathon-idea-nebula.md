---
description: "Hackathon project generation: 4 entropy-source generators, two blind rankings (buildable vs winnable), live feasibility grounding, simulated judge panel, hour-by-hour plan"
argument-hint: "<theme...> --rules <path> [--stack <desc>] [--team <n>] [--prize <category>] [--wild <n>] [--banlist] [--no-feasibility] [--write-to <path>]"
---

Invoke the `hackathon-idea-nebula` skill and follow it exactly.

Arguments forwarded: `$ARGUMENTS`

The skill answers two SEPARATE questions — is this worth spending the event on, and would it win — and never merges them. It requires a RULES AND CONSTRAINTS block (duration, theme, mandated tech, team cap, pre-work rules, submission requirements, the event's published rubric, prize categories). **With no rules supplied it stops and asks; it does not guess the event.**

The skill will:

1. Derive the rubric from the rules — the event's published criteria and weights verbatim when they exist, otherwise a stated default rubric (demoability, buildability, differentiation, judge legibility, scope escape hatch, rule compliance), reshaped for the targeted prize category.
2. Spawn 4 independent generators IN PARALLEL (no debate, no shared state): `tails` (verbalized-sampling tail ideas), `stage` (reverse-engineered from the on-stage wow moment), `alien` (far-domain defixation with structure-mapping), `scout` (live prior-art, credential, rate-limit and library mining). Every generator runs a boldness-revision pass and stamps each idea with its wow moment, hard part, rule compliance and escape hatch.
3. Rank the blind pool TWICE — once on "will it ship a working demo", once on "will it score under the rubric" — via round-robin duels judged in BOTH orders. No pointwise self-scores, no merged ranking.
4. Feasibility-check the top finalists against live evidence: credential availability, rate limits and latency, whether a library owns the hard part, whether the data exists, prior-art saturation, and mandated-tech compliance.
5. Simulate the panel as four conflicting judges (sponsor engineer, business judge, technical judge, time-pressured generalist), score each independently against the rubric, and report where they split — a split criterion is where the project is fragile.
6. Report both verdicts first, then the rubric provenance, judge scorecards, disagreements, the complete unfiltered findings list and evidence gaps, then the minimum demoable slice, a Not Doing list, and an hour-by-hour plan fitted to the stated duration.

Common invocations:

```
hackathon-idea-nebula climate tech --rules docs/events/climathon-rules.md
hackathon-idea-nebula agents for ops --rules rules.md --stack "TypeScript, Next.js, Postgres" --team 2
hackathon-idea-nebula fintech --rules rules.md --prize "Best use of the Plaid API" --wild 2
hackathon-idea-nebula local community tools --rules rules.md --banlist --write-to docs/ideas/weekend.md
```

Common flags:
- `--rules <path>` — the RULES AND CONSTRAINTS block (required; the skill stops and asks without it)
- `--stack <desc>` — what the team already ships in; no idea may require learning a new stack
- `--prize <category>` — the specific category targeted (reshapes the rubric)
- `--wild <n>` — 1–2 defixation generators (2 replaces `stage` to hold the 4-generator cap)
- `--banlist` — round 2 with the modal region (chatbot-over-your-docs and friends) excluded
- `--no-feasibility` — skip live grounding (report carries an UNGROUNDED warning)
- `--write-to <path>` — save the report (refuses to overwrite without `--force`)
