# idea-nebula-product

The product-first sibling of [`idea-nebula`](../idea-nebula/README.md). Same evidence-based idea generation, different definition of "best": ideas are ranked on how good they would be for the people using them, not on whether they would make money.

## What changed from idea-nebula

| idea-nebula | idea-nebula-product |
|---|---|
| One ranker judges novelty × plausibility × founder reachability × why-now | Three blind judges, one per axis: **Usability**, **Originality**, **Usefulness to the end user** |
| Ideas carry why-now and founder-fit fields | Ideas carry end user & moment, core interaction, why it's useful, what's original |
| Demand-check: ≥20 complaints, a paid vendor must exist, AI kill-zone needs a moat | User-check: ≥10 people describe the problem, what current tools fail at, already-solved check, core-interaction risk |
| Safe Picks + Moonshots | Rating matrix + Best Overall + Moonshots + Axis Leaders |
| Validate with fake doors, pre-sales, LOIs | Test with a prototype in front of 5 target users, or a Wizard-of-Oz version |
| `--founder` | removed — who builds it is not scored |

Every matrix cell is a round-robin duel record (W-D-L) judged in both presentation orders, never a 1–10 score. Each axis has its own judge so one overall impression can't inflate all three columns.

## Usage

```
/ThinkTime:idea-nebula-product <topic...> [--context <path>] [--wild <n>]
             [--banlist] [--no-check] [--check-top <n>] [--plain]
             [--write-to <path>] [--force]
```

Zero-ceremony default: `/ThinkTime:idea-nebula-product tools for people learning to cook at home` runs the full pipeline — four generators, prune, three axis judges, user-check on the top 5, matrix report.

## Pipeline

```
DIVERGE   4 generators in parallel, blind to each other:
          tails (VS tail ideas) · folk (ordinary personas) ·
          alien (far-domain mapping) · miner (live user-pain mining)
          each: draft → boldness revision → end-user + interaction stamps
POOL      strip attribution, dedupe, name the modal region, prune to ≤8
          (--banlist: re-run tails+alien with the modal region excluded)
JUDGE     3 judges in parallel — usability · originality · usefulness —
          each a round-robin of duels judged in BOTH orders
GROUND    per-finalist live user-check: ≥10 people with the problem,
          current-tool failures, already-solved, interaction risk
          (--no-check to skip)
REPORT    rating matrix, Best Overall, Moonshots, Axis Leaders,
          user evidence, modal-region map, test-next, human final cut
SAVE      offers to write the report (default
          docs/ideas/<topic-slug>-product-nebula.md)
```

## When to use which

- Side projects, open-source tools, free apps, internal tools, features inside an existing product → `idea-nebula-product`.
- Anything that has to find paying customers → `idea-nebula`.

## Install

```
claude plugin marketplace add z0rd0n88/ThinkTime
claude plugin install ThinkTime@thinktime
```
