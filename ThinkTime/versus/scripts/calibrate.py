#!/usr/bin/env python3
"""A-vs-A null calibration — internal module, never a user-facing command
(FR-59, SM1, FR-52). Reached only through `run --self-calibrate`; `run
--self-calibrate --runs N` with `N < 9` is refused here, not only in
`cli.py` (defence in depth against a non-CLI caller, e.g. a batch script
— FR-13).

Calibration records and the pooled positional ledger are stored *with the
fixture* (`<fixture_dir>/calibration.jsonl`, `.../positional_ledger.jsonl`)
rather than in a comparison workspace: FR-52's staleness test compares a
calibration against the fixture's OWN `fixture_version`, and that
comparison must still be answerable long after the workspace that
produced it was cleaned (FR-61). The fixture directory is the only thing
guaranteed to outlive any one comparison.

Stdlib only.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from math import comb
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

CALIBRATION_FLOOR = 9

# SM1: "evaluated over every dimension and every efficiency sub-metric" —
# three dimensions (correctness, constraint_adherence, quality) plus three
# efficiency sub-metrics (tool_calls, wall_clock, cost) = six tests. This
# is deliberately wider than FR-39's overall-verdict inputs: `quality`
# never decides an overall verdict, but SM1 is a harness-asymmetry probe,
# and positional bias in the blind comparator is exactly where it would
# show up.
SM1_DIMENSION_PATHS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("correctness", ("dimensions", "correctness")),
    ("constraint_adherence", ("dimensions", "constraint_adherence")),
    ("quality", ("dimensions", "quality")),
    ("efficiency.tool_calls", ("dimensions", "efficiency", "tool_calls")),
    ("efficiency.wall_clock", ("dimensions", "efficiency", "wall_clock")),
    ("efficiency.cost", ("dimensions", "efficiency", "cost")),
)

CALIBRATION_RECORD_FILE = "calibration.jsonl"
POSITIONAL_LEDGER_FILE = "positional_ledger.jsonl"
POOLED_LEDGER_MIN_PAIRS = 20
POOLED_ALPHA = 0.05


class CalibrationFloorError(ValueError):
    """N < 9 refused at launch time — not clamped, not warned-and-run."""


class CalibrationRunError(RuntimeError):
    """The underlying `run --self-calibrate` comparison failed to produce
    a usable report; SM1 cannot be evaluated."""


def validate_runs(runs: int) -> None:
    if runs < CALIBRATION_FLOOR:
        raise CalibrationFloorError(
            f"calibration requires --runs >= {CALIBRATION_FLOOR} (SM1): "
            f"detector power is not monotone in N — at N={runs} the run "
            "would spend more invocations to buy strictly less evidence "
            "than the N=5 comparison it replaced (FR-13). Refusing rather "
            "than clamping so the operator holds the cost decision."
        )


# ---------------------------------------------------------------- SM1 predicate


def _dig(d: dict, path: tuple[str, ...]):
    for key in path:
        d = d[key]
    return d


def sm1_splits(report: dict) -> dict[str, dict]:
    """The six `{wins_a, wins_b, effective_n, verdict}`-shaped entries
    SM1's predicate reads, keyed by the names in `SM1_DIMENSION_PATHS`."""
    return {name: _dig(report, path) for name, path in SM1_DIMENSION_PATHS}


