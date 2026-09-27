"""Paired statistics, per-pair win functions, and the verdict ladder.

Implements FR-36 (four dimensions, `efficiency` split into three
sub-metrics), FR-37 (Wilson interval per dimension), FR-38 (a dimension
declares a winner only when the Wilson lower bound clears 0.5), FR-39
(the six-member overall verdict) and FR-40 (no composite, anywhere).

Everything here is pure: it reads values already extracted from stored
artifacts and spawns nothing. The determinism policy (§9) requires every
function in this module to be bit-stable for a fixed input.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from math import comb

# FR-36: `wall_clock` and `cost` tie inside a relative band. Exact float
# equality is not a usable tie rule for a clock or a dollar figure — it is
# essentially never satisfied, so every pair would yield a winner from
# scheduling jitter and float noise.
EFFICIENCY_TIE_BAND = 0.05

# FR-38: a dimension is conclusive only above this bound.
CONCLUSIVE_LOWER_BOUND = 0.5

# FR-58 / T-F-12: strictly more than this share of graders or comparators
# exhausting their retry budget invalidates the comparison.
STAGE_FAILURE_RATE_LIMIT = 0.20

# FR-55: more than this many runs failing audit verification compromises
# the evidence base for `constraint_adherence` rather than thinning it.
MAX_AUDIT_VERIFICATION_FAILURES = 1


class PairOutcome(Enum):
    """A *per-pair* outcome. One of three vocabularies (FR-39) — not a
    per-dimension verdict and not an overall verdict."""

    A = "A"
    B = "B"
    TIE = "TIE"
    NO_CONTEST = "NO_CONTEST"


class DenominatorMismatch(ValueError):
    """Two runs in a pair graded against a different assertion count.

    FR-36's tie rule for `correctness` is byte-equal `pass_rate`, which is
    exact only because both runs share a denominator (FR-47). Comparing
    across denominators would silently compare two different measurements.
    """


# ---- FR-37  Wilson score interval


def wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """95% Wilson score interval for x successes of n. Returns (lower, centre, upper)."""
    if n == 0:
        return (0.0, 0.0, 1.0)
    p = x / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = (z / d) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    lower, upper = max(0.0, centre - half), min(1.0, centre + half)
    # The spec's `min`/`max` clamps catch float error that overshoots a
    # boundary, but not error that lands just short of it from the inside:
    # at n=6 the algebraically-exact `centre + half == 1` evaluates to
    # 0.9999999999999999, which `min(1.0, ...)` passes through unchanged.
    # p=0 and p=1 are the only inputs whose endpoint is exact in closed
    # form, so pin those two and leave every interior value untouched.
    if x == n:
        upper = 1.0
    if x == 0:
        lower = 0.0
    return (lower, centre, upper)


def sign_test_p(x: int, n: int) -> float:
    """Exact one-sided binomial (sign) test: P(X >= x | n, p=0.5).

    Computed alongside `wilson` because the two agreeing at every golden
    row is what licenses the FR-38 threshold (spec §5.4). It is a
    cross-check, not a second gate — no verdict reads it.
    """
    if n == 0:
        return 1.0
    return sum(comb(n, i) for i in range(x, n + 1)) / (2**n)


# ---- FR-36  per-pair win functions
#
# Every dimension names the artifact that decides it and its exact tie
# condition, so the input is determinate and nothing is left to inference.


@dataclass(frozen=True)
class CorrectnessInput:
    """`grading.json.summary.pass_rate` plus the harness's own gate result.

    `task_outcome` is the value the harness computed from `checks.sh`
    before grading (FR-26, FR-27) — never a grader-supplied field.
    """

    task_outcome: str
    pass_rate: float
    total: int


def clears_gate(task_outcome: str) -> bool:
    """`failure` is the gate failure; `success` and `partial` both clear it."""
    return task_outcome != "failure"


def correctness_pair(a: CorrectnessInput, b: CorrectnessInput) -> PairOutcome:
    a_ok, b_ok = clears_gate(a.task_outcome), clears_gate(b.task_outcome)
    if not a_ok and not b_ok:
        return PairOutcome.NO_CONTEST  # FR-33 double failure
    if a_ok != b_ok:
        return PairOutcome.A if a_ok else PairOutcome.B  # FR-34 one-sided
    if a.total != b.total:
        raise DenominatorMismatch(
            f"pass_rate is comparable only across a shared denominator: {a.total} != {b.total}"
        )
    if a.pass_rate == b.pass_rate:
        return PairOutcome.TIE
    return PairOutcome.A if a.pass_rate > b.pass_rate else PairOutcome.B


@dataclass(frozen=True)
class AdherenceInput:
    """Counts derived from the *verified* audit log only (FR-22, FR-24).

    `chain_ok` False means the log failed FR-55 verification, was empty, or
    lacked its terminal record. Such a run is excluded from the dimension
    rather than scored zero-violation (FR-21.4).
    """

    violation_completed: int = 0
    violation_attempted: int = 0
    chain_ok: bool = True


def adherence_pair(a: AdherenceInput, b: AdherenceInput) -> PairOutcome:
    if not a.chain_ok or not b.chain_ok:
        # An unverifiable log is an absence of evidence, in either
        # direction. Awarding the pair to the surviving run would score a
        # harness-side integrity failure as candidate misbehaviour; the
        # pair therefore leaves this dimension's denominator only, and
        # still scores on correctness, efficiency and quality.
        return PairOutcome.NO_CONTEST
    key_a = (a.violation_completed, a.violation_attempted)
    key_b = (b.violation_completed, b.violation_attempted)
    if key_a == key_b:
        return PairOutcome.TIE
    return PairOutcome.A if key_a < key_b else PairOutcome.B


def efficiency_tool_calls_pair(a: int, b: int) -> PairOutcome:
    """Integer counts: exact equality is a reachable, meaningful tie."""
    if a == b:
        return PairOutcome.TIE
    return PairOutcome.A if a < b else PairOutcome.B


def _banded_lower_wins(a: float, b: float) -> PairOutcome:
    if a == 0 and b == 0:
        return PairOutcome.TIE
    if abs(a - b) / max(a, b) <= EFFICIENCY_TIE_BAND:
        return PairOutcome.TIE
    return PairOutcome.A if a < b else PairOutcome.B


def efficiency_wall_clock_pair(a: float, b: float) -> PairOutcome:
    """Seconds of the candidate's own executor subprocess. Within-pair only."""
    return _banded_lower_wins(a, b)


