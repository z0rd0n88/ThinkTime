#!/usr/bin/env bash
# Deterministic builder for the review-round2-lens-rotation fixture.
# Re-runnable: wipes and rebuilds the work repo and all generated artifacts.
#
# FIXTURE VERSION 3. Why each version changed, and the results that forced the
# change, are in README.md - not repeated here.
#
# The one invariant to preserve when editing defects: the four class instances
# (B3, B8, B9, B10) are the same defect CLASS wearing four different PATTERNS,
# and each sits beside a correct compareTo sibling. Four identical `equals`
# calls would let one sighting hand over the other three, collapsing four
# observations back into one and undoing the power this version exists for.
set -euo pipefail

FIX="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)/lensrepo"

export GIT_AUTHOR_NAME=versus-dev GIT_AUTHOR_EMAIL=dev@versus.invalid
export GIT_COMMITTER_NAME=versus-dev GIT_COMMITTER_EMAIL=dev@versus.invalid
export GIT_AUTHOR_DATE="2026-09-05T12:00:00-07:00"
export GIT_COMMITTER_DATE="2026-09-05T12:00:00-07:00"

rm -rf "$WORK"; mkdir -p "$WORK/src" "$WORK/docs"
cd "$WORK"
git init -q -b main

# ---------------------------------------------------------------- base commit
# The spec. Round 1 never reads this file - it is the other axis. Both rules
# are given ONLY as worked examples, so neither can be quoted and matched
# against the code; the boundary rows have to be read against the comparisons.
cat > docs/pricing-rules.md <<'EOF'
# Pricing rules

## Volume tiers

Discount is determined by order quantity. Worked examples:

| Quantity | Tier | Discount |
|---|---|---|
| 9 | Standard | none |
| 10 | Bulk | 5% |
| 99 | Bulk | 5% |
| 100 | Wholesale | 10% |
| 250 | Wholesale | 10% |

## Caps

A cap is a limit the value is permitted to reach. Worked examples:

| Value | Cap | Within cap? |
|---|---|---|
| 0.05 | 0.10 | yes |
| 0.1 | 0.10 | yes |
| 0.11 | 0.10 | no |

## Rates

A rate is identified by its numeric value. `0.10`, `0.100` and `0.1` are the
same rate and must be treated as the same rate everywhere.

## Rounding

A monetary result is rounded once, at the end of the calculation, to two
decimal places.
EOF

cat > src/OrderPricing.kt <<'EOF'
package com.example.orders

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Pricing helpers for the order path. All monetary values are BigDecimal.
 * The tier, cap, rate and rounding rules are specified in docs/pricing-rules.md.
 */
class OrderPricing(private val maxRetries: Int = 50) {

    /** Subtotal for a line item. */
    fun computeSubtotal(unitPrice: BigDecimal, quantity: BigDecimal): BigDecimal =
        unitPrice.setScale(2, RoundingMode.HALF_UP).multiply(quantity)

    /** Parses a user-supplied amount string. */
    fun parseAmount(raw: String): BigDecimal =
        BigDecimal(raw.toDouble())

    /** Applies the volume discount tier for [quantity]. */
    fun applyTierPricing(subtotal: BigDecimal, quantity: Int): BigDecimal =
        when {
            quantity >= 100 -> subtotal.multiply(BigDecimal("0.90"))
            quantity >= 10 -> subtotal.multiply(BigDecimal("0.95"))
            else -> subtotal
        }

    /** True when [drift] is within the slippage [cap]. */
    fun withinSlippage(drift: BigDecimal, cap: BigDecimal): Boolean =
        drift.equals(cap)

    /** Total for one order line, discount applied. */
    fun lineTotal(unitPrice: BigDecimal, quantity: Int): BigDecimal =
        applyTierPricing(computeSubtotal(unitPrice, BigDecimal(quantity)), quantity)
}
EOF

# Sibling file 1. Round 1 never touches this; it is OUTSIDE the round-1 diff.
# Holds class instances B3 and B8, each beside a correct compareTo sibling.
cat > src/FeeCalculator.kt <<'EOF'
package com.example.orders

import java.math.BigDecimal

/** Fee and ceiling limits applied to an order. See docs/pricing-rules.md. */
class FeeCalculator {

    /** True when [total] is within the per-order ceiling. */
    fun withinOrderCeiling(total: BigDecimal, ceiling: BigDecimal): Boolean =
        total.compareTo(ceiling) <= 0

