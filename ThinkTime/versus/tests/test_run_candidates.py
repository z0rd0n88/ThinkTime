"""Phase D tests: run_candidates.py — FR-6, FR-12, FR-14..FR-18, FR-54,
FR-60 (T-U-21 env allowlist; dry-run; worktree fleet; pairing).

Tier 0: worktrees use a local throwaway git repo; no executor is spawned —
the spawn callable is injected and asserted against.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from run_candidates import (  # noqa: E402
    GIT_IDENTITY,
    RunnerError,
    batch_pairs,
    build_child_env,
    build_run_command,
    create_worktrees,
    plan_runs,
    write_run_settings,
)


# ---------------------------------------------------------------- T-U-21


PARENT_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/home/alex",
    "LANG": "en_GB.UTF-8",
    "TZ": "Europe/London",
    "GH_TOKEN": "real-gh-token",
    "GITHUB_PERSONAL_ACCESS_TOKEN": "real-pat",
    "DISCORD_BOT_TOKEN": "real-discord",
    "RUNPOD_API_KEY": "real-runpod",
    "VC_CANARY_SECRET": "canary-value",
    "CLAUDECODE": "1",
    "SSH_AUTH_SOCK": "/run/ssh.sock",
    "XDG_RUNTIME_DIR": "/run/user/1000",
}


class TestEnvAllowlist:
    def test_child_env_is_exactly_the_allowlist(self, tmp_path):
        fake_home = tmp_path / "fakehome"
        env = build_child_env(PARENT_ENV, fake_home=fake_home)
        assert set(env) == {
            "PATH",
            "HOME",
            "LANG",
            "TZ",
            "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME",
            "GIT_COMMITTER_EMAIL",
        }

    def test_unknown_parent_variable_never_leaks(self, tmp_path):
        # The allowlist-from-empty assertion: a denylist implementation
        # cannot satisfy this for a variable it has never heard of.
        parent = dict(PARENT_ENV, TOTALLY_NOVEL_VAR="x")
        env = build_child_env(parent, fake_home=tmp_path)
        assert "TOTALLY_NOVEL_VAR" not in env

    def test_claudecode_absent_by_construction(self, tmp_path):
        env = build_child_env(PARENT_ENV, fake_home=tmp_path)
        assert "CLAUDECODE" not in env

    def test_home_is_fake_home_not_real(self, tmp_path):
        env = build_child_env(PARENT_ENV, fake_home=tmp_path / "fh")
        assert env["HOME"] == str(tmp_path / "fh")
        assert env["HOME"] != "/home/alex"

    def test_git_identity_pinned_not_inherited(self, tmp_path):
        parent = dict(PARENT_ENV, GIT_AUTHOR_NAME="Alex Real")
        env = build_child_env(parent, fake_home=tmp_path)
        assert env["GIT_AUTHOR_NAME"] == GIT_IDENTITY["GIT_AUTHOR_NAME"]
        assert env["GIT_AUTHOR_NAME"] != "Alex Real"

    def test_credential_key_passthrough_when_named(self, tmp_path):
        env = build_child_env(PARENT_ENV, fake_home=tmp_path, credential_key="GH_TOKEN")
        assert env["GH_TOKEN"] == "real-gh-token"

    def test_no_credential_by_default(self, tmp_path):
        env = build_child_env(PARENT_ENV, fake_home=tmp_path)
        assert "GH_TOKEN" not in env

    def test_absent_parent_lang_tz_omitted_not_empty(self, tmp_path):
        env = build_child_env({"PATH": "/bin", "HOME": "/h"}, fake_home=tmp_path)
        assert "LANG" not in env and "TZ" not in env


# ---------------------------------------------------------------- FR-6


class TestRunCommand:
    def cmd(self, **kw):
        defaults = dict(
            prompt="do the task",
            model="haiku",
            effort=None,
            settings_path="/abs/settings.json",
            session_id="00000000-0000-0000-0000-000000000001",
            max_budget_usd=1.0,
        )
        defaults.update(kw)
        return build_run_command(**defaults)

    def test_minimum_flag_set_present(self):
        cmd = self.cmd()
        joined = " ".join(cmd)
        for flag in (
            "--output-format stream-json",
            "--verbose",
            "--include-partial-messages",
            "--include-hook-events",
            "--model haiku",
            "--settings /abs/settings.json",
            "--setting-sources project",
            "--strict-mcp-config",
            "--permission-mode bypassPermissions",
            "--max-budget-usd 1.0",
            "--session-id 00000000-0000-0000-0000-000000000001",
        ):
            assert flag in joined, flag
        assert cmd[0] == "claude"
        assert "-p" in cmd

    def test_mcp_config_is_empty_servers(self):
        cmd = self.cmd()
        i = cmd.index("--mcp-config")
        assert json.loads(cmd[i + 1]) == {"mcpServers": {}}

    def test_settings_path_must_be_absolute(self):
        # Observed 2026-07-29: a relative --settings silently fails to load.
        with pytest.raises(RunnerError):
            self.cmd(settings_path="rel/settings.json")

    def test_skill_run_adds_plugin_dir_only(self):
        cmd = self.cmd(plugin_dir="/abs/plug")
        assert "--plugin-dir" in cmd
        assert "--agents" not in cmd

    def test_agent_run_adds_agents_json_and_agent_name(self):
        agents = {"probe": {"description": "d", "prompt": "p", "tools": ["Read"]}}
        cmd = self.cmd(agents_json=agents, agent_name="probe")
        i = cmd.index("--agents")
        assert json.loads(cmd[i + 1]) == agents
        assert cmd[cmd.index("--agent") + 1] == "probe"

    def test_effort_omitted_when_none(self):
        assert "--effort" not in self.cmd(effort=None)
        assert "--effort" in self.cmd(effort="low")


# ---------------------------------------------------------------- settings


class TestRunSettings:
    def test_settings_wires_deny_hook_with_worktree_and_sink(self, tmp_path):
        p = write_run_settings(
            tmp_path, worktree=tmp_path / "wt", sink=tmp_path / "audit.jsonl"
        )
        assert p.is_absolute()
        data = json.loads(p.read_text())
        hooks = data["hooks"]["PreToolUse"]
        cmd = hooks[0]["hooks"][0]["command"]
        assert "deny.sh" in cmd
        assert str(tmp_path / "wt") in cmd
        assert str(tmp_path / "audit.jsonl") in cmd
        assert hooks[0]["matcher"] == "*"


# ---------------------------------------------------------------- FR-15/16


@pytest.fixture
def tiny_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), **GIT_IDENTITY}
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=env)
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True, env=env)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    ).stdout.strip()
    return repo, sha


class TestWorktrees:
    def test_creates_2n_detached_worktrees(self, tiny_repo, tmp_path):
        repo, sha = tiny_repo
        wts = create_worktrees(repo, sha, count=6, base_dir=tmp_path / "wts")
        assert len(wts) == 6
        for wt in wts:
            assert (wt / "f.txt").is_file()

    def test_bad_sha_aborts_before_any_worktree(self, tiny_repo, tmp_path):
        repo, _ = tiny_repo
        base = tmp_path / "wts2"
        with pytest.raises(RunnerError):
            create_worktrees(repo, "0" * 40, count=4, base_dir=base)
        assert not base.exists() or not any(base.iterdir())


# ---------------------------------------------------------------- FR-12/14


class TestPairing:
    def test_plan_produces_2n_specs_paired(self):
        specs = plan_runs(n=3)
        assert len(specs) == 6
        for k in range(3):
            pair = [s for s in specs if s.pair_index == k]
            assert sorted(s.arm for s in pair) == [0, 1]

    def test_batches_contain_whole_pairs_never_split(self):
        specs = plan_runs(n=5)
        batches = batch_pairs(specs, parallel_pairs=2)
        for batch in batches:
            pairs = {s.pair_index for s in batch}
            for k in pairs:
                assert len([s for s in batch if s.pair_index == k]) == 2

    def test_never_all_a_then_all_b(self):
        specs = plan_runs(n=3)
        batches = batch_pairs(specs, parallel_pairs=1)
        # every batch carries both arms of its pair (FR-12)
        for batch in batches:
            assert {s.arm for s in batch} == {0, 1}


class TestSettingsQuoting:
    def test_spacey_workspace_paths_are_shell_quoted(self, tmp_path):
        spacey = tmp_path / "John Doe" / "ws"
        spacey.mkdir(parents=True)
        p = write_run_settings(
            spacey, worktree=spacey / "wt", sink=spacey / "audit.jsonl"
        )
        import shlex

        cmd = json.loads(p.read_text())["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        parts = shlex.split(cmd)
        assert parts[-2] == str(spacey / "wt")
        assert parts[-1] == str(spacey / "audit.jsonl")


class TestSettingsAuditWiring:
    """Phase 2: the same sink/FIFO backs both hooks (T-U-17's basis for
    parsing containment_denied and tool_call records from one log)."""

    def test_audit_hook_wired_on_pretooluse_and_posttooluse(self, tmp_path):
        p = write_run_settings(
            tmp_path, worktree=tmp_path / "wt", sink=tmp_path / "audit.fifo"
        )
        data = json.loads(p.read_text())
        pre_cmds = [h["command"] for h in data["hooks"]["PreToolUse"][0]["hooks"]]
        post_cmds = [h["command"] for h in data["hooks"]["PostToolUse"][0]["hooks"]]
        assert any("deny.sh" in c for c in pre_cmds)
        assert any("audit-tool.sh" in c for c in pre_cmds)
        assert any("audit-tool.sh" in c for c in post_cmds)
        assert all(str(tmp_path / "audit.fifo") in c for c in pre_cmds + post_cmds)

    def test_deny_hook_stays_first_in_pretooluse(self, tmp_path):
        # T-U-20 exercises hooks[0] directly; deny must stay first so a
        # denial short-circuits before the audit hook runs.
        p = write_run_settings(
            tmp_path, worktree=tmp_path / "wt", sink=tmp_path / "audit.fifo"
        )
        data = json.loads(p.read_text())
        assert "deny.sh" in data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