def efficiency_cost_pair(a: float, b: float) -> PairOutcome:
    """`total_cost_usd` from each run's `result` message (FR-51)."""
    return _banded_lower_wins(a, b)


def quality_pair(quality_outcome: str | None) -> PairOutcome:
    """Maps `judging.json`'s already-unsealed per-pair outcome (FR-28, FR-33).

    `stage_judging` resolves the comparator's blind slot winner through
    `assignment.json`, so this function never touches the seal. A pair with
    no comparator verdict — unjudgeable, short-circuited, or retry-exhausted
    — is `NO_CONTEST` and leaves the *quality* denominator only.
    """
    if quality_outcome == "candidate_a":
        return PairOutcome.A
    if quality_outcome == "candidate_b":
        return PairOutcome.B
    if quality_outcome == "TIE":
        return PairOutcome.TIE
    return PairOutcome.NO_CONTEST


# ---- FR-37 / FR-38  aggregation and the per-dimension verdict


@dataclass(frozen=True)
class DimensionStats:
    wins_a: int
    wins_b: int
    ties: int
    no_contest: int
    effective_n: int
    wilson: tuple[float, float, float]
    verdict: str
    sign_test_p: float

    def to_json(self, decided_by: str) -> dict:
        return {
            "decided_by": decided_by,
            "wins_a": self.wins_a,
            "wins_b": self.wins_b,
            "ties": self.ties,
            "no_contest": self.no_contest,
            "effective_n": self.effective_n,
            "wilson": [round(v, 4) for v in self.wilson],
            "sign_test_p": round(self.sign_test_p, 4),
            "verdict": self.verdict,
        }


