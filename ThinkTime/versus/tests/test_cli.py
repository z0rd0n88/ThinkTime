"""Phase B tests: cli.py + calibrate.py — FR-59, FR-61, FR-63, FR-13 floor
(T-U-25).

Tier 0: in-process parse/validate, no subprocess spawn, no worktrees.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import calibrate  # noqa: E402
from calibrate import CalibrationFloorError  # noqa: E402
from cli import CliError, parse_and_validate  # noqa: E402


def parse(argv, env=None, plugin_version="0.0.1"):
    return parse_and_validate(argv, env=env or {}, plugin_version=plugin_version)


class TestGrammar:
    def test_bare_invocation_is_an_error(self):
        with pytest.raises(CliError):
            parse([])

    def test_unknown_subcommand_is_an_error(self):
        with pytest.raises(CliError):
            parse(["frobnicate"])

    def test_run_two_candidates_accepted(self):
        ns = parse(["run", "a", "b", "--fixture", "f"])
        assert ns.subcommand == "run"
        assert ns.candidates == ["a", "b"]

    def test_run_requires_fixture(self):
        with pytest.raises(CliError):
            parse(["run", "a", "b"])

    def test_verify_fixture_form(self):
        ns = parse(["verify-fixture", "f"])
        assert ns.subcommand == "verify-fixture"

    def test_report_form(self):
        ns = parse(["report", "cmp-1", "--format", "json"])
        assert ns.subcommand == "report"

    def test_clean_form(self):
        ns = parse(["clean"])
        assert ns.subcommand == "clean"

    def test_gc_is_alias_of_clean(self):
        ns = parse(["gc"])
        assert ns.subcommand == "clean"

    def test_clean_without_target_lists_only(self):
        # FR-61: neither --comparison-id nor --all → list and exit 0,
        # removing nothing.
        ns = parse(["clean"])
        assert ns.list_only is True

    def test_clean_with_all_not_list_only(self):
        ns = parse(["clean", "--all"])
        assert ns.list_only is False


class TestFlagOwnership:
    def test_run_flag_on_verify_fixture_is_error_not_ignored(self):
        with pytest.raises(CliError):
            parse(["verify-fixture", "f", "--runs", "5"])

    def test_run_flag_on_report_is_error(self):
        with pytest.raises(CliError):
            parse(["report", "cmp-1", "--parallel", "2"])

    def test_fixture_flag_on_clean_is_error(self):
        with pytest.raises(CliError):
            parse(["clean", "--fixture", "f"])

    def test_workspace_accepted_by_every_subcommand(self):
        for argv in (
            ["run", "a", "b", "--fixture", "f"],
            ["verify-fixture", "f"],
            ["clean"],
            ["report", "cmp-1"],
        ):
            ns = parse(argv + ["--workspace", "/tmp/w"])
            assert ns.workspace == "/tmp/w"


class TestSelfCalibrate:
    def test_self_calibrate_single_candidate_accepted(self):
        ns = parse(["run", "--self-calibrate", "a", "--fixture", "f", "--runs", "9"])
        assert ns.self_calibrate is True
        assert ns.candidates == ["a"]

    def test_self_calibrate_two_candidates_is_error_not_synonym(self):
        with pytest.raises(CliError):
            parse(["run", "--self-calibrate", "a", "b", "--fixture", "f"])

    def test_self_calibrate_default_runs_is_9(self):
        ns = parse(["run", "--self-calibrate", "a", "--fixture", "f"])
        assert ns.runs == 9

    def test_calibration_floor_names_sm1_at_cli(self):
        with pytest.raises(CliError) as exc:
            parse(["run", "--self-calibrate", "a", "--fixture", "f", "--runs", "7"])
        assert "SM1" in str(exc.value)

    def test_runs_9_and_11_accepted_for_calibration(self):
        for n in ("9", "11"):
            ns = parse(["run", "--self-calibrate", "a", "--fixture", "f", "--runs", n])
            assert ns.runs == int(n)

    def test_runs_7_accepted_without_self_calibrate(self):
        ns = parse(["run", "a", "b", "--fixture", "f", "--runs", "7"])
        assert ns.runs == 7

    def test_runs_below_3_is_error_for_comparison(self):
        with pytest.raises(CliError):
            parse(["run", "a", "b", "--fixture", "f", "--runs", "2"])

    def test_default_runs_is_5_quick_is_3(self):
        assert parse(["run", "a", "b", "--fixture", "f"]).runs == 5
        assert parse(["run", "a", "b", "--fixture", "f", "--quick"]).runs == 3


class TestCalibrateModuleFloor:
    """T-U-25: the N >= 9 floor asserted directly against calibrate.py,
    bypassing cli.py entirely — FR-13 places it at the module boundary."""

    def test_module_refuses_n_below_9_naming_sm1(self):
        with pytest.raises(CalibrationFloorError) as exc:
            calibrate.run_calibration(candidate="a", fixture="f", runs=7)
        assert "SM1" in str(exc.value)

    def test_module_refuses_n_5_too(self):
        with pytest.raises(CalibrationFloorError):
            calibrate.run_calibration(candidate="a", fixture="f", runs=5)

    def test_module_accepts_n_9(self):
        # Calibration proper is built (Phase 5): the floor check passes
        # and execution proceeds to fixture resolution, which fails for
        # a *different*, explicit reason — an unknown fixture id, not
        # the floor.
        from run_comparison import ComparisonRefused

        with pytest.raises(ComparisonRefused):
            calibrate.run_calibration(candidate="a", fixture="f", runs=9)


class TestDevGating:
    """FR-63: --unverified-fixture accepted only when VERSUS_DEV=1 AND the
    plugin version carries -dev; otherwise an unrecognized-argument error."""

    ARGV = ["run", "a", "b", "--fixture", "dev-noop", "--unverified-fixture"]

    def test_rejected_in_released_build(self):
        with pytest.raises(CliError):
            parse(self.ARGV, env={}, plugin_version="1.2.0")

    def test_rejected_with_env_but_release_version(self):
        with pytest.raises(CliError):
            parse(self.ARGV, env={"VERSUS_DEV": "1"}, plugin_version="1.2.0")

    def test_rejected_with_dev_version_but_no_env(self):
        with pytest.raises(CliError):
            parse(self.ARGV, env={}, plugin_version="1.2.0-dev")

    def test_accepted_with_both_gates(self):
        ns = parse(self.ARGV, env={"VERSUS_DEV": "1"}, plugin_version="1.2.0-dev")
        assert ns.unverified_fixture is True

    def test_banner_printed_when_accepted(self, capsys):
        parse(self.ARGV, env={"VERSUS_DEV": "1"}, plugin_version="1.2.0-dev")
        out = capsys.readouterr()
        assert "unverified" in (out.out + out.err).lower()


class TestMainSelfCalibrateDispatch:
    """`run --self-calibrate` must route through `calibrate.run_calibration`
    (which evaluates SM1 and writes the calibration record), never
    directly through `run_comparison.run_comparison` — a regression
    caught live 2026-08-04: the original wiring called `run_comparison`
    unconditionally, so a real `--self-calibrate` run produced a report
    but silently never wrote a calibration record at all."""

    def test_self_calibrate_calls_run_calibration_not_run_comparison(
        self, monkeypatch, capsys
    ):
        import cli
        import run_comparison

        calls = []
        monkeypatch.setattr(
            cli.calibrate,
            "run_calibration",
            lambda **kw: (calls.append(kw), {"result": "pass"})[1],
        )

        def canary(*a, **kw):
            raise AssertionError(
                "run_comparison.run_comparison must not be called directly "
                "for --self-calibrate"
            )

        monkeypatch.setattr(run_comparison, "run_comparison", canary)

        rc = cli.main(["run", "--self-calibrate", "cand", "--fixture", "f"])

        assert rc == 0
        assert len(calls) == 1
        assert calls[0]["candidate"] == "cand"
        assert calls[0]["fixture"] == "f"
        assert calls[0]["runs"] == calibrate.CALIBRATION_FLOOR
        assert "pass" in capsys.readouterr().out

    def test_self_calibrate_nonzero_exit_when_not_pass(self, monkeypatch):
        import cli

        monkeypatch.setattr(
            cli.calibrate, "run_calibration", lambda **kw: {"result": "fail"}
        )
        rc = cli.main(["run", "--self-calibrate", "cand", "--fixture", "f"])
        assert rc == 1

    def test_self_calibrate_dry_run_forwards_flag_and_exits_zero(self, monkeypatch):
        import cli

        calls = []
        monkeypatch.setattr(
            cli.calibrate,
            "run_calibration",
            lambda **kw: (calls.append(kw), None)[1],
        )
        rc = cli.main(
            ["run", "--self-calibrate", "cand", "--fixture", "f", "--dry-run"]
        )
        assert rc == 0
        assert calls[0]["dry_run"] is True
