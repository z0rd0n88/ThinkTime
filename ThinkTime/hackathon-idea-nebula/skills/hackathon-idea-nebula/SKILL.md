---
name: hackathon-idea-nebula
description: 'Use when deciding what to build for a hackathon and the obvious idea would lose — generates candidate projects and scores them separately on buildability and winnability against the event''s own rules, with simulated judge scorecards and an hour-by-hour plan.'
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - Agent
  - WebSearch
  - WebFetch
  - AskUserQuestion
---

# hackathon-idea-nebula

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Spawns a large parallel agent batch by default** — a full run dispatches
> up to ~13 subagents (4 generators + 2 rankers + up to `--feasibility-top`
> feasibility checks + 4 simulated judges), a token/agent budget well above a
> normal one-shot call.

Generates hackathon project candidates and answers two **separate** questions:
*is this worth spending the event on* and *would it win*. An idea can be a great
weekend and lose; an idea can win and be miserable to build. The two are scored
and reported separately. Requires a filled-in RULES AND CONSTRAINTS block — with
an empty one the skill stops and asks rather than guessing the event.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<topic...>` | free text | required | Theme/problem space to generate inside; empty input hard-fails. |
| `--rules <path>` | file path | none | The RULES AND CONSTRAINTS block (see §4). Absent and not supplied inline → the skill STOPS and asks. |
| `--stack <desc>` | free text | "whatever the repo in cwd already uses; otherwise ask" | What the team already ships in. Ideas are never allowed to require learning a new stack. |
| `--team <n>` | integer | `1` | Builders. Must not exceed the rules' team cap. |
| `--prize <category>` | free text | event's main prize | The specific prize category being targeted; reshapes the rubric. |
| `--wild <n>` | `1` or `2` | `1` | Number of `alien` far-domain generators; `2` replaces `stage` to hold the 4-generator cap. |
| `--banlist` | flag | off | After round 1, names the modal region and re-runs `tails` + `alien` excluding it. |
| `--no-feasibility` | flag | off (check ON) | Skips live build-feasibility grounding; forces an UNGROUNDED warning in the report. |
| `--feasibility-top <n>` | `1`–`8` | `5` | How many finalists get a live feasibility check. |
| `--plain` | flag | off | Disables Verbalized Sampling and boldness revision (A/B comparison mode only). |
| `--write-to <path>` | file path | none | Also saves the report to disk; refuses if the file exists unless `--force`. |
| `--force` | flag | off | With `--write-to`, allows overwriting an existing file. |

## 1. Purpose

Hackathon idea selection fails in two different directions and most advice
conflates them. This skill keeps them apart end to end:

- **Worth building** — does a shippable slice exist inside the stated duration,
  in a stack the team already knows, with an escape hatch when the integration
  breaks at 3am.
- **Would it win** — does the panel the rules imply score it highly, under the
  event's own rubric and weights, against the 40 other demos they will see.

Mechanism inherited from `ThinkTime:idea-nebula` (generation architecture and
bias controls) and `ThinkTime:idea-refine` (hard input gate, minimum slice, an
explicit Not Doing list). Enforced here:

- **Four independent parallel generators, blind to each other, once.** Each
  earns its slot as a different entropy source, not a persona label. No debate:
  dependent sampling collapses diversity round-over-round.
- **Hard cap of 4 generators**, mandatory **boldness-revision** pass in each.
- **No pointwise 1–10 self-scores anywhere.** Rankings come from blind pairwise
  duels judged in BOTH orders; only order-consistent wins count.
- **Two rankings, never merged**: a buildability ranking and a winnability
  ranking. Where they disagree is the most useful output this skill produces.
- **Evidence means build-feasibility evidence** — prior art, API availability
  and rate limits, whether the hard part has a library, whether the data exists
  — not market evidence. Opinions about feasibility are inadmissible; only what
  a check can quote and link counts.
- **Plural judges in conflict.** The panel is simulated as separate scorers with
  different incentives, scored independently; splits are reported, not averaged
  away.
- **Never recommend learning a new stack.** An idea requiring one is a failed
  idea, not an ambitious one.

References (loaded only while running):
- [`references/generator-briefs.md`](references/generator-briefs.md) — shared output contract + the four generator briefs.
- [`references/rubric-and-judges.md`](references/rubric-and-judges.md) — rubric derivation, duel protocol, judge panel, verdict ladder, report structure.
- [`references/feasibility-check.md`](references/feasibility-check.md) — feasibility sources, checks, hard thresholds.

## 2. What a typical hackathon involves

Reason from this baseline; override every line of it with the RULES block when
the two conflict.

- **Duration**: 24–48 hours wall-clock, of which 6–10 are lost to sleep, food,
  venue logistics, opening/closing ceremonies and the submission scramble.
  Usable build time is roughly 60% of the advertised number.
- **Team**: 1–4 people, often meeting that morning. Parallelism is lower than
  headcount suggests; integration cost rises with it.
- **Judging format**: a 2–5 minute live demo plus Q&A, or a recorded video and a
  Devpost-style written submission, scored by a panel against a published rubric.
  Science-fair format means judges arrive mid-sentence and leave early.
- **What "done" means on stage**: one path works, live, on the venue wifi, in
  front of a person who will not read your code. Nothing else counts.
- **Standard failure modes** — the report must address each for the top pick:
  - **Over-scoping** — three integrations planned, zero finished.
  - **Integration hell** — an unfamiliar API's auth/rate limits eat the night.
  - **Demo-day flakiness** — venue wifi, cold starts, rate limits, a live model
    call that times out on stage, a laptop that sleeps.
  - **Pre-work disqualification** — code written before the start window, or a
    mandated sponsor technology used trivially or not at all.

## 3. When to use

Trigger phrases:
- "what should I build for <hackathon>?" / "hackathon ideas for …"
- "pick me a project for this weekend's <event>"
- "run hackathon-idea-nebula on …" / explicit `hackathon-idea-nebula …`

Do NOT use for:
- Judging or stress-testing **one** idea that already exists — use
  `idea-autopsy:stress-test-idea` or `idea-autopsy:evaluate-proposal-harsh`.
- Brainstorming a product or business with no event, rules or deadline — use
  `ThinkTime:idea-nebula`.
- Anything that writes to source files — this skill is read-only (except
  `--write-to` and the Stage 7 save offer).

## 4. Invocation grammar and the RULES block

```
hackathon-idea-nebula <topic...> --rules <path> [--stack <desc>] [--team <n>]
                 [--prize <category>] [--wild <n>] [--banlist]
                 [--no-feasibility] [--feasibility-top <n>] [--plain]
                 [--write-to <path>] [--force]
