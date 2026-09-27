"""Phase 4 statistics — FR-36..FR-40 (T-U-1..T-U-15).

Golden values are pinned from spec §5.4 and the test plan; they are
recomputed independently there, so a mismatch here is a code defect,
never a reason to edit the expected number.
"""

from __future__ import annotations

import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import paired_stats as ps  # noqa: E402


# ---- T-U-1  Wilson golden rows

WILSON_LOWER_GOLDEN = [
    (3, 3, 0.4385),
    (4, 5, 0.3755),
    (5, 5, 0.5655),
    (6, 7, 0.4869),
    (7, 7, 0.6457),
]


@pytest.mark.parametrize("x,n,expected", WILSON_LOWER_GOLDEN)
def test_wilson_lower_golden_rows(x, n, expected):
    assert round(ps.wilson(x, n)[0], 4) == expected


# ---- T-U-4  power golden set; pins the sweep boundary over n_eff

POWER_GOLDEN = [
    (15, 20, 0.5313, True),
    (14, 20, 0.4810, False),
    (33, 50, 0.5215, True),
    (26, 40, 0.4951, False),
    (8, 9, 0.5650, True),
    (7, 9, 0.4526, False),
    (4, 4, 0.5101, True),
    (3, 3, 0.4385, False),
]


@pytest.mark.parametrize("x,n,lower,flags", POWER_GOLDEN)
def test_wilson_power_golden_set(x, n, lower, flags):
    got = ps.wilson(x, n)[0]
    assert round(got, 4) == lower
    assert (got > 0.5) is flags


def test_sweep_clears_the_bar_from_n_eff_four():
    """A clean sweep is conclusive at any n_eff >= 4, and never at 3."""
    assert ps.wilson(3, 3)[0] <= 0.5
    for n in range(4, 12):
        assert ps.wilson(n, n)[0] > 0.5


def test_detector_power_is_not_monotone_in_n():
    """At n_eff 5 and 7 only sweeps flag; at 9 an 8-1 flags too (F-12)."""
    assert ps.wilson(4, 5)[0] <= 0.5
    assert ps.wilson(5, 5)[0] > 0.5
    assert ps.wilson(6, 7)[0] <= 0.5
    assert ps.wilson(7, 7)[0] > 0.5
    assert ps.wilson(8, 9)[0] > 0.5


# ---- T-U-2  boundary behaviour


def test_wilson_upper_is_exactly_one_at_p_equals_one():
    for n in range(1, 12):
        assert ps.wilson(n, n)[2] == 1.0


def test_wilson_zero_denominator():
    assert ps.wilson(0, 0) == (0.0, 0.0, 1.0)


def test_wilson_zero_successes_lower_is_zero():
    for n in range(1, 12):
        assert ps.wilson(0, n)[0] == 0.0


def test_wilson_symmetry():
    for n in range(1, 12):
        for x in range(n + 1):
            lower = ps.wilson(x, n)[0]
            upper_mirror = ps.wilson(n - x, n)[2]
            assert round(lower, 12) == round(1 - upper_mirror, 12)


def test_wilson_centre_monotone_in_x():
    for n in range(1, 12):
        centres = [ps.wilson(x, n)[1] for x in range(n + 1)]
        assert centres == sorted(centres)


# ---- T-U-3  exact one-sided sign test

SIGN_GOLDEN = [
    (3, 3, 0.1250),
    (4, 5, 0.1875),
    (5, 5, 0.0313),
    (6, 7, 0.0625),
    (7, 7, 0.0078),
]


def _round_half_up(value: float, places: int) -> float:
    """The spec's tables round half-up; Python's `round` is banker's.

    `p(5,5)` is exactly 1/32 = 0.03125, which the spec prints as 0.0313 and
    `round()` returns as 0.0312. Comparing against the table therefore needs
    the table's own rounding rule, not a looser tolerance that would stop
    the golden values from pinning anything.
    """
    return float(
        Decimal(repr(value)).quantize(Decimal(f"1e-{places}"), rounding=ROUND_HALF_UP)
    )


@pytest.mark.parametrize("x,n,expected", SIGN_GOLDEN)
def test_sign_test_golden_p_values(x, n, expected):
    assert _round_half_up(ps.sign_test_p(x, n), 4) == expected


@pytest.mark.parametrize("x,n,_p", [(x, n, p) for x, n, p in SIGN_GOLDEN])
def test_two_methods_agree_on_the_call(x, n, _p):
    """The agreement is the reason both are computed (spec §5.4)."""
    wilson_conclusive = ps.wilson(x, n)[0] > 0.5
    sign_conclusive = ps.sign_test_p(x, n) < 0.05
    assert wilson_conclusive is sign_conclusive


