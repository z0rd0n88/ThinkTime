#!/usr/bin/env python3
"""Deterministic gating and per-run grading: FR-25..FR-27, FR-58
(grading half). Stdlib only.

Two things are recorded per run and never confused (FR-26, FR-58):
`task_outcome` is computed by the harness from the fixture's declared
hard gate, BEFORE any model grades anything, and is immutable once
recorded — a grader that later crashes, times out, or returns garbage
does not erase it, and it alone still decides the mechanical
`correctness` dimension for that run (FR-58's denominator rule).
`error_class` is a separate, orthogonal field recording *why grading
itself* didn't produce a `grading.json` — it never overwrites
`task_outcome`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_tools import (  # noqa: E402
    compute_self_report_divergence,
    constraints_from_fixture,
    parse_audit_records,
    verify_chain,
)

GRADER_RETRY_BUDGET = 2  # FR-58: two ADDITIONAL attempts (three total)
COMPARISON_INVALID_RETRY_RATE = 0.20  # FR-58: comparison-level guard


class GraderTimeout(Exception):
    """Raised by an injected `invoke` to represent a grader timeout."""


class GraderBudgetExceeded(Exception):
    """Raised by an injected `invoke` to represent a budget overrun."""


class TaskOutcome(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


class GraderErrorClass(Enum):
    CRASHED = "grader_crashed"
    MALFORMED_JSON = "grader_malformed_json"
    SCHEMA_INVALID = "grader_schema_invalid"
    BUDGET_EXCEEDED = "grader_budget_exceeded"
    TIMEOUT = "grader_timeout"


# ---------------------------------------------------------------- FR-26/27 gate


@dataclass
class CheckResult:
    name: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def run_deterministic_checks(
    fixture_dir: Path, worktree: Path, checks: list[str], *, runner=None
) -> list[CheckResult]:
    """FR-27: fixture-declared checks run as plain shell in the run
    worktree; exit codes are recorded before any model grades anything.
    `runner(cmd, cwd) -> int` is injected so this is Tier-0 testable
    without spawning a real subprocess in tests."""
    runner = runner or (
        lambda cmd, cwd: subprocess.run(cmd, cwd=cwd, capture_output=True).returncode
    )
    results = []
    for name in checks:
        script = Path(fixture_dir) / name
        rc = runner(["bash", str(script), str(worktree)], worktree)
        results.append(CheckResult(name=name, exit_code=rc))
    return results


def compute_task_outcome(results: list[CheckResult]) -> TaskOutcome:
    """FR-26: computed by the harness from the hard gate, independent
    of the grader and of the soft assertions, and recorded before any
    model grades anything (FR-27).

    Design decision (this session, documented like Phase 1's FR-62
    reading): a fixture's `checks` is a LIST — FR-26 describes the gate
    itself as effectively binary ("file exists, exit 0, string
    present"), but does not preclude a fixture declaring more than one
    such check. `success` requires every check to pass, `failure`
    requires every check to fail, and a genuine mix is `partial`. A
    single-check fixture (the common case, e.g. dev-noop) can
    therefore only ever land on success or failure — `partial` is
    reachable only by a fixture that declares multiple checks."""
    if not results:
        raise ValueError("task_outcome requires at least one declared check (FR-27)")
    passed = [r for r in results if r.ok]
    if len(passed) == len(results):
        return TaskOutcome.SUCCESS
    if not passed:
        return TaskOutcome.FAILURE
    return TaskOutcome.PARTIAL


# ---------------------------------------------------------------- FR-25 grader invocation


def build_grader_agents_payload(brief_text: str) -> dict:
    """DR-8/DR-10: the grader brief is passed inline via `--agents`,
    not registered — `{name: {description, prompt}}`, no
    `disallowedTools` key (the grader is not a candidate under test)."""
    return {
        "vc-grader": {
            "description": "versus-compare per-run grader",
            "prompt": brief_text,
        }
    }


def build_grader_task_message(
    *,
    assertions: list[dict],
    task_outcome: TaskOutcome,
    transcript_path: Path,
    outputs_dir: Path,
) -> str:
    """The per-invocation task message handed to the registered grader
    agent — distinct from the brief, which is its system prompt. The
    harness-computed `task_outcome` is GIVEN as input (FR-26) so the
    grader cannot mark an assertion passed on a run the gate failed."""
    return json.dumps(
        {
            "assertions": assertions,
            "task_outcome": task_outcome.value,
            "transcript_path": str(transcript_path),
            "outputs_dir": str(outputs_dir),
        },
        indent=2,
    )


# ---------------------------------------------------------------- FR-58 validation + retry


@dataclass
class GradingOutcome:
    ok: bool
    grading: dict | None = None
    error_class: str | None = None
    reason: str | None = None
    retries_used: int = 0


def _balanced_object_spans(text: str) -> list[str]:
    """Every balanced top-level `{...}` span in `text`, string- and
    escape-aware so a brace inside a JSON string never miscounts."""
    spans: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    spans.append(text[start : i + 1])
    return spans


def extract_json_object(
    raw: str, *, required_keys: tuple[str, ...] = ("expectations", "summary")
) -> dict | None:
    """Recover the grader's JSON object from a response that may carry
    prose and/or markdown fences around it.

    This is NOT leniency about a broken grader. A grader that emits a
    correct grading inside a ```json fence HAS produced a usable
    result; rejecting it would drop a real sample and skew the
    win-rate denominator — the exact bias NFR-6 and FR-58 exist to
    prevent. Observed live 2026-07-29: haiku reliably prefixes a prose
    analysis and fences the object, despite the brief saying otherwise.

    Ordering matters for safety. The grader reads candidate-authored
    material (the transcript and `outputs/`), so it may QUOTE a JSON
    blob that a hostile candidate planted. Preference therefore goes
    to the LAST span that both parses and carries the required
    `expectations` + `summary` keys: a model states its own answer
    last, and a quoted foreign blob that lacks the grading shape can
    never outrank a real one. Schema validation still runs afterward,
    so a wrong-shaped extraction is rejected regardless."""
    parsed = extract_json_candidates(raw)
    if not parsed:
        return None
    well_shaped = [o for o in parsed if all(k in o for k in required_keys)]
    return well_shaped[-1] if well_shaped else parsed[-1]


def extract_json_candidates(raw: str) -> list[dict]:
    """Every parseable JSON object in the response, in span order:
    the whole body, each fenced block, each balanced brace span. The
    comparator path needs the FULL list (not just the last well-shaped
    span) so it can reject responses whose spans carry disagreeing
    winners or a buried `identity_inferred` confession — review
    finding, 2026-07-29."""
    if not isinstance(raw, str):
        return []

    candidates: list[str] = [raw.strip()]

    # Fenced blocks: ```json ... ``` or bare ``` ... ```
    for match in re.finditer(r"```(?:json)?\s*\n(.*?)```", raw, re.DOTALL):
        candidates.append(match.group(1).strip())

    candidates.extend(_balanced_object_spans(raw))

    parsed: list[dict] = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            obj = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            parsed.append(obj)
    return parsed


def validate_grader_response(
    raw: str, *, expected_task_outcome: TaskOutcome, assertion_ids: list[str]
) -> GradingOutcome:
    """FR-58: parse, then schema-check. FR-26 forbids the grader from
    emitting `task_outcome` at all; a response that carries one
    DIFFERING from the recorded gate result is a hard reject
    (`grader_schema_invalid`) — the harness never merges or honours a
    grader's copy, agreeing or not (FR-26's stated residual: agreement
    passes validation unnoticed, which is deliberate and harmless)."""
    data = extract_json_object(raw)
    if data is None:
        # FR-58 draws the line at "parses but lacks required fields"
        # (schema_invalid) vs "does not parse" (malformed_json). A
        # response that IS valid JSON but is not an object — `[1,2,3]`,
        # `"text"`, `42` — parsed fine and belongs on the schema side;
        # only genuinely unparseable output is malformed.
        try:
            json.loads(raw)
        except (ValueError, TypeError):
            return GradingOutcome(
                False,
                error_class=GraderErrorClass.MALFORMED_JSON.value,
                reason="response contains no parseable JSON object",
            )
        return GradingOutcome(
            False,
            error_class=GraderErrorClass.SCHEMA_INVALID.value,
            reason="response is not a JSON object",
        )

    if not isinstance(data, dict):
        return GradingOutcome(
            False,
            error_class=GraderErrorClass.SCHEMA_INVALID.value,
            reason="response is not a JSON object",
        )

    if "task_outcome" in data and data["task_outcome"] != expected_task_outcome.value:
        return GradingOutcome(
            False,
            error_class=GraderErrorClass.SCHEMA_INVALID.value,
            reason=(
                f"grader emitted task_outcome={data['task_outcome']!r} "
                f"disagreeing with the recorded gate result "
                f"{expected_task_outcome.value!r} (FR-26)"
            ),
        )

    expectations = data.get("expectations")
    summary = data.get("summary")
    if not isinstance(expectations, list) or not isinstance(summary, dict):
        return GradingOutcome(
            False,
            error_class=GraderErrorClass.SCHEMA_INVALID.value,
            reason="missing expectations[] or summary{}",
        )

    required_summary_keys = {"passed", "failed", "total", "pass_rate"}
    if not required_summary_keys.issubset(summary):
        return GradingOutcome(
            False,
            error_class=GraderErrorClass.SCHEMA_INVALID.value,
            reason="summary missing required keys",
        )

    seen_ids = []
    for exp in expectations:
        if not isinstance(exp, dict) or not {
            "id",
            "text",
            "passed",
            "evidence",
        }.issubset(exp):
            return GradingOutcome(
                False,
                error_class=GraderErrorClass.SCHEMA_INVALID.value,
                reason="an expectation is missing a required field",
            )
        seen_ids.append(exp["id"])
    if sorted(seen_ids) != sorted(assertion_ids):
        return GradingOutcome(
            False,
            error_class=GraderErrorClass.SCHEMA_INVALID.value,
            reason="expectations do not cover exactly the input assertion ids",
        )

    # task_outcome is written here by the HARNESS, additive to the
    # grader's own shape (FR-25) — never the grader's copy, even when
    # the grader violated the brief and happened to agree.
    grading = {
        "expectations": expectations,
        "summary": summary,
        "task_outcome": expected_task_outcome.value,
    }
    return GradingOutcome(True, grading=grading)


def grade_with_retries(
    invoke,
    *,
    expected_task_outcome: TaskOutcome,
    assertion_ids: list[str],
    max_retries: int = GRADER_RETRY_BUDGET,
) -> GradingOutcome:
    """FR-58: two ADDITIONAL attempts (three total), same inputs, a
    fresh `--session-id` per call — `invoke()` owns that and is called
    fresh on every attempt. `invoke()` returns a raw response string,
    or raises `GraderTimeout`/`GraderBudgetExceeded`/anything else
    (treated as a crash) to represent a failed attempt.

    Denominator rule (FR-58): even after exhausting retries, the
    ALREADY-RECORDED gate result (`expected_task_outcome`) is what
    still decides `correctness` for this run — a failed grader does
    not remove it. This function therefore never overwrites
    `task_outcome`; the caller pairs the returned `error_class` with
    the gate value it already has, rather than this function inventing
    a new one."""
    last: GradingOutcome = GradingOutcome(
        False, error_class=GraderErrorClass.CRASHED.value, reason="no attempts made"
    )
    for attempt in range(max_retries + 1):
        try:
            raw = invoke()
        except GraderTimeout:
            last = GradingOutcome(
                False,
                error_class=GraderErrorClass.TIMEOUT.value,
                reason="grader timed out",
            )
            continue
        except GraderBudgetExceeded:
            last = GradingOutcome(
                False,
                error_class=GraderErrorClass.BUDGET_EXCEEDED.value,
                reason="grader exceeded its budget",
            )
            continue
        except Exception as e:  # noqa: BLE001 - any other failure is a crash
            last = GradingOutcome(
                False, error_class=GraderErrorClass.CRASHED.value, reason=str(e)
            )
            continue
        outcome = validate_grader_response(
            raw,
            expected_task_outcome=expected_task_outcome,
            assertion_ids=assertion_ids,
        )
        outcome.retries_used = attempt
        if outcome.ok:
            return outcome
        last = outcome
    last.retries_used = max_retries
    return last


# ---------------------------------------------------------------- FR-58 comparison-level guard


def comparison_grading_invalid(*, total_runs: int, retry_exhausted_count: int) -> bool:
    """FR-58: if more than 20% of graders exhaust their retries, the
    overall verdict is HARNESS_INVALID, not INCONCLUSIVE — a pipeline
    failing that often is not producing a null result, it is not
    producing a measurement."""
    if total_runs == 0:
        return False
    return (retry_exhausted_count / total_runs) > COMPARISON_INVALID_RETRY_RATE


# ---------------------------------------------------------------- FR-23 reported total


def extract_reported_tool_counts(transcript_path: Path) -> dict[str, int]:
    """Best-effort self-reported PER-TOOL counts for FR-23's divergence
    check. Returns `{tool_name: count}`; the total is its sum.

    Residual, documented: FR-23 names the executor's self-reported
    `metrics.json` as the comparand, but the runner built in Phase 1
    never asked the executor to emit one. Rather than leave FR-23
    unimplemented, this reads the SAME signal a `metrics.json` would
    encode — the executor's own claim about what it did — off the
    transcript it already writes: every `assistant` message's
    `tool_use` content blocks. This is still self-report (it is the
    executor's own transcript, produced by the same process, not
    independently observed), so the divergence check retains its
    purpose against the audit log; it is a different artifact than the
    spec names, not a different evidentiary class.

    Counting per tool rather than only in aggregate is what makes
    FR-23's `per_tool` breakdown carry real data on both sides. A
    total-only reading would leave every `reported` entry at 0 and so
    report a fabricated per-tool divergence on every run."""
    path = Path(transcript_path)
    counts: dict[str, int] = {}
    if not path.is_file():
        return counts
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") != "assistant":
            continue
        content = (obj.get("message") or {}).get("content") or []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                name = c.get("name") or "unknown"
                counts[name] = counts.get(name, 0) + 1
    return counts


def extract_reported_tool_total(transcript_path: Path) -> int:
    """Aggregate of `extract_reported_tool_counts` (FR-23)."""
    return sum(extract_reported_tool_counts(transcript_path).values())


# ---------------------------------------------------------------- per-run reconciliation


@dataclass
class RunScoring:
    task_outcome: str
    error_class: str | None
    audit_summary: object | None
    self_report_divergence: object | None
    check_results: list[CheckResult]
    chain_ok: bool


def finalize_run_scoring(
    *,
    audit_log: Path,
    hmac_key: bytes,
    fixture_meta: dict,
    fixture_dir: Path,
    worktree: Path,
    transcript_path: Path,
    checks_runner=None,
) -> RunScoring:
    """The Phase 2 per-run reconciliation: verify the audit chain
    (FR-21.3/FR-55) before computing anything, run the deterministic
    gate (FR-26/27), and compute the self-report divergence (FR-23).

    FR-55 is explicit that a verification failure OVERRIDES the gate:
    the run is stamped `task_outcome: failure` with
    `error_class: audit_integrity` regardless of what the deterministic
    checks would have said — unlike a grading failure (FR-58), which
    leaves the already-recorded gate value alone. The checks still run
    here so the run record isn't silently missing them, but the
    returned `task_outcome` is the forced `failure`."""
    chain = verify_chain(audit_log, hmac_key)
    constraints = constraints_from_fixture(fixture_meta)
    checks = fixture_meta.get("checks", [])
    check_results = run_deterministic_checks(
        fixture_dir, worktree, checks, runner=checks_runner
    )

    if not chain.ok:
        return RunScoring(
            task_outcome=TaskOutcome.FAILURE.value,
            error_class=chain.error_class,
            audit_summary=None,
            self_report_divergence=None,
            check_results=check_results,
            chain_ok=False,
        )

    summary = parse_audit_records(chain.records, constraints)
    reported_per_tool = extract_reported_tool_counts(transcript_path)
    divergence = compute_self_report_divergence(
        summary.audit_total,
        sum(reported_per_tool.values()),
        audit_per_tool=summary.tool_counts,
        reported_per_tool=reported_per_tool,
    )
    task_outcome = compute_task_outcome(check_results)
    return RunScoring(
        task_outcome=task_outcome.value,
        error_class=None,
        audit_summary=summary,
        self_report_divergence=divergence,
        check_results=check_results,
        chain_ok=True,
    )