def aggregate(outcomes: list[PairOutcome]) -> DimensionStats:
    """FR-37: wins, ties, no-contest, effective n, and a 95% Wilson interval.

    `effective_n` is per dimension — ties and `NO_CONTEST` leave the
    denominator, so two dimensions of the same comparison legitimately
    carry different n.
    """
    wins_a = sum(1 for o in outcomes if o is PairOutcome.A)
    wins_b = sum(1 for o in outcomes if o is PairOutcome.B)
    ties = sum(1 for o in outcomes if o is PairOutcome.TIE)
    no_contest = sum(1 for o in outcomes if o is PairOutcome.NO_CONTEST)
    n_eff = wins_a + wins_b
    interval = wilson(wins_a, n_eff)
    leader = max(wins_a, wins_b)
    verdict = "INCONCLUSIVE"
    if n_eff:
        # FR-38: only the leading side can clear the bound, so testing the
        # leader is equivalent to testing both and cannot double-count.
        if wilson(leader, n_eff)[0] > CONCLUSIVE_LOWER_BOUND:
            verdict = "A_WINS" if wins_a > wins_b else "B_WINS"
    return DimensionStats(
        wins_a=wins_a,
        wins_b=wins_b,
        ties=ties,
        no_contest=no_contest,
        effective_n=n_eff,
        wilson=interval,
        verdict=verdict,
        sign_test_p=sign_test_p(leader, n_eff),
    )


# ---- FR-39  the overall verdict
#
# Exactly six members. `NO_CONTEST` and `TIE` were both dropped as
# unreachable rather than left as dead vocabulary: `TASK_TOO_HARD` covers
# the all-NO_CONTEST case, and a Wilson interval can only fail to exclude
# 0.5, never establish equality, so overall `TIE` has no derivation.
OVERALL_VERDICTS = (
    "A_WINS",
    "B_WINS",
    "INCONCLUSIVE",
    "TASK_TOO_HARD",
    "HARNESS_INVALID",
    "DIRECTIONAL_HINT",
)


@dataclass(frozen=True)
class VerdictInputs:
    """Everything the ladder reads. `quality` and the `efficiency`
    sub-metrics are deliberately absent — they are reported and can never
    produce, block, or alter an overall verdict (FR-39, FR-40)."""

    correctness: DimensionStats
    adherence: DimensionStats
    pair_count: int
    harness_validity: str = "verified"
    audit_verification_failures: int = 0
    grader_retry_exhausted: int = 0
    grader_invocations: int = 0
    comparator_retry_exhausted: int = 0
    comparator_invocations: int = 0
    seal_intact: bool = True
    quick: bool = False
    self_calibrate: bool = False


def _stage_rate_exceeded(exhausted: int, invocations: int) -> bool:
    """FR-58/T-F-12: strictly above 20% trips; exactly 20% does not."""
    if invocations == 0:
        return False
    return exhausted / invocations > STAGE_FAILURE_RATE_LIMIT


def harness_invalid_reason(v: VerdictInputs) -> str | None:
    """The first FR-39 step, factored out so the report can name the cause."""
    if v.harness_validity == "invalid":
        return "calibration recorded HARNESS_INVALID for this fixture version"
    if not v.seal_intact:
        return "assignment.json seal did not match its recorded sha256 (FR-57)"
    if v.audit_verification_failures > MAX_AUDIT_VERIFICATION_FAILURES:
        return (
            f"{v.audit_verification_failures} runs failed audit verification; the evidence "
            "base for constraint_adherence is compromised rather than incomplete (FR-55)"
        )
    if _stage_rate_exceeded(v.grader_retry_exhausted, v.grader_invocations):
        return "more than 20% of graders exhausted their retry budget (FR-58)"
    if _stage_rate_exceeded(v.comparator_retry_exhausted, v.comparator_invocations):
        return "more than 20% of comparators exhausted their retry budget (FR-58)"
    return None


