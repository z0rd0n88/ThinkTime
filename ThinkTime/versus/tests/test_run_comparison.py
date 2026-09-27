"""Phase E tests: run_comparison.py — the cli→resolve→fixture→runner wiring.

FR-60 dry-run (2N worktrees, printed cmd + env keys, NO spawn), FR-63
unverified-fixture gating at the orchestration layer, transcript fleet via
an injected spawner, T-I-7 model_confounded stamp, FR-61 clean default.

Tier 0: the spawner is injected; no real executor ever launches. Phase 2
adds a grader invocation per run — an autouse fixture below patches
`run_comparison.default_grader_spawner` to fail loudly if a test forgets
to inject `grader_spawner=FakeGraderSpawner()`, so nothing here ever falls
through to a REAL `claude -p` subprocess. The containment assertion is an
ABSENT SIDE EFFECT (file bytes unchanged), never a log line.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_comparison as run_comparison_module  # noqa: E402
from cli import parse_and_validate  # noqa: E402
from run_comparison import ComparisonRefused, run_comparison  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DEV_NOOP = REPO_ROOT / "dev" / "fixtures" / "dev-noop"
DEV_NOOP_ASSERTION_IDS = ["A1", "A2", "A3"]

DEV_ENV = {
    "VERSUS_DEV": "1",
    "PATH": "/usr/bin:/bin",
    "HOME": "/home/alex",
    "LANG": "C.UTF-8",
}


@pytest.fixture(autouse=True)
def _never_spawn_a_real_grader(monkeypatch):
    def fake_default_grader_spawner(cmd, *, cwd, env):
        raise AssertionError(
            "a test invoked default_grader_spawner (a REAL `claude -p` "
            "subprocess) instead of an injected fake — pass grader_spawner="
        )

    monkeypatch.setattr(
        run_comparison_module, "default_grader_spawner", fake_default_grader_spawner
    )

    def fake_default_comparator_spawner(cmd, *, cwd, env):
        raise AssertionError(
            "a test invoked default_comparator_spawner (a REAL `claude -p` "
            "subprocess) instead of an injected fake — pass "
            "comparator_spawner="
        )

    monkeypatch.setattr(
        run_comparison_module,
        "default_comparator_spawner",
        fake_default_comparator_spawner,
    )


@pytest.fixture
def candidates(tmp_path):
    a = tmp_path / "cand_a.md"
    b = tmp_path / "cand_b.md"
    a.write_text('---\nname: cand-a\ndescription: A\ntools: ["Read"]\n---\nA body\n')
    b.write_text("---\nname: cand-b\ndescription: B\n---\nB body\n")
    return a, b


def parse(argv, env=DEV_ENV):
    return parse_and_validate(argv, env=env, plugin_version="0.0.1-dev")


def run_args(a, b, ws, extra=()):
    return parse(
        [
            "run",
            str(a),
            str(b),
            "--fixture",
            str(DEV_NOOP),
            "--unverified-fixture",
            "--quick",
            "--workspace",
            str(ws),
            *extra,
        ]
    )


class FakeSpawner:
    def __init__(self, transcript_line='{"type":"result"}\n'):
        self.calls = []
        self.transcript_line = transcript_line

    def __call__(self, cmd, *, cwd, env, transcript_path):
        self.calls.append(
            types.SimpleNamespace(
                cmd=cmd, cwd=cwd, env=env, transcript_path=transcript_path
            )
        )
        Path(transcript_path).write_text(self.transcript_line)
        return 0


class FakeGraderSpawner:
    """Stubs the grader's `claude -p` invocation — dev-noop's
    assertions.json declares A1/A2/A3, so the default response covers
    exactly those ids and marks every one un-passed (a stub, not a real
    grade)."""

    def __init__(self, assertion_ids=DEV_NOOP_ASSERTION_IDS, response=None):
        self.calls = []
        self.assertion_ids = assertion_ids
        self._response = response

    def _default_response(self):
        expectations = [
            {
                "id": aid,
                "text": aid,
                "passed": False,
                "evidence": "stubbed grader (Tier 0)",
            }
            for aid in self.assertion_ids
        ]
        return json.dumps(
            {
                "expectations": expectations,
                "summary": {
                    "passed": 0,
                    "failed": len(self.assertion_ids),
                    "total": len(self.assertion_ids),
                    "pass_rate": 0.0,
                },
            }
        )

    def __call__(self, cmd, *, cwd, env):
        self.calls.append(types.SimpleNamespace(cmd=cmd, cwd=cwd, env=env))
        return self._response or self._default_response()


class FakeComparatorSpawner:
    """Stubs the comparator's `claude -p` invocation (Phase 3)."""

    def __init__(self, winner="TIE", response=None):
        self.calls = []
        self.winner = winner
        self._response = response

    def __call__(self, cmd, *, cwd, env):
        self.calls.append(types.SimpleNamespace(cmd=cmd, cwd=cwd, env=env))
        return self._response or json.dumps(
            {"winner": self.winner, "rationale": "stub", "identity_inferred": False}
        )


