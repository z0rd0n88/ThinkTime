---
description: "Generate hackathon project candidates against one event's rules, then shortlist Safe and Swing demos"
argument-hint: "[optional focus text] + a filled RULES AND CONSTRAINTS block"
---

Invoke the `hackathon-idea-nebula` skill and follow it exactly.

Arguments forwarded: `$ARGUMENTS`

The skill will:

1. Require a filled RULES AND CONSTRAINTS block and stop and ask if any gating field is blank or a placeholder (duration, theme, mandated tech, pre-work rules, targeted category). An explicit `none` for mandated tech is a filled field. It does not invent the event.
2. Compute the productive-hours budget in person-hours from the duration and team size, showing the arithmetic, and brief every agent on that number and unit rather than the event's advertised length.
3. Spawn four independent generators in parallel, each a different entropy source: `tails` (verbalized sampling away from the obvious reading of the theme), `stage` (working backwards from what a judge sees on a screen), `alien` (far-domain structure-mapping onto the mandated tech), and `recon` (live mining of prior art, past winners and the mandated tech's own samples).
4. Pool the candidates blind, name the modal region the room will build, and rank by pairwise duels judged in both orders on demo moment × shippability in the hours budget × distance from that modal region × substantive use of the mandated tech.
5. Feasibility-check the top of each arm and then by standings, live: API access obtainable before the clock, free-tier limits against the demo's call arithmetic, whether the hard part is a library or unsolved, prior-art crowding, pre-work legality, stack match, and whether every submission artefact can actually be produced.
6. Return a barbell shortlist of Safe Demos and Swing Demos, never merged, plus anything a hard threshold killed and why, then hand off to `hackathon-judge` for the verdicts it deliberately does not produce.

It generates; it does not judge. Use `hackathon-judge` on the pick with the same rules block, and `idea-nebula` for a non-event brainstorm.
