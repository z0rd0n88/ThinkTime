---
name: swot-analysis
description: 'Use when strategically assessing a product, business, or competitive position — produces a full SWOT plus cross-quadrant strategy and prioritized recommendations'
---

# SWOT Analysis

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

Evaluates the internal and external factors shaping a product's success and
competitive position, then turns the four quadrants into cross-quadrant
strategies and prioritized recommendations. Use it for strategic assessment
and competitive positioning — not for critiquing a specific proposal document
(use `evaluate-proposal-harsh`) or generating new ideas (use `idea-nebula`).

| Option | Values | Default | Effect |
|---|---|---|---|
| `subject` | product, business, feature, or market position — as text or a file path | required | What the SWOT is run against; a file path is read for context, and the analysis is returned in chat unless an output path is given |

You are a strategic analyst conducting a SWOT analysis for the subject named in
the arguments. Evaluate the internal and external factors that will impact
product success and competitive positioning.

## Input requirements

Gather what is available before analyzing; note explicitly what is missing
rather than inventing it.

- Product description and current state
- Competitive landscape and market context
- Company capabilities, resources, and constraints
- Market trends and industry dynamics
- Customer feedback or usage data (optional)

## The four quadrants

### 1. Strengths (internal, positive)

What internal capabilities and advantages exist?

- Unique capabilities or expertise
- Brand recognition or reputation
- Customer relationships and loyalty
- Technology or IP advantages
- Cost advantages or operational efficiency
- Team talent and experience
- Existing customer base or distribution

### 2. Weaknesses (internal, negative)

What internal limitations or gaps exist?

- Resource constraints (budget, team size, skills)
- Technology or infrastructure limitations
- Lack of brand awareness or market presence
- Weak customer relationships or high churn
- High cost structure relative to competitors
- Outdated processes or legacy systems
- Dependence on key people or partners

### 3. Opportunities (external, positive)

What external trends or market dynamics could be leveraged?

- Growing market segments or customer needs
- Technological advances enabling new solutions
- Regulatory changes favoring this approach
- Competitor weaknesses or market gaps
- Partnership or acquisition opportunities
- Expansion into adjacent markets or segments
- Shifting customer preferences or behaviors

### 4. Threats (external, negative)

What external factors could have a negative impact?

- Emerging or stronger competitors
- Changing customer preferences or needs
- Technological disruption or obsolescence
- Regulatory changes or compliance risks
- Economic downturns or market contraction
- Supply chain disruptions
- Supplier or partner consolidation

## Steps

1. **Identify 5–7 strengths.** Be honest about which are genuine competitive
   advantages versus table stakes every competitor also has. Completion
   criterion: each entry names a specific advantage, not a generic virtue.

2. **List 5–7 weaknesses.** Do not minimize; focus on addressable gaps.
   Completion criterion: each entry is something the team could act on or must
   plan around, not a vague worry.

3. **Map 5–7 opportunities**, prioritized by market size and alignment with
   existing strengths.

4. **Flag 5–7 threats**, each with an assessed probability and impact.

5. **Cross-reference the quadrants** for strategic insight — this is where the
   value is, not in the four lists themselves:
   - How do we leverage strengths to capture opportunities? (SO)
   - How do we shore up weaknesses to mitigate threats? (WT)
   - Which opportunities can overcome weaknesses? (WO)
   - Which threats could exploit weaknesses? (ST)

6. **Develop 3–5 strategic recommendations**, each traceable to a specific
   cross-quadrant pairing from step 5.

7. **Prioritize actions and name owners.**

8. **Identify metrics** to track progress on each recommendation.

## Strategic applications

| Posture | When it applies |
|---|---|
| **Build** | Strong strengths meeting real opportunities — double down |
| **Defend** | Weaknesses exposed to live threats — fortify and mitigate |
| **Pivot** | An opportunity that changes the competitive dynamic outright |
| **Exit** | Too many threats against a weak competitive position |

## Notes

- SWOT reads internal first, then external.
- Context matters: compare against competitors and industry standards, not
  against an abstract ideal.
- Update the SWOT quarterly, or whenever market conditions shift.
- Feed the result into roadmap, partnership, and resource-allocation decisions.
- Opportunities and threats should cover both current and emerging dynamics.

## Common mistakes

| Mistake | Fix |
|---|---|
| Listing generic virtues ("good team") as strengths | Name what is specifically better than the named alternative |
| Soft-pedaling weaknesses | A weakness nobody would object to is not a weakness |
| Stopping at four lists | The cross-quadrant pass (step 5) is the deliverable |
| Recommendations untraceable to the analysis | Every recommendation cites the pairing it came from |
| Inventing market data to fill a quadrant | State the gap and mark the entry as unverified |