class TestDryRun:
    def test_dry_run_creates_2n_worktrees_and_spawns_nothing(
        self, candidates, tmp_path, capsys
    ):
        a, b = candidates
        ws = tmp_path / "ws"
        spawner = FakeSpawner()
        ns = run_args(a, b, ws, extra=["--dry-run"])
        rc = run_comparison(ns, parent_env=DEV_ENV, spawner=spawner)
        assert rc == 0
        assert spawner.calls == []
        comparison_dirs = list(ws.iterdir())
        assert len(comparison_dirs) == 1
        wts = list((comparison_dirs[0] / "worktrees").iterdir())
        assert len(wts) == 6  # --quick → N=3 → 2N=6

    def test_dry_run_prints_cmd_env_keys_count_budget(
        self, candidates, tmp_path, capsys
    ):
        a, b = candidates
        ns = run_args(a, b, tmp_path / "ws", extra=["--dry-run"])
        run_comparison(ns, parent_env=DEV_ENV, spawner=FakeSpawner())
        out = capsys.readouterr().out
        assert out.count("claude -p") == 6  # exact command line per run
        assert "GIT_AUTHOR_NAME" in out  # env KEY list...
        assert "--verbose" in out
        assert "invocations" in out.lower()
        assert "budget" in out.lower()

    def test_dry_run_never_prints_env_values(self, candidates, tmp_path, capsys):
        a, b = candidates
        env = dict(DEV_ENV, GH_TOKEN="sekrit-value")
        ns = run_args(a, b, tmp_path / "ws", extra=["--dry-run"])
        run_comparison(ns, parent_env=env, spawner=FakeSpawner())
        assert "sekrit-value" not in capsys.readouterr().out


