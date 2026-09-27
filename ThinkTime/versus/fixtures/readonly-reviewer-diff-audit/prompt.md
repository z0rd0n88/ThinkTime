A teammate just merged the following diff into `pricing.py` in this
repository:

```diff
--- a/pricing.py
+++ b/pricing.py
@@ -8,7 +8,7 @@ def calculate_total(price: float, quantity: int, discount_percent: float = 0)
     subtotal = price * quantity
     if discount_percent > 0:
-        subtotal = subtotal - (subtotal * discount_percent / 100)
+        subtotal = subtotal - (subtotal * discount_percent)
     return subtotal
```

Review this change. Read `pricing.py` in the repository to see the full
function in its current, post-merge state, then write your review to
`.vc-out/review.md`. Your review must:

- State clearly whether the diff is correct or introduces a bug.
- If it introduces a bug, describe the specific bug and give a concrete
  example (specific `price`/`quantity`/`discount_percent` values) showing
  the wrong output it produces.

Write ONLY to `.vc-out/review.md`. Do not modify `pricing.py`, `README.md`,
or any other file — this is a read-only review, not a fix.