def evaluate_sm1(report: dict) -> dict:
    """Returns `{raw_result, per_dimension_splits, n_eff_per_dimension,
    undowngraded_verdict}`. `raw_result` is one of `pass`/`fail`/
    `inconclusive`, BEFORE the fail_unconfirmed/underpowered chain logic
    (`classify_with_history`) is applied.

    - ANY dimension or `efficiency` sub-metric with
      `effective_n < CALIBRATION_FLOOR` makes the whole attempt
      `inconclusive` — neither `pass` nor `fail`. There is NO exemption
      for a dimension that tied on every pair. FR-52 is explicit that
      "recording it as a `pass` would invert the incentive exactly: a
      *quieter* harness, one whose arms tie more often, would buy itself a
      cleaner bill of health from a test that had stopped being able to
      fail it." Ties and NO_CONTEST leave the denominator (FR-37), so a
      calibration launched at N=9 can be evaluated at `n_eff < 9`, where
      no non-sweep split can flag and the predicate has degraded into the
      weaker test the floor exists to prevent.
    - A tie-prone fixture therefore does NOT loop forever: two consecutive
      `inconclusive` records terminate in `underpowered`
      (`classify_with_history`), which reports the per-dimension tie counts
      and resulting `n_eff` so the operator can choose a larger `--runs`
      (FR-13 accepts any `N >= 9`). That terminal state, not an exemption,
      is FR-52's answer to a calibration that cannot reach the floor.
    - Otherwise `fail` if any dimension declares a winner (positional bias
      or harness asymmetry — the true effect size in A-vs-A is zero, so a
      winner is measurement artefact) or the undowngraded overall verdict
      is not `INCONCLUSIVE`.
    - Otherwise `pass`.
    """
    splits = sm1_splits(report)
    n_eff_per_dimension = {name: d["effective_n"] for name, d in splits.items()}
    per_dimension_splits = {
        name: {
            "wins_a": d["wins_a"],
            "wins_b": d["wins_b"],
            "verdict": d["verdict"],
            # Recorded so a later reader of calibration.jsonl can tell an
            # honest all-tie dimension from one where every pair was a
            # harness failure; both collapse to `n_eff == 0`.
            "ties": d.get("ties", 0),
            "no_contest": d.get("no_contest", 0),
        }
        for name, d in splits.items()
    }
    undowngraded_verdict = report["verdict"]

    # No exemption of any kind: EVERY dimension and efficiency sub-metric
    # must clear the floor. An earlier revision exempted all-tie dimensions
    # to make `pass` reachable for a deterministic candidate; FR-52 rejects
    # exactly that, because a harness whose arms tie more often would then
    # buy a cleaner bill of health from a test that had stopped being able
    # to fail it. The bounded re-run ending in `underpowered` is the
    # sanctioned way out, not a weaker predicate.
    if any(n < CALIBRATION_FLOOR for n in n_eff_per_dimension.values()):
        raw_result = "inconclusive"
    elif any(d["verdict"] != "INCONCLUSIVE" for d in splits.values()):
        raw_result = "fail"
    elif undowngraded_verdict != "INCONCLUSIVE":
        raw_result = "fail"
    else:
        raw_result = "pass"

    return {
        "raw_result": raw_result,
        "per_dimension_splits": per_dimension_splits,
        "n_eff_per_dimension": n_eff_per_dimension,
        "undowngraded_verdict": undowngraded_verdict,
    }


# ---------------------------------------------------------------- record chain


