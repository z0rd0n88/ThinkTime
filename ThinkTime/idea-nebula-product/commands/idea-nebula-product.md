---
description: "Product-first brainstorm: 4 independent generators, a blind usability/originality/usefulness rating matrix, live user-need grounding"
argument-hint: "<topic...> [--context <path>] [--wild <n>] [--banlist] [--no-check] [--write-to <path>]"
---

Invoke the `idea-nebula-product` skill and follow it exactly.

Arguments forwarded: `$ARGUMENTS`

The skill will:

1. Spawn 4 independent generators IN PARALLEL (no debate, no shared state): `tails` (verbalized-sampling tail ideas), `folk` (ordinary-persona knowledge partitioning), `alien` (far-domain defixation with structure-mapping), `miner` (live user-pain mining from HN, Reddit, GitHub, app reviews). Every generator runs a mandatory boldness-revision pass and stamps each idea with end user, core interaction, usefulness, and originality fields.
2. Pool ideas BLIND (attribution stripped), dedupe, name the modal region, prune to ≤8 finalists.
3. Rank with three separate judges — Usability, Originality, Usefulness — each running round-robin pairwise duels judged in BOTH orders. The three duel records form the rating matrix. Revenue, market size, and founder fit are never scored.
4. User-check the top finalists in parallel against live web evidence (≥10 people describing the problem, current-tool failures, already-solved check, core-interaction risk).
5. Report the rating matrix, Best Overall picks, Moonshots, and per-axis leaders, with user evidence, the modal-region map, and an explicit human-final-cut paragraph.
6. Offer to save the report (suggested default: `docs/ideas/<topic-slug>-product-nebula.md`) when `--write-to` wasn't given.

Common invocations:

```
idea-nebula-product tools for people learning to cook at home
idea-nebula-product open-source developer tools for Claude Code plugin authors --wild 2
idea-nebula-product accessibility aids for older smartphone users --banlist
idea-nebula-product note-taking for students --context docs/research/ --write-to docs/ideas/notes-product-nebula.md
```

Common flags:
- `--wild <n>` — 1–2 defixation generators (2 replaces `tails`; `folk` stays)
- `--banlist` — round 2 with the modal region explicitly excluded
- `--no-check` — skip live user-need mining (report carries an UNGROUNDED warning)
- `--write-to <path>` — save the report (refuses to overwrite without `--force`)
