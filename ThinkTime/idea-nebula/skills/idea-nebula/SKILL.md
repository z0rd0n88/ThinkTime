---
name: idea-nebula
description: 'Use when brainstorming new products, features, or business directions and a single-pass idea dump would yield the obvious — returns a demand-grounded, bias-controlled, barbell-ranked shortlist.'
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - Agent
  - WebSearch
  - WebFetch
---

# idea-nebula

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Spawns a large parallel agent batch by default** — a full run dispatches
> up to ~10 subagents (4 generators + 1 ranker + up to `--demand-top` demand
> checks), a token/agent budget well above a normal one-shot call.

Runs an evidence-based brainstorm pipeline: four independent entropy-source
generators propose ideas in parallel, then blind pairwise ranking and live
demand-grounding produce a barbell shortlist of Safe Picks and Moonshots. Use
it when a single-pass idea dump would just surface the obvious; it is not for
evaluating an idea that already exists, or for quick single-pass ideation
where speed matters more than diversity.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<topic...>` | free text | required | The problem space/topic to brainstorm; empty input hard-fails. |
| `--founder <desc>` | free text | "a solo developer or 2-person team, affordable-loss first step, no external permission or funding" | Grounds the founder-fit field in the report. |
| `--context <path>` | file or directory path | none | Background material prepended to every generator brief (16 KB cap; missing path hard-fails). |
| `--wild <n>` | `1` or `2` | `1` | Number of `alien` far-domain generators; `2` replaces `folk` to hold the 4-generator cap. |
| `--banlist` | flag | off | After round 1, names the modal region and re-runs `tails` + `alien` excluding it. |
| `--no-demand` | flag | off (demand-check ON) | Skips the live demand-check stage; forces an UNGROUNDED warning in the report. |
| `--demand-top <n>` | `1`–`8` | `5` | How many finalists get a live demand-check. |
| `--plain` | flag | off | Disables Verbalized Sampling and boldness revision (A/B comparison mode only). |
| `--write-to <path>` | file path | none | Also saves the report to disk; refuses if the file exists unless `--force`. |
| `--force` | flag | off | With `--write-to`, allows overwriting an existing file. |

## 1. Purpose

A brainstorming pipeline built from the 2024–2026 ideation research, not from brainstorming folklore. Four **independent parallel generators** attack the same topic — but each earns its slot by being a different **entropy source**, not a different persona label:

| Generator | Entropy source | Evidence |
|---|---|---|
| `tails` | Verbalized Sampling — surface low-probability tail ideas the RLHF mode collapse hides | VS: 1.6–2.1x diversity, training-free (arXiv 2510.01171) |
| `folk` | Ordinary-persona knowledge partitioning — heterogeneous everyday users, never experts/celebrities | Wharton 2402.01727: ordinary personas partition knowledge; celebrity personas rank near-bottom |
| `alien` | Far-domain defixation — forced analogy from a named unrelated domain with explicit structure-mapping | Best single defixation move in the literature; far transfer needs mapping scaffold |
| `miner` | Live external data — complaint/gap mining from the real web injects entropy the model's prior cannot fabricate | Ideation–execution gap (arXiv 2506.20803): ungrounded novelty is a liability |

Design rules this skill enforces (all evidence-backed — see the guide that motivated it):

- **No debate, no discussion between generators.** Dependent sampling collapses diversity round-over-round ("structural coupling"). Generators run blind to each other, in parallel, once.
- **Hard cap: 4 generators.** Group-size scaling and dense topologies accelerate premature convergence (Diversity Collapse, ACL 2026).
- **No method-cosplay lenses.** SCAMPER / C-K / Design-Thinking / mental-model persona prompts do not beat simple bold cues (IDEAFix). Generators use simple wild/bold/unconventional cues plus their entropy mechanism.
- **Mandatory boldness revision** in every generator: draft, then "revise each idea to be bolder and maximally distinct from the others" before emitting. Best-evidenced diversity lever (cosine 0.255 vs 0.377 base).
- **Blind pairwise ranking, judged in both orders.** Position bias flips ~1/3 of LLM-judge verdicts; Claude-class judges self-prefer by up to +25%. Pointwise 1–10 self-scores are banned.
- **Demand grounding before the verdict.** Top ideas get live complaint/vendor/kill-zone checks with hard thresholds.
- **Barbell output, human final cut.** Safe picks and moonshots are reported separately (never averaged into one list), and the report states explicitly that pre-execution scores are weak predictors — the human decides.

References (loaded only while running):
- [`references/generator-briefs.md`](references/generator-briefs.md) — shared output contract + the four generator briefs.
- [`references/ranking-and-synthesis.md`](references/ranking-and-synthesis.md) — prune → blind duels → barbell report structure.
- [`references/demand-check.md`](references/demand-check.md) — data sources, thresholds, gap scoring.

## 2. When to use

Trigger phrases:
- "brainstorm ideas for …" / "what could we build in <space>?"
- "find me a product/niche/direction in …"
- "run idea-nebula on …" / explicit `idea-nebula …`

Do NOT use for:
- Evaluating an *existing* idea — use `idea-autopsy:evaluate-proposal-harsh` or `idea-autopsy:stress-test-idea`.
- Quick single-pass ideation where speed beats diversity — just answer directly.
- Anything that writes to source files — this skill is read-only (except `--write-to`).

## 3. Invocation grammar

```
idea-nebula <topic...> [--founder <desc>] [--context <path>] [--wild <n>]
            [--banlist] [--no-demand] [--demand-top <n>] [--plain]
            [--write-to <path>] [--force]
