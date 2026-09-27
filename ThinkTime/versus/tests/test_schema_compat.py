"""Schema-compatibility pin (spec §9.1, FR-25, DR-1, R4; Phase 0 task 10).

The eval-0 corpus is the wire-format commitment: `grading.json` field names
match the de facto upstream eval schema so a schema-compatible viewer loads
the run tree. The `configuration` VALUE and the `run_summary` KEYS are
asserted, not field names alone — upstream badges configurations against a
hardcoded with_skill|without_skill|new_skill|old_skill regex, so our
`candidate_*` values load WITHOUT badging; a field-name-only test cannot
catch that gap (DR-1). No upstream file is read; no viewer is opened.
"""

import json
from pathlib import Path

CORPUS = Path(__file__).parent / "corpus" / "eval-0"
CONFIGURATIONS = ("candidate_a", "candidate_b")


def _load(rel: str) -> dict:
    return json.loads((CORPUS / rel).read_text(encoding="utf-8"))


def test_tree_shape():
    for cfg in CONFIGURATIONS:
        run = CORPUS / cfg / "run-1"
        assert (run / "grading.json").is_file()
        assert (run / "timing.json").is_file()
    assert (CORPUS / "benchmark.json").is_file()


def test_grading_field_names_and_configuration_value():
    for cfg in CONFIGURATIONS:
        g = _load(f"{cfg}/run-1/grading.json")
        assert set(g) == {"configuration", "result"}
        # The VALUE, not just the field: candidate_* is the deliberate,
        # disclosed deviation from upstream's with_skill/without_skill
        # literals (DR-1 badging gap).
        assert g["configuration"] == cfg
        result = g["result"]
        assert set(result) == {"pass_rate", "assertions"}
        assert isinstance(result["pass_rate"], float)
        assert 0.0 <= result["pass_rate"] <= 1.0
        assert result["assertions"], "assertions must be non-empty"
        for a in result["assertions"]:
            assert set(a) == {"text", "passed", "evidence"}
            assert isinstance(a["text"], str) and a["text"]
            assert isinstance(a["passed"], bool)
            assert isinstance(a["evidence"], str) and a["evidence"]


def test_timing_field_names():
    for cfg in CONFIGURATIONS:
        t = _load(f"{cfg}/run-1/timing.json")
        assert set(t) == {"started_at", "ended_at", "duration_seconds"}
        assert isinstance(t["duration_seconds"], float)


def test_benchmark_run_summary_keys():
    b = _load("benchmark.json")
    assert set(b) == {"eval_name", "runs_per_configuration", "run_summary"}
    assert b["eval_name"] == "dev-noop"
    # Real count, not a placeholder (spec §9.1).
    assert b["runs_per_configuration"] == 1
    # run_summary is KEYED on the configuration values. Upstream keys on its
    # with_skill/without_skill literals; ours are candidate_* — asserting the
    # keys is what makes the badging gap visible in a test.
    assert set(b["run_summary"]) == set(CONFIGURATIONS)
    for cfg in CONFIGURATIONS:
        assert set(b["run_summary"][cfg]) == {"runs", "mean_pass_rate"}


def test_pass_rate_consistent_with_assertions():
    for cfg in CONFIGURATIONS:
        g = _load(f"{cfg}/run-1/grading.json")
        asserts = g["result"]["assertions"]
        expected = sum(a["passed"] for a in asserts) / len(asserts)
        assert g["result"]["pass_rate"] == expected