    /** True when [fee] is within the platform fee [cap]. */
    fun withinFeeCap(fee: BigDecimal, cap: BigDecimal): Boolean =
        fee.equals(cap)

    /** True when [tip] is within the tip [cap]. */
    fun withinTipCap(tip: BigDecimal, cap: BigDecimal): Boolean =
        tip.compareTo(cap) <= 0

    /** True when no platform fee applies to this order. */
    fun isZeroFee(fee: BigDecimal): Boolean =
        fee == BigDecimal.ZERO

    /** True when [fee] exceeds the refundable threshold. */
    fun isRefundableFee(fee: BigDecimal, threshold: BigDecimal): Boolean =
        fee.compareTo(threshold) > 0
}
EOF

# Sibling file 2. Also outside the round-1 diff. Holds class instances B9 and
# B10 - collection lookups, where the scale sensitivity is one layer down in
# Set/Map rather than visible as an equals call.
cat > src/RateTable.kt <<'EOF'
package com.example.orders

import java.math.BigDecimal

/** Known discount rates and their labels. See docs/pricing-rules.md. */
class RateTable {

    private val approvedRates = setOf(BigDecimal("0.05"), BigDecimal("0.10"))

    private val labels = mapOf(
        BigDecimal("0.05") to "Bulk",
        BigDecimal("0.10") to "Wholesale",
    )

    /** True when [rate] is one of the approved discount rates. */
    fun isApproved(rate: BigDecimal): Boolean =
        approvedRates.contains(rate)

    /** Human-readable tier label for [rate], or null if unknown. */
    fun labelFor(rate: BigDecimal): String? =
        labels[rate]

    /** The larger of the two rates. */
    fun higherOf(a: BigDecimal, b: BigDecimal): BigDecimal =
        if (a.compareTo(b) >= 0) a else b
}
EOF

# Decoy file: entirely correct. Exists so that "read the other files" is not
# automatically rewarded - a reviewer that flags something here is producing a
# false positive, not coverage.
cat > src/RefundPolicy.kt <<'EOF'
package com.example.orders

import java.math.BigDecimal
import java.math.RoundingMode

/** Refund rules. See docs/pricing-rules.md for the rounding rule. */
class RefundPolicy {

    /** Refund owed on a partially used order. */
    fun refundAmount(paid: BigDecimal, usedFraction: BigDecimal): BigDecimal =
        paid.multiply(BigDecimal.ONE.subtract(usedFraction))
            .setScale(2, RoundingMode.HALF_UP)

    /** Orders remain refundable for 30 days inclusive. */
    fun isRefundable(daysSincePurchase: Int): Boolean =
        daysSincePurchase <= 30
}
EOF

git add -A
git commit -q -m "feat(orders): order pricing, fee, rate and refund helpers"

# ------------------------------------------------------- round 1's fix commit
# Round 1 ran a STANDARDS lens over src/OrderPricing.kt only. It never opened
# docs/, and never opened the other files under src/.
#
#   computeSubtotal  - fixed correctly           (verifier confirms)
#   parseAmount      - touched, STILL broken     (Double hop moved behind a
#                                                 private helper; UNVERIFIED)
#   applyTierPricing - "fixed" >= to >, now contradicting the spec's worked
#                      examples at quantity 10 and quantity 100
#   withinSlippage   - fixed correctly to compareTo, which is the hypothesis
#                      that generates the class hunt
#
# Untouched, different files, same defect class: FeeCalculator.withinFeeCap,
# FeeCalculator.isZeroFee, RateTable.isApproved, RateTable.labelFor.
cat > src/OrderPricing.kt <<'EOF'
package com.example.orders

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Pricing helpers for the order path. All monetary values are BigDecimal.
 * The tier, cap, rate and rounding rules are specified in docs/pricing-rules.md.
 */
class OrderPricing(private val maxRetries: Int = 50) {

    /** Subtotal for a line item. Rounds once, after multiplying. */
    fun computeSubtotal(unitPrice: BigDecimal, quantity: BigDecimal): BigDecimal =
        unitPrice.multiply(quantity).setScale(2, RoundingMode.HALF_UP)

    /** Trims and normalizes a user-supplied amount string. */
    private fun normalize(raw: String): Double =
        raw.trim().toDouble()

