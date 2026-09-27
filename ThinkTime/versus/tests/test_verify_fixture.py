"""FR-44 discrimination gate — Tier-0: a fake grader spawner, no live
model call, exercising real git-bundle clones and real patch application
against the checked-in `dev-noop` fixture.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verify_fixture as vf  # noqa: E402

DEV_NOOP = Path(__file__).resolve().parents[3] / "dev" / "fixtures" / "dev-noop"


def _grading_json(*, pass_rate: float, total: int = 3) -> str:
    passed = round(pass_rate * total)
    exps = [
        {"id": f"A{i + 1}", "text": f"a{i + 1}", "passed": i < passed, "evidence": "ev"}
        for i in range(total)
    ]
    return json.dumps(
        {
            "expectations": exps,
            "summary": {
                "passed": passed,
                "failed": total - passed,
                "total": total,
                "pass_rate": passed / total,
            },
        }
    )


def _fake_spawner_by_solution(rates: dict) -> callable:
    def spawner(cmd, *, cwd, env):
        solution = Path(cwd).name
        return _grading_json(pass_rate=rates[solution])

    return spawner


@pytest.fixture()
def dev_noop_copy(tmp_path):
    """A scratch copy of `dev-noop` so a test run's `fixture.json` write
    (and any leftover `.vc-verify-*` scratch dir) never touches the
    checked-in fixture."""
    if not DEV_NOOP.is_dir():
        pytest.skip("dev-noop fixture not present in this checkout")
    dest = tmp_path / "dev-noop"
    shutil.copytree(DEV_NOOP, dest)
    return dest


def test_verify_fixture_writes_discrimination_block(dev_noop_copy):
    discrimination = vf.verify_fixture(
        dev_noop_copy,
        grader_spawner=_fake_spawner_by_solution({"reference": 1.0, "broken": 0.0}),
        provision_auth=lambda fake_home: None,
    )

    assert discrimination["reference_pass_rate"] == 1.0
    assert discrimination["broken_pass_rate"] == 0.0
    assert discrimination["gate_reference_exit"] == 0
    # dev-noop's checks.sh only requires OUTPUT.md to exist — broken/
    # still clears the gate (wrong content, present file), consistent
    # with FR-41's "wrong in content but still producing output".
    assert discrimination["gate_broken_hard_exit"] != 0
    assert "verified_at" in discrimination


def test_verify_fixture_persists_into_fixture_json(dev_noop_copy):
    vf.verify_fixture(
        dev_noop_copy,
        grader_spawner=_fake_spawner_by_solution({"reference": 1.0, "broken": 1 / 3}),
        provision_auth=lambda fake_home: None,
    )
    meta = json.loads((dev_noop_copy / "fixture.json").read_text())
    assert meta["discrimination"]["reference_pass_rate"] == 1.0
    assert meta["discrimination"]["broken_pass_rate"] == pytest.approx(1 / 3)
    assert meta["last_verified"] == meta["discrimination"]["verified_at"]
    # fixture_id/version/head_sha/bundle_sha256 must survive untouched.
    assert meta["fixture_id"] == "dev-noop"
    assert meta["bundle_sha256"]


def test_verify_fixture_cleans_up_scratch_dir_by_default(dev_noop_copy):
    vf.verify_fixture(
        dev_noop_copy,
        grader_spawner=_fake_spawner_by_solution({"reference": 1.0, "broken": 0.0}),
        provision_auth=lambda fake_home: None,
    )
    leftovers = list(dev_noop_copy.glob(".vc-verify-*"))
    assert leftovers == []


def test_verify_fixture_raises_on_grader_failure(dev_noop_copy):
    def crashing_spawner(cmd, *, cwd, env):
        raise RuntimeError("boom")

    with pytest.raises(vf.DiscriminationError):
        vf.verify_fixture(
            dev_noop_copy,
            grader_spawner=crashing_spawner,
            provision_auth=lambda fake_home: None,
        )


def test_verify_fixture_accepts_a_relative_fixture_dir(dev_noop_copy, monkeypatch):
    """`_apply_solution` runs `git apply` with `cwd=<worktree>`, so a
    relative `fixture_dir` must be resolved to absolute up front — a
    relative patch path would otherwise fail to locate `solution.patch`
    once the subprocess cwd has moved (regression, 2026-08-04)."""
    monkeypatch.chdir(dev_noop_copy.parent)
    relative = dev_noop_copy.name
    discrimination = vf.verify_fixture(
        relative,
        grader_spawner=_fake_spawner_by_solution({"reference": 1.0, "broken": 0.0}),
        provision_auth=lambda fake_home: None,
    )
    assert discrimination["reference_pass_rate"] == 1.0


def test_gate_exit_success_and_failure():
    from grading import CheckResult

    assert vf._gate_exit([CheckResult(name="checks.sh", exit_code=0)]) == 0
    assert vf._gate_exit([CheckResult(name="checks.sh", exit_code=1)]) == 1


def test_apply_solution_noop_on_empty_patch(tmp_path):
    fixture_dir = tmp_path / "fx"
    (fixture_dir / "broken_hard").mkdir(parents=True)
    (fixture_dir / "broken_hard" / "solution.patch").write_text("")
    target = tmp_path / "wt"
    target.mkdir()
    vf._apply_solution(fixture_dir, target, "broken_hard")  # must not raise


def test_apply_solution_raises_on_bad_patch(tmp_path):
    fixture_dir = tmp_path / "fx"
    (fixture_dir / "broken").mkdir(parents=True)
    (fixture_dir / "broken" / "solution.patch").write_text("not a real patch\n")
    target = tmp_path / "wt"
    target.mkdir()
    (target / ".git").mkdir()  # enough for `git apply` to attempt and fail cleanly
    with pytest.raises(vf.DiscriminationError):
        vf._apply_solution(fixture_dir, target, "broken")


# ------------------------------------------------------------------ Phase 5 review regressions


def test_scratch_dir_is_never_created_inside_the_fixture(dev_noop_copy):
    """The scratch dir holds a copy of the developer's real
    ~/.claude/.credentials.json. Fixture directories are tracked git
    content covered by no .gitignore, so a default work_dir inside one put
    live OAuth credentials an abnormal exit away from being committed.
    """
    seen = {}

    def recording_auth(fake_home):
        seen["fake_home"] = Path(fake_home)

    vf.verify_fixture(
        dev_noop_copy,
        grader_spawner=_fake_spawner_by_solution({"reference": 1.0, "broken": 0.0}),
        provision_auth=recording_auth,
    )

    assert dev_noop_copy not in seen["fake_home"].parents
    assert list(dev_noop_copy.glob(".vc-verify-*")) == []


def test_copied_credential_is_removed_even_for_caller_supplied_work_dir(
    dev_noop_copy, tmp_path
):
    """A caller-supplied work_dir got no cleanup at all, and the owned path
    relied on rmtree(ignore_errors=True), which swallows EBUSY/EPERM."""
    work_dir = tmp_path / "scratch"

    def planting_auth(fake_home):
        cred_dir = Path(fake_home) / ".claude"
        cred_dir.mkdir(parents=True, exist_ok=True)
        (cred_dir / ".credentials.json").write_text('{"token": "live-secret"}')

    vf.verify_fixture(
        dev_noop_copy,
        work_dir=work_dir,
        grader_spawner=_fake_spawner_by_solution({"reference": 1.0, "broken": 0.0}),
        provision_auth=planting_auth,
    )

    assert not (work_dir / "home" / ".claude" / ".credentials.json").exists()


def test_discrimination_block_is_bound_to_the_fixture_version(dev_noop_copy):
    """Without a version binding a passing block stayed valid forever, even
    after checks.sh or the patches were rewritten."""
    discrimination = vf.verify_fixture(
        dev_noop_copy,
        grader_spawner=_fake_spawner_by_solution({"reference": 1.0, "broken": 0.0}),
        provision_auth=lambda fake_home: None,
    )
    meta = json.loads((dev_noop_copy / "fixture.json").read_text())

    assert discrimination["verified_fixture_version"] == meta["fixture_version"]


def test_missing_reference_patch_is_refused_not_a_silent_noop(dev_noop_copy):
    """Only broken_hard/ may be an empty diff (FR-41). A missing reference/
    or broken/ patch silently graded the pristine bundle, so the arm was
    never actually applied yet the fixture still certified."""
    (dev_noop_copy / "broken" / "solution.patch").write_text("")

    with pytest.raises(vf.DiscriminationError, match="broken/solution.patch"):
        vf.verify_fixture(
            dev_noop_copy,
            grader_spawner=_fake_spawner_by_solution(
                {"reference": 1.0, "broken": 0.0}
            ),
            provision_auth=lambda fake_home: None,
        )


def test_empty_assertion_set_is_refused(dev_noop_copy):
    """Grading zero assertions is vacuous: the id-match check is trivially
    satisfied and the resulting rates can still clear FR-44."""
    (dev_noop_copy / "assertions.json").write_text(json.dumps({"assertions": []}))

    with pytest.raises(vf.DiscriminationError, match="assert"):
        vf.verify_fixture(
            dev_noop_copy,
            grader_spawner=_fake_spawner_by_solution(
                {"reference": 1.0, "broken": 0.0}
            ),
            provision_auth=lambda fake_home: None,
        )


def test_failed_fixture_json_write_leaves_no_stray_tmp(dev_noop_copy, monkeypatch):
    """The atomic-write temp lives inside the tracked fixture directory, so
    a failed write must not leave a stray for a later `git add`."""
    real_replace = Path.replace

    def exploding_replace(self, target):
        if self.name == "fixture.json.tmp":
            raise OSError("disk full")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", exploding_replace)

    with pytest.raises(OSError, match="disk full"):
        vf.verify_fixture(
            dev_noop_copy,
            grader_spawner=_fake_spawner_by_solution(
                {"reference": 1.0, "broken": 0.0}
            ),
            provision_auth=lambda fake_home: None,
        )

    assert not (dev_noop_copy / "fixture.json.tmp").exists()
