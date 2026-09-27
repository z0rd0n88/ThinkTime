#!/usr/bin/env python3
"""`versus-compare verify-fixture` — the FR-44 discrimination gate.

Applies `reference/`, `broken/`, and `broken_hard/` (FR-41) to fresh
worktrees cloned straight from the fixture's own bundle, runs the
fixture's deterministic `checks` (FR-27) against each, and grades
`reference/` and `broken/` against `assertions.json` — grading
`broken_hard/` would grade an absent output; its assertion is the gate
exit alone (FR-44). Writes `fixture.json`'s `discrimination` block:
`{reference_pass_rate, broken_pass_rate, gate_reference_exit,
gate_broken_hard_exit, verified_at}`, and bumps `last_verified`.

This module only COMPUTES and RECORDS the block. The refusal-to-run
gate that reads it (`reference_pass_rate < 0.9`, `broken_pass_rate >
0.2`, non-zero reference gate exit, zero broken_hard gate exit) already
lives in `run_comparison.check_discrimination` — duplicating it here
would be a second copy of the same threshold to drift out of sync.

Stdlib only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grading import (  # noqa: E402
    GraderTimeout,
    TaskOutcome,
    build_grader_agents_payload,
    build_grader_task_message,
    compute_task_outcome,
    grade_with_retries,
    run_deterministic_checks,
)
from prepare_fixture import FixtureError, load_fixture, prepare_worktree  # noqa: E402
from run_candidates import build_child_env, build_run_command  # noqa: E402

DEFAULT_GRADER_MODEL = "haiku"
DEFAULT_GRADER_BUDGET_USD = 0.5
GRADER_TIMEOUT_SECONDS = 300
GRADER_BRIEF_PATH = Path(__file__).resolve().parents[1] / "briefs" / "vc-grader.md"
SOLUTIONS = ("reference", "broken", "broken_hard")
GRADED_SOLUTIONS = ("reference", "broken")

NO_TRANSCRIPT_NOTE = (
    "No candidate transcript exists for this grading pass: verify-fixture "
    "applies the fixture's own solution patch directly to a fresh worktree "
    "rather than executing a candidate (FR-44). Grade outputs_dir alone; "
    "there is nothing else to read."
)


class DiscriminationError(Exception):
    """The discrimination test could not complete (patch/grader failure)."""


def _apply_solution(fixture_dir: Path, target: Path, solution: str) -> None:
    """Apply `<solution>/solution.patch` to an already-cloned `target`.

    An empty patch is valid for `broken_hard/` ONLY (FR-41: it is often an
    empty diff, since it must produce no output at all). For `reference/`
    and `broken/` a missing or empty patch is an error, not a no-op: the
    arm would silently grade the pristine bundle, and a `broken` arm that
    was never actually broken still scores ~0.0, so the fixture would be
    certified as discriminating without the broken variant ever existing.
    """
    patch_path = Path(fixture_dir) / solution / "solution.patch"
    missing = not patch_path.is_file() or patch_path.stat().st_size == 0
    if missing:
        if solution == "broken_hard":
            return
        raise DiscriminationError(
            f"{solution}/solution.patch is missing or empty; only "
            "broken_hard/ may be an empty diff (FR-41). Refusing to "
            f"certify a fixture whose {solution} arm was never applied."
        )
    res = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(patch_path)],
        cwd=target,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise DiscriminationError(
            f"{solution}/solution.patch failed to apply to {target}: "
            f"{res.stderr.strip()}"
        )


def _gate_exit(results: list) -> int:
    """Collapse a fixture's (possibly multi-check) gate result to the
    single exit code FR-42's `gate_reference_exit`/`gate_broken_hard_exit`
    record: 0 iff every declared check passed, 1 otherwise."""
    return 0 if compute_task_outcome(results) is TaskOutcome.SUCCESS else 1


def default_grader_spawner(cmd, *, cwd, env):
    """Real grader spawn — same headless transport `run_comparison` uses
    for its own grader/comparator calls (parse `stream-json` for the
    final `result` message's text)."""
    from run_comparison import _headless_result_text

    return _headless_result_text(
        cmd,
        cwd=cwd,
        env=env,
        timeout_seconds=GRADER_TIMEOUT_SECONDS,
        timeout_exc=GraderTimeout,
        label="grader",
    )


def _grade_solution(
    *,
    fixture_dir: Path,
    worktree: Path,
    assertions: list[dict],
    task_outcome: TaskOutcome,
    grader_spawner,
    env: dict,
) -> dict:
    brief_text = GRADER_BRIEF_PATH.read_text()
    transcript_path = worktree / ".vc-no-transcript.txt"
    transcript_path.write_text(NO_TRANSCRIPT_NOTE)
    assertion_ids = [a["id"] for a in assertions]
    settings_path = worktree / ".vc-grader-settings.json"
    settings_path.write_text(json.dumps({"hooks": {}}, indent=2) + "\n")

    def invoke():
        cmd = build_run_command(
            prompt=build_grader_task_message(
                assertions=assertions,
                task_outcome=task_outcome,
                transcript_path=transcript_path,
                outputs_dir=worktree,
            ),
            model=DEFAULT_GRADER_MODEL,
            effort=None,
            settings_path=settings_path,
            session_id=str(uuid.uuid4()),
            max_budget_usd=DEFAULT_GRADER_BUDGET_USD,
            agents_json=build_grader_agents_payload(brief_text),
            agent_name="vc-grader",
        )
        return grader_spawner(cmd, cwd=worktree, env=env)

    outcome = grade_with_retries(
        invoke, expected_task_outcome=task_outcome, assertion_ids=assertion_ids
    )
    if not outcome.ok:
        raise DiscriminationError(
            f"grading {worktree.name} failed: {outcome.error_class}: {outcome.reason}"
        )
    return outcome.grading


def verify_fixture(
    fixture_dir: Path,
    *,
    work_dir: Path | None = None,
    grader_spawner=None,
    env: dict | None = None,
    provision_auth=None,
) -> dict:
    """FR-44. Applies the three solutions, runs the gate, grades
    `reference/` and `broken/`, writes the `discrimination` block into
    `fixture.json`, and returns it.

    `grader_spawner(cmd, *, cwd, env) -> str` is injected so this is
    Tier-0 testable without a live model call; `default_grader_spawner`
    is the production default. `provision_auth(fake_home)` likewise
    defaults to the real credential-copy used elsewhere in the harness.
    """
    # Resolved to absolute up front: `_apply_solution` runs `git apply`
    # with `cwd=target` (a worktree elsewhere), so a relative fixture_dir
    # would silently fail to locate `<solution>/solution.patch` (observed
    # 2026-08-04 against the real fixtures).
    fixture_dir = Path(fixture_dir).resolve()
    meta = load_fixture(fixture_dir)
    assertions_path = fixture_dir / "assertions.json"
    assertions = (
        json.loads(assertions_path.read_text()).get("assertions", [])
        if assertions_path.is_file()
        else []
    )
    if not assertions:
        # Grading an empty assertion set is vacuous: the id-match check is
        # trivially satisfied and whatever pass_rate comes back can still
        # clear the FR-44 thresholds, certifying a fixture that asserts
        # nothing as "discriminating".
        raise DiscriminationError(
            f"{fixture_dir}/assertions.json is missing or defines no "
            "assertions; a fixture with nothing to assert cannot "
            "discriminate (FR-44)"
        )
    checks = meta["checks"]
    grader_spawner = grader_spawner or default_grader_spawner

    owns_work_dir = work_dir is None
    # Scratch goes under the workspace root, NEVER inside fixture_dir.
    # `provision_executor_auth` copies the developer's real
    # ~/.claude/.credentials.json into <work_dir>/home, and fixture
    # directories are tracked git content not covered by any .gitignore —
    # so the previous default (`fixture_dir/.vc-verify-<hex>`) put live
    # OAuth credentials one abnormal exit away from being staged and
    # pushed. `run_comparison` already keeps its fake homes under
    # ~/.versus for this reason; this is the same discipline.
    work_dir = (
        Path(work_dir)
        if work_dir
        else Path.home() / ".versus" / f"vc-verify-{uuid.uuid4().hex[:8]}"
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        fake_home = work_dir / "home"
        fake_home.mkdir(exist_ok=True)
        if provision_auth is not None:
            provision_auth(fake_home)
        else:
            from run_comparison import provision_executor_auth

            provision_executor_auth(fake_home)
        child_env = build_child_env(env or dict(os.environ), fake_home=fake_home)

        gate_results = {}
        worktrees = {}
        for solution in SOLUTIONS:
            wt = work_dir / solution
            try:
                prepare_worktree(fixture_dir, wt)
            except FixtureError as e:
                raise DiscriminationError(str(e)) from e
            _apply_solution(fixture_dir, wt, solution)
            worktrees[solution] = wt
            gate_results[solution] = run_deterministic_checks(fixture_dir, wt, checks)

        gate_reference_exit = _gate_exit(gate_results["reference"])
        gate_broken_hard_exit = _gate_exit(gate_results["broken_hard"])

        pass_rates = {}
        for solution in GRADED_SOLUTIONS:
            task_outcome = compute_task_outcome(gate_results[solution])
            grading = _grade_solution(
                fixture_dir=fixture_dir,
                worktree=worktrees[solution],
                assertions=assertions,
                task_outcome=task_outcome,
                grader_spawner=grader_spawner,
                env=child_env,
            )
            pass_rates[solution] = grading["summary"]["pass_rate"]
    finally:
        # Unlink the copied credential explicitly BEFORE the best-effort
        # rmtree, and do it whether or not we own work_dir. `rmtree(...,
        # ignore_errors=True)` swallows EBUSY/EPERM, and a caller-supplied
        # work_dir was never cleaned at all — either path could leave a
        # live token on disk. This mirrors run_comparison's per-run
        # `cred.unlink(missing_ok=True)` discipline.
        try:
            (work_dir / "home" / ".claude" / ".credentials.json").unlink(
                missing_ok=True
            )
        except OSError as e:
            print(
                f"versus: warning: could not remove copied credential under "
                f"{work_dir}: {e}",
                file=sys.stderr,
            )
        if owns_work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)

    discrimination = {
        "reference_pass_rate": pass_rates["reference"],
        "broken_pass_rate": pass_rates["broken"],
        "gate_reference_exit": gate_reference_exit,
        "gate_broken_hard_exit": gate_broken_hard_exit,
        # Bind the attestation to the version it measured, mirroring
        # calibration's `calibrated_fixture_version`. Without it an edit to
        # checks.sh or the patches left a passing block valid forever, and
        # nothing could tell that the fixture had changed underneath it.
        "verified_fixture_version": meta["fixture_version"],
        "verified_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    meta["discrimination"] = discrimination
    meta["last_verified"] = discrimination["verified_at"]
    # Atomic replace: fixture.json pins `bundle_sha256` and `head_sha`, so a
    # truncate-then-write interrupted by Ctrl-C, OOM, or a full disk left the
    # fixture permanently unloadable with no copy to recover from.
    tmp = fixture_dir / "fixture.json.tmp"
    try:
        tmp.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
        tmp.replace(fixture_dir / "fixture.json")
    except BaseException:
        # The temp file lives inside the tracked fixture directory, so a
        # failed write must not leave a stray behind for a later `git add`
        # to pick up. BaseException so a KeyboardInterrupt — the very
        # interruption this atomic write exists to survive — also cleans up.
        tmp.unlink(missing_ok=True)
        raise
    return discrimination


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: verify_fixture.py <fixture-dir>", file=sys.stderr)
        return 2
    try:
        discrimination = verify_fixture(Path(argv[0]))
    except (FixtureError, DiscriminationError) as e:
        print(f"verify-fixture error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(discrimination, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
