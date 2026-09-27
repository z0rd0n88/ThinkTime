"""FR-52/SM1 — A-vs-A calibration: the predicate, the record chain
(fail_unconfirmed / inconclusive / underpowered), staleness, and the
pooled positional ledger. All Tier-0: `run_calibration`'s underlying
comparison is injected, never a live `claude -p` call.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import calibrate as cal  # noqa: E402


def _dim(wins_a=0, wins_b=0, effective_n=9, verdict="INCONCLUSIVE"):
    return {
        "decided_by": "mechanical",
        "wins_a": wins_a,
        "wins_b": wins_b,
        "ties": 0,
        "no_contest": 0,
        "effective_n": effective_n,
        "wilson": [0.4, 0.5, 0.6],
        "sign_test_p": 1.0,
        "verdict": verdict,
    }


def _report(*, overall="INCONCLUSIVE", n_eff=9, sweep_dim=None, fixture_version=1):
    """A minimal, report.py-shaped `report.json` for SM1 purposes.
    `sweep_dim` names one of the six SM1 dimensions to give a conclusive
    A_WINS split instead of a clean tie, simulating a positional/harness
    asymmetry.

    NOTE: `n_eff` is set independently of `wins_a`/`wins_b` here, which
    `paired_stats.aggregate` (where `n_eff == wins_a + wins_b`) would never
    emit. That is deliberate for the predicate tests — it lets a dimension
    express "decided n_eff pairs, tied overall" in one knob — but it means
    these canned reports are NOT proof that a state is reachable in
    production. `test_sm1_all_tie_dimensions_are_exempt_from_floor` below
    covers the realistic all-tie shape (n_eff == 0).
    """
    dims = {
        "correctness": _dim(effective_n=n_eff),
        "constraint_adherence": _dim(effective_n=n_eff),
        "efficiency": {
            "tool_calls": _dim(effective_n=n_eff),
            "wall_clock": _dim(effective_n=n_eff),
            "cost": _dim(effective_n=n_eff),
        },
        "quality": {**_dim(effective_n=n_eff), "verdict_determining": False},
    }
    if sweep_dim:
        target = (
            dims["efficiency"][sweep_dim.split(".", 1)[1]]
            if sweep_dim.startswith("efficiency.")
            else dims[sweep_dim]
        )
        target["wins_a"] = n_eff
        target["verdict"] = "A_WINS"
    # `fixture` mirrors report.py's real shape: run_calibration stamps its
    # record with the version the RUN measured, read from here, rather than
    # re-reading fixture.json after the fact.
    return {
        "verdict": overall,
        "dimensions": dims,
        "fixture": {
            "fixture_id": "fx",
            "fixture_version": fixture_version,
            "fixture_unverified": False,
        },
    }


# ---------------------------------------------------------------- validate_runs


def test_validate_runs_below_floor_raises():
    with pytest.raises(cal.CalibrationFloorError):
        cal.validate_runs(7)


def test_validate_runs_at_floor_ok():
    cal.validate_runs(9)  # must not raise


# ---------------------------------------------------------------- evaluate_sm1


def test_evaluate_sm1_pass_on_clean_ties():
    result = cal.evaluate_sm1(_report())
    assert result["raw_result"] == "pass"


def test_evaluate_sm1_fail_when_a_dimension_sweeps():
    result = cal.evaluate_sm1(_report(sweep_dim="correctness"))
    assert result["raw_result"] == "fail"


def test_evaluate_sm1_fail_on_efficiency_submetric_winner():
    result = cal.evaluate_sm1(_report(sweep_dim="efficiency.cost"))
    assert result["raw_result"] == "fail"


def test_evaluate_sm1_fail_on_quality_winner():
    """SM1 evaluates quality too — positional bias in the blind
    comparator is exactly what this predicate must catch, even though
    quality never decides an overall verdict (FR-39)."""
    result = cal.evaluate_sm1(_report(sweep_dim="quality"))
    assert result["raw_result"] == "fail"


def test_evaluate_sm1_fail_when_overall_verdict_not_inconclusive():
    result = cal.evaluate_sm1(_report(overall="TASK_TOO_HARD"))
    assert result["raw_result"] == "fail"


def test_evaluate_sm1_inconclusive_when_n_eff_below_floor():
    result = cal.evaluate_sm1(_report(n_eff=8))
    assert result["raw_result"] == "inconclusive"


def test_evaluate_sm1_n_eff_below_floor_takes_priority_over_a_winner():
    """A thin sample AND a winner: FR-52 treats sub-floor n_eff as an
    absence-of-evidence state, not proof of asymmetry — inconclusive
    wins."""
    report = _report(n_eff=8, sweep_dim="correctness")
    result = cal.evaluate_sm1(report)
    assert result["raw_result"] == "inconclusive"


# ---------------------------------------------------------------- record chain


def test_classify_first_pass():
    assert cal.classify_with_history("pass", []) == "pass"


def test_classify_first_fail_is_unconfirmed():
    assert cal.classify_with_history("fail", []) == "fail_unconfirmed"


def test_classify_fail_confirms_after_prior_unconfirmed():
    records = [{"result": "fail_unconfirmed"}]
    assert cal.classify_with_history("fail", records) == "fail"


def test_classify_fail_after_pass_is_unconfirmed_again():
    records = [{"result": "pass"}]
    assert cal.classify_with_history("fail", records) == "fail_unconfirmed"


def test_classify_inconclusive_chain_neutral_still_confirms_fail():
    """fail_unconfirmed -> inconclusive -> fail must confirm
    (HARNESS_INVALID) — an inconclusive attempt in between neither
    resets nor confirms the pending flag (FR-52)."""
    records = [{"result": "fail_unconfirmed"}, {"result": "inconclusive"}]
    assert cal.classify_with_history("fail", records) == "fail"


def test_classify_two_consecutive_inconclusive_is_underpowered():
    records = [{"result": "inconclusive"}]
    assert cal.classify_with_history("inconclusive", records) == "underpowered"


def test_classify_single_inconclusive_stays_inconclusive():
    records = [{"result": "pass"}]
    assert cal.classify_with_history("inconclusive", records) == "inconclusive"


def test_classify_underpowered_resets_pending_fail_unconfirmed():
    """FR-52: reaching `underpowered` drops a prior `fail_unconfirmed`
    rather than letting it be confirmed later at a different N."""
    records = [
        {"result": "fail_unconfirmed"},
        {"result": "inconclusive"},
        {"result": "underpowered"},
    ]
    # A subsequent fail must NOT confirm against the dropped flag.
    assert cal.classify_with_history("fail", records) == "fail_unconfirmed"


# ---------------------------------------------------------------- staleness_status


def test_staleness_no_record_is_unverified(tmp_path):
    status, record = cal.staleness_status(tmp_path, fixture_version=1)
    assert status == "unverified"
    assert record is None


def test_staleness_pass_at_current_version_is_verified(tmp_path):
    cal._append_record(tmp_path, {"result": "pass", "calibrated_fixture_version": 1})
    status, record = cal.staleness_status(tmp_path, fixture_version=1)
    assert status == "verified"
    assert record["result"] == "pass"


def test_staleness_pass_at_stale_version_is_unverified(tmp_path):
    cal._append_record(tmp_path, {"result": "pass", "calibrated_fixture_version": 1})
    status, _ = cal.staleness_status(tmp_path, fixture_version=2)
    assert status == "unverified"


def test_staleness_confirmed_fail_is_invalid(tmp_path):
    cal._append_record(tmp_path, {"result": "fail", "calibrated_fixture_version": 1})
    status, _ = cal.staleness_status(tmp_path, fixture_version=1)
    assert status == "invalid"


def test_staleness_fail_unconfirmed_is_unverified_not_invalid(tmp_path):
    cal._append_record(
        tmp_path, {"result": "fail_unconfirmed", "calibrated_fixture_version": 1}
    )
    status, _ = cal.staleness_status(tmp_path, fixture_version=1)
    assert status == "unverified"


# ---------------------------------------------------------------- pooled ledger


def test_two_sided_binomial_p_symmetric_split_is_one():
    assert cal.two_sided_binomial_p(10, 20) == 1.0


def test_two_sided_binomial_p_extreme_split_is_small():
    assert cal.two_sided_binomial_p(20, 20) < 0.001


def test_pooled_ledger_not_evaluated_below_min_pairs(tmp_path):
    entries = [{"position": "A", "fixture_version": 1, "date": "d"} for _ in range(19)]
    cal._append_ledger_entries(tmp_path, entries)
    assert cal.pooled_ledger_failed(tmp_path, fixture_version=1) is False


def test_pooled_ledger_fails_on_lopsided_split(tmp_path):
    entries = [{"position": "A", "fixture_version": 1, "date": "d"} for _ in range(20)]
    cal._append_ledger_entries(tmp_path, entries)
    assert cal.pooled_ledger_failed(tmp_path, fixture_version=1) is True


def test_pooled_ledger_scoped_to_fixture_version(tmp_path):
    """Entries from a stale fixture_version never count toward the
    current version's pooled test — a fixture edit is a different test
    (module docstring)."""
    stale = [{"position": "A", "fixture_version": 1, "date": "d"} for _ in range(20)]
    cal._append_ledger_entries(tmp_path, stale)
    assert cal.pooled_ledger_failed(tmp_path, fixture_version=2) is False


def test_positional_entries_from_judging_excludes_ties_and_none():
    judging = {
        "pairs": {
            "pair-1": {"slot_winner": "A"},
            "pair-2": {"slot_winner": "TIE"},
            "pair-3": {"slot_winner": None},
            "pair-4": {"slot_winner": "B"},
        }
    }
    entries = cal.positional_entries_from_judging(judging, fixture_version=1, date="d")
    assert sorted(e["position"] for e in entries) == ["A", "B"]


# ---------------------------------------------------------------- run_calibration


def test_run_calibration_writes_record_and_ledger(tmp_path):
    fixture_dir = tmp_path / "fixtures" / "dev-noop"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "fixture.json").write_text(json.dumps({"fixture_version": 3}))

    workspace = tmp_path / "workspace"

    def fake_run_comparison(ns):
        cmp_dir = Path(ns.workspace) / ns.comparison_id
        (cmp_dir / "eval-0").mkdir(parents=True)
        # Version matches fixture.json's 3: the record is stamped from the
        # version the RUN measured (report.json), so the two agree here.
        # test_calibration_record_uses_the_version_the_run_measured pins
        # the behaviour when they diverge.
        (cmp_dir / "report.json").write_text(json.dumps(_report(fixture_version=3)))
        (cmp_dir / "eval-0" / "judging.json").write_text(
            json.dumps(
                {
                    "pairs": {
                        f"pair-{i}": {"slot_winner": "A" if i % 2 else "B"}
                        for i in range(9)
                    }
                }
            )
        )
        return 0

    # Patch the module-level import site used inside run_calibration.
    import run_comparison as rc_module

    original = rc_module.resolve_fixture_dir
    rc_module.resolve_fixture_dir = lambda spec, *, dev: fixture_dir
    try:
        record = cal.run_calibration(
            candidate="some/skill",
            fixture="dev-noop",
            runs=9,
            workspace=str(workspace),
            run_comparison_fn=fake_run_comparison,
            date="2026-07-30T00:00:00Z",
        )
    finally:
        rc_module.resolve_fixture_dir = original

    assert record["result"] == "pass"
    assert record["calibrated_fixture_version"] == 3
    assert (fixture_dir / "calibration.jsonl").is_file()
    ledger = cal._read_ledger(fixture_dir)
    assert len(ledger) == 9


def test_run_calibration_dry_run_returns_none_and_forwards_flag():
    """FR-60: --dry-run rehearses setup and spawns nothing, so there is
    no report.json to evaluate SM1 against — the caller must not treat
    a None return as a crash."""
    calls = []

    def spy(ns):
        calls.append(ns)
        return 0

    record = cal.run_calibration(
        candidate="x", fixture="dev-noop", runs=9, dry_run=True, run_comparison_fn=spy
    )
    assert record is None
    assert len(calls) == 1
    assert calls[0].dry_run is True


def test_run_calibration_below_floor_refuses_before_any_run():
    calls = []

    def spy(ns):
        calls.append(ns)
        return 0

    with pytest.raises(cal.CalibrationFloorError):
        cal.run_calibration(
            candidate="x", fixture="dev-noop", runs=5, run_comparison_fn=spy
        )
    assert calls == []


def test_run_calibration_raises_when_report_missing(tmp_path):
    fixture_dir = tmp_path / "fixtures" / "dev-noop"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "fixture.json").write_text(json.dumps({"fixture_version": 1}))
    workspace = tmp_path / "workspace"

    def broken_run_comparison(ns):
        Path(ns.workspace, ns.comparison_id).mkdir(parents=True)
        return 1  # crashed, no report.json written

    import run_comparison as rc_module

    original = rc_module.resolve_fixture_dir
    rc_module.resolve_fixture_dir = lambda spec, *, dev: fixture_dir
    try:
        with pytest.raises(cal.CalibrationRunError):
            cal.run_calibration(
                candidate="x",
                fixture="dev-noop",
                runs=9,
                workspace=str(workspace),
                run_comparison_fn=broken_run_comparison,
            )
    finally:
        rc_module.resolve_fixture_dir = original


# ------------------------------------------------------------------ Phase 5 review regressions
#
# Each test below pins a defect found in multi-agent review of PR #51.


def test_third_consecutive_fail_stays_confirmed():
    """A confirmed `fail` must not decay back to `fail_unconfirmed`.

    Matching only `fail_unconfirmed` made the chain oscillate, so a third
    failing calibration demoted the fixture from `invalid` to merely
    `unverified` — more evidence of bias producing a weaker verdict.
    """
    records = []
    seen = []
    for _ in range(4):
        result = cal.classify_with_history("fail", records)
        seen.append(result)
        records.append({"result": result, "calibrated_fixture_version": 1})

    assert seen == ["fail_unconfirmed", "fail", "fail", "fail"]


def test_repeated_inconclusive_latches_underpowered():
    """`underpowered` must latch rather than alternate with inconclusive."""
    records = []
    seen = []
    for _ in range(4):
        result = cal.classify_with_history("inconclusive", records)
        seen.append(result)
        records.append({"result": result, "calibrated_fixture_version": 1})

    assert seen == ["inconclusive", "underpowered", "underpowered", "underpowered"]


def test_inconclusive_after_confirmed_fail_does_not_clear_invalid(tmp_path):
    """FR-52 makes `inconclusive` chain-neutral when WRITING a record;
    `staleness_status` must honour that when READING one. Consuming
    records[-1] blindly let one thin run erase a HARNESS_INVALID."""
    for result in ("fail_unconfirmed", "fail"):
        cal._append_record(
            tmp_path, {"result": result, "calibrated_fixture_version": 1}
        )
    assert cal.staleness_status(tmp_path, 1)[0] == "invalid"

    cal._append_record(
        tmp_path, {"result": "inconclusive", "calibrated_fixture_version": 1}
    )

    assert cal.staleness_status(tmp_path, 1)[0] == "invalid"


def test_staleness_rejects_record_from_a_higher_version(tmp_path):
    """`<` accepted a record calibrated at a HIGHER version, so rolling
    fixture_version back left replaced content reading as verified."""
    cal._append_record(tmp_path, {"result": "pass", "calibrated_fixture_version": 7})

    assert cal.staleness_status(tmp_path, 3)[0] == "unverified"
    assert cal.staleness_status(tmp_path, 7)[0] == "verified"


def test_calibration_record_carries_candidate_identity(tmp_path):
    """The A-vs-A probe measures one candidate's workload; the record must
    say which, or it silently vouches for every candidate.

    Asserts the WRITTEN record, not the source text: an earlier version of
    this test grepped inspect.getsource() for a literal, which would pass
    even if the value never reached disk.
    """
    fixture_dir, workspace, fake = _calibration_harness(
        tmp_path, report_version=1, disk_version=1
    )

    record = _run_with_patched_resolver(fixture_dir, workspace, fake)

    assert record["candidate"] == "some/skill"
    on_disk = json.loads(
        (fixture_dir / "calibration.jsonl").read_text().strip().splitlines()[-1]
    )
    assert on_disk["candidate"] == "some/skill"


def _calibration_harness(tmp_path, *, report_version, disk_version, rc=0):
    """Shared rig: a fixture on disk at `disk_version` and a canned report
    claiming `report_version`, so the two can be made to diverge."""
    fixture_dir = tmp_path / "fixtures" / "dev-noop"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "fixture.json").write_text(
        json.dumps({"fixture_version": disk_version})
    )
    workspace = tmp_path / "workspace"

    def fake_run_comparison(ns):
        cmp_dir = Path(ns.workspace) / ns.comparison_id
        (cmp_dir / "eval-0").mkdir(parents=True)
        (cmp_dir / "report.json").write_text(
            json.dumps(_report(fixture_version=report_version))
        )
        (cmp_dir / "eval-0" / "judging.json").write_text(json.dumps({"pairs": {}}))
        return rc

    return fixture_dir, workspace, fake_run_comparison


def _run_with_patched_resolver(fixture_dir, workspace, fake_run_comparison, **kw):
    import run_comparison as rc_module

    original = rc_module.resolve_fixture_dir
    rc_module.resolve_fixture_dir = lambda spec, *, dev: fixture_dir
    try:
        return cal.run_calibration(
            candidate="some/skill",
            fixture="dev-noop",
            runs=9,
            workspace=str(workspace),
            run_comparison_fn=fake_run_comparison,
            date="2026-07-30T00:00:00Z",
            **kw,
        )
    finally:
        rc_module.resolve_fixture_dir = original


def test_calibration_record_uses_the_version_the_run_measured(tmp_path):
    """A fixture edited mid-calibration must not make the record claim a
    version it never measured — that is the staleness the field prevents."""
    fixture_dir, workspace, fake = _calibration_harness(
        tmp_path, report_version=1, disk_version=2
    )

    record = _run_with_patched_resolver(fixture_dir, workspace, fake)

    assert record["calibrated_fixture_version"] == 1


def test_harness_invalid_run_is_not_recorded_as_calibration(tmp_path):
    """rc == 1 is run_comparison's HARNESS_INVALID signal. Accepting it let
    a broken seal or comparator failure mutate the record chain and seed
    the pooled positional ledger from a stage the harness disowned."""
    fixture_dir, workspace, fake = _calibration_harness(
        tmp_path, report_version=1, disk_version=1, rc=1
    )

    with pytest.raises(cal.CalibrationRunError):
        _run_with_patched_resolver(fixture_dir, workspace, fake)

    assert not (fixture_dir / "calibration.jsonl").exists()


def test_calibration_forwards_run_flags_instead_of_hardcoding(tmp_path):
    """The `run` subparser accepts these six; hardcoding them made them
    parse cleanly and then do nothing — worst of all --max-budget-usd on
    the most expensive path the harness has."""
    fixture_dir, workspace, _ = _calibration_harness(
        tmp_path, report_version=1, disk_version=1
    )
    seen = {}

    def capturing_run_comparison(ns):
        seen.update(vars(ns))
        cmp_dir = Path(ns.workspace) / ns.comparison_id
        (cmp_dir / "eval-0").mkdir(parents=True)
        (cmp_dir / "report.json").write_text(json.dumps(_report()))
        (cmp_dir / "eval-0" / "judging.json").write_text(json.dumps({"pairs": {}}))
        return 0

    _run_with_patched_resolver(
        fixture_dir,
        workspace,
        capturing_run_comparison,
        isolation="clone",
        double_judge=True,
        keep_worktrees="always",
        max_budget_usd=0.25,
        respect_candidate_model=True,
    )

    assert seen["isolation"] == "clone"
    assert seen["double_judge"] is True
    assert seen["keep_worktrees"] == "always"
    assert seen["max_budget_usd"] == 0.25
    assert seen["respect_candidate_model"] is True


# ------------------------------------------------------------------ re-review regressions
#
# Defects found by re-reviewing the first round of fixes. Each of these
# passed the earlier tests, which is why they are pinned explicitly.


def _dim_nc(effective_n=0, ties=0, no_contest=0):
    """A dimension distinguishing an honest all-tie from a NO_CONTEST
    washout — both collapse to effective_n == 0."""
    return {
        "decided_by": "mechanical",
        "wins_a": 0,
        "wins_b": 0,
        "ties": ties,
        "no_contest": no_contest,
        "effective_n": effective_n,
        "wilson": [0.4, 0.5, 0.6],
        "sign_test_p": 1.0,
        "verdict": "INCONCLUSIVE",
    }


def _report_with(mk_thin):
    report = _report()
    report["dimensions"]["correctness"] = mk_thin()
    report["dimensions"]["constraint_adherence"] = mk_thin()
    report["dimensions"]["efficiency"]["tool_calls"] = mk_thin()
    report["dimensions"]["efficiency"]["cost"] = mk_thin()
    return report


def test_record_distinguishes_ties_from_no_contest():
    """The record must let a reader tell the two apart after the fact."""
    splits = cal.evaluate_sm1(_report_with(lambda: _dim_nc(no_contest=9)))

    assert splits["per_dimension_splits"]["correctness"]["no_contest"] == 9
    assert splits["per_dimension_splits"]["correctness"]["ties"] == 0


def test_two_inconclusives_cannot_clear_a_confirmed_fail(tmp_path):
    """The first round only pinned ONE trailing inconclusive. The second is
    written as `underpowered`, which `_last_chain_relevant` stops on, so
    the fixture walked from invalid back to unverified."""
    for result in ("fail_unconfirmed", "fail", "inconclusive", "underpowered"):
        cal._append_record(
            tmp_path, {"result": result, "calibrated_fixture_version": 1}
        )

    assert cal.staleness_status(tmp_path, 1)[0] == "invalid"


def test_a_later_pass_does_supersede_a_confirmed_fail(tmp_path):
    """The latch must not be absolute — a genuine later `pass` clears it."""
    for result in ("fail_unconfirmed", "fail", "pass"):
        cal._append_record(
            tmp_path, {"result": result, "calibrated_fixture_version": 1}
        )

    assert cal.staleness_status(tmp_path, 1)[0] == "verified"


def test_confirmed_fail_latches_through_an_underpowered_record():
    """An intervening `underpowered` demoted the next genuine failure back
    to `fail_unconfirmed`."""
    records = [
        {"result": r}
        for r in ("fail_unconfirmed", "fail", "inconclusive", "underpowered")
    ]

    assert cal.classify_with_history("fail", records) == "fail"


def test_fail_needs_reconfirmation_after_a_pass():
    """But a `pass` resets the latch: the next single failure is unconfirmed."""
    records = [{"result": r} for r in ("fail_unconfirmed", "fail", "pass")]

    assert cal.classify_with_history("fail", records) == "fail_unconfirmed"


def test_fail_confirmation_does_not_span_fixture_versions(tmp_path):
    """A `fail_unconfirmed` at v1 must not confirm the FIRST failure at v2
    into a hard `fail` — that blocked every comparison at a brand-new
    version off one attempt."""
    fixture_dir, workspace, fake = _calibration_harness(
        tmp_path, report_version=2, disk_version=2
    )
    cal._append_record(
        fixture_dir, {"result": "fail_unconfirmed", "calibrated_fixture_version": 1}
    )

    # Force a failing SM1 outcome at v2 via a sweeping dimension.
    def sweeping_run(ns):
        cmp_dir = Path(ns.workspace) / ns.comparison_id
        (cmp_dir / "eval-0").mkdir(parents=True)
        (cmp_dir / "report.json").write_text(
            json.dumps(_report(fixture_version=2, sweep_dim="correctness"))
        )
        (cmp_dir / "eval-0" / "judging.json").write_text(json.dumps({"pairs": {}}))
        return 0

    record = _run_with_patched_resolver(fixture_dir, workspace, sweeping_run)

    assert record["result"] == "fail_unconfirmed"


def test_ties_dropping_a_dimension_to_zero_is_inconclusive_not_pass():
    """FR-52 spec row: "a calibration launched at N=9 in which ties drop any
    dimension or `efficiency` sub-metric below `n_eff = 9` writes
    `{result: inconclusive}` — not `pass`".

    This case had NO coverage: the existing floor test used n_eff=8, never
    0, so an exemption for all-tie dimensions passed the suite green while
    inverting the incentive FR-52 calls out — a quieter harness buying a
    cleaner bill of health from a test that had stopped being able to fail
    it. The bounded re-run terminating in `underpowered` is the sanctioned
    way out for a tie-prone fixture, not a weaker predicate.
    """
    report = _report()
    report["dimensions"]["correctness"] = _dim_nc(ties=9)
    report["dimensions"]["constraint_adherence"] = _dim_nc(ties=9)

    assert cal.evaluate_sm1(report)["raw_result"] == "inconclusive"


def test_a_single_tied_pair_anywhere_is_inconclusive():
    """The bar is on n_eff, not N (FR-52/SM1): one tie in one sub-metric
    drops that dimension to 8 and sinks the whole attempt."""
    report = _report()
    report["dimensions"]["efficiency"]["wall_clock"] = _dim_nc(effective_n=8, ties=1)

    assert cal.evaluate_sm1(report)["raw_result"] == "inconclusive"


def test_tie_prone_fixture_terminates_in_underpowered():
    """FR-52's bounded re-run: two consecutive `inconclusive` records
    terminate in `underpowered` rather than looping forever."""
    records = []
    seen = []
    for _ in range(3):
        result = cal.classify_with_history("inconclusive", records)
        seen.append(result)
        records.append({"result": result, "calibrated_fixture_version": 1})

    assert seen[:2] == ["inconclusive", "underpowered"]