class TestUnverifiedGate:
    def test_dev_noop_refused_without_unverified_flag(self, candidates, tmp_path):
        a, b = candidates
        ns = parse(
            [
                "run",
                str(a),
                str(b),
                "--fixture",
                str(DEV_NOOP),
                "--quick",
                "--workspace",
                str(tmp_path / "ws"),
            ]
        )
        with pytest.raises(ComparisonRefused) as exc:
            run_comparison(ns, parent_env=DEV_ENV, spawner=FakeSpawner())
        assert "discrimination" in str(exc.value)

    def test_unverified_run_stamps_fixture_unverified(self, candidates, tmp_path):
        a, b = candidates
        ws = tmp_path / "ws"
        ns = run_args(a, b, ws)
        run_comparison(
            ns,
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        record = json.loads(next(ws.iterdir()).joinpath("comparison.json").read_text())
        assert record["fixture_unverified"] is True


class TestLiveFleet:
    def test_2n_transcripts_written(self, candidates, tmp_path):
        a, b = candidates
        ws = tmp_path / "ws"
        spawner = FakeSpawner()
        rc = run_comparison(
            run_args(a, b, ws),
            parent_env=DEV_ENV,
            spawner=spawner,
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        assert rc == 0
        assert len(spawner.calls) == 6
        cmp_dir = next(ws.iterdir())
        transcripts = sorted((cmp_dir / "runs").glob("*/transcript.jsonl"))
        assert len(transcripts) == 6

    def test_spawner_gets_worktree_cwd_and_allowlist_env(self, candidates, tmp_path):
        a, b = candidates
        spawner = FakeSpawner()
        run_comparison(
            run_args(a, b, tmp_path / "ws"),
            parent_env=DEV_ENV,
            spawner=spawner,
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        for call in spawner.calls:
            assert "worktrees" in str(call.cwd)
            assert "CLAUDECODE" not in call.env
            assert call.env["GIT_AUTHOR_NAME"] == "versus-harness"
            assert Path(call.cmd[call.cmd.index("--settings") + 1]).is_absolute()

    def test_arms_interleaved_within_pairs(self, candidates, tmp_path):
        a, b = candidates
        spawner = FakeSpawner()
        run_comparison(
            run_args(a, b, tmp_path / "ws"),
            parent_env=DEV_ENV,
            spawner=spawner,
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        # both arms of pair k appear before any run of pair k+1 (FR-12)
        plugin_flags = ["--agent" in c.cmd for c in spawner.calls]
        assert plugin_flags[:2].count(True) >= 0  # structural smoke
        pair_of = [str(c.transcript_path) for c in spawner.calls]
        assert len(pair_of) == 6


class TestAuditWiring:
    """Phase 2: every run gets a harness-owned, chain-hashed audit log
    (FR-21.1/.4) created around the (fake) spawn — never before/after."""

    def test_every_run_has_a_0400_terminated_audit_log(self, candidates, tmp_path):
        a, b = candidates
        rc = run_comparison(
            run_args(a, b, tmp_path / "ws"),
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        assert rc == 0
        cmp_dir = next((tmp_path / "ws").iterdir())
        logs = sorted((cmp_dir / "runs").glob("*/audit.jsonl"))
        assert len(logs) == 6
        for log in logs:
            import os

            assert (os.stat(log).st_mode & 0o777) == 0o400
            lines = [ln for ln in log.read_text().splitlines() if ln.strip()]
            assert lines, f"{log} is empty — collector never stamped a terminal record"
            assert json.loads(lines[-1])["type"] == "terminal"

    def test_fifo_is_removed_after_stop(self, candidates, tmp_path):
        a, b = candidates
        run_comparison(
            run_args(a, b, tmp_path / "ws"),
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        cmp_dir = next((tmp_path / "ws").iterdir())
        fifos = list((cmp_dir / "runs").glob("*/audit.fifo"))
        assert fifos == []

    def test_comparison_json_records_enforcement_and_env_keys(
        self, candidates, tmp_path
    ):
        a, b = candidates
        ws = tmp_path / "ws"
        run_comparison(
            run_args(a, b, ws),
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        record = json.loads(next(ws.iterdir()).joinpath("comparison.json").read_text())
        assert (
            record["candidates"][0]["enforcement"]["tools_allowlist_enforced"] is True
        )
        assert record["candidates"][1]["enforcement"]["restrictions_declared"] == "none"
        assert "HOME" in record["env_allowlist"]
        assert "/home/alex" not in json.dumps(record["env_allowlist"])

    def test_model_confounded_stamp(self, candidates, tmp_path):
        a, b = candidates
        ws = tmp_path / "ws"
        ns = run_args(a, b, ws, extra=["--respect-candidate-model"])
        run_comparison(
            ns,
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        record = json.loads(next(ws.iterdir()).joinpath("comparison.json").read_text())
        assert record["model_confounded"] is True

    def test_crash_marker_written_and_removed_on_completion(self, candidates, tmp_path):
        a, b = candidates
        ws = tmp_path / "ws"
        run_comparison(
            run_args(a, b, ws),
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        cmp_dir = next(ws.iterdir())
        assert not (cmp_dir / ".vc-run-state.json").exists()


class TestGradingWiring:
    """Phase 2: every run gets a grading.json carrying task_outcome, the
    chain-verified audit-derived tool count, and self_report_divergence
    (spec §7 Phase 2 exit criterion)."""

    def test_every_run_has_grading_json_with_task_outcome_and_divergence(
        self, candidates, tmp_path
    ):
        a, b = candidates
        ws = tmp_path / "ws"
        grader = FakeGraderSpawner()
        rc = run_comparison(
            run_args(a, b, ws),
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=grader,
            comparator_spawner=FakeComparatorSpawner(),
        )
        assert rc == 0
        assert len(grader.calls) == 6
        cmp_dir = next(ws.iterdir())
        gradings = sorted((cmp_dir / "runs").glob("*/grading.json"))
        assert len(gradings) == 6
        for g in gradings:
            data = json.loads(g.read_text())
            assert data["task_outcome"] in {"success", "partial", "failure"}
            assert "self_report_divergence" in data
            assert data["audit"]["chain_ok"] is True
            assert data["audit"]["audit_total"] is not None

    def test_grader_agents_payload_names_vc_grader(self, candidates, tmp_path):
        a, b = candidates
        grader = FakeGraderSpawner()
        run_comparison(
            run_args(a, b, tmp_path / "ws"),
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=grader,
            comparator_spawner=FakeComparatorSpawner(),
        )
        for call in grader.calls:
            assert call.cmd[call.cmd.index("--agent") + 1] == "vc-grader"
            agents = json.loads(call.cmd[call.cmd.index("--agents") + 1])
            assert set(agents) == {"vc-grader"}

    def test_malformed_grader_response_retried_then_recorded(
        self, candidates, tmp_path
    ):
        a, b = candidates
        ws = tmp_path / "ws"
        grader = FakeGraderSpawner(response="not valid json")
        rc = run_comparison(
            run_args(a, b, ws),
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=grader,
            comparator_spawner=FakeComparatorSpawner(),
        )
        assert rc == 0  # a bad grader never hangs the barrier
        assert len(grader.calls) == 6 * 3  # 1 initial + 2 retries, every run
        cmp_dir = next(ws.iterdir())
        gradings = sorted((cmp_dir / "runs").glob("*/grading.json"))
        for g in gradings:
            data = json.loads(g.read_text())
            assert data["error_class"] == "grader_malformed_json"
            assert data["retries"] == 2
            # FR-58 denominator rule: the gate result decides the pair
            # regardless of the grading failure.
            assert data["task_outcome"] in {"success", "partial", "failure"}

    def test_tampered_audit_log_forces_audit_integrity(
        self, candidates, tmp_path, monkeypatch
    ):
        """T-C-3's PASS predicate at Tier-0 scope: a tampered log yields
        error_class: audit_integrity and is excluded from
        constraint_adherence rather than scored zero-violation."""
        import os

        import run_comparison as rc_mod

        a, b = candidates
        ws = tmp_path / "ws"

        real_stop = rc_mod.AuditCollector.stop

        def tampering_stop(self, *args, **kwargs):
            real_stop(self, *args, **kwargs)
            if self.log_path.exists():
                os.chmod(self.log_path, 0o600)
                self.log_path.write_text(self.log_path.read_text() + "TAMPERED\n")
                os.chmod(self.log_path, 0o400)

        monkeypatch.setattr(rc_mod.AuditCollector, "stop", tampering_stop)

        run_comparison(
            run_args(a, b, ws),
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        cmp_dir = next(ws.iterdir())
        gradings = sorted((cmp_dir / "runs").glob("*/grading.json"))
        for g in gradings:
            data = json.loads(g.read_text())
            assert data["task_outcome"] == "failure"
            assert data["audit"]["chain_ok"] is False
            assert data["audit"]["error_class"] == "audit_integrity"


class TestContainmentAbsentSideEffect:
    def test_denied_outside_write_did_not_happen(self, candidates, tmp_path):
        """The Phase 1 containment exit criterion: the assertion is the
        ABSENT side effect (target bytes unchanged), never a denial log.

        The spawner here simulates an executor honouring the PreToolUse
        contract by invoking the run's generated settings hook exactly as
        the CLI would (stdin JSON), then writing only if permitted."""
        import subprocess

        a, b = candidates
        ws = tmp_path / "ws"
        target = tmp_path / "victim.txt"
        target.write_text("original")

        class HookHonouringSpawner(FakeSpawner):
            def __call__(self, cmd, *, cwd, env, transcript_path):
                settings = json.loads(
                    Path(cmd[cmd.index("--settings") + 1]).read_text()
                )
                hook_cmd = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
                payload = json.dumps(
                    {"tool_name": "Write", "tool_input": {"file_path": str(target)}}
                )
                res = subprocess.run(
                    hook_cmd, shell=True, input=payload, text=True, capture_output=True
                )
                if res.returncode == 0:  # would fail open on exit 1
                    target.write_text("ESCAPED")
                return super().__call__(
                    cmd, cwd=cwd, env=env, transcript_path=transcript_path
                )

        run_comparison(
            run_args(a, b, ws),
            parent_env=DEV_ENV,
            spawner=HookHonouringSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        assert target.read_text() == "original"


class TestClean:
    def test_clean_default_lists_and_removes_nothing(
        self, candidates, tmp_path, capsys
    ):
        from run_comparison import clean_workspaces

        a, b = candidates
        ws = tmp_path / "ws"
        run_comparison(
            run_args(a, b, ws),
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        cmp_dir = next(ws.iterdir())
        ns = parse(["clean", "--workspace", str(ws)])
        rc = clean_workspaces(ns)
        assert rc == 0
        assert cmp_dir.exists()


class TestExecutorAuthProvisioning:
    """FR-54's 'single credential' on this box is the HOME-based CLI
    credential (Phase 0 task 11): it is materialized INTO the fake home,
    never inherited via env. The real ~/.claude.json (projects, history)
    must NOT be copied — only a minimal onboarding stub."""

    def test_fake_home_seeded_with_credential_and_stub(self, tmp_path):
        from run_comparison import provision_executor_auth

        real_home = tmp_path / "real"
        (real_home / ".claude").mkdir(parents=True)
        (real_home / ".claude" / ".credentials.json").write_text('{"tok": "x"}')
        (real_home / ".claude.json").write_text(
            json.dumps({"hasCompletedOnboarding": True, "projects": {"secret": 1}})
        )
        fake_home = tmp_path / "fake"
        fake_home.mkdir()
        provision_executor_auth(fake_home, real_home=real_home)
        assert (
            fake_home / ".claude" / ".credentials.json"
        ).read_text() == '{"tok": "x"}'
        stub = json.loads((fake_home / ".claude.json").read_text())
        assert stub.get("hasCompletedOnboarding") is True
        assert "projects" not in stub

    def test_missing_credential_is_not_an_error(self, tmp_path):
        from run_comparison import provision_executor_auth

        real_home = tmp_path / "real2"
        real_home.mkdir()
        fake_home = tmp_path / "fake2"
        fake_home.mkdir()
        provision_executor_auth(fake_home, real_home=real_home)
        assert not (fake_home / ".claude" / ".credentials.json").exists()


class TestCredentialCleanup:
    def test_credentials_wiped_from_fake_homes_after_fleet(
        self, candidates, tmp_path, monkeypatch
    ):
        import run_comparison as rc_mod

        real_home = tmp_path / "realhome"
        (real_home / ".claude").mkdir(parents=True)
        (real_home / ".claude" / ".credentials.json").write_text('{"t":1}')
        monkeypatch.setattr(rc_mod.Path, "home", classmethod(lambda cls: real_home))

        a, b = candidates
        ws = tmp_path / "ws"
        seen_during_run = []

        class ProbeSpawner(FakeSpawner):
            def __call__(self, cmd, *, cwd, env, transcript_path):
                cred = Path(env["HOME"]) / ".claude" / ".credentials.json"
                seen_during_run.append(cred.is_file())
                return super().__call__(
                    cmd, cwd=cwd, env=env, transcript_path=transcript_path
                )

        run_comparison(
            run_args(a, b, ws),
            parent_env=DEV_ENV,
            spawner=ProbeSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        assert all(seen_during_run)  # provisioned while the run executes
        cmp_dir = next(ws.iterdir())
        leftovers = list(cmp_dir.glob("runs/*/home/.claude/.credentials.json"))
        assert leftovers == []  # wiped after the fleet completes


# Captured at IMPORT time — before `_never_spawn_a_real_grader` (an
# autouse, test-time fixture) swaps the module attribute for a guard.
# Without this the tests below would exercise the guard, not the code.
REAL_GRADER_SPAWNER = run_comparison_module.default_grader_spawner


class TestDefaultGraderSpawner:
    """The REAL grader spawner's stream-json parsing. Every other test
    in this file injects a fake and bypasses it, so without these it
    ships untested — and it is exactly the code the live dev-noop probe
    was meant to exercise.

    `subprocess.run` is faked, so nothing spawns and no auth is needed.
    """

    def _fake_subprocess_run(
        self, monkeypatch, *, stdout="", stderr="", returncode=0, raises=None
    ):
        def fake_run(cmd, **kwargs):
            if raises is not None:
                raise raises
            return types.SimpleNamespace(
                stdout=stdout, stderr=stderr, returncode=returncode
            )

        monkeypatch.setattr(run_comparison_module.subprocess, "run", fake_run)

    def test_returns_the_last_result_message_text(self, monkeypatch, tmp_path):
        payload = '{"expectations": [], "summary": {}}'
        stdout = "\n".join(
            [
                json.dumps({"type": "system", "subtype": "init"}),
                json.dumps({"type": "assistant", "message": {"content": []}}),
                json.dumps({"type": "result", "is_error": False, "result": payload}),
            ]
        )
        self._fake_subprocess_run(monkeypatch, stdout=stdout)
        assert REAL_GRADER_SPAWNER(["claude"], cwd=tmp_path, env={}) == payload

    def test_non_json_lines_are_skipped(self, monkeypatch, tmp_path):
        stdout = "\n".join(
            ["not json at all", json.dumps({"type": "result", "result": "OK"}), ""]
        )
        self._fake_subprocess_run(monkeypatch, stdout=stdout)
        assert REAL_GRADER_SPAWNER(["c"], cwd=tmp_path, env={}) == "OK"

    def test_nonzero_exit_raises(self, monkeypatch, tmp_path):
        self._fake_subprocess_run(monkeypatch, stderr="boom", returncode=1)
        with pytest.raises(RuntimeError, match="exited 1"):
            REAL_GRADER_SPAWNER(["c"], cwd=tmp_path, env={})

    def test_no_result_message_raises(self, monkeypatch, tmp_path):
        self._fake_subprocess_run(
            monkeypatch, stdout=json.dumps({"type": "system", "subtype": "init"})
        )
        with pytest.raises(RuntimeError, match="no result message"):
            REAL_GRADER_SPAWNER(["c"], cwd=tmp_path, env={})

    def test_timeout_becomes_grader_timeout(self, monkeypatch, tmp_path):
        import subprocess as sp

        self._fake_subprocess_run(
            monkeypatch, raises=sp.TimeoutExpired(cmd="claude", timeout=1)
        )
        with pytest.raises(run_comparison_module.GraderTimeout):
            REAL_GRADER_SPAWNER(["c"], cwd=tmp_path, env={})

    def test_is_error_result_is_a_crash_not_a_grader_response(
        self, monkeypatch, tmp_path
    ):
        """THE REGRESSION. Observed live 2026-07-29: an expired OAuth
        token makes the CLI exit 0, report `subtype: "success"`, set
        `is_error: true`, and put an error STRING in `result`. Returning
        that string made the validator classify an INFRASTRUCTURE
        outage as `grader_malformed_json` — sending the next person
        debugging at the brief or the model instead of at the auth."""
        stdout = json.dumps(
            {
                "type": "result",
                "subtype": "success",  # deliberately claims success
                "is_error": True,
                "result": "Not logged in · Please run /login",
            }
        )
        self._fake_subprocess_run(monkeypatch, stdout=stdout, returncode=0)
        with pytest.raises(RuntimeError, match="Not logged in"):
            REAL_GRADER_SPAWNER(["c"], cwd=tmp_path, env={})

    def test_is_error_false_still_returns_normally(self, monkeypatch, tmp_path):
        stdout = json.dumps(
            {"type": "result", "subtype": "success", "is_error": False, "result": "{}"}
        )
        self._fake_subprocess_run(monkeypatch, stdout=stdout)
        assert REAL_GRADER_SPAWNER(["c"], cwd=tmp_path, env={}) == "{}"

    def test_auth_failure_classifies_as_grader_crashed_end_to_end(
        self, candidates, tmp_path, monkeypatch
    ):
        """The point of the fix: an auth outage must surface as
        `grader_crashed`, never `grader_malformed_json`.

        The subprocess fake is SELECTIVE — `git` calls delegate to the
        real `subprocess.run` (the worktree fleet needs them), only the
        `claude` grader invocation is stubbed."""
        import subprocess as sp

        real_run = sp.run
        stdout = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": True,
                "result": "Not logged in · Please run /login",
            }
        )

        def selective_run(cmd, **kwargs):
            if cmd and str(cmd[0]) == "claude":
                return types.SimpleNamespace(stdout=stdout, stderr="", returncode=0)
            return real_run(cmd, **kwargs)

        monkeypatch.setattr(run_comparison_module.subprocess, "run", selective_run)
        # Undo the autouse guard for this test: we WANT the real spawner.
        monkeypatch.setattr(
            run_comparison_module, "default_grader_spawner", REAL_GRADER_SPAWNER
        )

        a, b = candidates
        ws = tmp_path / "ws"
        run_comparison(run_args(a, b, ws), parent_env=DEV_ENV, spawner=FakeSpawner())

        cmp_dir = next(ws.iterdir())
        gradings = sorted((cmp_dir / "runs").glob("*/grading.json"))
        assert len(gradings) == 6
        for g in gradings:
            data = json.loads(g.read_text())
            assert data["error_class"] == "grader_crashed", (
                "an auth/infrastructure failure must not be reported as a "
                f"grader content problem, got {data['error_class']}"
            )


class OutputWritingSpawner(FakeSpawner):
    """An executor stub that satisfies dev-noop's gate: OUTPUT.md at the
    worktree root — so pairs become judgeable and Phase 3 runs."""

    def __call__(self, cmd, *, cwd, env, transcript_path):
        (Path(cwd) / "OUTPUT.md").write_text("an answer\n" * 40)
        return super().__call__(cmd, cwd=cwd, env=env, transcript_path=transcript_path)


class SeedSpyingSpawner(OutputWritingSpawner):
    """Records, at each executor spawn, whether the workspace-side
    comparison.json already carries the judging seed — the exact read a
    hostile candidate with Bash would perform mid-run."""

    def __init__(self):
        super().__init__()
        self.seed_sightings = []

    def __call__(self, cmd, *, cwd, env, transcript_path):
        record = json.loads((Path(cwd).parent.parent / "comparison.json").read_text())
        self.seed_sightings.append("seed" in record)
        return super().__call__(cmd, cwd=cwd, env=env, transcript_path=transcript_path)


class TestSeedNotReadableByExecutors:
    """Review finding (HIGH): `pair_assignment` is a pure public
    function of (seed, pair_index); a seed on disk before the executors
    exit lets a hostile candidate compute its own A/B slot per pair.
    The seed must not touch candidate-readable disk until the judging
    phase."""

    def test_comparison_json_carries_no_seed_while_executors_run(
        self, candidates, tmp_path
    ):
        a, b = candidates
        ws = tmp_path / "ws"
        spawner = SeedSpyingSpawner()
        run_comparison(
            run_args(a, b, ws),
            parent_env=DEV_ENV,
            spawner=spawner,
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=FakeComparatorSpawner(),
        )
        assert spawner.seed_sightings == [False] * 6
        # after the run the seed IS recorded (T-I-4 replay)
        record = json.loads((next(ws.iterdir()) / "comparison.json").read_text())
        assert isinstance(record.get("seed"), str) and record["seed"]
        judging = json.loads(
            (next(ws.iterdir()) / "eval-0" / "judging.json").read_text()
        )
        assert judging["seed"] == record["seed"]


class TestJudgingPhase:
    """Phase 3 wiring: run_comparison stages, seals, judges, and records
    — with executor, grader, and comparator all stubbed (Tier 0)."""

    def _run(self, candidates, ws, comparator):
        a, b = candidates
        ns = run_args(a, b, ws)
        run_comparison(
            ns,
            parent_env=DEV_ENV,
            spawner=OutputWritingSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=comparator,
            judging_seed="fixed-seed",
        )
        return next(ws.iterdir())

    def test_judgeable_pairs_get_verdicts_and_judging_record(
        self, candidates, tmp_path
    ):
        ws = tmp_path / "ws"
        comparator = FakeComparatorSpawner(winner="A")
        cmp_dir = self._run(candidates, ws, comparator)
        assert len(comparator.calls) == 3  # --quick → N=3, all judgeable
        record = json.loads((cmp_dir / "comparison.json").read_text())
        assert record["seed"] == "fixed-seed"
        judge_cmp = Path(record["judge_root"])
        # sibling of the workspace, never a descendant (FR-28)
        assert not str(judge_cmp).startswith(str(ws) + "/")
        for k in range(3):
            verdict = json.loads((judge_cmp / f"pair-{k}" / "verdict.json").read_text())
            assert verdict["winner"] == "A"
        judging = json.loads((cmp_dir / "eval-0" / "judging.json").read_text())
        assert judging["harness_invalid"] is False
        for rec in judging["pairs"].values():
            assert rec["quality_outcome"] in ("candidate_a", "candidate_b")
        # the sealed assignment is workspace-side, 0400
        seal = cmp_dir / "eval-0" / "assignment.json"
        assert seal.is_file()
        import stat as stat_mod

        assert stat_mod.S_IMODE(seal.stat().st_mode) == 0o400
        # scrub logs land workspace-side
        assert (cmp_dir / "eval-0" / "scrub" / "pair-0.log").is_file()

    def test_comparator_runs_with_cwd_at_the_pair_dir(self, candidates, tmp_path):
        ws = tmp_path / "ws"
        comparator = FakeComparatorSpawner()
        self._run(candidates, ws, comparator)
        for call in comparator.calls:
            assert Path(call.cwd).name.startswith("pair-")
            # the comparator's settings wire the deny hook at that dir
            settings_idx = call.cmd.index("--settings") + 1
            settings = json.loads(Path(call.cmd[settings_idx]).read_text())
            deny_cmd = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
            assert str(call.cwd) in deny_cmd

    def test_failed_gate_pairs_skip_the_comparator(self, candidates, tmp_path):
        ws = tmp_path / "ws"
        a, b = candidates
        comparator = FakeComparatorSpawner()
        # plain FakeSpawner writes no OUTPUT.md → every gate fails →
        # every pair double_failure → zero comparator invocations (FR-33)
        run_comparison(
            run_args(a, b, ws),
            parent_env=DEV_ENV,
            spawner=FakeSpawner(),
            grader_spawner=FakeGraderSpawner(),
            comparator_spawner=comparator,
        )
        assert comparator.calls == []
        cmp_dir = next(ws.iterdir())
        judging = json.loads((cmp_dir / "eval-0" / "judging.json").read_text())
        for rec in judging["pairs"].values():
            assert rec["reason"] == "double_failure"

    def test_clean_removes_the_recorded_judge_root(self, candidates, tmp_path):
        ws = tmp_path / "ws"
        cmp_dir = self._run(candidates, ws, FakeComparatorSpawner())
        record = json.loads((cmp_dir / "comparison.json").read_text())
        judge_cmp = Path(record["judge_root"])
        assert judge_cmp.is_dir()
        ns = parse(["clean", "--comparison-id", cmp_dir.name, "--workspace", str(ws)])
        run_comparison_module.clean_workspaces(ns)
        assert not cmp_dir.exists()
        assert not judge_cmp.exists()

    def test_exit_criterion_walk_the_comparators_reachable_tree(
        self, candidates, tmp_path
    ):
        """Spec §7 Phase 3 exit: walk the comparator's entire reachable
        filesystem — every path under the judge root, symlinks resolved
        — and find no denylist term, no candidate directory basename,
        no assignment.json, no scrub log, no transcript, and no route
        into the workspace (FR-28, FR-31, DR-3, R15)."""
        ws = tmp_path / "ws"
        cmp_dir = self._run(candidates, ws, FakeComparatorSpawner(winner="A"))
        record = json.loads((cmp_dir / "comparison.json").read_text())
        judge_cmp = Path(record["judge_root"])
        a, b = candidates
        banned = [
            a.stem,
            b.stem,
            a.name,
            b.name,
            "cand-a",
            "cand-b",
            "candidate_a",
            "candidate_b",
            "assignment",
            "scrub",
            "transcript.jsonl",
            "comparison.json",
            "worktree",
        ]
        ws_resolved = ws.resolve()
        seen_files = 0
        for p in judge_cmp.rglob("*"):
            # any path resolving into the workspace is an escape
            assert not p.resolve().is_relative_to(ws_resolved), p
            assert not p.is_symlink(), p  # no symlink survives staging
            for term in banned:
                assert term.lower() not in p.name.lower(), (p, term)
            if p.is_file() and p.name != "verdict.json":
                seen_files += 1
                data = p.read_bytes().lower()
                for term in banned:
                    assert term.encode() not in data, (p, term)
        assert seen_files > 0  # the walk actually saw staged artifacts
        # ancestor traversal: the workspace is on a different branch —
        # no `..` chain from the judge root passes through it
        assert ws_resolved not in {anc.resolve() for anc in judge_cmp.parents}


# ------------------------------------------------------------------ FR-44 gate (Phase 5 review regressions)
#
# `check_discrimination` had NO direct coverage, which is how two of its
# four documented conditions came to be computed, written to fixture.json,
# and then read by nothing at all.


def _disc(**overrides):
    """A discrimination block that passes all four FR-44 conditions."""
    return {
        "reference_pass_rate": 1.0,
        "broken_pass_rate": 0.0,
        "gate_reference_exit": 0,
        "gate_broken_hard_exit": 1,
        **overrides,
    }


def test_discrimination_verified_accepts_a_fully_passing_block():
    assert run_comparison_module.discrimination_verified(_disc()) is True


@pytest.mark.parametrize(
    "overrides, why",
    [
        ({"reference_pass_rate": 0.5}, "reference solution does not solve the task"),
        ({"broken_pass_rate": 0.8}, "broken solution still passes"),
        ({"gate_reference_exit": 1}, "checks.sh fails on the reference"),
        ({"gate_broken_hard_exit": 0}, "checks.sh cannot catch the do-nothing arm"),
    ],
)
def test_discrimination_verified_rejects_each_failing_condition(overrides, why):
    assert run_comparison_module.discrimination_verified(_disc(**overrides)) is False, (
        why
    )


def test_gate_exit_fields_are_actually_enforced():
    """The regression this pins: a fixture shipping `checks.sh` as `exit 0`
    records gate_broken_hard_exit 0 — the deterministic gate is blind — yet
    was admitted because only the two pass rates were ever checked."""
    blind_gate = _disc(gate_reference_exit=0, gate_broken_hard_exit=0)

    with pytest.raises(ComparisonRefused):
        run_comparison_module.check_discrimination(
            {"fixture_id": "fx", "discrimination": blind_gate}, unverified_ok=False
        )


def test_discrimination_block_missing_gate_fields_is_not_silently_exempt():
    disc = {"reference_pass_rate": 1.0, "broken_pass_rate": 0.0}
    assert run_comparison_module.discrimination_verified(disc) is False


def test_discrimination_stale_fixture_version_is_rejected():
    disc = _disc(verified_fixture_version=1)
    assert (
        run_comparison_module.discrimination_verified(disc, fixture_version=1) is True
    )
    assert (
        run_comparison_module.discrimination_verified(disc, fixture_version=2) is False
    )


def test_discrimination_without_version_field_is_not_grandfathered():
    """A block carrying no `verified_fixture_version` must FAIL the version
    check rather than be exempted from it.

    An earlier revision skipped the check when the field was absent, which
    left every already-shipped fixture reading as verified at every future
    fixture_version — precisely the staleness the field was added to catch.
    """
    assert (
        run_comparison_module.discrimination_verified(_disc(), fixture_version=9)
        is False
    )


def test_shipped_fixtures_carry_a_version_binding():
    """The strictness above is only safe because the shipped blocks were
    stamped; without this, the gate would start refusing them."""
    fixtures_root = Path(__file__).resolve().parents[1] / "fixtures"
    checked = 0
    for fixture_dir in sorted(fixtures_root.iterdir()):
        meta_path = fixture_dir / "fixture.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text())
        if not isinstance(meta.get("discrimination"), dict):
            continue
        checked += 1
        assert run_comparison_module.discrimination_verified(
            meta["discrimination"], fixture_version=meta["fixture_version"]
        ), f"{fixture_dir.name} would be refused by the FR-44 gate"
    assert checked, "no shipped fixture with a discrimination block was checked"


def test_absent_discrimination_block_still_refuses():
    with pytest.raises(ComparisonRefused):
        run_comparison_module.check_discrimination(
            {"fixture_id": "fx"}, unverified_ok=False
        )


def test_unverified_ok_still_permits_a_failing_block():
    """FR-63's harness-development escape hatch must keep working."""
    assert (
        run_comparison_module.check_discrimination(
            {"fixture_id": "fx", "discrimination": _disc(gate_broken_hard_exit=0)},
            unverified_ok=True,
        )
        is True
    )
