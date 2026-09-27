#!/usr/bin/env python3
"""versus CLI — FR-59 grammar: exactly four subcommands in five invocation
forms; no bare invocation; every flag is owned by exactly one subcommand
(--workspace excepted, accepted by all four). FR-61 clean/gc. FR-63 dev
gating for --unverified-fixture. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import calibrate  # noqa: E402


class CliError(Exception):
    """Grammar or validation error; main() prints it and exits non-zero."""


class _Parser(argparse.ArgumentParser):
    """argparse that raises CliError instead of calling sys.exit()."""

    def error(self, message):  # noqa: A003
        raise CliError(message)


def _dev_gate_open(env: dict, plugin_version: str) -> bool:
    """FR-63: both gates or the flag does not exist at all."""
    return env.get("VERSUS_DEV") == "1" and "-dev" in plugin_version


def _plugin_version() -> str:
    manifest = Path(__file__).resolve().parents[2] / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(manifest.read_text()).get("version", "")
    except (OSError, ValueError):
        return ""


def build_parser(*, dev_gate: bool) -> _Parser:
    parser = _Parser(prog="versus", allow_abbrev=False)
    sub = parser.add_subparsers(dest="subcommand")

    def add_workspace(p):
        p.add_argument("--workspace")

    run = sub.add_parser("run", allow_abbrev=False)
    run.add_argument("candidates", nargs="+")
    run.add_argument("--fixture", required=True)
    run.add_argument("--runs", type=int, default=None)
    run.add_argument("--quick", action="store_true")
    run.add_argument("--parallel", type=int, default=3)
    run.add_argument("--model")
    run.add_argument("--effort")
    run.add_argument("--isolation", choices=["worktree", "clone"], default="worktree")
    run.add_argument("--double-judge", action="store_true")
    run.add_argument(
        "--keep-worktrees",
        choices=["on-failure", "always", "never"],
        default="on-failure",
    )
    run.add_argument("--max-budget-usd", type=float, default=None)
    run.add_argument("--respect-candidate-model", action="store_true")
    run.add_argument("--self-calibrate", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    if dev_gate:
        run.add_argument("--unverified-fixture", action="store_true")
    add_workspace(run)

    verify = sub.add_parser("verify-fixture", allow_abbrev=False)
    verify.add_argument("fixture")
    verify.add_argument("--fixture-dir")
    add_workspace(verify)

    clean = sub.add_parser("clean", aliases=["gc"], allow_abbrev=False)
    clean.add_argument("--comparison-id")
    clean.add_argument("--all", action="store_true", dest="clean_all")
    clean.add_argument("--dry-run", action="store_true")
    add_workspace(clean)

    report = sub.add_parser("report", allow_abbrev=False)
    report.add_argument("comparison_id")
    report.add_argument("--format", choices=["json", "md", "both"], default="both")
    add_workspace(report)

    return parser


def parse_and_validate(
    argv, *, env: dict | None = None, plugin_version: str | None = None
):
    """Parse argv against the FR-59 grammar and run launch-time validation.

    Raises CliError before any worktree or subprocess exists (T-U-25:
    "exit non-zero with zero worktrees created")."""
    env = dict(env) if env is not None else dict(__import__("os").environ)
    if plugin_version is None:
        plugin_version = _plugin_version()

    dev_gate = _dev_gate_open(env, plugin_version)
    parser = build_parser(dev_gate=dev_gate)
    ns = parser.parse_args(list(argv))

    if not ns.subcommand:
        raise CliError(
            "no bare invocation form exists: use one of "
            "run | verify-fixture | clean | report (FR-59)"
        )
    if ns.subcommand == "gc":
        ns.subcommand = "clean"

    if ns.subcommand == "run":
        _validate_run(ns)
    if ns.subcommand == "clean":
        ns.list_only = not (ns.comparison_id or ns.clean_all)

    if getattr(ns, "unverified_fixture", False):
        print(
            "*** UNVERIFIED FIXTURE: this comparison runs against a fixture "
            "with no passing discrimination block; the verdict is capped at "
            "INCONCLUSIVE (FR-63) ***",
            file=sys.stderr,
        )
    else:
        ns.unverified_fixture = getattr(ns, "unverified_fixture", False)

    return ns


def _validate_run(ns) -> None:
    if ns.self_calibrate:
        if len(ns.candidates) != 1:
            raise CliError(
                "run --self-calibrate takes exactly one positional "
                "candidate; supplying two is an error, not a synonym "
                "(FR-59)"
            )
        if ns.runs is None:
            ns.runs = calibrate.CALIBRATION_FLOOR
        try:
            calibrate.validate_runs(ns.runs)
        except calibrate.CalibrationFloorError as e:
            raise CliError(str(e)) from e
    else:
        if len(ns.candidates) != 2:
            raise CliError(
                f"run takes exactly two candidates, got {len(ns.candidates)} (FR-59)"
            )
        if ns.runs is None:
            ns.runs = 3 if ns.quick else 5
        if ns.runs < 3:
            raise CliError(f"--runs must be >= 3, got {ns.runs} (FR-13)")


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    try:
        ns = parse_and_validate(argv)
    except CliError as e:
        print(f"versus: error: {e}", file=sys.stderr)
        return 2

    if ns.subcommand == "run":
        if ns.self_calibrate:
            record = calibrate.run_calibration(
                candidate=ns.candidates[0],
                fixture=ns.fixture,
                runs=ns.runs,
                workspace=ns.workspace,
                parallel=ns.parallel,
                model=ns.model,
                effort=ns.effort,
                unverified_fixture=ns.unverified_fixture,
                dry_run=ns.dry_run,
                # Forwarded, not hardcoded: the `run` subparser accepts all
                # five, so dropping them here made them parse and silently
                # do nothing — worst of all for `--max-budget-usd` on the
                # most expensive path the harness has.
                isolation=ns.isolation,
                double_judge=ns.double_judge,
                keep_worktrees=ns.keep_worktrees,
                max_budget_usd=ns.max_budget_usd,
                respect_candidate_model=ns.respect_candidate_model,
            )
            if record is None:  # FR-60: --dry-run spawned nothing to evaluate
                return 0
            print(json.dumps(record, indent=2, sort_keys=True))
            return 0 if record["result"] == "pass" else 1

        from run_comparison import run_comparison  # Phase E wiring

        return run_comparison(ns)
    if ns.subcommand == "verify-fixture":
        from run_comparison import (
            ComparisonRefused,
            discrimination_verified,
            resolve_fixture_dir,
        )
        from verify_fixture import DiscriminationError, verify_fixture
        from prepare_fixture import FixtureError

        if ns.fixture_dir:
            fixture_dir = Path(ns.fixture_dir)
        else:
            # Reuse the canonical resolver rather than re-deriving the
            # paths: the hand-rolled copy reached `dev/fixtures/`
            # unconditionally, bypassing the FR-63 VERSUS_DEV gate that
            # every other fixture access honours, and it rejected the
            # directory-path specifier that `run --fixture` accepts.
            dev = os.environ.get("VERSUS_DEV") == "1"
            try:
                fixture_dir = resolve_fixture_dir(ns.fixture, dev=dev)
            except ComparisonRefused:
                fixture_dir = None
        if fixture_dir is None or not fixture_dir.is_dir():
            print(f"versus: error: fixture not found: {ns.fixture}", file=sys.stderr)
            return 2
        try:
            discrimination = verify_fixture(fixture_dir)
        except (FixtureError, DiscriminationError) as e:
            print(f"verify-fixture error: {e}", file=sys.stderr)
            return 1
        print(json.dumps(discrimination, indent=2, sort_keys=True))
        # Exit non-zero when the measured block would not satisfy the FR-44
        # gate. Returning 0 unconditionally made `verify-fixture X && publish`
        # publish a non-discriminating fixture, deferring the failure to a
        # ComparisonRefused much later.
        if not discrimination_verified(discrimination):
            print(
                "verify-fixture: fixture does not meet the FR-44 discrimination "
                "bar; it cannot support a comparison",
                file=sys.stderr,
            )
            return 1
        return 0
    if ns.subcommand == "clean":
        from run_comparison import clean_workspaces  # Phase E wiring

        return clean_workspaces(ns)
    if ns.subcommand == "report":
        from report import generate  # Phase 4 wiring

        workspace = Path(ns.workspace) if ns.workspace else Path.home() / ".versus"
        cmp_dir = workspace / ns.comparison_id
        if not cmp_dir.is_dir():
            print(f"versus: error: no comparison at {cmp_dir}", file=sys.stderr)
            return 2
        # Standalone regeneration has no memory of the original run's env,
        # so credential VALUES are unavailable here — only the pattern-based
        # sweep in redact.py runs (see report.generate's docstring). The
        # value-based sweep is guaranteed once, at `run` time.
        report = generate(
            cmp_dir,
            eval_name=json.loads((cmp_dir / "comparison.json").read_text())[
                "fixture_id"
            ],
        )
        if ns.format in ("json", "both"):
            print(json.dumps(report, indent=2, sort_keys=True))
        if ns.format in ("md", "both"):
            print((cmp_dir / "report.md").read_text())
        return 0
    raise AssertionError(f"unreachable subcommand: {ns.subcommand}")


if __name__ == "__main__":
    raise SystemExit(main())
