---
description: "Judge a hackathon idea against one event's rules: worth building, and would it win"
argument-hint: "[idea — text or file path] + a filled RULES AND CONSTRAINTS block"
---

Invoke the `hackathon-judge` skill and follow it exactly.

Arguments forwarded: `$ARGUMENTS`

The skill will:

1. Require a filled RULES AND CONSTRAINTS block (duration, theme, mandated tech, team cap, pre-work rules, submission requirements, published rubric and weights, prize categories) and stop and ask if it is missing — it does not guess the event.
2. Build the rubric from those rules: the event's published criteria and weights verbatim where they exist, otherwise six stated criteria with stated weights, reshaped for the targeted prize category.
3. Simulate four judges with conflicting incentives (sponsor engineer, business judge, technical judge, time-pressured generalist), score each criterion independently, and report where they split.
4. Return two separate verdicts — worth spending a hackathon on, and would it win — on the ladder BUILD IT / BUILD WITH SCOPE CUTS / SAME DOMAIN, DIFFERENT DEMO / PICK SOMETHING ELSE, each citing the deciding criterion.
5. Report the complete findings list and build-feasibility evidence gaps, then the minimum demoable slice and an hour-by-hour build plan fitted to the stated duration.
