---
name: idea-nebula-product
description: 'Use when brainstorming products or features judged on how good they are for users rather than on profit — usability, originality, and end-user usefulness over revenue, market size, or founder fit.'
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

# idea-nebula-product

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Spawns a large parallel agent batch by default** — a full run dispatches
> up to ~13 subagents (4 generators + 1 prune + 3 axis judges + up to
> `--check-top` user checks), a token/agent budget well above a normal one-shot call.

The product-first sibling of `idea-nebula`. Four independent entropy-source
generators propose ideas in parallel; three blind judges each rank the finalists
on one axis — usability, originality, usefulness to the end user — producing a
rating matrix; a live user-check tests whether real people have the problem.
Revenue, market size, and founder fit are not scored. Use it when you want the
best product for its users, not the best business; use `idea-nebula` when the
idea has to make money.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<topic...>` | free text | required | The problem space/topic to brainstorm; empty input hard-fails. |
| `--context <path>` | file or directory path | none | Background material prepended to every generator brief (16 KB cap; missing path hard-fails). |
| `--wild <n>` | `1` or `2` | `1` | Number of `alien` far-domain generators; `2` replaces `tails` to hold the 4-generator cap. |
| `--banlist` | flag | off | After round 1, names the modal region and re-runs `tails` + `alien` excluding it. |
| `--no-check` | flag | off (user-check ON) | Skips the live user-check stage; forces an UNGROUNDED warning in the report. |
| `--check-top <n>` | `1`–`8` | `5` | How many finalists get a live user-check. |
| `--plain` | flag | off | Disables Verbalized Sampling and boldness revision (A/B comparison mode only). |
| `--write-to <path>` | file path | none | Also saves the report to disk; refuses if the file exists unless `--force`. |
| `--force` | flag | off | With `--write-to`, allows overwriting an existing file. |

## 1. Purpose

Same generation engine as `idea-nebula` — four **independent parallel generators**, each a different **entropy source** — but a different definition of "best". `idea-nebula` ranks on novelty × plausibility × founder reachability × why-now and grounds ideas in paid demand. This skill ranks on three user-side axes only and grounds ideas in whether real people have the problem.

| Generator | Entropy source | Evidence |
|---|---|---|
| `tails` | Verbalized Sampling — surface low-probability tail ideas the RLHF mode collapse hides | VS: 1.6–2.1x diversity, training-free (arXiv 2510.01171) |
| `folk` | Ordinary-persona knowledge partitioning — heterogeneous everyday users, never experts/celebrities | Wharton 2402.01727: ordinary personas partition knowledge; celebrity personas rank near-bottom |
| `alien` | Far-domain defixation — forced analogy from a named unrelated domain with explicit structure-mapping | Best single defixation move in the literature; far transfer needs mapping scaffold |
| `miner` | Live user-pain mining — real complaints and current-tool failures from the web | Ideation–execution gap (arXiv 2506.20803): ungrounded novelty is a liability |

The rating matrix:

| Axis | The judge's question |
|---|---|
| Usability | Which would its end user find easier to start and keep using? |
| Originality | Which is farther from the modal region and from what the user can already get? |
| Usefulness | Which would matter more to its end user — more painful or frequent problem, more benefit per use? |

Design rules this skill enforces:

- **No debate, no discussion between generators.** Dependent sampling collapses diversity round-over-round. Generators run blind to each other, in parallel, once.
- **Hard cap: 4 generators.** Larger groups converge faster (Diversity Collapse, ACL 2026).
- **Mandatory boldness revision** in every generator: draft, then revise each idea bolder and maximally distinct before emitting.
- **One judge per axis.** A judge scoring several criteria lets its overall impression bleed into each (halo effect). Each axis judge sees only its own question.
- **Every matrix cell is a duel record, judged in both orders.** Position bias flips ~1/3 of LLM-judge verdicts; pointwise 1–10 scores are banned.
- **User grounding before the verdict.** Top ideas get a live check for real need, current-tool failures, and whether something already solves it.
- **Human final cut.** The report states that pre-execution scores are weak predictors and that usability only shows up in real use.

References (loaded only while running):
- [`references/generator-briefs.md`](references/generator-briefs.md) — shared output contract + the four generator briefs.
- [`references/ranking-and-synthesis.md`](references/ranking-and-synthesis.md) — prune → three axis judges → matrix → report structure.
- [`references/user-check.md`](references/user-check.md) — data sources, thresholds, need scoring.

## 2. When to use

Trigger phrases:
- "brainstorm the best product for …" / "what would users love in <space>?"
- "ideas for a side project / open-source tool / free app for …"
- "rank these by usability / originality / usefulness"
- "run idea-nebula-product on …" / explicit `idea-nebula-product …`

Do NOT use for:
- Ideas that must make money or attract funding — use `idea-nebula`.
- Evaluating an *existing* idea — use `idea-autopsy:evaluate-proposal-harsh` or `idea-autopsy:stress-test-idea`.
- Quick single-pass ideation where speed beats diversity — just answer directly.
- Anything that writes to source files — this skill is read-only (except `--write-to`).

## 3. Invocation grammar

```
idea-nebula-product <topic...> [--context <path>] [--wild <n>] [--banlist]
                    [--no-check] [--check-top <n>] [--plain]
                    [--write-to <path>] [--force]