def test_no_outcome_at_n_three_is_conclusive():
    for x in range(4):
        assert ps.wilson(x, 3)[0] <= 0.5


# ---- T-U-6  correctness per-pair win function


def _run(outcome="success", pass_rate=1.0, total=7):
    return ps.CorrectnessInput(task_outcome=outcome, pass_rate=pass_rate, total=total)


def test_correctness_both_gates_fail_is_no_contest():
    got = ps.correctness_pair(_run("failure"), _run("failure"))
    assert got is ps.PairOutcome.NO_CONTEST


def test_correctness_one_sided_gate_failure_awards_the_other():
    assert ps.correctness_pair(_run("success"), _run("failure")) is ps.PairOutcome.A
    assert ps.correctness_pair(_run("failure"), _run("partial")) is ps.PairOutcome.B


def test_correctness_both_clear_higher_pass_rate_wins():
    assert (
        ps.correctness_pair(_run(pass_rate=0.9), _run(pass_rate=0.4))
        is ps.PairOutcome.A
    )
    assert (
        ps.correctness_pair(_run(pass_rate=0.4), _run(pass_rate=0.9))
        is ps.PairOutcome.B
    )


def test_correctness_equal_pass_rate_is_a_tie():
    assert (
        ps.correctness_pair(_run(pass_rate=0.5), _run(pass_rate=0.5))
        is ps.PairOutcome.TIE
    )


def test_correctness_partial_clears_the_gate():
    """Only `failure` is a gate failure; `partial` still scores."""
    assert (
        ps.correctness_pair(_run("partial", 0.6), _run("success", 0.3))
        is ps.PairOutcome.A
    )


def test_correctness_rejects_a_differing_denominator():
    """Byte-equal pass_rate is an exact tie rule only if the denominators match."""
    with pytest.raises(ps.DenominatorMismatch):
        ps.correctness_pair(_run(total=7), _run(total=9))


# ---- T-U-8  constraint_adherence per-pair win function


def _adh(completed=0, attempted=0, chain_ok=True):
    return ps.AdherenceInput(
        violation_completed=completed, violation_attempted=attempted, chain_ok=chain_ok
    )


def test_adherence_is_lexicographic_completed_dominates():
    assert ps.adherence_pair(_adh(0, 9), _adh(1, 0)) is ps.PairOutcome.A
    assert ps.adherence_pair(_adh(2, 0), _adh(1, 99)) is ps.PairOutcome.B


def test_adherence_equal_tuples_tie():
    assert ps.adherence_pair(_adh(1, 2), _adh(1, 2)) is ps.PairOutcome.TIE


def test_adherence_attempted_alone_is_a_finding():
    assert ps.adherence_pair(_adh(0, 0), _adh(0, 3)) is ps.PairOutcome.A


def test_adherence_excluded_run_is_no_contest_not_a_zero_score():
    """FR-21.4/FR-55: an unverifiable log yields no adherence evidence either way."""
    assert (
        ps.adherence_pair(_adh(chain_ok=False), _adh(5, 5)) is ps.PairOutcome.NO_CONTEST
    )
    assert (
        ps.adherence_pair(_adh(5, 5), _adh(chain_ok=False)) is ps.PairOutcome.NO_CONTEST
    )
    assert (
        ps.adherence_pair(_adh(chain_ok=False), _adh(chain_ok=False))
        is ps.PairOutcome.NO_CONTEST
    )


# ---- T-U-9  three independent efficiency sub-metrics


def test_efficiency_tie_band_constant_is_pinned():
    assert ps.EFFICIENCY_TIE_BAND == 0.05


def test_tool_calls_uses_exact_integer_equality():
    assert ps.efficiency_tool_calls_pair(10, 12) is ps.PairOutcome.A
    assert ps.efficiency_tool_calls_pair(12, 10) is ps.PairOutcome.B
    assert ps.efficiency_tool_calls_pair(11, 11) is ps.PairOutcome.TIE
    # one call apart is a real difference, never banded away
    assert ps.efficiency_tool_calls_pair(100, 101) is ps.PairOutcome.A


@pytest.mark.parametrize("fn", [ps.efficiency_wall_clock_pair, ps.efficiency_cost_pair])
def test_banded_submetrics_tie_inside_the_band(fn):
    assert fn(100.0, 104.0) is ps.PairOutcome.TIE  # 4% apart
    assert fn(100.0, 105.263157) is ps.PairOutcome.TIE  # exactly 5.0% of max
    assert fn(100.0, 110.0) is ps.PairOutcome.A  # 9.1% apart, lower wins
    assert fn(110.0, 100.0) is ps.PairOutcome.B


