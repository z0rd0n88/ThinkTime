"""Wire-format export: harness-native artifacts -> upstream-compatible
eval-0 tree + benchmark.json/benchmark.md (FR-25, FR-50, DR-1).

The harness's own `runs/pair{k}-arm{a}/` tree and its own `grading.json`/
`timing.json` shapes are NOT the wire format — `tests/test_schema_compat.py`
pins the wire format independently as a hand-authored corpus. This module
is the bridge: it reads the harness-native tree and produces the
schema-compat shape, so both schemas must be handled without conflating
them (same filenames, disjoint contents, different directories).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import aggregate_benchmark as ab  # noqa: E402


def _seed_run(
    cmp_dir: Path, pair: int, arm: int, *, grading: dict, timing: dict
) -> None:
    run_dir = cmp_dir / "runs" / f"pair{pair}-arm{arm}"
    run_dir.mkdir(parents=True)
    (run_dir / "grading.json").write_text(json.dumps(grading))
    (run_dir / "timing.json").write_text(json.dumps(timing))


def _well_formed_grading(passed: int, total: int) -> dict:
    expectations = [
        {
            "id": f"A{i}",
            "text": f"assertion {i}",
            "passed": i < passed,
            "evidence": "ev",
        }
        for i in range(total)
    ]
    return {
        "expectations": expectations,
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": passed / total,
        },
        "task_outcome": "success",
        "retries": 0,
    }


def _timing(cost=0.1, duration=1.0):
    return {
        "started_at": "2026-07-29T00:00:00Z",
        "ended_at": "2026-07-29T00:00:01Z",
        "duration_seconds": duration,
        "cost_usd": cost,
    }


# ---- run discovery and arm/pair mapping


def test_arm_zero_is_candidate_a_arm_one_is_candidate_b(tmp_path):
    _seed_run(tmp_path, 0, 0, grading=_well_formed_grading(3, 3), timing=_timing())
    _seed_run(tmp_path, 0, 1, grading=_well_formed_grading(0, 3), timing=_timing())
    runs = ab.discover_runs(tmp_path)
    by_config = {r.configuration: r for r in runs}
    assert set(by_config) == {"candidate_a", "candidate_b"}
    assert by_config["candidate_a"].pair_index == 0
    assert by_config["candidate_b"].pair_index == 0


def test_pair_index_k_maps_to_one_based_run_number(tmp_path):
    _seed_run(tmp_path, 0, 0, grading=_well_formed_grading(1, 1), timing=_timing())
    _seed_run(tmp_path, 1, 0, grading=_well_formed_grading(1, 1), timing=_timing())
    runs = sorted(
        (r for r in ab.discover_runs(tmp_path) if r.configuration == "candidate_a"),
        key=lambda r: r.pair_index,
    )
    assert [r.run_number for r in runs] == [1, 2]


# ---- export mapping


def test_export_grading_maps_to_the_wire_compat_shape():
    exported = ab.export_grading("candidate_a", _well_formed_grading(2, 3))
    assert set(exported) == {"configuration", "result"}
    assert exported["configuration"] == "candidate_a"
    result = exported["result"]
    assert set(result) == {"pass_rate", "assertions"}
    assert result["pass_rate"] == 2 / 3
    for a in result["assertions"]:
        assert set(a) == {"text", "passed", "evidence"}


def test_export_grading_pass_rate_matches_assertions():
    exported = ab.export_grading("candidate_b", _well_formed_grading(1, 4))
    expected = sum(a["passed"] for a in exported["result"]["assertions"]) / 4
    assert exported["result"]["pass_rate"] == expected


def test_degraded_run_is_excluded_from_the_export():
    """A run with no expectations (grader crashed, audit-integrity failure,
    etc.) has no per-assertion evidence to export; the wire format's own
    invariant is a non-empty assertions list, so such a run is dropped from
    the wire-compat tree rather than exported with a fabricated one."""
    degraded = {
        "error_class": "grader_crashed",
        "reason": "timeout",
        "task_outcome": "failure",
    }
    assert ab.export_grading("candidate_a", degraded) is None


def test_export_timing_drops_cost_usd():
    exported = ab.export_timing(_timing(cost=0.42))
    assert set(exported) == {"started_at", "ended_at", "duration_seconds"}


# ---- full tree + benchmark.json


def test_full_export_matches_schema_compat_shape(tmp_path):
    cmp_dir = tmp_path / "vc-abc"
    _seed_run(
        cmp_dir, 0, 0, grading=_well_formed_grading(3, 3), timing=_timing(cost=0.1)
    )
    _seed_run(
        cmp_dir, 0, 1, grading=_well_formed_grading(1, 3), timing=_timing(cost=0.2)
    )

    eval_dir = ab.export_benchmark(cmp_dir, eval_name="dev-noop")

    for cfg in ("candidate_a", "candidate_b"):
        run_dir = eval_dir / cfg / "run-1"
        g = json.loads((run_dir / "grading.json").read_text())
        assert set(g) == {"configuration", "result"}
        t = json.loads((run_dir / "timing.json").read_text())
        assert set(t) == {"started_at", "ended_at", "duration_seconds"}

    b = json.loads((eval_dir / "benchmark.json").read_text())
    assert set(b) == {"eval_name", "runs_per_configuration", "run_summary"}
    assert b["eval_name"] == "dev-noop"
    assert b["runs_per_configuration"] == 1
    assert set(b["run_summary"]) == {"candidate_a", "candidate_b"}
    for cfg in ("candidate_a", "candidate_b"):
        assert set(b["run_summary"][cfg]) == {"runs", "mean_pass_rate"}
    assert b["run_summary"]["candidate_a"]["mean_pass_rate"] == 1.0
    assert round(b["run_summary"]["candidate_b"]["mean_pass_rate"], 4) == round(
        1 / 3, 4
    )


def test_runs_per_configuration_is_a_real_count_not_a_placeholder(tmp_path):
    cmp_dir = tmp_path / "vc-abc"
    for pair in range(3):
        _seed_run(
            cmp_dir, pair, 0, grading=_well_formed_grading(1, 1), timing=_timing()
        )
        _seed_run(
            cmp_dir, pair, 1, grading=_well_formed_grading(1, 1), timing=_timing()
        )
    eval_dir = ab.export_benchmark(cmp_dir, eval_name="dev-noop")
    b = json.loads((eval_dir / "benchmark.json").read_text())
    assert b["runs_per_configuration"] == 3
    assert b["run_summary"]["candidate_a"]["runs"] == 3


def test_degraded_runs_are_excluded_but_do_not_crash_the_export(tmp_path):
    cmp_dir = tmp_path / "vc-abc"
    _seed_run(cmp_dir, 0, 0, grading=_well_formed_grading(1, 1), timing=_timing())
    _seed_run(
        cmp_dir,
        0,
        1,
        grading={
            "error_class": "grader_crashed",
            "reason": "x",
            "task_outcome": "failure",
        },
        timing=_timing(),
    )
    eval_dir = ab.export_benchmark(cmp_dir, eval_name="dev-noop")
    assert not (eval_dir / "candidate_b" / "run-1").exists()
    b = json.loads((eval_dir / "benchmark.json").read_text())
    assert b["run_summary"]["candidate_b"]["runs"] == 0
    assert b["run_summary"]["candidate_b"]["mean_pass_rate"] is None


def test_benchmark_md_is_written_and_human_readable(tmp_path):
    cmp_dir = tmp_path / "vc-abc"
    _seed_run(cmp_dir, 0, 0, grading=_well_formed_grading(3, 3), timing=_timing())
    _seed_run(cmp_dir, 0, 1, grading=_well_formed_grading(1, 3), timing=_timing())
    eval_dir = ab.export_benchmark(cmp_dir, eval_name="dev-noop")
    md = (eval_dir / "benchmark.md").read_text()
    assert "dev-noop" in md
    assert "candidate_a" in md and "candidate_b" in md


def test_aggregator_never_imports_paired_stats():
    """FR-50: benchmark.json is descriptive-only and never feeds the verdict.

    Asserted as an import-graph guard rather than a docstring grep: the
    real property is that this module cannot call into `paired_stats`, so
    a verdict computed with `benchmark.json` present or deleted is
    necessarily byte-identical (T-U-14 covers the reverse direction, from
    `paired_stats`'s side).
    """
    assert "paired_stats" not in ab.__dict__
    assert not any(
        getattr(mod, "__name__", "") == "paired_stats"
        for mod in vars(ab).values()
        if hasattr(mod, "__name__")
    )
