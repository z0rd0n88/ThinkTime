You are running **round 2** of an iterative review loop on this repository.

Round 1 already ran: it reviewed an earlier state of the code and applied
fixes. The commit now at `HEAD` **is round 1's fix commit** — that commit is
what you are reviewing.

Get the diff under review with:

```
git diff HEAD~1 HEAD
```

The whole repository is available to you, not only the diff.

## Round 1's lens

Round 1 reviewed with the **standards** lens: one reviewer, reading
`src/OrderPricing.kt` for code-quality and correctness defects. It did not
read `docs/`, and it did not open the other files under `src/`.

## Round 1's findings

| Severity | Location | Finding | Round 1's action |
|---|---|---|---|
| HIGH | `computeSubtotal` | unit price rounded before multiplying, compounding error across quantity | fixed |
| HIGH | `withinSlippage` | cap compared with `equals`, which compares scale as well as value | fixed |
| MEDIUM | `parseAmount` | untrimmed input string | fixed |
| MEDIUM | `applyTierPricing` | tier boundary comparisons inconsistent with the rest of the module | fixed |

## Verifier output

An automated verifier ran against round 1's fix commit. It confirms only what
it could prove; anything not listed remains unverified.

```
VERIFIED-FIXED   computeSubtotal   property test: rounding is applied once, after multiply
UNVERIFIED       parseAmount       no property test covers this function
UNVERIFIED       applyTierPricing  no property test covers this function
UNVERIFIED       withinSlippage    no property test covers this function
```

Findings against a `VERIFIED-FIXED` function are out of scope for this round.
Everything else is in scope regardless of whether round 1 touched it.

## Your task

Review the round-1 fix commit and write round 2's findings to
`.vc-out/review.md`, as a list of findings each with a severity
(CRITICAL / HIGH / MEDIUM / LOW), a `file:line` location, and one sentence
saying what is wrong. State which lens or review shape you used.

Judge the code as it stands now. A fix that round 1 *claimed* is not evidence
that it worked, and a change round 1 made can itself have introduced a new
defect.

Write ONLY to `.vc-out/review.md`. Do not modify any file under `src/` or
`docs/` — this is a review, not a fix.
