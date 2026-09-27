# Fixture: `review-round2-lens-rotation`

Measures whether a review candidate **changes its lens between rounds** and
whether that rotation finds defects the previous lens structurally could not.

Sibling to `review-round2-carryforward`, which measured — and rejected — the
name-the-finding suppression prelude. This fixture measures the replacement
mechanism: carry forward **structure state** (which lens ran, which functions a
verifier confirmed) rather than **finding text**.

## The two mechanisms under test

Both carriers are subtractive and neither names a defect — which is the whole
point. The rejected prelude failed because naming a finding in order to
suppress it raised that finding's salience, and the arm carrying the
suppression list re-raised deferred findings *more* than the arm without it.

| Carrier | Payload in `prompt.md` | Assertions |
|---|---|---|
| Used-lens set | `round 1 used: standards`, over `src/OrderPricing.kt` only | B1, B2, B3, B4 |
| Verified-fixed set | verifier output: `computeSubtotal` VERIFIED-FIXED, everything else UNVERIFIED | B5, B6 |

## The planted defects (v3)

`HEAD` is round 1's fix commit; `git diff HEAD~1 HEAD` touches **only**
`src/OrderPricing.kt`.

| Defect | Where | Reachable by | Assertion |
|---|---|---|---|
| Tier bounds changed `>=` → `>`, contradicting the spec's worked examples | `applyTierPricing` vs `docs/pricing-rules.md` | merged spec+standards — the doc is outside the diff | B2 |
| Still round-trips through `Double`, now behind a private helper | `parseAmount` → `normalize`, in the diff, UNVERIFIED | any lens, but only if it ignores "round 1 touched it" and reads past the public method | B5 |
| Correct, and VERIFIED-FIXED | `computeSubtotal`, in the diff | flagging it is a scope leak | B6 |
| Correct throughout — the precision decoy | `src/RefundPolicy.kt` | flagging it is a false positive | B7 |

### The class-hunt set — four instances, one class

Round 1 fixes `withinSlippage` from `equals` to `compareTo`. That fix is a
*hypothesis*: BigDecimal is being compared by scale-sensitive identity
elsewhere. Four surviving instances test whether the candidate acts on it. All
four are outside the round-1 diff, and each sits beside a correct `compareTo`
sibling so the hunt has to discriminate rather than flag every comparison.

| Assertion | Instance | Why it is a separate act of noticing |
|---|---|---|
| B3 | `FeeCalculator.withinFeeCap` — `fee.equals(cap)` | the direct analogue |
| B8 | `FeeCalculator.isZeroFee` — `fee == BigDecimal.ZERO` | Kotlin `==` dispatches to `equals`; wears an operator, not a method call |
| B9 | `RateTable.isApproved` — `setOf(…).contains(rate)` | scale sensitivity is one layer down, inside Set `equals`/`hashCode` |
| B10 | `RateTable.labelFor` — `mapOf(…)[rate]` | same, inside Map lookup |

Four *identical* `equals` calls would let one sighting hand over the other
three, correlating the observations and giving back the power v3 exists to buy.
Same class, different patterns.

**The class-hunt set is load-bearing.** These are the assertions a rotated lens
can pass that a repeated standards lens cannot. Without them the fixture would
reward *declaring* a lens (B1) while proving nothing about whether rotating it
helps.

**B5, B6 and B7 are the guard set, and none works alone.** B6 alone rewards
blindfolding; B5 fails any candidate that treats "round 1 touched it" as "round
1 settled it"; B7 fails any candidate that earns coverage credit by flagging
things in files it merely opened. B7 matters more in v3 than v2: the fixture now
actively rewards reading beyond the diff, and one that rewards breadth without
penalising false positives measures verbosity.

**Known limitation:** B9 and B10 both live in `src/RateTable.kt`, so a candidate
that opens that file at all tends to get both. They are correlated despite the
differing patterns, and the real power gain is below 4×.

