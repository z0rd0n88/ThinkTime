"""Report assembly — FR-39, FR-46, FR-50, FR-51, FR-52.

Reads the harness-native tree (`runs/pair{k}-arm{a}/{grading.json,
timing.json}`, `comparison.json`, `eval-0/judging.json`), threads each
run's fields through `paired_stats`'s pure per-pair win functions, and
writes `report.json`/`report.md`. Report generation is deterministic —
this module reads stored artifacts and formats them; there is no model
invocation anywhere in it (DR-11).

Two extraction rules go beyond what `paired_stats` states, because the
harness-native tree can be in states the pure per-pair functions were
never asked to model:

  - A run that cleared the gate but whose grader exhausted its retry
    budget carries no `summary`/`pass_rate`. If BOTH sides of a pair need
    `pass_rate` to break the tie (both cleared the gate) and either side
    lacks it, the pair is excluded from `correctness` (NO_CONTEST) rather
    than scored on a fabricated rate. If only one side needs it (the
    other failed the gate outright), `correctness_pair`'s one-sided
    branch never reads `pass_rate` for the failing side, so a missing
    summary there is not an obstacle.
  - `efficiency.cost`/`tool_calls` read `timing.json`/`grading.json.audit`
    values that can independently be `None` (cost extraction failed;
    audit chain broken). Either side missing excludes that pair from
    that specific sub-metric only — the same "excluded, not scored"
    pattern FR-21.4 established for constraint_adherence.

`harness_validity` for a normal (non-`--self-calibrate`) run reads
`calibrate.staleness_status` against the fixture directory recorded in
`comparison.json["fixture_dir"]` (absent on a comparison created before
this field existed, which falls back to `unverified` rather than
crashing). A `--self-calibrate` run is always stamped `self` — FR-52's
carve-out, so the first calibration at a new fixture_version is
gradeable rather than force-downgraded before it can ever record a
`pass` (SM1).
"""

from __future__ import annotations

import json
from pathlib import Path

import calibrate as cal
import paired_stats as ps
from aggregate_benchmark import discover_runs, export_benchmark

CREDENTIAL_SUSPECT_THRESHOLD_PCT = 25.0


def _clears_gate(grading: dict) -> bool:
    return ps.clears_gate(grading["task_outcome"])


def _correctness_outcome(grading_a: dict, grading_b: dict) -> ps.PairOutcome:
    a_needs_rate = _clears_gate(grading_a)
    b_needs_rate = _clears_gate(grading_b)
    if a_needs_rate and b_needs_rate:
        if "summary" not in grading_a or "summary" not in grading_b:
            return ps.PairOutcome.NO_CONTEST
    summary_a = grading_a.get("summary", {"pass_rate": 0.0, "total": 0})
    summary_b = grading_b.get("summary", {"pass_rate": 0.0, "total": 0})
    a_in = ps.CorrectnessInput(
        task_outcome=grading_a["task_outcome"],
        pass_rate=summary_a["pass_rate"],
        total=summary_a["total"],
    )
    b_in = ps.CorrectnessInput(
        task_outcome=grading_b["task_outcome"],
        pass_rate=summary_b["pass_rate"],
        total=summary_b["total"],
    )
    return ps.correctness_pair(a_in, b_in)


def _adherence_input(grading: dict) -> ps.AdherenceInput:
    audit = grading["audit"]
    return ps.AdherenceInput(
        violation_completed=audit["violation_completed"] or 0,
        violation_attempted=audit["violation_attempted"] or 0,
        chain_ok=audit["chain_ok"],
    )


def _submetric_pair(a, b, fn):
    if a is None or b is None:
        return ps.PairOutcome.NO_CONTEST
    return fn(a, b)


def _scrub_redaction_count(cmp_dir: Path) -> int:
    """Total FR-29 blinding-scrub substitutions across every pair.

    Distinct from `redactions.credential_matches` (FR-56) — this counts
    identity terms removed from judge inputs before judging, not
    credentials swept from retained output after. `stage_judging.py`
    writes one JSON record per substitution to `eval-0/scrub/<pair>.log`
    (`result.substitutions = len(log_entries)`); this sums line counts
    across every such log rather than duplicating that bookkeeping.
    """
    scrub_dir = Path(cmp_dir) / "eval-0" / "scrub"
    if not scrub_dir.is_dir():
        return 0
    return sum(
        1
        for log_path in scrub_dir.glob("*.log")
        for line in log_path.read_text().splitlines()
        if line.strip()
    )


