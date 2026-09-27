# ThinkTime

Seven thinking and decision skills packaged as a Claude Code plugin: idea generation, panel thinking, design critique, SWOT analysis, option comparison, and usage reflection.

## Install

```bash
claude plugin marketplace add z0rd0n88/ThinkTime
claude plugin install ThinkTime@thinktime
```

The marketplace registers the consolidated `ThinkTime` plugin. Its skills run under the `/ThinkTime:` namespace; see each skill's README for its triggers and usage.

## Included skills

| Skill | Purpose |
|---|---|
| `idea-nebula` | Generate, rank, and refine ideas. |
| `idea-panel` | Explore a topic through multiple thinking lenses. |
| `idea-refine` | Turn a rough idea into an actionable concept through structured divergent and convergent thinking. |
| `i-cant-even` | Evaluate a design choice through distinct personas. |
| `improve-me` | Audit Claude Code usage and propose evidence-based improvements. |
| `swot-analysis` | Assess strengths, weaknesses, opportunities, and threats. |
| `versus` | Compare candidate approaches using structured evaluation. |

## Development

The plugin lives in `ThinkTime/`; the repository root is its marketplace. Keep the marketplace entry name and plugin manifest name aligned. Bump the plugin version in both manifests for every published change.