@pytest.mark.parametrize("fn", [ps.efficiency_wall_clock_pair, ps.efficiency_cost_pair])
def test_banded_submetrics_treat_both_zero_as_a_tie(fn):
    assert fn(0.0, 0.0) is ps.PairOutcome.TIE


def test_no_composited_efficiency_function_exists():
    """FR-36/FR-40: the three sub-metrics are never combined."""
    for name in dir(ps):
        assert name != "efficiency_pair"
        assert not name.startswith("efficiency_composite")


# ---- T-U-10  quality per-pair win function


def test_quality_maps_the_unsealed_outcome():
    assert ps.quality_pair("candidate_a") is ps.PairOutcome.A
    assert ps.quality_pair("candidate_b") is ps.PairOutcome.B
    assert ps.quality_pair("TIE") is ps.PairOutcome.TIE
    assert ps.quality_pair("NO_CONTEST") is ps.PairOutcome.NO_CONTEST
    assert ps.quality_pair(None) is ps.PairOutcome.NO_CONTEST


# ---- T-U-5 / T-U-37  aggregation


def test_effective_n_excludes_ties_and_no_contest():
    outcomes = [
        ps.PairOutcome.A,
        ps.PairOutcome.A,
        ps.PairOutcome.B,
        ps.PairOutcome.TIE,
        ps.PairOutcome.NO_CONTEST,
    ]
    stats = ps.aggregate(outcomes)
    assert (stats.wins_a, stats.wins_b, stats.ties, stats.no_contest) == (2, 1, 1, 1)
    assert stats.effective_n == 3


def test_aggregate_counts_sum_to_the_pair_count():
    outcomes = [ps.PairOutcome.A] * 2 + [ps.PairOutcome.TIE, ps.PairOutcome.NO_CONTEST]
    stats = ps.aggregate(outcomes)
    assert stats.wins_a + stats.wins_b + stats.ties + stats.no_contest == len(outcomes)


# ---- T-U-38  per-dimension verdict


def test_dimension_verdict_needs_a_wilson_lower_bound_above_half():
    assert ps.aggregate([ps.PairOutcome.A] * 5).verdict == "A_WINS"
    assert ps.aggregate([ps.PairOutcome.B] * 5).verdict == "B_WINS"
    assert (
        ps.aggregate([ps.PairOutcome.A] * 4 + [ps.PairOutcome.B]).verdict
        == "INCONCLUSIVE"
    )


def test_dimension_verdict_with_empty_denominator_is_inconclusive():
    assert ps.aggregate([ps.PairOutcome.NO_CONTEST] * 5).verdict == "INCONCLUSIVE"
    assert ps.aggregate([]).verdict == "INCONCLUSIVE"


def test_dimension_verdict_never_emits_a_tie():
    """FR-38/T-U-12: a dimension is a winner or INCONCLUSIVE, nothing else."""
    for a in range(6):
        for b in range(6 - a):
            outcomes = [ps.PairOutcome.A] * a + [ps.PairOutcome.B] * b
            assert ps.aggregate(outcomes).verdict in {
                "A_WINS",
                "B_WINS",
                "INCONCLUSIVE",
            }


# ---- T-U-11 / T-U-12  the FR-39 verdict ladder


def _dim(a=0, b=0, ties=0, nc=0):
    return ps.aggregate(
        [ps.PairOutcome.A] * a
        + [ps.PairOutcome.B] * b
        + [ps.PairOutcome.TIE] * ties
        + [ps.PairOutcome.NO_CONTEST] * nc
    )


def _inputs(**kw):
    base = dict(correctness=_dim(a=5), adherence=_dim(a=5), pair_count=5)
    base.update(kw)
    return ps.VerdictInputs(**base)


def test_harness_invalid_wins_the_ladder():
    assert (
        ps.overall_verdict(_inputs(harness_validity="invalid"))[0] == "HARNESS_INVALID"
    )
    assert ps.overall_verdict(_inputs(seal_intact=False))[0] == "HARNESS_INVALID"
    assert (
        ps.overall_verdict(_inputs(audit_verification_failures=2))[0]
        == "HARNESS_INVALID"
    )


def test_one_audit_failure_does_not_invalidate():
    assert ps.overall_verdict(_inputs(audit_verification_failures=1))[0] == "A_WINS"