```

### RULES AND CONSTRAINTS — required input

Supply via `--rules <path>`, or inline in the invocation, or answer for it when
asked. **If it is missing or empty, STOP and ask for it. Do not guess the event,
do not substitute a generic hackathon, do not spawn a single agent.** Fields:

```
DURATION AND SCHEDULE   : start/end timestamps, mandatory ceremonies, demo slot length
THEME                   : the stated theme or track wording, verbatim
MANDATED TECH           : sponsor APIs/SDKs/platforms that MUST be used, and how ("non-trivially"?)
TEAM SIZE CAP           : max members
PRE-WORK RULES          : what may exist before the start window; boilerplate/template policy
SUBMISSION REQUIREMENTS : repo, video length, written form, deadline (and whether it is hard)
PUBLISHED RUBRIC        : the event's own criteria and weights, verbatim if published
PRIZE CATEGORIES        : all categories, and which one is being targeted
```

Partially filled is acceptable: proceed, and list every unsupplied field in the
report's **Evidence gaps** section. A missing PUBLISHED RUBRIC is the one field
with a defined fallback (§Stage 1 below). A missing DURATION is not — ask.

## 5. Workflow

### Stage 0 — Parse, validate, gate
1. Split topic from flags. Hard-fail on empty topic with a one-line usage summary.
2. Load the RULES block. Missing/empty → **stop and ask** (AskUserQuestion when
   available, else a plain question listing the eight fields). Spawn nothing.
3. Resolve `{{STACK}}`: `--stack`, else infer from the repo in cwd (manifest
   files, lockfiles) and state the inference, else ask.
4. `--team` over the rules' cap → clamp to the cap and warn.
5. `--write-to` overwrite guard runs HERE, before any agent is spawned.

### Stage 1 — Derive the rubric from the rules, not from a template
Build `{{RUBRIC}}` before generating, so generators aim at the real target.

- **Event publishes a rubric** → use its criteria and weights **verbatim**, and
  say so in the report. Do not substitute your own, do not "improve" them, do
  not add criteria it omitted.
- **No published rubric** → build one from the six criteria and default weights
  in [`references/rubric-and-judges.md`](references/rubric-and-judges.md)
  §Fallback rubric, and state in the report that the weights are this skill's
  defaults, not the event's.
- **Prize category reshapes it** — score against `--prize` specifically, never a
  generic "best overall". A sponsor-API category raises mandated-tech weight; a
  social-impact category raises legibility; a technical category raises the
  hard-part test.

### Stage 2 — DIVERGE: spawn generators IN PARALLEL

> ⚠️ **PARALLELISM RULE — DO NOT SERIALIZE, DO NOT LET GENERATORS INTERACT.** All generator `Agent` calls MUST be issued in a SINGLE assistant message. Each brief is fully self-contained; generators share no state and never see each other's output. `subagent_type: general-purpose`, `description: "hackathon-idea-nebula: <generator>"`.

Default roster: `tails`, `stage`, `alien`, `scout`. With `--wild 2`: `tails`,
`alien`×2 (each forced to a different domain), `scout` — `stage` is dropped to
hold the 4-cap. Expand each brief from
[`references/generator-briefs.md`](references/generator-briefs.md) with
`{{TOPIC}}`, `{{RULES_BLOCK}}`, `{{STACK}}`, `{{TEAM}}`, `{{RUBRIC}}` and the
generator-specific instruction. `scout` needs live web access (WebSearch /
WebFetch / `curl`) — prepend the §Sources table from
[`references/feasibility-check.md`](references/feasibility-check.md) to its brief.

With `--plain`: strip the VS and boldness-revision steps (comparison mode).

### Stage 3 — Collect and pool
Capture each generator's output verbatim. A generator that fails or returns empty
is noted as `<name>: [FAILED — no output]`; continue if ≥2 generators returned.
**Strip generator attribution** before ranking (blind judging); keep a private
attribution map for the final report.

If `--banlist`: name the modal region now — the cluster any generic hackathon
brainstorm produces for this theme (chatbot-over-your-docs, RAG on a PDF,
sentiment dashboard, "Uber for X", a wrapper with a chat box) — then re-run
`tails` and `alien` once with that region excluded and merge the new ideas in.

### Stage 4 — CONVERGE: two blind rankings, run in parallel
Two `Agent` calls, issued together, over the same blind pool, using the duel
protocol in [`references/rubric-and-judges.md`](references/rubric-and-judges.md)
§Duel protocol:

- `description: "hackathon-idea-nebula: rank-build"` — duel question is **"which is
  more likely to actually ship a working live demo by the deadline, for this
  team, in this stack?"**
- `description: "hackathon-idea-nebula: rank-win"` — duel question is **"which scores
  higher under the rubric for the targeted prize category?"**

Each ranker dedupes, names the modal region, prunes to ≤8 finalists (dominated
only), runs round-robin duels judged in BOTH orders with order-inconsistent
verdicts recorded as draws, and justifies novelty as distance from the named
modal region. **Never merge the two standings into one score.**

### Stage 5 — GROUND: build-feasibility check (default ON)
Unless `--no-feasibility`: one `Agent` call per finalist up to
`--feasibility-top`, IN PARALLEL (`description: "hackathon-idea-nebula: feasibility
<title>"`), running the brief in
[`references/feasibility-check.md`](references/feasibility-check.md) with its
§Sources table prepended. Hard thresholds applied by the orchestrator:
credential gated behind sales/waitlist/paid-only → DOWNGRADE; hard part has no
library and is not shippable in the window → DOWNGRADE; the hard part is one API
call → WRAPPER flag; the same project has won or saturated comparable events →
SATURATED; mandated tech unused or used trivially, or pre-work rules violated →
RULE-RISK **BLOCK**.

