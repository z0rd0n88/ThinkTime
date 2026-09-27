# idea-nebula

Evidence-based brainstorming pipeline for Claude Code. Built from the 2024–2026 ideation research — not brainstorming folklore.

## Executive summary

Naive LLM brainstorming reliably produces the **modal region**: the same scheduling/CRM/marketplace/dashboard ideas for any vertical, ranked by self-asserted scores, with no demand evidence. `idea-nebula` attacks each documented failure with the intervention the research validated:

| Failure | Intervention | Evidence |
|---|---|---|
| RLHF mode collapse → homogeneous ideas | Verbalized Sampling: generate with explicit probabilities, keep only the tail | 1.6–2.1x diversity, training-free (arXiv 2510.01171) |
| Idea sets converge on each other | Mandatory boldness-revision pass in every generator | Best diversity lever of 35 strategies (Wharton, arXiv 2402.01727) |
| Persona/method prompts don't help | No SCAMPER/C-K/mental-model cosplay; ordinary-user sampling + simple bold cues | IDEAFix (arXiv 2606.00875) |
| Fixation on the obvious | Far-domain analogy with explicit structure-mapping | Strongest single defixation move in the literature |
| Debate/groupthink kills diversity | 4 independent parallel generators, hard cap, zero interaction | Diversity Collapse (ACL 2026 Findings) |
| Judges are biased (position, verbosity, self-preference) | Blind pairwise duels judged in both orders; pointwise scores banned | MT-Bench (arXiv 2306.05685) |
| Novel ideas flop when built | Live demand mining (HN Algolia, Reddit, GitHub) with hard thresholds + kill-zone check | Ideation–execution gap (arXiv 2506.20803) |
| Averaging kills sharp edges | Barbell output: Safe Picks + Moonshots, human final cut | Portfolio literature + Stanford RCTs |

## Usage

```
/ThinkTime:idea-nebula <topic...> [--founder <desc>] [--context <path>] [--wild <n>]
             [--banlist] [--no-demand] [--demand-top <n>] [--plain]
             [--write-to <path>] [--force]
```

Zero-ceremony default: `/ThinkTime:idea-nebula tools for indie coffee shops` runs the full pipeline — four generators, blind ranking, demand-check on the top 5, barbell report.

## Pipeline

```
DIVERGE   4 generators in parallel, blind to each other:
          tails (VS tail ideas) · folk (ordinary personas) ·
          alien (far-domain mapping) · miner (live complaint mining)
          each: draft → boldness revision → why-now + founder-fit stamps
POOL      strip attribution, dedupe, name the modal region
          (--banlist: re-run tails+alien with the modal region excluded)
RANK      ≤8 finalists, round-robin duels judged in BOTH orders
GROUND    per-finalist live demand-check: ≥20-complaint threshold,
          vendor check, AI-kill-zone check  (--no-demand to skip)
REPORT    Safe Picks + Moonshots (never merged), demand-evidence table,
          modal-region map, validate-next playbook, human final cut
SAVE      offers to write the report to a file (default
          docs/ideas/<topic-slug>-nebula.md) when --write-to wasn't given
```

## Relationship to other plugins

- **idea-panel** (this plugin) is the predecessor — a mental-model lens panel. idea-nebula supersedes its generation strategy based on evidence that method/persona lenses underperform simple bold cues + real entropy sources. idea-panel remains available.
- Downstream: `idea-autopsy:iterate-to-v2` → `product-management:write-spec` / `to-prd` → `idea-autopsy:evaluate-proposal-harsh`.

## Install

```
claude plugin marketplace add z0rd0n88/ThinkTime
claude plugin install ThinkTime@thinktime
```