def _assertion_observations(
    by_pair: dict[int, dict[str, object]], n_pairs: int
) -> list[ps.AssertionObservations]:
    """FR-46: one AssertionObservations per assertion id, aggregated across
    every run of each candidate (not per-pair — the classification needs
    the full 2N-run sample). A degraded run (no `expectations`, e.g. a
    grader that exhausted retries) contributes nothing for that run; the
    assertion's `a`/`b` lists are simply shorter, which `classify_assertion`
    already accounts for.
    """
    per_assertion: dict[str, dict] = {}
    for k in range(n_pairs):
        pair = by_pair.get(k, {})
        for configuration, arm_key in (("candidate_a", "a"), ("candidate_b", "b")):
            run = pair.get(configuration)
            if run is None:
                continue
            expectations = run.grading.get("expectations")
            if not isinstance(expectations, list):
                continue
            for exp in expectations:
                entry = per_assertion.setdefault(
                    exp["id"], {"text": exp["text"], "a": [], "b": []}
                )
                entry[arm_key].append(bool(exp["passed"]))
    return [
        ps.AssertionObservations(
            assertion_id=aid, text=data["text"], a=data["a"], b=data["b"]
        )
        for aid, data in sorted(per_assertion.items())
    ]


def build_report(cmp_dir: Path, *, quick: bool = False) -> dict:
    cmp_dir = Path(cmp_dir)
    comparison = json.loads((cmp_dir / "comparison.json").read_text())
    judging = json.loads((cmp_dir / "eval-0" / "judging.json").read_text())
    runs = discover_runs(cmp_dir)

    by_pair: dict[int, dict[str, dict]] = {}
    for run in runs:
        by_pair.setdefault(run.pair_index, {})[run.configuration] = run

    n_pairs = comparison["runs"]
    correctness_outcomes = []
    adherence_outcomes = []
    tool_calls_outcomes = []
    wall_clock_outcomes = []
    cost_outcomes = []
    quality_outcomes = []
    audit_verification_failures = 0
    grader_retry_exhausted = 0

    for k in range(n_pairs):
        pair = by_pair.get(k, {})
        run_a, run_b = pair.get("candidate_a"), pair.get("candidate_b")
        ga = run_a.grading if run_a else {"task_outcome": "failure"}
        gb = run_b.grading if run_b else {"task_outcome": "failure"}

        correctness_outcomes.append(_correctness_outcome(ga, gb))

        for g in (ga, gb):
            audit = g.get("audit")
            if audit is not None and not audit["chain_ok"]:
                audit_verification_failures += 1
            if _clears_gate(g) and "summary" not in g:
                grader_retry_exhausted += 1

        if "audit" in ga and "audit" in gb:
            adherence_outcomes.append(
                ps.adherence_pair(_adherence_input(ga), _adherence_input(gb))
            )
        else:
            adherence_outcomes.append(ps.PairOutcome.NO_CONTEST)

        audit_a, audit_b = ga.get("audit", {}), gb.get("audit", {})
        tool_calls_outcomes.append(
            _submetric_pair(
                audit_a.get("audit_total"),
                audit_b.get("audit_total"),
                ps.efficiency_tool_calls_pair,
            )
        )

        ta = run_a.timing if run_a else None
        tb = run_b.timing if run_b else None
        wall_clock_outcomes.append(
            _submetric_pair(
                ta["duration_seconds"] if ta else None,
                tb["duration_seconds"] if tb else None,
                ps.efficiency_wall_clock_pair,
            )
        )
        cost_outcomes.append(
            _submetric_pair(
                ta.get("cost_usd") if ta else None,
                tb.get("cost_usd") if tb else None,
                ps.efficiency_cost_pair,
            )
        )

        pair_record = judging["pairs"].get(f"pair-{k}", {})
        quality_outcomes.append(ps.quality_pair(pair_record.get("quality_outcome")))

    correctness = ps.aggregate(correctness_outcomes)
    adherence = ps.aggregate(adherence_outcomes)
    tool_calls = ps.aggregate(tool_calls_outcomes)
    wall_clock = ps.aggregate(wall_clock_outcomes)
    cost = ps.aggregate(cost_outcomes)
    quality = ps.aggregate(quality_outcomes)
    assertion_health = ps.assertion_health(_assertion_observations(by_pair, n_pairs))

    self_calibrate = bool(comparison.get("self_calibrate", False))
    calibration_record = None
    if self_calibrate:
        # FR-52: a calibration run is exempt from the downgrade it would
        # otherwise trigger — the first calibration at a new
        # fixture_version must be gradeable, not force-downgraded before
        # it can ever record a `pass` (SM1).
        harness_validity_status = "self"
    else:
        fixture_dir_str = comparison.get("fixture_dir")
        if fixture_dir_str:
            harness_validity_status, calibration_record = cal.staleness_status(
                Path(fixture_dir_str), comparison["fixture_version"]
            )
        else:
            # No resolvable fixture directory recorded (e.g. an older
            # comparison predating this field) — cannot check staleness,
            # so this is unverified rather than a crash.
            harness_validity_status = "unverified"

    judging_invalid = bool(judging.get("harness_invalid", False))
    verdict_inputs = ps.VerdictInputs(
        correctness=correctness,
        adherence=adherence,
        pair_count=n_pairs,
        harness_validity=harness_validity_status,
        audit_verification_failures=audit_verification_failures,
        grader_retry_exhausted=grader_retry_exhausted,
        grader_invocations=len(runs),
        comparator_retry_exhausted=0,
        comparator_invocations=0,
        seal_intact=not judging_invalid,
        quick=quick,
        self_calibrate=self_calibrate,
    )
    verdict, note = ps.overall_verdict(verdict_inputs)
    if (
        judging_invalid
        and verdict == "HARNESS_INVALID"
        and judging.get("harness_invalid_reason")
    ):
        note = judging["harness_invalid_reason"]

    suspect_runs = []
    self_report_divergence = []
    for run in runs:
        d = run.grading.get("self_report_divergence")
        if d and d.get("suspect"):
            run_id = f"{run.configuration}/run-{run.run_number}"
            suspect_runs.append(run_id)
            self_report_divergence.append({"run": run_id, **d})

    grader_attempts_total = sum(r.grading.get("retries", 0) for r in runs)
    cost_total = sum(
        r.timing["cost_usd"] for r in runs if r.timing.get("cost_usd") is not None
    )
    comparator_invocations = judging.get("invocations", 0)
    invocations = len(runs) + len(runs) + comparator_invocations

    report = {
        "verdict": verdict,
        "candidates": {
            "a": comparison["candidates"][0],
            "b": comparison["candidates"][1],
        },
        "execution": {
            "path": comparison["execution_path"],
            "runs_per_candidate": n_pairs,
            "model_confounded": comparison["model_confounded"],
        },
        "fixture": {
            "fixture_id": comparison["fixture_id"],
            "fixture_version": comparison["fixture_version"],
            "fixture_unverified": comparison["fixture_unverified"],
        },
        "harness_validity": {
            "status": harness_validity_status,
            "calibration": calibration_record,
        },
        "dimensions": {
            "correctness": correctness.to_json("mechanical"),
            "constraint_adherence": adherence.to_json("mechanical"),
            "efficiency": {
                "tool_calls": tool_calls.to_json("mechanical"),
                "wall_clock": wall_clock.to_json("mechanical"),
                "cost": cost.to_json("mechanical"),
            },
            "quality": {
                **quality.to_json("blind_comparator"),
                "verdict_determining": False,
            },
        },
        "verdict_note": note,
        "composite_score": None,
        "composite_score_note": "Deliberately absent. See DR-4.",
        "suspect_runs": suspect_runs,
        "self_report_divergence": self_report_divergence,
        "scrub": {
            "redactions": _scrub_redaction_count(cmp_dir),
            "unjudgeable_blind_pairs": [
                name
                for name, rec in judging["pairs"].items()
                if rec.get("unjudgeable_blind")
            ],
        },
        # FR-56: the real count is only known after `redact_comparison()`
        # runs, which happens in `generate()` AFTER this report is first
        # written (report.json is itself one of the redacted artifacts —
        # it can't count its own sweep before the sweep exists). `generate()`
        # patches this field with the real total and rewrites the file;
        # `build_report()` alone (e.g. a bare unit test) legitimately has
        # no sweep to report yet, so 0 here is correct for THIS function,
        # not a placeholder that silently stays wrong.
        "redactions": {"credential_matches": 0},
        "retries": {
            "graders": grader_attempts_total,
            "comparators": judging.get("retries", 0),
        },
        "cost": {
            "total_usd": cost_total,
            "per_run_usd_mean": (cost_total / len(runs)) if runs else 0.0,
            "invocations": invocations,
            "invocation_breakdown": {
                "executors": len(runs),
                "graders": len(runs),
                "comparators": comparator_invocations,
            },
            # `invocation_breakdown`'s COUNTS are exact for all three
            # categories. `total_usd`/`per_run_usd_mean` are NOT: only the
            # executor's `total_cost_usd` is captured anywhere in the
            # codebase (`extract_cost_usd` in run_comparison.py). Grader
            # and comparator invocations go through `_headless_result_text`,
            # which discards the `result` message's cost field and returns
            # only its text — threading cost through would mean changing
            # the injected `grader_spawner`/`comparator_spawner` call
            # signature that ~30 Phase 2/3 tests depend on. Disclosed
            # rather than silently under-reported; see FR-51.
            "cost_note": (
                "total_usd covers executor invocations only; grader and "
                "comparator cost is not yet captured (a known Phase 4 "
                "residual, not an estimate — FR-51 forbids estimating, so "
                "the honest answer is to disclose the gap rather than "
                "guess a number for it)."
            ),
        },
        "assertion_health": assertion_health,
    }
    return report


