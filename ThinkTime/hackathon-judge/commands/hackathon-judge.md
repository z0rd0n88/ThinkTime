---
description: "Judge a hackathon idea against one event's rules: worth building, and would it win"
argument-hint: "[idea — text or file path] + a filled RULES AND CONSTRAINTS block [--category NAME] [--research]"
---

Invoke the `hackathon-judge` skill and follow it exactly.

Arguments forwarded: `$ARGUMENTS`

The skill will:

1. Require a filled RULES AND CONSTRAINTS block, stopping and asking when any field the skill marks required is blank — it does not guess the event. The skill's own field list is authoritative.
2. Build the rubric from those rules: the event's published criteria verbatim where they exist — with its weights too, or equal weights when it publishes none — otherwise six stated criteria with stated weights. A targeted prize category reshapes the judge weights, not the criteria. `--research` lifts the closed-world default and authorises external checking of evidence gaps.
3. Simulate four judges with conflicting incentives (sponsor engineer, business judge, technical judge, time-pressured generalist), score each criterion independently, and report where they split.
4. Return two separate verdicts — worth spending a hackathon on, and would it win — on the ladder BUILD IT / BUILD WITH SCOPE CUTS / SAME DOMAIN, DIFFERENT DEMO / PICK SOMETHING ELSE, each citing the criterion or finding that decided it.
5. Report the complete findings list and build-feasibility evidence gaps, then the minimum demoable slice and an hour-by-hour build plan fitted to the stated duration.