```

| Position / flag | Required | Values |
|---|---|---|
| `<topic...>` | yes | Free-text topic/problem space. Everything not consumed by a flag. Empty → hard-fail. |
| `--founder <desc>` | no | Who is building — grounds the founder-fit field. Default: `"a solo developer or 2-person team, affordable-loss first step, no external permission or funding"`. |
| `--context <path>` | no | File or directory of background material prepended to every generator brief. Resolved relative to repo root when not absolute; missing → hard-fail; 16 KB cap (dir = concatenated tracked files, same cap). |
| `--wild <n>` | no | Number of `alien` defixation generators (1–2, each with a *different* forced domain). Default 1. n=2 replaces `folk` to hold the 4-cap. |
| `--banlist` | no | After round 1, name the modal region and re-run `tails` + `alien` once with it excluded; merge new ideas into the pool before ranking. |
| `--no-demand` | no | Skip the demand-check stage (faster; the report must then carry a prominent UNGROUNDED warning). |
| `--demand-top <n>` | no | How many finalists get demand-checked. Default 5, max 8. |
| `--plain` | no | Disable VS and boldness revision (A/B comparison mode only — never the default). |
| `--write-to <path>` | no | Also save the report; refuse if the file exists unless `--force`. |
| `--force` | no | With `--write-to`, allow overwriting. |

## 4. Workflow

### Stage 0 — Parse and validate
1. Split topic from flags. Hard-fail on empty topic with a one-line usage summary.
2. Resolve `--context` (absolute; hard-fail if missing; 16 KB cap) into `{{CONTEXT_BLOCK}}`; absent → strip the block from briefs.
3. `--write-to` overwrite guard runs HERE, before any agent is spawned.
4. Resolve `{{FOUNDER}}` from `--founder` or the default.

### Stage 1 — DIVERGE: spawn generators IN PARALLEL

> ⚠️ **PARALLELISM RULE — DO NOT SERIALIZE, DO NOT LET GENERATORS INTERACT.** All generator `Agent` calls MUST be issued in a SINGLE assistant message. Each brief is fully self-contained; generators share no state and never see each other's output. `subagent_type: general-purpose`, `description: "idea-nebula: <generator>"`.

Default roster: `tails`, `folk`, `alien`, `miner`. With `--wild 2`: `tails`, `alien`×2 (each forced to a different domain), `miner` — `folk` is dropped to hold the 4-cap. Expand each brief from `references/generator-briefs.md` with `{{TOPIC}}`, `{{CONTEXT_BLOCK}}`, `{{FOUNDER}}`, and the generator-specific instruction. The `miner` generator needs live web access (WebSearch/WebFetch/Bash for `curl`/`gh`) — prepend the §Sources table from `references/demand-check.md` into its brief, since the brief refers to "the endpoints you were given".

With `--plain`: strip the VS and boldness-revision instructions from the briefs (comparison mode).

### Stage 2 — Collect and pool
Capture each generator's output verbatim. A generator that fails/returns empty is noted as `<name>: [FAILED — no output]`; continue if ≥2 generators returned. **Strip generator attribution** from each idea before ranking (blind judging — the ranker must not know which mechanism produced an idea); keep a private attribution map for the final report.

If `--banlist`: identify the modal region now (the idea-space cluster that any generic brainstorm would produce — themes appearing across ≥3 generators or matching obvious category tropes), then re-run `tails` and `alien` once with an explicit exclusion list appended to their briefs. Merge new ideas into the pool.

### Stage 3 — CONVERGE: blind ranking
One `Agent` call (`description: "idea-nebula: rank"`) with the ranking brief from `references/ranking-and-synthesis.md`:
1. Dedupe the pool; convergence across generators = stronger signal, note it.
2. Prune to ≤8 finalists (drop dominated ideas: strictly less novel AND less plausible AND less reachable than another).
3. Round-robin **pairwise duels among finalists, every pair judged in BOTH orders**; only order-consistent wins count, order-flips are draws. Standings by win count.
4. Name the **modal region** explicitly, and score each finalist's novelty as *distance from that modal region* (justified in one line each) — never as a self-asserted number.

### Stage 4 — GROUND: demand-check (default ON)
Unless `--no-demand`: one `Agent` call per finalist up to `--demand-top`, IN PARALLEL (`description: "idea-nebula: demand <title>"`), each running the live-mining brief from `references/demand-check.md` with the §Sources table prepended. Hard thresholds: <20 independent complaints → DOWNGRADE flag; no existing paid vendor/substitute → DOWNGRADE; free ChatGPT/Claude covers ≥80% of core function with no data/community/network moat → KILL-ZONE flag. Each returns a demand-evidence block with sourced links/quotes.

### Stage 5 — REPORT
Assemble the final report per `references/ranking-and-synthesis.md` §Report: executive summary → **Safe Picks** and **Moonshots** (barbell, separate lists) → demand-evidence table → modal-region map → convergence & productive disagreement → what-to-validate-next (fake-door / LOI playbook pointers) → the mandatory human-final-cut disclaimer. Print verbatim as the final message. If `--write-to`: `mkdir -p` parent, write, prepend `Wrote: <absolute path>`. Suggest the follow-on pipeline: `idea-autopsy:iterate-to-v2` → `product-management:write-spec` / `to-prd` → `idea-autopsy:evaluate-proposal-harsh`.

### Stage 6 — OFFER TO SAVE
Skip this stage entirely when `--write-to` was given (the report is already on disk). Otherwise, after printing the report, prompt the user to save it — a report this size is lost to scrollback and context compaction if it only lives in the conversation. Ask (via AskUserQuestion when available, else a plain question) whether to save, suggesting a default path: `docs/ideas/<topic-slug>-nebula.md` relative to the repo root, or `<topic-slug>-nebula.md` in the cwd outside a repo. On yes: `mkdir -p` the parent, write the report verbatim, confirm with `Wrote: <absolute path>`; if the file already exists, refuse and ask for a different path or explicit overwrite confirmation (same guard as `--write-to` without `--force`). On no: end without writing.

## 5. Error handling

| Condition | Action |
|---|---|
| Empty topic | Hard-fail with usage summary; spawn nothing. |
| `--context` missing / over 16 KB | Hard-fail with path and cap. |
| `--write-to` exists, no `--force` | Hard-fail in Stage 0. |
| `--wild` outside 1–2 | Clamp, warn. |
| `--demand-top` outside 1–8 | Clamp, warn. |
| A generator fails | Note `[FAILED]`, continue if ≥2 returned; else hard-fail. |
| `miner` has no web access | Note it, continue with 3 generators, and force the UNGROUNDED warning in the report. |
| Demand-check agent fails for an idea | Mark that idea `demand: UNVERIFIED` in the table; never silently omit. |
| Ranker fails | Print `Ranker failed. Generator outputs follow:` and dump each verbatim with `---` delimiters (write to `--write-to` too if set). |

## 6. Red flags — the ranking is lying to you if…

- Any idea carries a bare novelty/plausibility score with no modal-region distance justification.
- The shortlist is one merged ranking instead of Safe Picks + Moonshots.
- A duel verdict was accepted from a single presentation order.
- The report recommends building anything without demand evidence or an explicit UNGROUNDED warning.
- Generators produced ideas that survive swapping the topic's noun for a neighboring vertical — that's the modal region wearing a costume; it must be named as such, not ranked as novel.