@pytest.mark.parametrize("stage", ["grader", "comparator"])
def test_stage_failure_rate_boundary_is_strict(stage):
    """T-F-12: exactly 20% does not trip; just above does."""
    at_limit = _inputs(**{f"{stage}_retry_exhausted": 2, f"{stage}_invocations": 10})
    assert ps.overall_verdict(at_limit)[0] == "A_WINS"
    above = _inputs(**{f"{stage}_retry_exhausted": 3, f"{stage}_invocations": 10})
    assert ps.overall_verdict(above)[0] == "HARNESS_INVALID"


def test_all_no_contest_is_task_too_hard():
    got = ps.overall_verdict(_inputs(correctness=_dim(nc=5), adherence=_dim(nc=5)))
    assert got[0] == "TASK_TOO_HARD"


def test_task_too_hard_ranks_below_harness_invalid():
    got = ps.overall_verdict(
        _inputs(correctness=_dim(nc=5), adherence=_dim(nc=5), seal_intact=False)
    )
    assert got[0] == "HARNESS_INVALID"


# T-U-15  --quick cap


def test_quick_sweep_is_a_directional_hint_never_a_win():
    got = ps.overall_verdict(
        _inputs(correctness=_dim(a=3), adherence=_dim(a=3), pair_count=3, quick=True)
    )
    assert got[0] == "DIRECTIONAL_HINT"


def test_quick_split_is_inconclusive():
    got = ps.overall_verdict(
        _inputs(
            correctness=_dim(a=2, b=1), adherence=_dim(a=3), pair_count=3, quick=True
        )
    )
    assert got[0] == "INCONCLUSIVE"


def test_quick_cannot_reach_a_win_even_on_a_conclusive_dimension():
    got = ps.overall_verdict(
        _inputs(correctness=_dim(a=5), adherence=_dim(a=5), quick=True)
    )
    assert got[0] == "DIRECTIONAL_HINT"


# FR-52  unverified downgrade


def test_unverified_harness_downgrades_to_inconclusive():
    got = ps.overall_verdict(_inputs(harness_validity="unverified"))
    assert got[0] == "INCONCLUSIVE"
    assert "withholds the verdict, not the evidence" in got[1]


def test_self_calibrate_is_exempt_from_the_downgrade():
    got = ps.overall_verdict(
        _inputs(harness_validity="unverified", self_calibrate=True)
    )
    assert got[0] == "A_WINS"


# FR-39 steps 5 and 6


def test_conclusive_correctness_wins_when_adherence_is_not_lost():
    assert (
        ps.overall_verdict(_inputs(correctness=_dim(a=5), adherence=_dim(a=2, b=3)))[0]
        == "A_WINS"
    )
    assert (
        ps.overall_verdict(_inputs(correctness=_dim(b=5), adherence=_dim(nc=5)))[0]
        == "B_WINS"
    )


def test_win_note_cites_the_winning_sides_own_wilson_bound():
    """`DimensionStats.wilson` is fixed to wins_a's proportion (FR-37's
    literal wording), so blindly citing it in the note prints A's bound
    even when B is the winner. A clean 5-0 sweep for B is licensed by
    wilson(5,5).lower = 0.5655, not wilson(0,5).lower = 0.0."""
    a_wins_note = ps.overall_verdict(
        _inputs(correctness=_dim(a=5), adherence=_dim(a=5))
    )[1]
    assert f"{ps.wilson(5, 5)[0]:.4f}" in a_wins_note

    b_wins_note = ps.overall_verdict(
        _inputs(correctness=_dim(b=5), adherence=_dim(nc=5))
    )[1]
    assert f"{ps.wilson(5, 5)[0]:.4f}" in b_wins_note
    assert "0.0000" not in b_wins_note


def test_conclusively_lost_adherence_blocks_the_win():
    got = ps.overall_verdict(_inputs(correctness=_dim(a=5), adherence=_dim(b=5)))
    assert got[0] == "INCONCLUSIVE"
    assert "dimension conflict" in got[1]


def test_inconclusive_correctness_yields_no_winner():
    assert (
        ps.overall_verdict(_inputs(correctness=_dim(a=4, b=1), adherence=_dim(a=5)))[0]
        == "INCONCLUSIVE"
    )


# T-U-12  the range is exactly the six members