```

| Position / flag | Required | Values |
|---|---|---|
| `<topic...>` | yes | Free-text topic/problem space. Everything not consumed by a flag. Empty → hard-fail. |
| `--context <path>` | no | File or directory of background material prepended to every generator brief. Resolved relative to repo root when not absolute; missing → hard-fail; 16 KB cap (dir = concatenated tracked files, same cap). |
| `--wild <n>` | no | Number of `alien` defixation generators (1–2, each with a *different* forced domain). Default 1. n=2 replaces `tails`; `folk` stays because it samples end users directly. |
| `--banlist` | no | After round 1, name the modal region and re-run `tails` + `alien` once with it excluded (with `--wild 2`, both `alien`s); merge new ideas into the pool before ranking. |
| `--no-check` | no | Skip the user-check stage (faster; the report must then carry a prominent UNGROUNDED warning). |
| `--check-top <n>` | no | How many finalists get user-checked. Default 5, max 8. |
| `--plain` | no | Disable VS and boldness revision (A/B comparison mode only — never the default). |
| `--write-to <path>` | no | Also save the report; refuse if the file exists unless `--force`. |
| `--force` | no | With `--write-to`, allow overwriting. |

## 4. Workflow

### Stage 0 — Parse and validate
1. Split topic from flags. Hard-fail on empty topic with a one-line usage summary.
2. Resolve `--context` (absolute; hard-fail if missing; 16 KB cap) into `{{CONTEXT_BLOCK}}`; absent → strip the block from briefs.
3. `--write-to` overwrite guard runs HERE, before any agent is spawned.

### Stage 1 — DIVERGE: spawn generators IN PARALLEL

> ⚠️ **PARALLELISM RULE — DO NOT SERIALIZE, DO NOT LET GENERATORS INTERACT.** All generator `Agent` calls MUST be issued in a SINGLE assistant message. Each brief is fully self-contained; generators share no state and never see each other's output. `subagent_type: general-purpose`, `description: "idea-nebula-product: <generator>"`.

Default roster: `tails`, `folk`, `alien`, `miner`. With `--wild 2`: `folk`, `alien`×2 (each forced to a different domain), `miner`. Expand each brief from `references/generator-briefs.md` with `{{TOPIC}}`, `{{CONTEXT_BLOCK}}`, and the generator-specific instruction. The `miner` generator needs live web access (WebSearch/WebFetch/Bash for `curl`/`gh`) — prepend the §Sources table from `references/user-check.md` into its brief, since the brief refers to "the endpoints you were given".

With `--plain`: strip the VS and boldness-revision instructions from the briefs (comparison mode).

### Stage 2 — Collect and pool
Capture each generator's output verbatim. A generator that fails/returns empty is noted as `<name>: [FAILED — no output]`; continue if ≥2 generators returned. **Strip generator attribution** from each idea before ranking (blind judging); keep a private attribution map for the final report.

If `--banlist`: identify the modal region now (themes appearing across ≥3 generators or matching obvious category tropes), then re-run `tails` and `alien` once with the exclusion appendix from `references/generator-briefs.md` (with `--wild 2`, re-run both `alien`s instead). Merge new ideas into the pool.

### Stage 3 — CONVERGE: prune, then three axis judges
Follow `references/ranking-and-synthesis.md`:
1. **Prune** — one `Agent` call (`description: "idea-nebula-product: prune"`): dedupe, name the modal region, drop off-topic ideas, prune to ≤8 finalists (drop only ideas dominated on all three axes).
2. **Judge** — three `Agent` calls in ONE message (`description: "idea-nebula-product: judge <axis>"`), one per axis. Each runs round-robin duels over the finalists, every pair judged in BOTH orders; only order-consistent wins count, order-flips are draws.
3. **Matrix** — you join the three standings on ID and compute total wins. Best Overall, Moonshots, and Axis Leaders are picked in Stage 5, after the user-check flags are in.

### Stage 4 — GROUND: user-check (default ON)
Unless `--no-check`: one `Agent` call per finalist, top `--check-top` by total wins, IN PARALLEL (`description: "idea-nebula-product: check <title>"`), each running the brief from `references/user-check.md` with the §Sources table prepended. Flags: <10 independent people describing the problem → NEED-UNPROVEN; an existing product already does it well → ALREADY-SOLVED; evidence contradicts the core interaction → INTERACTION-RISK. Each returns an evidence block with sourced quotes and links.

### Stage 5 — REPORT
Assemble the report per `references/ranking-and-synthesis.md` §Report: executive summary → **Rating Matrix** → Best Overall → Moonshots → Axis Leaders → user-evidence table → modal-region map → convergence & disagreement → test-next → the mandatory final-cut paragraph. Print verbatim as the final message. If `--write-to`: `mkdir -p` parent, write, prepend `Wrote: <absolute path>`. Suggest the follow-on: build a throwaway prototype of the top pick (e.g. the `prototype` skill) and put it in front of 5 target users.

### Stage 6 — OFFER TO SAVE
Skip this stage entirely when `--write-to` was given. Otherwise, after printing the report, ask (via AskUserQuestion when available, else a plain question) whether to save it, suggesting `docs/ideas/<topic-slug>-product-nebula.md` relative to the repo root, or `<topic-slug>-product-nebula.md` in the cwd outside a repo. On yes: `mkdir -p` the parent, write the report verbatim, confirm with `Wrote: <absolute path>`; if the file already exists, refuse and ask for a different path or explicit overwrite confirmation. On no: end without writing.

## 5. Error handling

| Condition | Action |
|---|---|
| Empty topic | Hard-fail with usage summary; spawn nothing. |
| `--context` missing / over 16 KB | Hard-fail with path and cap. |
| `--write-to` exists, no `--force` | Hard-fail in Stage 0. |
| `--wild` outside 1–2 | Clamp, warn. |
| `--check-top` outside 1–8 | Clamp, warn. |
| A generator fails | Note `[FAILED]`, continue if ≥2 returned; else hard-fail. |
| `miner` has no web access | Note it, continue with 3 generators, and force the UNGROUNDED warning in the report. |
| Prune agent fails | Print `Prune step failed. Generator outputs follow:` and dump each verbatim with `---` delimiters (write to `--write-to` too if set). |
| One axis judge fails | Show `—` in that matrix column, say which axis is missing above the matrix, and compute totals from the remaining two. |
| Two or more axis judges fail | Print the finalists and any standings that did return, labelled as an incomplete matrix. |
| User-check agent fails for an idea | Mark that idea `user-check: UNCHECKED` in the table; never silently omit. |

## 6. Red flags — the matrix is lying to you if…

- A matrix cell holds a bare 1–10 score instead of a W-D-L duel record.
- One judge scored more than one axis.
- A judge's reason cites revenue, pricing, willingness to pay, market size, or build cost — the business lens leaked back in.
- A duel verdict was accepted from a single presentation order.
- The report recommends building anything without user evidence or an explicit UNGROUNDED warning.
- Generators produced ideas that survive swapping the topic's noun for a neighboring space — that's the modal region wearing a costume; it must be named as such, not ranked as original.
