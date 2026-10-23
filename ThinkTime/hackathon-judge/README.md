# hackathon-judge

Judges one project idea against one specific hackathon. Answers two separate
questions — is this worth spending a hackathon on, and would it win — scored
and reported apart, because an idea can be a great weekend and still lose.

Takes a required RULES AND CONSTRAINTS block (duration, theme, mandated
sponsor tech, team cap, pre-work rules, submission requirements, the event's
published rubric and weights, prize categories) and stops to ask rather than
guessing the event. Builds the rubric from those rules, simulates a four-judge
panel with conflicting incentives, reports where the judges split, and closes
with the minimum demoable slice and an hour-by-hour build plan.

Evidence here means build feasibility — prior art, API availability and rate
limits, whether the hard part has a library, whether the data exists — not
market evidence.

- Skill: `skills/hackathon-judge/SKILL.md`
- Command: `/ThinkTime:hackathon-judge [idea] + RULES AND CONSTRAINTS block`

Use `idea-nebula` to generate candidate ideas first, and `swot-analysis` for
strategic positioning rather than event-scoped judging.