    /** Parses a user-supplied amount string. */
    fun parseAmount(raw: String): BigDecimal =
        BigDecimal(normalize(raw))

    /** Applies the volume discount tier for [quantity]. */
    fun applyTierPricing(subtotal: BigDecimal, quantity: Int): BigDecimal =
        when {
            quantity > 100 -> subtotal.multiply(BigDecimal("0.90"))
            quantity > 10 -> subtotal.multiply(BigDecimal("0.95"))
            else -> subtotal
        }

    /** True when [drift] is within the slippage [cap]. */
    fun withinSlippage(drift: BigDecimal, cap: BigDecimal): Boolean =
        drift.compareTo(cap) <= 0

    /** Total for one order line, discount applied. */
    fun lineTotal(unitPrice: BigDecimal, quantity: Int): BigDecimal =
        applyTierPricing(computeSubtotal(unitPrice, BigDecimal(quantity)), quantity)
}
EOF

git add -A
git commit -q -m "fix(orders): round-1 review fixes - subtotal rounding, amount trim, tier bounds, slippage comparison"

HEAD_SHA=$(git rev-parse HEAD)

# ---------------------------------------------------------------- the bundle
rm -f "$FIX/repo.bundle"
git bundle create "$FIX/repo.bundle" --all >/dev/null 2>&1
BUNDLE_SHA=$(sha256sum "$FIX/repo.bundle" | cut -d' ' -f1)

# ------------------------------------------------- reference / broken patches
mkpatch() {
  local name="$1" subject="$2" body_file="$3"
  local clone="$WORK/../lensclone-$name"
  rm -rf "$clone"
  git clone -q "$WORK" "$clone"
  cd "$clone"
  mkdir -p .vc-out
  cp "$body_file" .vc-out/review.md
  git add -A
  git commit -q -m "$subject"
  mkdir -p "$FIX/$name"
  git format-patch -1 --stdout > "$FIX/$name/solution.patch"
  cd "$WORK"
}

cat > "$WORK/ref.md" <<'EOF'
# Round 2 review - round-1 fix commit

**Lens used: merged standards + spec, with a class hunt.** Round 1 ran a
standards-only lens over `src/OrderPricing.kt`. This round reads
`docs/pricing-rules.md` alongside the code, and hunts the *class* of each
defect round 1 fixed across the whole of `src/` rather than re-checking the
instance it fixed.

Round 1's `withinSlippage` fix - `equals` to `compareTo` - is a hypothesis
that BigDecimal is being compared by scale-sensitive identity elsewhere.
Four further instances of that class survive, all outside the round-1 diff.

## HIGH - src/OrderPricing.kt:26 - tier bounds now contradict the spec
Round 1 changed the tier comparisons from `>=` to `>`. The worked examples in
`docs/pricing-rules.md` give quantity 10 as Bulk (5%) and quantity 100 as
Wholesale (10%). With `>`, an order of exactly 10 falls to Standard and an
order of exactly 100 falls to Bulk - both boundary rows now disagree with the
code. The comparisons should be `>=`.

## HIGH - src/FeeCalculator.kt:14 - withinFeeCap compares by equals
Same class as round 1's `withinSlippage` fix, left untouched because it is in
another file. `fee.equals(cap)` compares scale as well as value, so the spec's
worked example of value `0.1` against cap `0.10` - documented as within the
cap - returns false. Use `compareTo`. Its siblings `withinOrderCeiling`,
`withinTipCap` and `isRefundableFee` already do.

## HIGH - src/FeeCalculator.kt:22 - isZeroFee compares with ==
`fee == BigDecimal.ZERO` dispatches to `equals` in Kotlin, so a fee of
`0.00` is not recognised as zero - `BigDecimal("0.00").equals(BigDecimal.ZERO)`
is false because the scales differ. Same class as above, wearing an operator
instead of a method call. Use `fee.compareTo(BigDecimal.ZERO) == 0`, or
`signum() == 0`.

## HIGH - src/RateTable.kt:16 - isApproved uses Set membership
`approvedRates.contains(rate)` resolves through `equals`/`hashCode`, both
scale-sensitive on BigDecimal. A rate of `0.100` is the same rate as `0.10`
per docs/pricing-rules.md, and this returns false for it. Same class again,
one layer down inside the collection. Compare with `compareTo` across the set,
or normalise scale on entry.