### Stage 6 — JUDGE: simulate the panel, plural and in conflict
Four `Agent` calls IN PARALLEL (`description: "hackathon-idea-nebula: judge
<persona>"`), one per persona in
[`references/rubric-and-judges.md`](references/rubric-and-judges.md) §Judge panel
— sponsor engineer, business judge, technical judge, time-pressured generalist.
Each scores **every finalist against every rubric criterion** independently, with
one line of reasoning per criterion, and never sees another judge's scores. Then
aggregate to a panel score using the event's weights, and extract the
disagreements: a criterion where judges split is where the project is fragile.

### Stage 7 — REPORT
Assemble per [`references/rubric-and-judges.md`](references/rubric-and-judges.md)
§Report, in exactly that order: the two verdicts first (worth building /
would it win, each citing the criterion that decided it) → rubric and weight
provenance → per-judge scorecards → disagreements → the complete findings list
and evidence gaps, **never pre-filtered by severity** → minimum demoable slice
and Not Doing list → hour-by-hour build plan fitted to the stated duration.
Verdict ladder per candidate: **BUILD IT** / **BUILD WITH SCOPE CUTS** (name the
cuts) / **SAME DOMAIN, DIFFERENT DEMO** (name it) / **PICK SOMETHING ELSE**.
Print verbatim as the final message. If `--write-to`: `mkdir -p` parent, write,
prepend `Wrote: <absolute path>`.

