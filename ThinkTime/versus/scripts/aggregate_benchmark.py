"""Wire-format export: harness-native artifacts -> the upstream-compatible
`eval-0` tree (FR-25, DR-1) plus this harness's own `benchmark.json`/
`benchmark.md` (FR-50).

The harness-native tree lives at `<cmp_dir>/runs/pair{k}-arm{a}/` with its
own `grading.json`/`timing.json` shapes (`grade_run` in `run_comparison.py`,
`write_timing` for the executor capture). Those are NOT the wire format —
`tests/test_schema_compat.py` pins the wire format independently against a
hand-authored corpus. This module is the bridge, and only the bridge: it
maps arm 0/1 to `candidate_a`/`candidate_b`, 0-based `pair_index` to
1-based `run-N`, and the harness's richer per-field shapes down to the
wire-compat subset. It does not compute a verdict and does not import
`paired_stats` — `benchmark.json` is descriptive-only (FR-50) and must
never become a second path into the verdict.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_RUN_DIR_RE = re.compile(r"^pair(\d+)-arm([01])$")
_ARM_TO_CONFIGURATION = {0: "candidate_a", 1: "candidate_b"}


@dataclass(frozen=True)
class DiscoveredRun:
    """One harness-native run, resolved to its wire-compat coordinates."""

    configuration: str  # "candidate_a" | "candidate_b"
    pair_index: int  # 0-based, matches the harness's own pairing
    run_number: int  # 1-based, matches the wire format's run-N naming
    grading: dict  # harness-native grading.json contents
    timing: dict  # harness-native timing.json contents


def discover_runs(cmp_dir: Path) -> list[DiscoveredRun]:
    """Scan `<cmp_dir>/runs/` for the harness-native run tree.

    A run directory not matching `pair{k}-arm{0,1}`, or one missing either
    artifact, is skipped rather than raising — a comparison mid-flight or
    partially torn down should not crash the export.
    """
    runs_dir = Path(cmp_dir) / "runs"
    if not runs_dir.is_dir():
        return []
    discovered = []
    for run_dir in sorted(runs_dir.iterdir()):
        match = _RUN_DIR_RE.match(run_dir.name)
        if not match:
            continue
        grading_path = run_dir / "grading.json"
        timing_path = run_dir / "timing.json"
        if not grading_path.is_file() or not timing_path.is_file():
            continue
        pair_index, arm = int(match.group(1)), int(match.group(2))
        discovered.append(
            DiscoveredRun(
                configuration=_ARM_TO_CONFIGURATION[arm],
                pair_index=pair_index,
                run_number=pair_index + 1,
                grading=json.loads(grading_path.read_text()),
                timing=json.loads(timing_path.read_text()),
            )
        )
    return discovered


def export_grading(configuration: str, grading: dict) -> dict | None:
    """Map one harness-native `grading.json` to the wire-compat shape.

    Returns None for a degraded run (no `expectations`/`summary` — a
    grader crash, timeout, or schema violation recorded as `error_class`
    instead). Such a run has no per-assertion evidence to export, and the
    wire format's own invariant is a non-empty `assertions` list — export
    with no assertions would violate the shape it exists to satisfy, so
    the run is dropped from the wire-compat tree rather than represented
    with fabricated data. It is still visible in this harness's own
    `report.json` (a separate artifact `report.py` produces).
    """
    expectations = grading.get("expectations")
    summary = grading.get("summary")
    if not isinstance(expectations, list) or not isinstance(summary, dict):
        return None
    return {
        "configuration": configuration,
        "result": {
            "pass_rate": summary["pass_rate"],
            "assertions": [
                {"text": e["text"], "passed": e["passed"], "evidence": e["evidence"]}
                for e in expectations
            ],
        },
    }


def export_timing(timing: dict) -> dict:
    """Drop the harness-only `cost_usd` field; keep the three wire-compat keys."""
    return {
        "started_at": timing["started_at"],
        "ended_at": timing["ended_at"],
        "duration_seconds": timing["duration_seconds"],
    }


def _run_summary_for(runs: list[DiscoveredRun]) -> dict:
    """`{runs, mean_pass_rate}` over the *exportable* runs of one
    configuration. A configuration with zero exportable runs (every run
    degraded) reports `mean_pass_rate: null` rather than dividing by zero
    or silently reporting a misleading 0.0 — an empty mean is not a low
    score, it is an absence of evidence, the same distinction FR-21.4
    draws for the audit dimension.
    """
    rates = [r.grading["summary"]["pass_rate"] for r in runs if "summary" in r.grading]
    return {
        "runs": len(rates),
        "mean_pass_rate": (sum(rates) / len(rates)) if rates else None,
    }


def render_benchmark_md(benchmark: dict) -> str:
    lines = [
        f"# Benchmark — {benchmark['eval_name']}",
        "",
        f"Runs per configuration: {benchmark['runs_per_configuration']}",
        "",
        "| Configuration | Runs | Mean pass rate |",
        "| --- | --- | --- |",
    ]
    for cfg, summary in sorted(benchmark["run_summary"].items()):
        mean = summary["mean_pass_rate"]
        mean_str = f"{mean:.4f}" if mean is not None else "n/a"
        lines.append(f"| {cfg} | {summary['runs']} | {mean_str} |")
    lines.append("")
    lines.append(
        "Descriptive only — means, unlike Wilson intervals, are never a basis "
        "for a verdict (DR-4). See `report.md` for the paired win-rate verdict."
    )
    return "\n".join(lines) + "\n"


def export_benchmark(
    cmp_dir: Path, *, eval_name: str, eval_dir: Path | None = None
) -> Path:
    """Write the full wire-compat tree: per-run `grading.json`/`timing.json`
    under `<eval_dir>/<configuration>/run-<N>/`, plus `benchmark.json` and
    `benchmark.md` at `<eval_dir>` root. Returns `eval_dir`.

    Defaults `eval_dir` to `<cmp_dir>/eval-0` — the name the wire-compat
    corpus pins and the same directory Phase 3's judging internals
    (`judging.json`, `assignment.json`, `scrub/`) already occupy. The two
    write disjoint filenames, so the directory is shared rather than
    duplicated under a second name.
    """
    cmp_dir = Path(cmp_dir)
    eval_dir = Path(eval_dir) if eval_dir is not None else cmp_dir / "eval-0"
    eval_dir.mkdir(parents=True, exist_ok=True)

    runs = discover_runs(cmp_dir)
    by_config: dict[str, list[DiscoveredRun]] = {
        "candidate_a": [],
        "candidate_b": [],
    }
    for run in runs:
        by_config[run.configuration].append(run)

    max_n = 0
    for cfg, cfg_runs in by_config.items():
        for run in cfg_runs:
            exported_grading = export_grading(cfg, run.grading)
            if exported_grading is None:
                continue
            run_out_dir = eval_dir / cfg / f"run-{run.run_number}"
            run_out_dir.mkdir(parents=True, exist_ok=True)
            (run_out_dir / "grading.json").write_text(
                json.dumps(exported_grading, indent=2, sort_keys=True) + "\n"
            )
            (run_out_dir / "timing.json").write_text(
                json.dumps(export_timing(run.timing), indent=2, sort_keys=True) + "\n"
            )
        max_n = max(max_n, len(cfg_runs))

    benchmark = {
        "eval_name": eval_name,
        "runs_per_configuration": max_n,
        "run_summary": {
            cfg: _run_summary_for(cfg_runs) for cfg, cfg_runs in by_config.items()
        },
    }
    (eval_dir / "benchmark.json").write_text(
        json.dumps(benchmark, indent=2, sort_keys=True) + "\n"
    )
    (eval_dir / "benchmark.md").write_text(render_benchmark_md(benchmark))
    return eval_dir