def render_report_md(report: dict) -> str:
    lines = [
        f"# versus-compare report — {report['verdict']}",
        "",
        report["verdict_note"],
        "",
        f"Harness validity: **{report['harness_validity']['status']}**",
        "",
        "## Dimensions",
        "",
        "| Dimension | Wins A | Wins B | Ties | No contest | n_eff | Wilson lower | Verdict |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    def row(name: str, d: dict) -> str:
        return (
            f"| {name} | {d['wins_a']} | {d['wins_b']} | {d['ties']} | "
            f"{d['no_contest']} | {d['effective_n']} | {d['wilson'][0]:.4f} | "
            f"{d['verdict']} |"
        )

    dims = report["dimensions"]
    lines.append(row("correctness", dims["correctness"]))
    lines.append(row("constraint_adherence", dims["constraint_adherence"]))
    lines.append(row("efficiency.tool_calls", dims["efficiency"]["tool_calls"]))
    lines.append(row("efficiency.wall_clock", dims["efficiency"]["wall_clock"]))
    lines.append(row("efficiency.cost", dims["efficiency"]["cost"]))
    lines.append(row("quality", dims["quality"]))
    lines += [
        "",
        f"**No composite score.** {report['composite_score_note']}",
        "",
        f"Cost: ${report['cost']['total_usd']:.2f} total, "
        f"{report['cost']['invocations']} invocations "
        f"({report['cost']['invocation_breakdown']['executors']} executors + "
        f"{report['cost']['invocation_breakdown']['graders']} graders + "
        f"{report['cost']['invocation_breakdown']['comparators']} comparators). "
        f"*{report['cost']['cost_note']}*",
        "",
    ]
    if report["suspect_runs"]:
        lines.append(
            f"Suspect runs (self-report divergence): {', '.join(report['suspect_runs'])}"
        )
        lines.append("")
    return "\n".join(lines) + "\n"


def write_report(cmp_dir: Path, report: dict) -> None:
    cmp_dir = Path(cmp_dir)
    (cmp_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    (cmp_dir / "report.md").write_text(render_report_md(report))


def generate(
    cmp_dir: Path,
    *,
    quick: bool = False,
    eval_name: str = "",
    credentials: dict | None = None,
) -> dict:
    """Full orchestration: export the wire-compat tree, build and write
    the report, then sweep the whole comparison directory for credentials
    (FR-56) — report.json/report.md are themselves in the redacted set, so
    the sweep runs last, after they exist on disk.

    `credentials` is the FR-54 allowlist's known VALUES, available only in
    the same process that ran the comparison (`run_comparison.py` has
    `parent_env`; a later, standalone `report` regeneration has no memory
    of the original run's secrets and gets pattern-only coverage — see
    `cli.py`'s `report` subcommand).
    """
    from redact import redact_comparison, write_redaction_record

    cmp_dir = Path(cmp_dir)
    export_benchmark(
        cmp_dir,
        eval_name=eval_name
        or json.loads((cmp_dir / "comparison.json").read_text())["fixture_id"],
    )
    report = build_report(cmp_dir, quick=quick)
    write_report(cmp_dir, report)
    redaction = redact_comparison(cmp_dir, credentials)
    write_redaction_record(cmp_dir, redaction)
    # FR-56: `build_report`'s first write necessarily carries a placeholder
    # `credential_matches: 0` — the sweep that produces the real number
    # cannot run before report.json exists (report.json is itself one of
    # the redacted artifacts). Patch the real total in now and rewrite,
    # rather than leaving report.json permanently wrong about the one
    # machine-readable signal an operator would use to know a credential
    # was found and scrubbed (review finding, 2026-07-29).
    final = json.loads((cmp_dir / "report.json").read_text())
    final["redactions"]["credential_matches"] = redaction.total
    (cmp_dir / "report.json").write_text(
        json.dumps(final, indent=2, sort_keys=True) + "\n"
    )
    return final