## Version history — what each rebuild fixed

Each version changed the bundle, so `bundle_sha256`, `head_sha` and the
`discrimination` block all moved with it. **Results do not transfer across
versions.** They are kept below only as the record of why the next version
exists.

### v1 → v2: saturation

v1's comparison could not answer the question it was built for. At sonnet, N=9,
*both* arms passed B2–B6 in 9 of 9 runs — the harness classified all five
`always_passes_both`. At haiku the baseline sat at 100% on four of six. **A
fixture whose baseline is at ceiling can measure damage but never improvement.**

| | v1 | v2 |
|---|---|---|
| Haystack | one 5-method file, every method defective — enumerating the file *was* the review | three source files, most methods correct; finding defects needs discrimination, not exhaustion |
| Class sibling | `withinFeeCap` sat directly beneath the method round 1 fixed, in the same file | moved to `src/FeeCalculator.kt`, outside the diff, flanked by two *correct* comparisons |
| Spec | stated the violated rule in bolded prose, liftable verbatim | both rules given only as worked-example tables; the contradiction must be inferred from boundary rows |

The `parseAmount` defect also moved one hop behind a private helper.

**Only one of those three axes actually bit.** B3 went from saturated to
discriminating; B2, B4, B6 and B7 stayed at 100% for both arms at both tiers.
Restating the spec as worked examples did not make the tier contradiction any
harder to spot.

### v2 → v3: power

v2 produced the first replicated signal for the mechanism — B3 moved **+22
points at both tiers** (haiku 0/9 → 2/9, sonnet 5/9 → 7/9). Pooled: A 5/18 vs
B 9/18, Fisher exact **p = 0.305**. Right direction, twice, and underpowered.

The cause is structural, not statistical: **one planted class-sibling defect
yields one observation per run**, so 9 runs buy 9 observations however much they
cost. v3 plants four instances of the same class and scores each independently —
36 observations per arm per tier, same run count, same price.

v3 also overshot on B3 at haiku in the other direction: the baseline hit **0/9**,
so the assertion discriminates from the floor rather than the middle. Target for
a healthy assertion is a baseline around 40–70%.

## v3 result — the mechanism passed, and shipped

**A** = skill without the mechanism, **B** = with it. N=9 per tier, zero grader
or comparator retries, 18/18 runs successful at sonnet.

| Assertion | haiku A→B | sonnet A→B | |
|---|---|---|---|
| B1 declares a rotated lens | 5/9 → 8/9 | 6/9 → 9/9 | |
| B2 spec-vs-code | 8/9 → 9/9 | 9/9 → 9/9 *(sat)* | |
| **B3** `withinFeeCap` equals | 0/9 → 1/9 | **1/9 → 8/9** | `splits_cleanly` |
| B4 does not restate | 8/9 → 9/9 | 9/9 → 9/9 *(sat)* | |
| B5 unverified ≠ settled | 8/9 → 9/9 | 9/9 → 9/9 *(sat)* | guard held |
| B6 no scope leak | 8/9 → 9/9 | 9/9 → 9/9 *(sat)* | guard held |
| B7 no decoy false positive | 8/9 → 9/9 | 9/9 → 9/9 *(sat)* | guard held |
| **B8** `isZeroFee` `==` | 0/9 → 0/9 | 1/9 → 2/9 | |
| **B9** Set `contains` | 0/9 → 1/9 | **1/9 → 8/9** | `splits_cleanly` |
| **B10** Map lookup | 0/9 → 1/9 | **1/9 → 7/9** | |

**Class-hunt pooled — sonnet: A 4/36 (11%) vs B 25/36 (69%), Fisher exact
p ≈ 1e-6.** Under the conservative collapse of B9+B10 into one `RateTable.kt`
observation (they share a file and tend to be found together, as this README
predicted before the run): **A 3/27 vs B 17/27, p = 0.00016.** The result
survives its own stated objection.