### Stage 8 — OFFER TO SAVE
Skip entirely when `--write-to` was given. Otherwise offer to save — a report
this size is lost to scrollback and compaction. Default path:
`docs/ideas/<topic-slug>-hackathon.md` relative to the repo root, or
`<topic-slug>-hackathon.md` in cwd outside a repo. On yes: `mkdir -p` parent,
write verbatim, confirm `Wrote: <absolute path>`; refuse to overwrite an existing
file without explicit confirmation. On no: end without writing.

## 6. Error handling

| Condition | Action |
|---|---|
| Empty topic | Hard-fail with usage summary; spawn nothing. |
| RULES block missing/empty | STOP and ask for the eight fields; spawn nothing. Never guess the event. |
| RULES block partially filled | Proceed; list every unsupplied field under Evidence gaps. |
| No DURATION in the rules | Ask — the build plan and escape hatch are meaningless without it. |
| No PUBLISHED RUBRIC | Use the fallback rubric and label the weights as this skill's defaults. |
| `--stack` absent and uninferable | Ask. Never assume, and never resolve it by picking a stack to learn. |
| `--team` over the rules' cap | Clamp to cap, warn. |
| `--wild` outside 1–2 / `--feasibility-top` outside 1–8 | Clamp, warn. |
| A generator fails | Note `[FAILED]`, continue if ≥2 returned; else hard-fail. |
| `scout` has no web access | Note it, continue with 3 generators, force the UNGROUNDED warning. |
| Feasibility agent fails for an idea | Mark that idea `feasibility: UNVERIFIED`; never silently omit. |
| A judge agent fails | Report the panel with that seat marked `[NO SCORE]`; never fill it in yourself. |
| A ranker fails | Report the surviving ranking, mark the other `[FAILED]`, and dump the generator outputs verbatim with `---` delimiters. |

## 7. Red flags — the output is lying to you if…

- The buildability and winnability verdicts have been merged into one score.
- A finalist carries a bare novelty or feasibility number with no modal-region
  distance or no quoted source behind it.
- A duel verdict was accepted from a single presentation order.
- The panel is reported as an average with the disagreements smoothed out.
- Any recommended project requires a stack the team does not already ship in.
- A candidate has no escape hatch — no answer to "what still demos at 6 hours to
  deadline with the integration broken". An absent hatch is a finding, not a
  footnote.
- The findings list was trimmed to the important ones. Report all of them.
- The rubric was invented while the event publishes one, or the event's weights
  were "adjusted".
- The plan recommends building without feasibility evidence and without an
  explicit UNGROUNDED warning.
