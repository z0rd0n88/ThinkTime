#!/usr/bin/env python3
"""Run planning and execution: FR-6, FR-12, FR-14..FR-18, FR-54, FR-60.

Containment is carried by FR-53 (deny hook), FR-54 (allowlist env), and
the worktree boundary — never by the permission layer (`bypassPermissions`
is deliberate; a headless run has no prompt answerer). Stdlib only.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"

# FR-18: identity pinned via env on the subprocess, never via git config
# (git config is shared across worktrees).
GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "versus-harness",
    "GIT_AUTHOR_EMAIL": "versus@localhost",
    "GIT_COMMITTER_NAME": "versus-harness",
    "GIT_COMMITTER_EMAIL": "versus@localhost",
}


class RunnerError(Exception):
    """A setup step failed; the comparison must abort before tokens spend."""


# ---------------------------------------------------------------- FR-54


def build_child_env(
    parent_env: dict, *, fake_home: str | Path, credential_key: str | None = None
) -> dict:
    """Build the child environment by allowlist FROM AN EMPTY DICT — never
    by stripping a denylist from the parent (T-U-21: an unknown parent
    variable must be absent, which a denylist cannot guarantee).

    `CLAUDECODE` is absent by construction (NFR-7). `HOME` is the per-run
    fake home. Git identity is pinned, not inherited (FR-18)."""
    env: dict[str, str] = {}
    for key in ("PATH", "LANG", "TZ"):
        if key in parent_env:
            env[key] = parent_env[key]
    env["HOME"] = str(fake_home)
    env.update(GIT_IDENTITY)
    if credential_key is not None:
        if credential_key not in parent_env:
            raise RunnerError(
                f"credential key {credential_key} absent from parent "
                "environment (FR-54)"
            )
        env[credential_key] = parent_env[credential_key]
    return env


# ---------------------------------------------------------------- FR-6


def build_run_command(
    *,
    prompt: str,
    model: str,
    effort: str | None,
    settings_path: str | Path,
    session_id: str,
    max_budget_usd: float,
    plugin_dir: str | Path | None = None,
    agents_json: dict | None = None,
    agent_name: str | None = None,
) -> list[str]:
    """The FR-6 minimum flag set. `--verbose` is not optional: on 2.1.204
    `-p` + `--output-format stream-json` exits 1 without it; the spawner
    must also redirect stdin from /dev/null or the CLI stalls (observed
    2026-07-29). `--settings` must be absolute — a relative path silently
    fails to load (observed)."""
    settings_path = Path(settings_path)
    if not settings_path.is_absolute():
        raise RunnerError(
            f"--settings must be an absolute path, got {settings_path} "
            "(a relative path silently fails to load, observed 2026-07-29)"
        )

    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--include-hook-events",
        "--model",
        model,
        "--settings",
        str(settings_path),
        "--setting-sources",
        "project",
        "--mcp-config",
        json.dumps({"mcpServers": {}}),
        "--strict-mcp-config",
        "--session-id",
        session_id,
        "--max-budget-usd",
        str(max_budget_usd),
        "--permission-mode",
        "bypassPermissions",
    ]
    if effort is not None:
        cmd += ["--effort", effort]
    if plugin_dir is not None:
        cmd += ["--plugin-dir", str(plugin_dir)]
    if agents_json is not None:
        cmd += ["--agents", json.dumps(agents_json)]
    if agent_name is not None:
        cmd += ["--agent", agent_name]
    return cmd


# ---------------------------------------------------------------- settings


def write_run_settings(run_dir: Path, *, worktree: Path, sink: Path) -> Path:
    """Generate the per-run --settings file wiring both hooks with this
    run's worktree root and audit channel baked into the command line.
    Returns the absolute settings path.

    `sink` is the run's audit FIFO (FR-20, FR-21.1): the deny hook
    (FR-53) writes its `containment_denied` records into it, and the
    audit hook (hooks/audit-tool.sh, Phase 2) forwards every permitted
    tool call into it, so both land in the SAME harness-collected,
    chain-hashed log — T-U-17's basis for excluding containment_denied
    from constraint_adherence while still parsing it. One writer
    function, extended rather than duplicated (handoff note)."""
    deny = HOOKS_DIR / "deny.sh"
    audit = HOOKS_DIR / "audit-tool.sh"
    deny_cmd = " ".join(shlex.quote(str(x)) for x in ("bash", deny, worktree, sink))
    audit_cmd = " ".join(shlex.quote(str(x)) for x in ("bash", audit, sink))
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": deny_cmd},
                        {"type": "command", "command": audit_cmd},
                    ],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": audit_cmd}],
                }
            ],
        },
    }
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "settings.json"
    path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n")
    return path


# ---------------------------------------------------------------- FR-15/16


def create_worktrees(
    clone: Path, pinned_sha: str, *, count: int, base_dir: Path
) -> list[Path]:
    """FR-15/FR-16: `count` detached worktrees at the pinned sha, ALL
    created before any executor is spawned. Any failure aborts with
    nothing left behind — a worktree-creation failure must cost zero
    tokens."""
    base_dir = Path(base_dir).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for i in range(count):
            wt = base_dir / f"run-{i}"
            res = subprocess.run(
                ["git", "worktree", "add", "--detach", str(wt), pinned_sha],
                cwd=clone,
                capture_output=True,
                text=True,
            )
            if res.returncode != 0:
                raise RunnerError(
                    f"worktree {i + 1}/{count} failed at {pinned_sha}: "
                    f"{res.stderr.strip()} (FR-16: aborting before any "
                    "spawn)"
                )
            created.append(wt)
        return created
    except RunnerError:
        for wt in created:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(wt)],
                cwd=clone,
                capture_output=True,
            )
        shutil.rmtree(base_dir, ignore_errors=True)
        raise


# ---------------------------------------------------------------- FR-12/14


@dataclass(frozen=True)
class RunSpec:
    pair_index: int
    arm: int  # 0 = candidate A, 1 = candidate B (launch-order labels)
    run_id: str = ""
    worktree: Path | None = None
    cmd: list[str] = field(default_factory=list)
    env: dict = field(default_factory=dict)


def plan_runs(*, n: int) -> list[RunSpec]:
    """2N run specs, arms interleaved by pair: A_k and B_k are adjacent so
    batching can never produce all-A-then-all-B (FR-12)."""
    return [RunSpec(pair_index=k, arm=arm) for k in range(n) for arm in (0, 1)]


def batch_pairs(specs: list[RunSpec], *, parallel_pairs: int) -> list[list[RunSpec]]:
    """FR-14: concurrency is counted in PAIRS; a batch always holds whole
    pairs so both arms of pair k launch in the same batch (FR-12)."""
    by_pair: dict[int, list[RunSpec]] = {}
    for s in specs:
        by_pair.setdefault(s.pair_index, []).append(s)
    pairs = [by_pair[k] for k in sorted(by_pair)]
    return [
        sum(pairs[i : i + parallel_pairs], [])
        for i in range(0, len(pairs), parallel_pairs)
    ]
