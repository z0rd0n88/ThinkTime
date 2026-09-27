"""Report assembly — FR-39/FR-50/FR-51/FR-52 wired against real artifacts.

Builds `report.json`/`report.md` from the harness-native tree: `runs/`,
`comparison.json`, and `eval-0/judging.json`. Everything upstream of this
module (paired_stats' pure functions, aggregate_benchmark's wire export,
redact's credential sweep) is tested independently; these tests exercise
the integration — reading real artifact shapes and threading them through.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import report as rp  # noqa: E402


def _grading(
    passed=3,
    total=3,
    task_outcome="success",
    completed=0,
    attempted=0,
    chain_ok=True,
    degraded=False,
):
    if degraded:
        return {
            "error_class": "grader_crashed",
            "reason": "boom",
            "task_outcome": task_outcome,
            "retries": 2,
            "audit": {
                "chain_ok": chain_ok,
                "tool_counts": {},
                "audit_total": 5 if chain_ok else None,
                "violation_attempted": attempted if chain_ok else None,
                "violation_completed": completed if chain_ok else None,
            },
            "self_report_divergence": None,
        }
    exps = [
        {"id": f"A{i}", "text": f"a{i}", "passed": i < passed, "evidence": "ev"}
        for i in range(total)
    ]
    return {
        "expectations": exps,
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": passed / total,
        },
        "task_outcome": task_outcome,
        "retries": 0,
        "audit": {
            "chain_ok": chain_ok,
            "tool_counts": {"Read": 5},
            "audit_total": 5 if chain_ok else None,
            "violation_attempted": attempted if chain_ok else None,
            "violation_completed": completed if chain_ok else None,
        },
        "self_report_divergence": None,
    }


def _timing(cost=0.1, duration=10.0):
    return {
        "started_at": "2026-07-29T00:00:00Z",
        "ended_at": "2026-07-29T00:00:10Z",
        "duration_seconds": duration,
        "cost_usd": cost,
    }


def _seed_comparison(
    tmp_path,
    *,
    pairs,
    runs=None,
    quick=False,
    self_calibrate=False,
    unverified=True,
    fixture_dir=None,
    fixture_version=1,
):
    """`pairs`: list of (grading_a, grading_b, timing_a, timing_b).
    `runs`: list of judging.json per-pair dicts keyed pair-{k}, defaults to
    a straightforward candidate_a-favouring quality outcome per pair."""
    cmp_dir = tmp_path / "vc-xyz"
    for k, (ga, gb, ta, tb) in enumerate(pairs):
        for arm, (g, t) in enumerate([(ga, ta), (gb, tb)]):
            run_dir = cmp_dir / "runs" / f"pair{k}-arm{arm}"
            run_dir.mkdir(parents=True)
            (run_dir / "grading.json").write_text(json.dumps(g))
            (run_dir / "timing.json").write_text(json.dumps(t))

    (cmp_dir / "comparison.json").write_text(
        json.dumps(
            {
                "comparison_id": "vc-xyz",
                "seed": "deadbeef",
                "fixture_id": "dev-noop",
                "fixture_dir": str(fixture_dir) if fixture_dir else None,
                "fixture_version": fixture_version,
                "fixture_unverified": unverified,
                "runs": len(pairs),
                "execution_path": "subprocess",
                "model_confounded": False,
                "self_calibrate": self_calibrate,
                "candidates": [
                    {"kind": "agent", "source_path": "/a.md", "head_sha": "aaa"},
                    {"kind": "agent", "source_path": "/b.md", "head_sha": "bbb"},
                ],
            }
        )
    )

    eval_dir = cmp_dir / "eval-0"
    eval_dir.mkdir(parents=True)
    pair_records = runs or {
        f"pair-{k}": {
            "comparator_spawned": True,
            "retries": 0,
            "slot_winner": "A",
            "quality_outcome": "candidate_a",
        }
        for k in range(len(pairs))
    }
    (eval_dir / "judging.json").write_text(
        json.dumps(
            {
                "seed": "deadbeef",
                "assignment_sha256": "abc123",
                "double_judge": False,
                "pairs": pair_records,
                "invocations": len(pairs),
                "retries": 0,
                "retry_exhausted": 0,
                "harness_invalid": False,
                "harness_invalid_reason": None,
            }
        )
    )
    return cmp_dir


# ---- per-pair extraction correctness


def test_all_pairs_a_wins_correctness_and_adherence_and_quality(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[
            (_grading(3, 3), _grading(0, 3), _timing(), _timing()),
            (_grading(3, 3), _grading(0, 3), _timing(), _timing()),
            (_grading(3, 3), _grading(0, 3), _timing(), _timing()),
            (_grading(3, 3), _grading(0, 3), _timing(), _timing()),
            (_grading(3, 3), _grading(0, 3), _timing(), _timing()),
        ],
    )
    report = rp.build_report(cmp_dir)
    assert report["dimensions"]["correctness"]["verdict"] == "A_WINS"
    assert report["dimensions"]["constraint_adherence"]["wins_a"] == 0
    assert report["dimensions"]["constraint_adherence"]["wins_b"] == 0
    assert report["dimensions"]["constraint_adherence"]["ties"] == 5
    assert report["dimensions"]["quality"]["wins_a"] == 5


def test_degraded_grading_with_gate_cleared_is_no_contest_for_correctness(tmp_path):
    """Both sides clear the gate but B's grader exhausted retries with no
    summary — pass_rate cannot decide the pair, so it is excluded rather
    than scored on a fabricated value."""
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[
            (
                _grading(3, 3, task_outcome="success"),
                _grading(task_outcome="partial", degraded=True),
                _timing(),
                _timing(),
            )
        ]
        * 5,
    )
    report = rp.build_report(cmp_dir)
    assert report["dimensions"]["correctness"]["no_contest"] == 5
    assert report["dimensions"]["correctness"]["effective_n"] == 0


def test_degraded_grading_with_a_failed_gate_does_not_need_pass_rate(tmp_path):
    """A's gate failed outright (task_outcome=failure); B cleared with a
    real pass_rate. correctness_pair's one-sided branch never reads pass_rate
    for the failed side, so a missing summary there is not an obstacle."""
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[
            (
                _grading(task_outcome="failure", degraded=True),
                _grading(2, 3, task_outcome="success"),
                _timing(),
                _timing(),
            )
        ]
        * 5,
    )
    report = rp.build_report(cmp_dir)
    assert report["dimensions"]["correctness"]["verdict"] == "B_WINS"
    assert report["dimensions"]["correctness"]["no_contest"] == 0


def test_audit_chain_failure_excludes_the_pair_from_adherence_only(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[
            (
                _grading(3, 3, chain_ok=False),
                _grading(1, 3),
                _timing(),
                _timing(),
            )
        ]
        * 5,
    )
    report = rp.build_report(cmp_dir)
    assert report["dimensions"]["constraint_adherence"]["no_contest"] == 5
    # correctness is unaffected by an audit-chain failure — it reads
    # pass_rate, not the audit block, so a broken chain there doesn't
    # exclude the pair from this dimension.
    assert report["dimensions"]["correctness"]["effective_n"] == 5
    assert report["dimensions"]["correctness"]["verdict"] == "A_WINS"


def test_missing_cost_excludes_the_pair_from_the_cost_submetric_only(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(3, 3), _timing(cost=None), _timing(cost=0.2))]
        * 5,
    )
    report = rp.build_report(cmp_dir)
    assert report["dimensions"]["efficiency"]["cost"]["no_contest"] == 5
    assert report["dimensions"]["efficiency"]["tool_calls"]["effective_n"] >= 0


def test_efficiency_wall_clock_and_tool_calls_read_from_timing_and_audit(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[
            (
                _grading(3, 3),
                _grading(3, 3),
                _timing(duration=10.0),
                _timing(duration=20.0),
            )
        ]
        * 5,
    )
    report = rp.build_report(cmp_dir)
    assert report["dimensions"]["efficiency"]["wall_clock"]["verdict"] == "A_WINS"


# ---- overall verdict wiring


def test_no_calibration_record_downgrades_to_inconclusive(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 5,
        self_calibrate=False,
    )
    report = rp.build_report(cmp_dir)
    assert report["verdict"] == "INCONCLUSIVE"
    assert report["harness_validity"]["status"] == "unverified"


def test_self_calibrate_is_exempt_from_the_downgrade(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 5,
        self_calibrate=True,
    )
    report = rp.build_report(cmp_dir)
    assert report["verdict"] == "A_WINS"
    assert report["harness_validity"]["status"] == "self"


def test_a_passing_calibration_record_verifies_the_harness(tmp_path):
    """FR-52: a real `pass` record at the CURRENT fixture_version lifts
    the downgrade — a conclusive dimension can now stand as-is."""
    fixture_dir = tmp_path / "fixtures" / "dev-noop"
    fixture_dir.mkdir(parents=True)
    import calibrate as cal

    cal._append_record(fixture_dir, {"result": "pass", "calibrated_fixture_version": 1})
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 5,
        self_calibrate=False,
        fixture_dir=fixture_dir,
    )
    report = rp.build_report(cmp_dir)
    assert report["harness_validity"]["status"] == "verified"
    assert report["harness_validity"]["calibration"]["result"] == "pass"
    assert report["verdict"] == "A_WINS"


def test_a_stale_calibration_record_stays_unverified(tmp_path):
    fixture_dir = tmp_path / "fixtures" / "dev-noop"
    fixture_dir.mkdir(parents=True)
    import calibrate as cal

    cal._append_record(fixture_dir, {"result": "pass", "calibrated_fixture_version": 1})
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 5,
        self_calibrate=False,
        fixture_dir=fixture_dir,
        fixture_version=2,  # fixture bumped past the calibrated version
    )
    report = rp.build_report(cmp_dir)
    assert report["harness_validity"]["status"] == "unverified"


def test_a_confirmed_failed_calibration_invalidates_the_harness(tmp_path):
    """FR-52: two consecutive calibration failures record HARNESS_INVALID
    for the fixture version — a normal comparison against it must return
    HARNESS_INVALID too, not merely INCONCLUSIVE."""
    fixture_dir = tmp_path / "fixtures" / "dev-noop"
    fixture_dir.mkdir(parents=True)
    import calibrate as cal

    cal._append_record(fixture_dir, {"result": "fail", "calibrated_fixture_version": 1})
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 5,
        self_calibrate=False,
        fixture_dir=fixture_dir,
    )
    report = rp.build_report(cmp_dir)
    assert report["harness_validity"]["status"] == "invalid"
    assert report["verdict"] == "HARNESS_INVALID"


def test_judging_harness_invalid_propagates_and_uses_its_own_reason(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 5,
        self_calibrate=True,
    )
    judging = json.loads((cmp_dir / "eval-0" / "judging.json").read_text())
    judging["harness_invalid"] = True
    judging["harness_invalid_reason"] = (
        "assignment.json seal did not match its recorded sha256"
    )
    (cmp_dir / "eval-0" / "judging.json").write_text(json.dumps(judging))
    report = rp.build_report(cmp_dir)
    assert report["verdict"] == "HARNESS_INVALID"
    assert "seal" in report["verdict_note"]


# ---- top-level shape, composite absence, cost accounting


def test_report_json_top_level_keys(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 5,
    )
    report = rp.build_report(cmp_dir)
    expected = {
        "verdict",
        "candidates",
        "execution",
        "fixture",
        "harness_validity",
        "dimensions",
        "verdict_note",
        "composite_score",
        "composite_score_note",
        "suspect_runs",
        "self_report_divergence",
        "scrub",
        "redactions",
        "retries",
        "cost",
        "assertion_health",
    }
    assert set(report) == expected


def test_no_composite_score_anywhere(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 5,
    )
    report = rp.build_report(cmp_dir)
    assert report["composite_score"] is None
    import re

    blob = json.dumps(report)
    for key in re.findall(r'"([a-zA-Z_]+)":', blob):
        if key in ("composite_score", "composite_score_note"):
            continue
        assert not re.search(r"score|weight|composite|overall_rating|rank", key, re.I)


def test_cost_invocation_breakdown_matches_ti3_shape(tmp_path):
    """T-I-3: N=3, no retries -> 3 executors + 3 graders + 3 comparators = 9
    per arm side... i.e. runs=2N executors/graders, N comparators."""
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(1, 1), _grading(1, 1), _timing(cost=0.1), _timing(cost=0.1))]
        * 3,
    )
    report = rp.build_report(cmp_dir)
    breakdown = report["cost"]["invocation_breakdown"]
    assert breakdown["executors"] == 6
    assert breakdown["graders"] == 6
    assert breakdown["comparators"] == 3
    assert report["cost"]["invocations"] == 15


def test_cost_total_is_the_sum_of_recorded_cost_usd(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(1, 1), _grading(1, 1), _timing(cost=0.1), _timing(cost=0.2))]
        * 3,
    )
    report = rp.build_report(cmp_dir)
    assert round(report["cost"]["total_usd"], 4) == round(3 * (0.1 + 0.2), 4)


# ---- --quick


def test_quick_sweep_yields_directional_hint(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 3,
        self_calibrate=False,
    )
    report = rp.build_report(cmp_dir, quick=True)
    assert report["verdict"] == "DIRECTIONAL_HINT"


# ---- report.md rendering


def test_report_md_renders_the_verdict_and_dimensions(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 5,
        self_calibrate=True,
    )
    report = rp.build_report(cmp_dir)
    md = rp.render_report_md(report)
    assert "A_WINS" in md
    assert "correctness" in md
    assert "quality" in md
    assert "composite" in md.lower()


def test_write_report_writes_both_files(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 5,
        self_calibrate=True,
    )
    report = rp.build_report(cmp_dir)
    rp.write_report(cmp_dir, report)
    assert (cmp_dir / "report.json").is_file()
    assert (cmp_dir / "report.md").is_file()
    on_disk = json.loads((cmp_dir / "report.json").read_text())
    assert on_disk == report


def test_cost_note_discloses_the_executor_only_scope(tmp_path):
    """total_usd currently sums only executor cost — grader/comparator cost
    is never captured anywhere in the codebase. This must be disclosed,
    not silently presented as a complete total (FR-51 forbids estimating,
    and a silent gap is its own kind of misleading number)."""
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 5,
    )
    report = rp.build_report(cmp_dir)
    assert "executor" in report["cost"]["cost_note"]
    assert "grader" in report["cost"]["cost_note"]
    md = rp.render_report_md(report)
    assert report["cost"]["cost_note"] in md


def test_assertion_health_is_wired_not_hardcoded_empty(tmp_path):
    """FR-46: build_report must classify real assertions, not report an
    empty list regardless of input."""
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[
            (_grading(3, 3), _grading(0, 3), _timing(), _timing()),
            (_grading(3, 3), _grading(0, 3), _timing(), _timing()),
            (_grading(3, 3), _grading(0, 3), _timing(), _timing()),
            (_grading(3, 3), _grading(0, 3), _timing(), _timing()),
            (_grading(3, 3), _grading(0, 3), _timing(), _timing()),
        ],
    )
    report = rp.build_report(cmp_dir)
    assert report["assertion_health"], (
        "assertion_health must not be empty for real data"
    )
    by_id = {row["id"]: row for row in report["assertion_health"]}
    assert set(by_id) == {"A0", "A1", "A2"}
    for row in by_id.values():
        assert row["classification"] == "splits_cleanly"
        assert row["pass_count_a"] == 5
        assert row["pass_count_b"] == 0
        assert "recommendation" not in row


def test_assertion_health_flags_always_passing_assertions_for_removal(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(3, 3), _timing(), _timing())] * 5,
    )
    report = rp.build_report(cmp_dir)
    assert all(
        row["classification"] == "always_passes_both"
        for row in report["assertion_health"]
    )
    assert all(row["recommendation"] for row in report["assertion_health"])


def test_assertion_health_excludes_degraded_runs_gracefully(tmp_path):
    """A run with no `expectations` (grader retry-exhausted) contributes
    nothing to that run's assertions rather than crashing the classifier."""
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[
            (
                _grading(3, 3),
                _grading(task_outcome="partial", degraded=True),
                _timing(),
                _timing(),
            )
        ]
        * 5,
    )
    report = rp.build_report(cmp_dir)
    for row in report["assertion_health"]:
        assert row["runs_a"] == 5
        assert row["runs_b"] == 0