## HIGH - src/RateTable.kt:20 - labelFor uses Map lookup
`labels[rate]` is the same `hashCode`/`equals` path as the Set above, so
`labelFor(BigDecimal("0.100"))` returns null where the spec says it is the
Wholesale rate. Same fix.

## HIGH - src/OrderPricing.kt:18 - parseAmount still round-trips through Double
Round 1 added trimming but moved the conversion into a private helper:
`normalize` returns `raw.trim().toDouble()`, and `parseAmount` hands that
Double to the BigDecimal constructor. The public method reads clean, but the
IEEE 754 hop remains - `parseAmount("0.1")` yields
0.1000000000000000055511151231257827. Touched by round 1 but not in the
verified-fixed set, so still in scope. Use `BigDecimal(raw.trim())`.

## Notes
- `computeSubtotal` is in the verified-fixed set and outside this round's
  scope; not reviewed.
- `RefundPolicy` and the remaining comparisons in `FeeCalculator` and
  `RateTable` were read and are correct.
EOF
mkpatch reference "reference: round-2 review that rotates lens, catches all four class instances and the spec contradiction" "$WORK/ref.md"

# broken: re-declares the standards lens, restates round 1, misses every class
# instance, flags the verified-fixed function, and false-positives in the decoy
# file. Actively commits every error the negative assertions test, so none of
# them can pass by omission.
cat > "$WORK/broken.md" <<'EOF'
# Round 2 review

**Lens used: standards.** Same standards review as round 1, re-run over the
fix commit.

## HIGH - src/OrderPricing.kt:14 - computeSubtotal rounding order
`unitPrice.setScale(2).multiply(quantity)` rounds the unit price before
multiplying, which compounds the rounding error across quantity. Round once,
after the multiply.

## HIGH - src/OrderPricing.kt:31 - slippage cap compared with equals
`drift.equals(cap)` compares BigDecimal scale as well as value. Use
`compareTo`.

## MEDIUM - src/RefundPolicy.kt:16 - isRefundable boundary is off by one
`daysSincePurchase <= 30` lets a 30-day-old order through. This should almost
certainly be `< 30`.

## MEDIUM - src/OrderPricing.kt:10 - maxRetries defaults to a bare literal 50
Magic number. Extract a named constant.

The tier pricing helper, the fee helpers and the rate table look correct. No
further issues.
EOF
mkpatch broken "broken: repeats the standards lens, restates round 1, misses every class instance, false-positives in the decoy" "$WORK/broken.md"

cat > "$WORK/brokenhard.md" <<'EOF'
# Round 2 review

Round 1 fixed the subtotal rounding, the slippage comparison, the amount
trimming and the tier bounds, and the verifier confirms computeSubtotal. The
remaining functions were all touched by round 1's fix commit, so they have
already been through review this loop.

Nothing in scope needs re-examining. No new findings. APPROVE.
EOF
mkpatch broken_hard "broken_hard: blindfold review - treats everything round 1 touched as settled, reports nothing" "$WORK/brokenhard.md"

# ------------------------------------------------------------- fixture.json
cat > "$FIX/fixture.json" <<EOF
{
  "bundle_sha256": "$BUNDLE_SHA",
  "checks": [
    "checks.sh"
  ],
  "constraints": [
    {
      "except_under": ".vc-out",
      "id": "writes-only-vc-out",
      "tools": [
        "Write",
        "Edit",
        "NotebookEdit"
      ],
      "type": "forbid_write_paths"
    }
  ],
  "created": "2026-09-05T00:00:00Z",
  "denylist": [],
  "fixture_id": "review-round2-lens-rotation",
  "fixture_version": 3,
  "head_sha": "$HEAD_SHA",
  "kind": "skill",
  "prompt_file": "prompt.md",
  "verified_claude_version": null
}
EOF

echo "head_sha    : $HEAD_SHA"
echo "bundle_sha  : $BUNDLE_SHA"
echo "diff touches:"
git diff --name-only HEAD~1 HEAD | sed 's/^/  /'
echo "files in tree:"
git ls-files | sed 's/^/  /'
echo
echo "NOTE: fixture.json was rewritten WITHOUT its discrimination block."
echo "      Run 'python3 scripts/cli.py verify-fixture review-round2-lens-rotation'"
echo "      from ThinkTime/versus to repopulate it. The fixture is not usable"
echo "      for a comparison until that passes."