Every guard held at both tiers. Baseline sat at 11% at sonnet — inside the
headroom band — and two assertions came back `splits_cleanly`.

### Where the rule was and was not satisfied

The v3 rule asked for a win at **both** tiers. That was not achieved, and the
result is not reported as a clean pass.

- **Sonnet: passes decisively.** p well below 0.05 on both accountings, guards
  intact, healthy headroom.
- **Haiku: unmeasurable.** Baseline **0/36** — the registered headroom check
  fires, so this is recorded as a fixture failure at that tier, not as a win
  for B. Both arms scored zero on all four class instances; haiku does not hunt
  a defect class outside the diff whatever it is told. B8 was
  `always_fails_both` there.

What distinguishes v3 from every prior positive is *which* assertions moved. v1
and v2's gains were concentrated in B1 — declaring a lens, i.e. self-description.
Here B1 moves too, but so do three assertions that require leaving the diff and
finding real defects nobody pointed at.

**Cost is real.** Tool calls lost 7–0 (p=0.0078) at sonnet and cost lost 8–0
(p=0.0039) at haiku. Rotation reads more files every round. At sonnet quality
went B_WINS 8–1 (p=0.0195) and correctness B_WINS 7–1 (p=0.0352).

**Shipped** into `SKILL.md` §4 as the loop's round-state carrier — the block is
byte-identical to the arm B measured here — with the tier caveat recorded
alongside it.

## Prior results (superseded — do not compare across versions)

**A** = skill without the mechanism, **B** = with it. N=9 per tier throughout.

### v1 — the mechanism looked like pure self-description

| Assertion | haiku A→B | sonnet A→B |
|---|---|---|
| B1 declares a rotated lens | 4/9 → 7/9 | 5/9 → **9/9** |
| B2 spec-vs-code | **9/9 → 7/9** | 9/9 → 9/9 *(saturated)* |
| B3 second instance of class | **9/9 → 7/9** | 9/9 → 9/9 *(saturated)* |
| B4 does not restate | 9/9 → 7/9 | 9/9 → 9/9 *(saturated)* |
| B5 unverified ≠ settled | 5/9 → 6/9 | 9/9 → 9/9 *(saturated)* |
| B6 no scope leak | 9/9 → 8/9 | 9/9 → 9/9 *(saturated)* |

At sonnet the aggregates read `quality: B_WINS` 7–1 (p=0.035) and
`correctness: B_WINS` 4–0 (p=0.0625) — but with B2–B6 tied at 100%, the only
assertion moving is B1, so **the entire B_WINS result is the declare-your-lens
assertion**. The mechanism changed what a review said about itself and produced
no evidence it found more.

### v2 — the first replicated signal

| Assertion | haiku A→B | sonnet A→B |
|---|---|---|
| B1 declares a rotated lens | 7/9 → 7/9 | 9/9 → 9/9 *(saturated)* |
| B2 spec-vs-code | 9/9 → 9/9 *(saturated)* | 9/9 → 9/9 *(saturated)* |
| **B3 class sibling** | **0/9 → 2/9** | **5/9 → 7/9** |
| B4 does not restate | 9/9 → 9/9 *(saturated)* | 9/9 → 9/9 *(saturated)* |
| B5 unverified ≠ settled | 9/9 → 8/9 | 9/9 → 9/9 *(saturated)* |
| B6 no scope leak | 9/9 → 9/9 *(saturated)* | 9/9 → 9/9 *(saturated)* |
| B7 no decoy false positive | 9/9 → 9/9 *(saturated)* | 9/9 → 9/9 *(saturated)* |

B3 moved **+22 points in the same direction at both tiers** — the first
evidence in this investigation that the mechanism does the thing it was
designed to do rather than merely announcing it. Pooled A 5/18 vs B 9/18,
Fisher exact **p = 0.305**: not significant, and the reason v3 exists.

Every dimension was `INCONCLUSIVE` at sonnet, with no cost or quality penalty.
At haiku, A won cost 7–2, tool calls 6–2 and wall clock 6–2 — reading other
files is not free.

