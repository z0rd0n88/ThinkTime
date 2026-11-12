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

- Decision to inform, time horizon, and alternatives under consideration
- Product description and current state
- Competitive landscape and market context
- Company capabilities, resources, and constraints
- Market trends and industry dynamics
- Customer feedback or usage data (optional)

For material claims, identify the source and date when available. Distinguish
observed facts, estimates, and assumptions; flag disputed or missing evidence.

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

1. **Identify material strengths.** Distinguish genuine advantages from table
   stakes shared by competitors. Each entry should name a specific capability
   and the alternative it is strong against; do not fill a quota.

2. **Identify material weaknesses.** Focus on gaps the team could address or
   must plan around. Missing input is an analysis gap, not automatically a
   weakness of the subject. Leave a quadrant sparse if the evidence is sparse.

3. **Map material opportunities.** Assess relevance to the decision and
   feasibility. Use market size or strength alignment where supported, and
   mark unknowns instead of inventing figures.

4. **Flag material threats.** Describe likelihood and consequence where there
   is a basis to assess them; otherwise mark them unknown. Do not turn rough
   ratings into a numerical ranking without a justified method.

5. **Cross-reference the quadrants** to generate strategic options. Make a
   pairing only when both factors have support; otherwise mark it unavailable.
   Treat each option as a hypothesis, not proof that it will work:
   - How could strengths help capture opportunities? (SO)
   - How could opportunities help overcome weaknesses? (WO)
   - How could strengths help counter threats? (ST)
   - How could weaknesses be reduced to limit exposure to threats? (WT)

6. **Develop recommendations only where warranted.** Trace each strategic
   recommendation to specific factors and a valid pairing from step 5; state
   what would test or change it. List research needed to fill evidence gaps
   separately from strategic recommendations.

7. **Prioritize actions.** Name an owner if known, or identify who must decide.

8. **Identify a measurable check** for each recommendation where meaningful.

## Strategic applications

| Posture | When it applies |
|---|---|
| **Build** | Consider investing where supported strengths meet credible opportunities |
| **Defend** | Consider reducing exposure where credible threats meet material weaknesses |
| **Pivot** | Consider changing direction when a better option is supported by evidence |
| **Exit** | Consider withdrawal only after comparing alternatives, costs, and evidence |

## Notes

- The quadrants organize the analysis; their order does not determine the decision.
- Context matters: compare against competitors and industry standards, not
  against an abstract ideal.
- Revisit the analysis when material assumptions, capabilities, competitors, or
  market conditions change. Choose any calendar cadence for an explicit reason.
- Use the result as input to roadmap, partnership, and resource-allocation
  decisions; the matrix itself does not validate an action.
- Opportunities and threats should cover both current and emerging dynamics.

## Common mistakes

| Mistake | Fix |
|---|---|
| Listing generic virtues ("good team") as strengths | Name what is specifically better than the named alternative |
| Soft-pedaling weaknesses | A weakness nobody would object to is not a weakness |
| Stopping at four lists | The cross-quadrant pass (step 5) is the deliverable |
| Recommendations untraceable to the analysis | Every recommendation cites the pairing it came from |
| Inventing market data to fill a quadrant | State the gap and mark the entry as unverified |
