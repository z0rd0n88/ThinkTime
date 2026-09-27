# ThinkTime repository rules

ThinkTime is one Claude Code plugin distributed through this repository's marketplace.

- The repository root contains the single `.claude-plugin/marketplace.json`.
- `ThinkTime/.claude-plugin/plugin.json` is the only plugin manifest.
- Keep the marketplace entry name and plugin manifest name aligned: `ThinkTime`.
- Add skills and commands under `ThinkTime/<slug>/` and register their directories in the explicit arrays in `ThinkTime/.claude-plugin/plugin.json`.
- Bump the plugin version in `plugin.json` and the marketplace plugin entry for every shipped change.
- Runtime paths in plugin content use `${CLAUDE_PLUGIN_ROOT}`.
- Tracked changes go through a feature branch and pull request.