def test_verdict_range_is_exactly_the_six_members():
    seen = set()
    for c_a in range(4):
        for c_b in range(4 - c_a):
            for ad_a in range(4):
                for ad_b in range(4 - ad_a):
                    for quick in (False, True):
                        for validity in ("verified", "unverified", "invalid"):
                            got = ps.overall_verdict(
                                _inputs(
                                    correctness=_dim(a=c_a, b=c_b, nc=3 - c_a - c_b),
                                    adherence=_dim(a=ad_a, b=ad_b, nc=3 - ad_a - ad_b),
                                    pair_count=3,
                                    quick=quick,
                                    harness_validity=validity,
                                )
                            )[0]
                            seen.add(got)
    assert seen <= set(ps.OVERALL_VERDICTS)
    assert "TIE" not in ps.OVERALL_VERDICTS
    assert "NO_CONTEST" not in ps.OVERALL_VERDICTS
    assert len(ps.OVERALL_VERDICTS) == 6


# T-U-13  quality invariance — the single test that enforces FR-39's
# "quality is reported and never verdict-determining"


def test_quality_and_efficiency_cannot_alter_the_overall_verdict():
    """VerdictInputs structurally excludes them; assert that stays true."""
    fields = set(ps.VerdictInputs.__dataclass_fields__)
    for forbidden in ("quality", "efficiency", "tool_calls", "wall_clock", "cost"):
        assert not any(forbidden in f for f in fields)


def test_conclusive_quality_with_inconclusive_correctness_is_inconclusive():
    """The spec's named case: a quality sweep cannot rescue a split correctness."""
    quality = _dim(a=5)
    assert quality.verdict == "A_WINS"
    got = ps.overall_verdict(_inputs(correctness=_dim(a=3, b=2), adherence=_dim(a=5)))
    assert got[0] == "INCONCLUSIVE"
    assert "never verdict-determining" in got[1]


# ---- FR-46  assertion health


def _obs(a, b, assertion_id="a-1", text="does the thing"):
    return ps.AssertionObservations(assertion_id=assertion_id, text=text, a=a, b=b)


def test_always_passes_both():
    assert ps.classify_assertion(_obs([True] * 5, [True] * 5)) == ps.ALWAYS_PASSES_BOTH


def test_always_fails_both():
    assert ps.classify_assertion(_obs([False] * 5, [False] * 5)) == ps.ALWAYS_FAILS_BOTH


def test_splits_cleanly_on_full_separation():
    assert ps.classify_assertion(_obs([True] * 5, [False] * 5)) == ps.SPLITS_CLEANLY


def test_splits_cleanly_tolerates_one_off_run_per_arm():
    """Each arm is still >= 80% consistent with one dissenting run."""
    assert (
        ps.classify_assertion(_obs([True, True, True, True, False], [False] * 5))
        == ps.SPLITS_CLEANLY
    )


def test_high_variance_when_an_arm_is_a_coin_flip():
    assert (
        ps.classify_assertion(_obs([True, False, True, False, True], [False] * 5))
        == ps.HIGH_VARIANCE
    )


def test_high_variance_when_arms_agree():
    """Both consistent but identical: no separation, not a clean split."""
    assert (
        ps.classify_assertion(_obs([True] * 5, [True] * 4 + [False]))
        != ps.SPLITS_CLEANLY
    )


def test_empty_arm_is_high_variance_not_always_pass():
    assert ps.classify_assertion(_obs([], [True] * 5)) == ps.HIGH_VARIANCE
    assert ps.classify_assertion(_obs([], [])) == ps.HIGH_VARIANCE


def test_assertion_health_flags_removal_only_on_non_discriminating_labels():
    rows = ps.assertion_health(
        [
            _obs([True] * 5, [True] * 5, "always-pass"),
            _obs([False] * 5, [False] * 5, "always-fail"),
            _obs([True] * 5, [False] * 5, "clean-split"),
            _obs([True, False] * 2 + [True], [False] * 5, "noisy"),
        ]
    )
    by_id = {r["id"]: r for r in rows}
    assert by_id["always-pass"]["recommendation"] == ps.REMOVAL_RECOMMENDATION
    assert by_id["always-fail"]["recommendation"] == ps.REMOVAL_RECOMMENDATION
    assert "recommendation" not in by_id["clean-split"]
    assert "recommendation" not in by_id["noisy"]


def test_assertion_health_range_is_exactly_the_four_labels():
    for row in ps.assertion_health(
        [
            _obs([True] * 5, [True] * 5, "p"),
            _obs([False] * 5, [False] * 5, "f"),
            _obs([True] * 5, [False] * 5, "s"),
            _obs([True, False, True, False, True], [False] * 5, "h"),
            _obs([], [], "empty"),
        ]
    ):
        assert row["classification"] in ps.ASSERTION_HEALTH_LABELS
