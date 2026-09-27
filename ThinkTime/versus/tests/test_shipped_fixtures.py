"""Mechanics-only regression coverage for the two shipped fixtures (FR-41):
bundle loads, each solution applies cleanly, and the deterministic gate
lands where FR-44 expects — reference passes, broken passes (wrong
content, still produces output), broken_hard fails. No grader, no live
model call; that's verify_fixture's job (FR-44) and is run live
separately.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from prepare_fixture import load_fixture, prepare_worktree  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
SHIPPED_FIXTURE_IDS = ["readonly-reviewer-diff-audit", "spec-from-vague-issue"]


def _apply(patch_path: Path, target: Path) -> None:
    if patch_path.stat().st_size == 0:
        return
    res = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(patch_path)],
        cwd=target,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr


@pytest.mark.parametrize("fixture_id", SHIPPED_FIXTURE_IDS)
def test_fixture_loads(fixture_id, tmp_path):
    fx = FIXTURES_DIR / fixture_id
    meta = load_fixture(fx)
    assert meta["fixture_id"] == fixture_id
    assert meta["checks"] == ["checks.sh"]


@pytest.mark.parametrize("fixture_id", SHIPPED_FIXTURE_IDS)
@pytest.mark.parametrize(
    "solution,expect_gate_pass",
    [("reference", True), ("broken", True), ("broken_hard", False)],
)
def test_fixture_solution_gate(fixture_id, solution, expect_gate_pass, tmp_path):
    fx = FIXTURES_DIR / fixture_id
    target = tmp_path / solution
    prepare_worktree(fx, target)
    _apply(fx / solution / "solution.patch", target)
    rc = subprocess.run(["bash", str(fx / "checks.sh"), str(target)]).returncode
    assert (rc == 0) is expect_gate_pass


@pytest.mark.parametrize("fixture_id", SHIPPED_FIXTURE_IDS)
def test_fixture_has_no_discrimination_block_yet(fixture_id):
    """Sanity guard for the live-verification step this test file does
    NOT perform: until `verify-fixture` runs, these fixtures must still
    require `--unverified-fixture` (FR-44) — a `discrimination` block
    appearing here without a corresponding live run would be a silent,
    unverified claim."""
    meta = load_fixture(FIXTURES_DIR / fixture_id)
    if "discrimination" in meta:
        disc = meta["discrimination"]
        assert disc.get("verified_at"), (
            f"{fixture_id} carries a discrimination block with no verified_at "
            "— looks fabricated rather than produced by a real verify-fixture run"
        )