### The pre-registered rule, and why it was revised for v3

v1 and v2 both ran under: *B must win B2 and B3, without losing the guards.*
That rule became unevaluable — B2 was 9/9 for both arms in all four runs across
two fixture versions, so no candidate can win it.

The rule was revised **before v3 was run**, on the strength of v1+v2 evidence
that B2 cannot discriminate. Revising it after seeing v3 numbers would be the
exact failure pre-registration exists to prevent.

> **v3 rule.** Decision assertions: B3, B8, B9, B10. B must win the pooled
> class-hunt rate at **both** tiers, with pooled two-tier Fisher exact
> **p < 0.05**. Guards — B5, B6, B7 — no material loss. B1, B2, B4 excluded as
> non-discriminating. **Headroom check independent of the winner:** a baseline
> at 0% or 100% on the class assertions means the fixture failed again, and that
> is the result, not the deltas.

## Known bias, stated deliberately

`prompt.md` supplies the lens state and verifier output but **does not instruct
the candidate to rotate**. Whether the skill acts on that state is the measured
variable. A capable baseline may therefore rotate spontaneously, which biases
the fixture **against** the change being measured — the right direction, and
the same choice the sibling fixture made.

Round 1's findings are given to both arms for the same reason: B4 (does not
merely restate) is untestable if the candidate never sees what round 1 said.

## The deterministic gate

`checks.sh` only answers "did the review report any finding at all". Which
findings were raised is graded by `assertions.json`.

It has been wrong twice, in opposite directions, and both bugs were found by
*running* the fixture rather than by verifying it:

- too loose — matched the bare word "low" in prose, so a finding-free review passed;
- too strict — accepted headings, `-*+` bullets and bare `**` but **not** ordered
  lists, so `1. **CRITICAL** — ...` scored 0/6. That voided 12 of 18 sonnet runs,
  unevenly across arms, because sonnet formats findings as numbered lists more
  often than haiku. The gate was silently model-dependent.

`verify-fixture` passed throughout both. Its FR-44 check asks whether the
reference and broken solutions separate — never whether the gate accepts the
range of formats a real model produces, and never whether a *capable* candidate
has headroom above the baseline. **Neither fixture bug found this session was
catchable by `verify-fixture`.**

## Rebuilding

The bundle is generated deterministically (fixed author/committer dates) by the
build script; a rebuild reproduces `bundle_sha256` exactly. Re-run
`verify-fixture` after any change to the bundle, the assertions or the
references.

```bash
cd ThinkTime/versus
bash fixtures/review-round2-lens-rotation/build.sh
python3 scripts/cli.py verify-fixture review-round2-lens-rotation
```

## Running it

```bash
cd ThinkTime/versus
python3 scripts/cli.py run <old-skill.md> <new-skill.md> \
  --fixture review-round2-lens-rotation --workspace /tmp/versus-lens-rotation
```

`--quick` (N=3) is a smoke test for wiring only. The sibling fixture's `--quick`
run swept 3–0 for a change that N=9 showed to be a regression, and `--quick`
caps its verdict at `DIRECTIONAL_HINT` for exactly that reason. **N=9 on both
executor tiers before any merge decision**, with outcomes pre-registered and the
burden on the addition.

Check `cost.total_usd` before reading any verdict. A run whose credentials
failed reports `TASK_TOO_HARD — every pair was NO_CONTEST` at **$0.00**, which
reads exactly like a real finding about the fixture being too hard.

## What this fixture cannot tell you

It measures one round transition in isolation, not a real loop. In particular it
cannot detect the failure mode this design is most at risk of: **lens rotation
raising `loop_metrics.py`'s `mean_carry_rate` — flipping a run from `RANDOM_WALK`
to `CONVERGING` — without finding more real defects.** Carry rate is a
diagnostic, never the success metric. These assertions are.