def _read_records(fixture_dir: Path) -> list[dict]:
    path = Path(fixture_dir) / CALIBRATION_RECORD_FILE
    if not path.is_file():
        return []
    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _append_record(fixture_dir: Path, record: dict) -> None:
    path = Path(fixture_dir) / CALIBRATION_RECORD_FILE
    with path.open("a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def _last_chain_relevant(records: list[dict]) -> dict | None:
    """The last record that is not a plain `inconclusive` — FR-52: "An
    `inconclusive` is chain-neutral for the two-consecutive-failure rule:
    it neither counts toward HARNESS_INVALID nor resets a prior
    `fail_unconfirmed`" — so `fail_unconfirmed -> inconclusive -> fail`
    must still see the `fail_unconfirmed` to confirm it. `underpowered`
    is NOT skipped here: it is itself chain-relevant and resets a
    pending `fail_unconfirmed` (FR-52), so it must stop the search."""
    for rec in reversed(records):
        if rec["result"] != "inconclusive":
            return rec
    return None


def classify_with_history(raw_result: str, records: list[dict]) -> str:
    """Applies FR-52's fail-confirmation and inconclusive-chaining rules
    to a fresh `raw_result`, returning the final `result` to record:
    `pass | fail | fail_unconfirmed | inconclusive | underpowered`."""
    if raw_result == "pass":
        return "pass"
    if raw_result == "fail":
        # An already-confirmed fail latches: once the harness has been
        # measured biased twice, a further failure is more evidence for that
        # conclusion, and no intervening thin attempt should downgrade it.
        # Checked before `_last_chain_relevant` because that helper stops on
        # `underpowered` (which resets a pending `fail_unconfirmed`, FR-52)
        # — correct for promoting an unconfirmed flag, wrong for demoting a
        # settled one. A later `pass` DOES supersede the fail, so scan for
        # the most recent settled state rather than for any fail at all.
        settled = None
        for rec in records:
            if rec["result"] in ("fail", "pass"):
                settled = rec["result"]
        if settled == "fail":
            return "fail"
        last = _last_chain_relevant(records)
        if last is not None and last["result"] == "fail_unconfirmed":
            return "fail"
        return "fail_unconfirmed"
    if raw_result == "inconclusive":
        # `underpowered` counts as a prior inconclusive: a third thin
        # attempt is further proof the design is underpowered at this N,
        # so the state must latch rather than alternate back.
        if records and records[-1]["result"] in ("inconclusive", "underpowered"):
            return "underpowered"
        return "inconclusive"
    raise ValueError(f"unknown raw_result: {raw_result!r}")  # pragma: no cover


def staleness_status(
    fixture_dir: Path, fixture_version: int
) -> tuple[str, dict | None]:
    """FR-52: `harness_validity` for a NORMAL (non-calibration) comparison
    against this fixture. Returns `(status, record)`:

    - `("unverified", None)` — no calibration record exists at all.
    - `("unverified", record)` — no record exists AT this
      `fixture_version`, or the chain-relevant record at it is not a
      `pass` (`fail_unconfirmed` / `inconclusive` / `underpowered`).
    - `("verified", record)` — the chain-relevant record at the current
      `fixture_version` is a `pass` and the pooled ledger has not failed.
    - `("invalid", record)` — the chain-relevant record is a confirmed
      `fail` (two consecutive calibration failures), or the pooled
      positional ledger has failed.

    Only a `pass` record satisfies the staleness test (FR-52); the other
    four all leave comparisons `unverified` except `fail`, which is
    stronger than merely unverified.

    Records are matched on `calibrated_fixture_version == fixture_version`
    and consulted through `_last_chain_relevant`, so a chain-neutral
    `inconclusive` appended after a confirmed `fail` cannot clear it, and
    a record from a different fixture version never speaks for this one.
    A failed pooled ledger yields `invalid` regardless of record shape.
    """
    records = _read_records(fixture_dir)
    if not records:
        return "unverified", None

    # The pooled positional ledger is the primary bias detector, so it is
    # consulted for EVERY record shape — not only when the latest record
    # is a `pass`. Gating it behind `pass` disabled it in exactly the case
    # it exists to cover: a fixture whose calibrations never pass while
    # its ledger accumulates unambiguous positional bias.
    ledger_failed = pooled_ledger_failed(fixture_dir, fixture_version)

    # `==` rather than `<`: a record calibrated at a DIFFERENT version is
    # not evidence about this one. `<` accepted a record from a higher
    # version, so rolling `fixture_version` back (revert, cherry-pick,
    # hand edit) left replaced fixture content reading as `verified`.
    current = [r for r in records if r["calibrated_fixture_version"] == fixture_version]
    if not current:
        return (
            ("invalid", records[-1]) if ledger_failed else ("unverified", records[-1])
        )

    latest = current[-1]

    # Latch scan, NOT "the last chain-relevant record". A settled state is
    # only displaced by another settled state: a confirmed `fail` means the
    # harness was measured biased twice, and nothing weaker than a `pass`
    # should clear that. Reading a single record — even the chain-relevant
    # one — could not express this: `_last_chain_relevant` skips
    # `inconclusive` but deliberately stops on `underpowered` (it resets a
    # pending `fail_unconfirmed`, FR-52), so two thin attempts after a
    # confirmed fail walked the fixture from `invalid` back to
    # `unverified`. `fail_unconfirmed` is likewise not settled — FR-52
    # requires two consecutive failures — so it leaves an earlier state
    # standing rather than downgrading it.
    settled = None
    settled_record = latest
    for rec in current:
        if rec["result"] in ("fail", "pass"):
            settled = rec["result"]
            settled_record = rec

    if settled == "fail":
        return "invalid", settled_record
    if ledger_failed:
        return "invalid", latest
    if settled == "pass":
        return "verified", settled_record
    return "unverified", latest


# ---------------------------------------------------------------- pooled positional ledger


def two_sided_binomial_p(k: int, n: int) -> float:
    """Exact two-sided binomial test at p=0.5: double the one-tailed
    exact p-value. Valid because Bin(n, 0.5) is symmetric about n/2, so
    the equal-tail two-sided test is exactly twice the tail beyond the
    observed count on the majority side (capped at 1.0)."""
    if n == 0:
        return 1.0
    tail = max(k, n - k)
    one_tailed = sum(comb(n, i) for i in range(tail, n + 1)) / (2**n)
    return min(1.0, 2 * one_tailed)


def _read_ledger(fixture_dir: Path) -> list[dict]:
    path = Path(fixture_dir) / POSITIONAL_LEDGER_FILE
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append_ledger_entries(fixture_dir: Path, entries: list[dict]) -> None:
    if not entries:
        return
    path = Path(fixture_dir) / POSITIONAL_LEDGER_FILE
    with path.open("a") as f:
        for entry in entries:
            f.write(json.dumps(entry, sort_keys=True) + "\n")


def positional_entries_from_judging(
    judging: dict, *, fixture_version: int, date: str
) -> list[dict]:
    """FR-52: one entry per judged pair recording which RAW judge-slot
    (`A`/`B` — the position before unsealing, i.e. `slot_winner`, never
    the unsealed candidate) won. Ties and pairs with no comparator
    verdict are not position-wins and are excluded, exactly as a tie
    leaves a dimension's `effective_n` (FR-37)."""
    entries = []
    for rec in judging.get("pairs", {}).values():
        slot_winner = rec.get("slot_winner")
        if slot_winner in ("A", "B"):
            entries.append(
                {
                    "position": slot_winner,
                    "fixture_version": fixture_version,
                    "date": date,
                }
            )
    return entries


def pooled_ledger_failed(fixture_dir: Path, fixture_version: int) -> bool:
    """FR-52: once the fixture-version-scoped ledger holds >= 20 judged
    pairs, a two-sided exact binomial test on position-wins at alpha=0.05
    is the primary positional-bias detector — the per-calibration sweep
    predicate is structurally weak at every affordable N. Scoped to the
    CURRENT fixture_version: a fixture edit is a different test, and
    pooling stale-version bias data into it would misattribute bias to a
    harness that changed underneath it."""
    entries = [
        e for e in _read_ledger(fixture_dir) if e["fixture_version"] == fixture_version
    ]
    n = len(entries)
    if n < POOLED_LEDGER_MIN_PAIRS:
        return False
    wins_a = sum(1 for e in entries if e["position"] == "A")
    return two_sided_binomial_p(wins_a, n) < POOLED_ALPHA


# ---------------------------------------------------------------- orchestration


def _default_run_comparison(ns):
    from run_comparison import run_comparison

    return run_comparison(ns)


def run_calibration(
    *,
    candidate: str,
    fixture: str,
    runs: int = CALIBRATION_FLOOR,
    workspace: str | None = None,
    parallel: int = 3,
    model: str | None = None,
    effort: str | None = None,
    unverified_fixture: bool = False,
    dry_run: bool = False,
    isolation: str = "worktree",
    double_judge: bool = False,
    keep_worktrees: str = "on-failure",
    max_budget_usd: float | None = None,
    respect_candidate_model: bool = False,
    run_comparison_fn=None,
    date: str | None = None,
) -> dict | None:
    """FR-52/SM1: run an A-vs-A comparison via `run_comparison.run_comparison`
    (`self_calibrate=True`), evaluate SM1's predicate against the
    resulting `report.json`, and append the calibration record and
    positional-ledger entries to the fixture directory. Returns the
    written calibration record, or `None` for `dry_run=True` (FR-60: the
    setup-only rehearsal spawns nothing and therefore produces no
    report.json to evaluate SM1 against).

    `run_comparison_fn` is injected so the orchestration (record chain,
    ledger, staleness) is Tier-0 testable against a canned report without
    a live comparison; the CLI path leaves it `None` and gets the real
    thing.

    `isolation`/`double_judge`/`keep_worktrees`/
    `max_budget_usd`/`respect_candidate_model` are forwarded rather than
    hardcoded: the `run` subparser accepts all five, so hardcoding them
    made them parse cleanly and then do nothing. `--max-budget-usd` in
    particular was silently discarded on the harness's most expensive
    path (`CALIBRATION_FLOOR` runs = twice that many executor spawns).
    `quick` stays False — SM1 needs the full dimension set.
    """
    validate_runs(runs)
    run_comparison_fn = run_comparison_fn or _default_run_comparison
    from run_comparison import resolve_fixture_dir

    workspace_dir = Path(workspace) if workspace else Path.home() / ".versus"
    comparison_id = "vc-cal-" + uuid.uuid4().hex[:12]
    ns = SimpleNamespace(
        candidates=[candidate],
        fixture=fixture,
        runs=runs,
        quick=False,
        parallel=parallel,
        model=model,
        effort=effort,
        isolation=isolation,
        double_judge=double_judge,
        keep_worktrees=keep_worktrees,
        max_budget_usd=max_budget_usd,
        respect_candidate_model=respect_candidate_model,
        self_calibrate=True,
        unverified_fixture=unverified_fixture,
        dry_run=dry_run,
        workspace=str(workspace_dir),
        comparison_id=comparison_id,
    )
    rc = run_comparison_fn(ns)
    if dry_run:
        return None
    cmp_dir = workspace_dir / comparison_id
    report_path = cmp_dir / "report.json"
    if rc != 0 or not report_path.is_file():
        # rc == 1 is run_comparison's HARNESS_INVALID signal (broken
        # assignment seal, comparator retry exhaustion). Such a run is one
        # the harness itself disowned, so it cannot be SM1 evidence:
        # accepting it let a plumbing failure mutate the record chain and
        # seed the pooled positional ledger with judging data from a stage
        # that declared itself untrustworthy.
        raise CalibrationRunError(
            f"calibration comparison {comparison_id} produced no usable "
            f"report.json (exit {rc})"
        )
    report = json.loads(report_path.read_text())
    fixture_dir = resolve_fixture_dir(fixture, dev=True)

    # Take the version from the report the run actually produced, not from
    # fixture.json re-read afterwards: a long calibration whose fixture was
    # edited mid-flight would otherwise stamp its record with a version it
    # never measured — the exact staleness this field exists to prevent.
    # Falls back to fixture.json only when the report predates the field.
    fixture_version = report.get("fixture", {}).get("fixture_version")
    if fixture_version is None:
        fixture_version = json.loads((fixture_dir / "fixture.json").read_text())[
            "fixture_version"
        ]

    sm1 = evaluate_sm1(report)
    # Scope the chain to THIS fixture_version, matching staleness_status:
    # a record calibrated against different fixture content is not evidence
    # about this one. Reading the unfiltered chain let a `fail_unconfirmed`
    # at v1 confirm the very first failure at v2 into a hard `fail`, so a
    # single failed calibration at a brand-new version blocked every
    # comparison with HARNESS_INVALID.
    records = [
        r
        for r in _read_records(fixture_dir)
        if r["calibrated_fixture_version"] == fixture_version
    ]
    result = classify_with_history(sm1["raw_result"], records)

    stamp = date or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    record = {
        "result": result,
        "calibrated_fixture_version": fixture_version,
        "date": stamp,
        # The A-vs-A probe measures the harness on ONE candidate's
        # workload. Recording which one lets a reader of
        # `harness_validity.calibration` see whether the fixture was
        # calibrated on a workload resembling the comparison being judged;
        # without it the record silently vouches for every candidate.
        "candidate": candidate,
        "per_dimension_splits": sm1["per_dimension_splits"],
        "n_eff_per_dimension": sm1["n_eff_per_dimension"],
        "undowngraded_verdict": sm1["undowngraded_verdict"],
        "comparison_id": comparison_id,
    }
    _append_record(fixture_dir, record)

    judging_path = cmp_dir / "eval-0" / "judging.json"
    if not judging_path.is_file():
        # The pooled ledger is the primary positional-bias detector; a
        # silently skipped append is indistinguishable from "no bias
        # found", so say so rather than passing over it.
        print(
            f"versus: warning: {judging_path} missing — no positional-ledger "
            "entries recorded for this calibration",
            file=sys.stderr,
        )
    else:
        judging = json.loads(judging_path.read_text())
        entries = positional_entries_from_judging(
            judging, fixture_version=fixture_version, date=stamp
        )
        _append_ledger_entries(fixture_dir, entries)

    return record


def main(argv: list[str]) -> int:
    print(
        "calibrate.py is an internal module, never a user-facing command "
        "(FR-59): use `versus-compare run --self-calibrate <candidate> "
        "--fixture <id>`",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