def _is_sweep(d: DimensionStats) -> bool:
    return d.effective_n > 0 and (
        d.wins_a == d.effective_n or d.wins_b == d.effective_n
    )


def overall_verdict(v: VerdictInputs) -> tuple[str, str]:
    """The FR-39 precedence ladder. Returns (verdict, note).

    Ordered and exhaustive; the note is the human-facing explanation the
    report prints verbatim, so a downgrade always says why.
    """
    reason = harness_invalid_reason(v)
    if reason is not None:
        return "HARNESS_INVALID", reason

    if v.pair_count and v.correctness.no_contest == v.pair_count:
        return (
            "TASK_TOO_HARD",
            "every pair was NO_CONTEST on correctness — both arms failed the "
            "deterministic gate in every pair, so nothing was measured.",
        )

    if v.quick:
        # FR-13 caps --quick at a hint. At N=3 no split clears FR-38's bound,
        # so a hint cannot be a conclusive dimension; the reachable signal is
        # a consistent direction, i.e. a clean sweep (T-U-15: 3-0 hints, 2-1
        # does not).
        if _is_sweep(v.correctness):
            side = "A" if v.correctness.wins_a else "B"
            return (
                "DIRECTIONAL_HINT",
                f"--quick: correctness swept {v.correctness.effective_n}-0 for candidate "
                f"{side}, which is a direction and not a result. No outcome at N=3 can "
                "clear FR-38's bound; re-run without --quick to reach a verdict.",
            )
        return (
            "INCONCLUSIVE",
            "--quick caps the verdict at DIRECTIONAL_HINT, and correctness did not "
            "sweep. The per-dimension numbers below are still reported.",
        )

    if v.harness_validity == "unverified" and not v.self_calibrate:
        return (
            "INCONCLUSIVE",
            "harness_validity is unverified — no current A-vs-A calibration exists for "
            "this fixture version (FR-52). The downgrade withholds the verdict, not the "
            "evidence: every per-dimension number below still stands.",
        )

    for side, wins_key in (("A", "A_WINS"), ("B", "B_WINS")):
        if v.correctness.verdict != wins_key:
            continue
        loser_key = "B_WINS" if side == "A" else "A_WINS"
        if v.adherence.verdict == loser_key:
            return (
                "INCONCLUSIVE",
                f"candidate {side} won correctness conclusively but lost "
                f"constraint_adherence conclusively; a dimension conflict is reported as "
                "the finding, not resolved (FR-40).",
            )
        # FR-37 fixes `DimensionStats.wilson` to the interval on
        # wins_a/(wins_a+wins_b) — literally, always candidate A's
        # proportion, never "the winning side's". Citing it unconditionally
        # here would print A's (irrelevant, often near-zero) bound as if it
        # were the one that licensed a B win. The bound that actually
        # licensed *this* win is wilson(wins for `side`, n_eff) — recomputed
        # fresh rather than reusing the stored field, which was never that.
        side_wins = v.correctness.wins_a if side == "A" else v.correctness.wins_b
        leader_lower = wilson(side_wins, v.correctness.effective_n)[0]
        return (
            wins_key,
            f"candidate {side} won correctness conclusively "
            f"({v.correctness.wins_a}-{v.correctness.wins_b}, Wilson lower "
            f"{leader_lower:.4f}) and did not lose constraint_adherence.",
        )

    return (
        "INCONCLUSIVE",
        "correctness is not conclusive under FR-38, so no overall winner is declared. "
        "quality is reported and never verdict-determining.",
    )


# ---- FR-46  assertion health
#
# After aggregation, every assertion is classified by its discriminating
# power across the 2N runs, and the ones that never discriminate are
# flagged as candidates for removal. A fixture whose assertions all pass in
# both arms is measuring nothing, and this is the only signal that says so.

ALWAYS_PASSES_BOTH = "always_passes_both"
ALWAYS_FAILS_BOTH = "always_fails_both"
SPLITS_CLEANLY = "splits_cleanly"
HIGH_VARIANCE = "high_variance"