def test_scrub_redaction_count_sums_real_scrub_logs(tmp_path):
    """FR-29's blinding-scrub count — distinct from FR-56's credential
    sweep — is read from the per-pair scrub logs stage_judging.py writes,
    not hardcoded."""
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 2,
    )
    scrub_dir = cmp_dir / "eval-0" / "scrub"
    scrub_dir.mkdir(parents=True)
    (scrub_dir / "pair-0.log").write_text(
        '{"offset": 0, "term": "x"}\n{"offset": 5, "term": "y"}\n'
    )
    (scrub_dir / "pair-1.log").write_text('{"offset": 0, "term": "z"}\n')
    report = rp.build_report(cmp_dir)
    assert report["scrub"]["redactions"] == 3


def test_scrub_redaction_count_is_zero_with_no_scrub_dir(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 2,
    )
    report = rp.build_report(cmp_dir)
    assert report["scrub"]["redactions"] == 0


def test_generate_patches_the_real_credential_count_into_report_json(tmp_path):
    """FR-56: report.json's own redactions.credential_matches must reflect
    the actual sweep, not stay permanently 0 (review finding, 2026-07-29)."""
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 2,
    )
    # Seed a real secret into a retained artifact the sweep covers.
    run_dir = cmp_dir / "runs" / "pair0-arm0"
    (run_dir / "transcript.jsonl").write_text(
        "token: ghp_realSecretValue0123456789abcd\n"
    )

    final = rp.generate(cmp_dir, eval_name="dev-noop")
    assert final["redactions"]["credential_matches"] >= 1

    on_disk = json.loads((cmp_dir / "report.json").read_text())
    assert on_disk["redactions"]["credential_matches"] >= 1
    assert (
        "ghp_realSecretValue0123456789abcd"
        not in (run_dir / "transcript.jsonl").read_text()
    )


def test_generate_reports_zero_when_no_credential_present(tmp_path):
    cmp_dir = _seed_comparison(
        tmp_path,
        pairs=[(_grading(3, 3), _grading(0, 3), _timing(), _timing())] * 2,
    )
    final = rp.generate(cmp_dir, eval_name="dev-noop")
    assert final["redactions"]["credential_matches"] == 0
