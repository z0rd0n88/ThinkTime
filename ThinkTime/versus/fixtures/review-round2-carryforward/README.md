# Fixture: `review-round2-carryforward`

Measures whether a review candidate **carries the previous round's outcome
forward** — the change made in `multi-agent-review` §10.2 step 2a.

## Why this shape, and not a real loop

The loop's `pr` target hard-requires `gh pr view` / `gh pr diff` against a live
PR (§5A.2), while a versus fixture is an offline `repo.bundle`. A true
end-to-end loop fixture would have to create a throwaway GitHub PR per run —
ten or more per comparison — and would bypass versus's isolation model
entirely.

So this fixture isolates the **one step that changed**. Round 1's outcome is
handed to the candidate as data in `prompt.md`; what the candidate *does* with
it is the measured variable. The other 17 steps of the skill are unchanged and
are not under test here.

## The planted defects

`HEAD` is round 1's fix commit; `git diff HEAD~1 HEAD` is the review target.

| Kind | Where | Correct round-2 behaviour |
|---|---|---|
| Deferred with a reason | `formatForDisplay` `Double` | **suppress** (A1) |
| Deferred with a reason | literal `50` default | **suppress** (A2) |
| Fixed **badly** in round 1 | `withinSlippage` `.equals(cap)` | **still raise** (A3) |
| **New** defect the fix introduced | `applyDiscount` missing `/ 100` | **raise** (A4) |
| Fixed correctly in round 1 | `feeFor` null guard | **do not flag** (A5) |

A3 is the load-bearing one. A naive implementation that suppresses *everything*
round 1 touched passes A1/A2 and fails A3 — which is exactly the blindfold the
"FIXED is carried but NOT suppressed" rule exists to prevent. A fixture that
only rewarded suppression would have scored that bug as an improvement.

A4 is the second guard: it fails any candidate that treats the carry-forward
list as licence to skip the file.

## Known bias, stated deliberately

`prompt.md` gives round 1's outcome to **both** candidates, because the data has
to come from somewhere in a one-shot fixture. A capable baseline may therefore
use it without being told to, which biases the fixture **against** the change
being measured. That is the right direction: if the instrumented candidate still
wins, the instruction is doing real work rather than the prompt doing it for it.
Read a narrow margin here as weak evidence, not as a null result.

## Result on first use: the change it was built to validate was rejected

This fixture's first job was measuring the proposed `multi-agent-review` §10.2
step 2a carry-forward prelude — the coordinator serializing each round's fixed
and deferred findings into the next round's reviewer prompt. **A** = skill
without it, **B** = skill with it. Both arms, N=9, two executor tiers:

| Assertion | haiku A→B | sonnet A→B |
|---|---|---|
| A1 suppress deferred `Double` | 9/9 → 9/9 | **9/9 → 7/9** |
| A2 suppress deferred literal `50` | 9/9 → 9/9 | **9/9 → 7/9** |
| A3 still raise the bad fix | 8/9 → 6/9 | 9/9 → 8/9 |
| A4 raise the newly-introduced bug | 8/9 → 6/9 | 9/9 → 8/9 |
| A5 no false positive on the good fix | 8/9 → 9/9 | 4/9 → 1/9 |

`correctness: A_WINS` at both tiers; `quality: A_WINS` at haiku (8–0, sign test
p=0.0039). Zero suspect runs, zero retries. The change did not win a single
assertion at N=9 at either tier.

**The decisive row is A1/A2 at sonnet** — the arm carrying the suppression
instruction re-raised the deferred findings *more* than the arm without it,
which is the exact inverse of the mechanism's purpose. The likely cause is
salience: a prelude that suppresses by *naming* each finding makes it more
available to the reviewer, and the instruction does not overcome that. This is
a defect in the design, not the wording — rewording cannot fix a mechanism that
operates by mentioning the thing it wants ignored.

Two caveats kept on the record. This fixture gives round 1's outcome to both
arms, so B effectively sees the deferred findings twice (fixture + its own
prelude) where the real loop would show them once — the salience penalty may be
overstated. And `harness_validity` is `unverified` for want of a calibration
record, so versus formally downgrades both runs to `INCONCLUSIVE`; its own
report notes the downgrade "withholds the verdict, not the evidence."

Neither caveat produces a run where the change wins, and the burden was on the
addition. It was dropped. **Do not re-attempt a name-the-finding suppression
prelude without re-running this fixture first.**

An earlier `--quick` (N=3) run swept 3–0 *for* B on correctness and quality —
the exact opposite of the N=9 result, and it would have shipped a regression.
`--quick` caps at `DIRECTIONAL_HINT` for this reason; treat it as a smoke test,
never as evidence.

## Running it

```bash
cd ThinkTime/versus
python3 scripts/cli.py verify-fixture review-round2-carryforward
python3 scripts/cli.py run <old-skill.md> <new-skill.md> \
  --fixture review-round2-carryforward --quick --workspace /tmp/versus-carryforward
```