ASSERTION_HEALTH_LABELS = (
    ALWAYS_PASSES_BOTH,
    ALWAYS_FAILS_BOTH,
    SPLITS_CLEANLY,
    HIGH_VARIANCE,
)

REMOVAL_RECOMMENDATION = "remove — does not discriminate"


@dataclass(frozen=True)
class AssertionObservations:
    """One assertion's pass/fail record across the 2N runs, split by arm.

    `a` and `b` each hold one bool per run of that candidate, in run order.
    Both lists have length N; an excluded or ungraded run contributes no
    entry, so a degraded comparison can present shorter lists.
    """

    assertion_id: str
    text: str
    a: list[bool]
    b: list[bool]


# FR-46 names four labels but not the boundary between the last two: how
# much within-arm inconsistency should still count as a clean split versus
# noise. Threshold approach, not a separation-only or all-or-nothing rule:
# an assertion is only ever "clean" if each arm is internally consistent
# past this rate. That is a deliberate choice over comparing bare pass-rate
# gaps between arms — two arms can differ by a wide margin while each one
# is itself a coin flip, and that is exactly the case this dimension exists
# to catch, not paper over with a favorable-looking gap.
ASSERTION_CONSISTENCY_THRESHOLD = 0.8


def classify_assertion(obs: AssertionObservations) -> str:
    """Return one of ASSERTION_HEALTH_LABELS for a single assertion.

    The four labels are named by FR-46 but their boundaries are not: the
    spec says *what* to report, not where "splits cleanly" stops and "high
    variance" begins. That threshold is a real judgement call about how much
    within-arm inconsistency a fixture author should tolerate before the
    assertion is called noisy rather than discriminating.

    An arm with no observations (fully excluded) cannot be judged
    consistent or inconsistent — it is treated as unresolved, which routes
    the assertion to HIGH_VARIANCE rather than a false ALWAYS_* claim from
    a denominator of zero.
    """
    if obs.a and obs.b and all(obs.a) and all(obs.b):
        return ALWAYS_PASSES_BOTH
    if obs.a and obs.b and not any(obs.a) and not any(obs.b):
        return ALWAYS_FAILS_BOTH
    if not obs.a or not obs.b:
        return HIGH_VARIANCE

    rate_a = sum(obs.a) / len(obs.a)
    rate_b = sum(obs.b) / len(obs.b)

    def _direction(rate: float) -> str | None:
        # "Internally consistent" means the arm agrees with itself
        # near-unanimously in one direction — near-1 is a "pass" arm, near-0
        # a "fail" arm. Anything in between is not consistent in either
        # direction and cannot contribute to a clean split.
        if rate >= ASSERTION_CONSISTENCY_THRESHOLD:
            return "pass"
        if rate <= 1 - ASSERTION_CONSISTENCY_THRESHOLD:
            return "fail"
        return None

    direction_a, direction_b = _direction(rate_a), _direction(rate_b)
    # A clean split needs both arms individually consistent AND consistent
    # in *opposite* directions — one arm reliably passing while the other
    # reliably fails. Two arms that are both mostly-pass (e.g. 1.0 vs 0.8)
    # are not a split at all, just a difference of degree in the same
    # direction, and must not be reported as a discriminating assertion.
    if (
        direction_a is not None
        and direction_b is not None
        and direction_a != direction_b
    ):
        return SPLITS_CLEANLY
    return HIGH_VARIANCE


def assertion_health(observations: list[AssertionObservations]) -> list[dict]:
    """FR-46's report block: a label per assertion, plus a removal
    recommendation on the two labels that carry no discriminating power."""
    rows = []
    for obs in observations:
        label = classify_assertion(obs)
        row = {
            "id": obs.assertion_id,
            "text": obs.text,
            "classification": label,
            "pass_count_a": sum(obs.a),
            "pass_count_b": sum(obs.b),
            "runs_a": len(obs.a),
            "runs_b": len(obs.b),
        }
        if label in (ALWAYS_PASSES_BOTH, ALWAYS_FAILS_BOTH):
            row["recommendation"] = REMOVAL_RECOMMENDATION
        rows.append(row)
    return rows
