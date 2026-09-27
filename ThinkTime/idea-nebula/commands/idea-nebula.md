---
description: "Evidence-based brainstorm: 4 independent entropy-source generators, blind pairwise ranking, live demand grounding, barbell shortlist"
argument-hint: "<topic...> [--founder <desc>] [--context <path>] [--wild <n>] [--banlist] [--no-demand] [--write-to <path>]"
---

Invoke the `idea-nebula` skill and follow it exactly.

Arguments forwarded: `$ARGUMENTS`

The skill will:

1. Spawn 4 independent generators IN PARALLEL (no debate, no shared state): `tails` (verbalized-sampling tail ideas), `folk` (ordinary-persona knowledge partitioning), `alien` (far-domain defixation with structure-mapping), `miner` (live complaint/gap mining from HN, Reddit, GitHub, Product Hunt). Every generator runs a mandatory boldness-revision pass and stamps each idea with why-now + founder-fit.
2. Pool ideas BLIND (attribution stripped), dedupe, name the modal region, prune to ≤8 finalists.
3. Rank via round-robin pairwise duels judged in BOTH orders (order-inconsistent verdicts = draws). No pointwise self-scores.
4. Demand-check the top finalists in parallel against live web evidence (≥20-complaint threshold, vendor check, AI-kill-zone check).
5. Report a barbell shortlist — Safe Picks + Moonshots, never one merged ranking — with demand evidence, the modal-region map, and an explicit human-final-cut disclaimer.
6. Offer to save the report to a file (suggested default: `docs/ideas/<topic-slug>-nebula.md`) when `--write-to` wasn't given, so the shortlist survives scrollback and compaction.

Common invocations:

```
idea-nebula tools for indie coffee shops
idea-nebula developer tooling for Claude Code plugin authors --wild 2
idea-nebula compliance automation --founder "ex-auditor, no coding background" --banlist
idea-nebula authentication UX --context docs/research/ --write-to docs/ideas/auth-nebula.md
```

Common flags:
- `--founder <desc>` — who's building (grounds the founder-fit field; default: solo dev / 2-person team)
- `--wild <n>` — 1–2 defixation generators (2 replaces `folk` to hold the 4-generator cap)
- `--banlist` — round 2 with the modal region explicitly excluded
- `--no-demand` — skip live demand mining (report carries an UNGROUNDED warning)
- `--write-to <path>` — save the report (refuses to overwrite without `--force`)
