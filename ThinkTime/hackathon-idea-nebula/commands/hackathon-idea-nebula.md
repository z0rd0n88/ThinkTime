---
description: "Generate hackathon project candidates against one event's rules, then shortlist Safe and Swing demos"
argument-hint: "[optional focus text] + a filled RULES AND CONSTRAINTS block"
---

Invoke the `hackathon-idea-nebula` skill and follow it exactly.

Arguments forwarded: `$ARGUMENTS`

The skill will:

1. Require a filled RULES AND CONSTRAINTS block and stop and ask if any gating field is blank (duration, theme, mandated tech, pre-work rules, targeted category) — it does not invent the event.
2. Compute the productive-hours budget from the duration, showing the arithmetic, and brief every generator on that number rather than the event's advertised length.
3. Spawn four independent generators in parallel, each a different entropy source: `tails` (verbalized sampling away from the obvious reading of the theme), `stage` (working backwards from what a judge sees on a screen), `alien` (far-domain structure-mapping onto the mandated tech), and `recon` (live mining of prior art, past winners and the mandated tech's own samples).
4. Pool the candidates blind, name the modal region the room will build, and rank by pairwise duels judged in both orders — demo moment × shippability in the hours budget × distance from that modal region × substantive use of the mandated tech.
5. Feasibility-check the finalists live: API access obtainable before the clock, free-tier limits surviving a live demo, whether the hard part is a library or unsolved, prior-art crowding, pre-work legality, and stack match.
6. Return a barbell shortlist — Safe Demos and Swing Demos, never merged — plus anything a hard threshold killed and why, then hand off to `hackathon-judge` for the verdicts it deliberately does not produce.

It generates; it does not judge. Use `hackathon-judge` on the pick with the same rules block, and `idea-nebula` for a non-event brainstorm.
