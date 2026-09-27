#!/usr/bin/env python3
"""Comparison orchestration: cli → resolve → fixture → worktrees → fleet.

Phase 1 scope: setup, containment wiring, dry-run (FR-60), and the
transcript fleet. Grading, audit reconciliation, judging, and the verdict
are Phases 2-4. Stdlib only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_tools import AuditCollector  # noqa: E402
from grading import (  # noqa: E402
    GraderTimeout,
    TaskOutcome,
    build_grader_agents_payload,
    build_grader_task_message,
    finalize_run_scoring,
    grade_with_retries,
)
from prepare_fixture import FixtureError, load_fixture, prepare_worktree  # noqa: E402
from resolve_candidates import (  # noqa: E402
    Candidate,
    CandidateKind,
    resolve_candidate,
    resolve_enforcement,
    resolve_pair,
    synthesize_wrapper,
)
from stage_judging import (  # noqa: E402
    COMPARATOR_BRIEF_PATH,
    COMPARATOR_TIMEOUT_SECONDS,
    DEFAULT_COMPARATOR_BUDGET_USD,
    DEFAULT_COMPARATOR_MODEL,
    JudgeTimeout,
    build_comparator_agents_payload,
    derive_denylist,
    judge_root_for,
    run_judging,
    write_judge_settings,
)
from run_candidates import (  # noqa: E402
    GIT_IDENTITY,
    RunnerError,
    batch_pairs,
    build_child_env,
    build_run_command,
    create_worktrees,
    plan_runs,
    write_run_settings,
)

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXECUTOR_MODEL = "haiku"
DEFAULT_RUN_BUDGET_USD = 1.0
DEFAULT_GRADER_MODEL = "haiku"
DEFAULT_GRADER_BUDGET_USD = 0.5
GRADER_BRIEF_PATH = PLUGIN_ROOT / "briefs" / "vc-grader.md"
GRADER_TIMEOUT_SECONDS = 300


class ComparisonRefused(Exception):
    """The comparison must not launch; the reason is printed, not logged."""


# ---------------------------------------------------------------- fixture


def resolve_fixture_dir(spec: str, *, dev: bool) -> Path:
    """A fixture specifier is a path or an id. Ids resolve under the
    plugin's fixtures/; with the dev gate open, also under the repo-root
    dev/fixtures/ (never shipped)."""
    p = Path(spec)
    if p.is_dir():
        return p.resolve()
    shipped = PLUGIN_ROOT / "fixtures" / spec
    if shipped.is_dir():
        return shipped
    if dev:
        dev_dir = REPO_ROOT / "dev" / "fixtures" / spec
        if dev_dir.is_dir():
            return dev_dir
    raise ComparisonRefused(f"fixture not found: {spec}")


def discrimination_verified(
    disc: object, *, fixture_version: int | None = None
) -> bool:
    """FR-44's four conditions over a `discrimination` block, in one place
    so the gate and `verify-fixture`'s exit code cannot disagree.

    A fixture discriminates only when the model-graded arms separate AND
    the deterministic gate itself separates them:

    - `reference_pass_rate >= 0.9` — the reference solution really solves it
    - `broken_pass_rate <= 0.2` — the broken solution really fails it
    - `gate_reference_exit == 0` — `checks.sh` passes on the reference
    - `gate_broken_hard_exit != 0` — `checks.sh` CATCHES the do-nothing
      solution; a zero here means the deterministic gate is blind and every
      correctness pair would rest on grader judgement alone

    The last two were previously computed by `verify_fixture`, written into
    `fixture.json`, and read by nothing — this function's docstring claimed
    they were enforced here while only the two pass rates actually were.
    Blocks predating the gate-exit fields are treated as failing rather
    than silently exempt; re-run `verify-fixture` to refresh them.

    When `fixture_version` is given, the block must carry a matching
    `verified_fixture_version` — the discrimination equivalent of
    calibration's staleness test. A block with no such field is treated as
    failing, NOT grandfathered: exempting it would leave every fixture
    verified at every future version, which is exactly the staleness the
    field exists to catch. Shipped fixtures carry the field; re-run
    `verify-fixture` to refresh any block that does not.
    """
    if not isinstance(disc, dict):
        return False
    if fixture_version is not None:
        if disc.get("verified_fixture_version") != fixture_version:
            return False
    return (
        disc.get("reference_pass_rate", 0) >= 0.9
        and disc.get("broken_pass_rate", 1) <= 0.2
        and disc.get("gate_reference_exit") == 0
        and disc.get("gate_broken_hard_exit") not in (None, 0)
    )


def check_discrimination(meta: dict, *, unverified_ok: bool) -> bool:
    """FR-44 gate: an absent or failing discrimination block refuses the
    comparison unless --unverified-fixture (FR-63) is in force. Returns
    True when the fixture is UNVERIFIED (for the report stamp)."""
    if discrimination_verified(
        meta.get("discrimination"), fixture_version=meta.get("fixture_version")
    ):
        return False
    if not unverified_ok:
        raise ComparisonRefused(
            f"fixture {meta.get('fixture_id')} has an absent or failing "
            "discrimination block (FR-44); it cannot support a comparison. "
            "Harness development only: --unverified-fixture (FR-63)"
        )
    return True


# ---------------------------------------------------------------- prompt


def compose_prompt(fixture_dir: Path, meta: dict, candidate: Candidate) -> str:
    prompt = (fixture_dir / meta["prompt_file"]).read_text()
    if candidate.kind is CandidateKind.SKILL:
        # FR-7: the run prompt names the skill explicitly.
        prompt += f"\n\nUse the {Path(candidate.source_path).name} skill."
    return prompt


def executor_model(ns, candidate: Candidate) -> str:
    if ns.respect_candidate_model and candidate.agent and candidate.agent.get("model"):
        return candidate.agent["model"]
    return ns.model or DEFAULT_EXECUTOR_MODEL


def agents_payload(candidate: Candidate) -> dict:
    """The documented --agents shape: {description, prompt, tools, model};
    disallowedTools passes through per the FR-62 pass-through branch
    (transport observed as denial, 2026-07-29)."""
    a = candidate.agent
    entry: dict = {"description": a["description"], "prompt": a["prompt"]}
    if a["tools"] is not None:
        entry["tools"] = a["tools"]
    if a["disallowedTools"] is not None:
        entry["disallowedTools"] = a["disallowedTools"]
    return {a["name"]: entry}


# ---------------------------------------------------------------- auth


def provision_executor_auth(fake_home: Path, *, real_home: Path | None = None) -> None:
    """Materialize the FR-54 'single credential' into the per-run fake
    home: on this box the executor authenticates via HOME credentials
    (Phase 0 task 11), so the credential file is copied in — never
    inherited through the environment. The real ~/.claude.json holds
    project history and MUST NOT be copied; a minimal onboarding stub
    replaces it. Missing credentials are not an error (CI, keychain-auth
    boxes)."""
    real_home = Path(real_home) if real_home is not None else Path.home()
    cred = real_home / ".claude" / ".credentials.json"
    if cred.is_file():
        dest = Path(fake_home) / ".claude"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(cred, dest / ".credentials.json")
        (dest / ".credentials.json").chmod(0o600)
    (Path(fake_home) / ".claude.json").write_text(
        json.dumps({"hasCompletedOnboarding": True}) + "\n"
    )


# ---------------------------------------------------------------- spawner


def default_spawner(cmd, *, cwd, env, transcript_path):
    """Real executor spawn: stdin MUST be /dev/null (the CLI stalls
    waiting on it otherwise — observed 2026-07-29)."""
    with open(transcript_path, "w") as out:
        res = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
        )
    return res.returncode


def extract_cost_usd(transcript_path: Path) -> float | None:
    """FR-51: read `total_cost_usd` from the executor's own `result`
    message. Never estimated — a transcript with no result message (a
    crashed run, or a Tier-0 fake with a stubbed line) yields `None`
    rather than a guessed number.

    `transcript_path` is the executor's own stdout — `default_spawner`
    already redirects the full `stream-json` output there, so this reads
    the same file the transcript is retained as, not a second stream.
    """
    try:
        lines = Path(transcript_path).read_text().splitlines()
    except OSError:
        return None
    cost = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") == "result" and "total_cost_usd" in obj:
            cost = obj["total_cost_usd"]
    return cost


def write_timing(
    run_dir: Path, *, started_at: str, ended_at: str, duration_seconds: float, cost_usd
) -> dict:
    """Writes `timing.json` in the upstream-compatible wire shape pinned by
    `tests/test_schema_compat.py` (§5.5): `started_at`/`ended_at` as
    ISO-8601 UTC, `duration_seconds` a float. `cost_usd` is additional to
    that shape — an executor-only figure FR-36's `efficiency.cost` reads,
    kept alongside rather than folded into the wire-compat fields it
    doesn't define.
    """
    payload = {
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": duration_seconds,
        "cost_usd": cost_usd,
    }
    (run_dir / "timing.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    return payload


def _headless_result_text(cmd, *, cwd, env, timeout_seconds, timeout_exc, label):
    """Shared spawn-and-parse for harness-side model calls (grader and
    comparator): run `claude -p`, parse the `stream-json` output for the
    final `result` message's text — the agent's JSON response IS that
    text, since its brief requires responding with only the JSON
    object."""
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as e:
        raise timeout_exc() from e
    if res.returncode != 0:
        raise RuntimeError(
            f"{label} subprocess exited {res.returncode}: {res.stderr[-500:]}"
        )
    last_result = None
    last_is_error = False
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") == "result":
            last_result = obj.get("result")
            last_is_error = bool(obj.get("is_error"))
    if last_result is None:
        raise RuntimeError(f"{label} produced no result message")
    # A CLI-level failure sets `is_error` and puts an ERROR STRING in
    # `result` — while still exiting 0 and still reporting
    # `subtype: "success"` (observed 2026-07-29: an expired OAuth token
    # yields exit 0 + `is_error: true` + "Not logged in · Please run
    # /login"). Returning that string as if it were the grader's answer
    # makes the validator classify an INFRASTRUCTURE outage as
    # `grader_malformed_json`, which sends the next person debugging
    # the brief or the model instead of the auth. Surface it as a crash
    # so `error_class` names the real fault. `is_error` is the
    # discriminator, not `subtype` and not the exit code.
    if last_is_error:
        raise RuntimeError(f"{label} CLI reported an error: {str(last_result)[:300]}")
    return last_result


def default_grader_spawner(cmd, *, cwd, env):
    """Real grader spawn (DR-8: inline `--agents`, no registration)."""
    return _headless_result_text(
        cmd,
        cwd=cwd,
        env=env,
        timeout_seconds=GRADER_TIMEOUT_SECONDS,
        timeout_exc=GraderTimeout,
        label="grader",
    )


def default_comparator_spawner(cmd, *, cwd, env):
    """Real comparator spawn — same transport as the grader, its own
    timeout exception so FR-58 records `judge_timeout`, not
    `grader_timeout`."""
    return _headless_result_text(
        cmd,
        cwd=cwd,
        env=env,
        timeout_seconds=COMPARATOR_TIMEOUT_SECONDS,
        timeout_exc=JudgeTimeout,
        label="comparator",
    )


def _grader_brief_text() -> str:
    return GRADER_BRIEF_PATH.read_text()


def grade_run(
    r: dict, *, hmac_key: bytes, fixture_dir: Path, meta: dict, grader_spawner
) -> None:
    """Phase 2 per-run reconciliation and grading (FR-25..FR-27, FR-58):
    verify the audit chain, run the deterministic gate, invoke the
    grader with a retry budget, and write ONE `grading.json` carrying
    the grader's `expectations`/`summary` (or the `error_class` if
    grading never produced one), the harness-recorded `task_outcome`,
    the chain-verified audit-derived tool count, and
    `self_report_divergence` — additive fields beyond the upstream
    shape (FR-25), which a schema-compatible viewer ignores. Mutates
    `r` with `scoring`/`grading` for any in-process caller."""
    run_dir = Path(r["audit_log"]).parent
    scoring = finalize_run_scoring(
        audit_log=r["audit_log"],
        hmac_key=hmac_key,
        fixture_meta=meta,
        fixture_dir=fixture_dir,
        worktree=r["worktree"],
        transcript_path=r["transcript"],
    )
    r["scoring"] = scoring

    assertions_path = Path(fixture_dir) / "assertions.json"
    assertions = []
    if assertions_path.is_file():
        assertions = json.loads(assertions_path.read_text()).get("assertions", [])
    assertion_ids = [a["id"] for a in assertions]

    task_outcome_enum = TaskOutcome(scoring.task_outcome)
    brief_text = _grader_brief_text()

    def invoke():
        settings_path = run_dir / "grader-settings.json"
        if not settings_path.exists():
            settings_path.write_text(json.dumps({"hooks": {}}, indent=2) + "\n")
        cmd = build_run_command(
            prompt=build_grader_task_message(
                assertions=assertions,
                task_outcome=task_outcome_enum,
                transcript_path=r["transcript"],
                outputs_dir=r["worktree"],
            ),
            model=DEFAULT_GRADER_MODEL,
            effort=None,
            settings_path=settings_path,
            session_id=str(uuid.uuid4()),
            max_budget_usd=DEFAULT_GRADER_BUDGET_USD,
            agents_json=build_grader_agents_payload(brief_text),
            agent_name="vc-grader",
        )
        # Reuses the run's own allowlisted env/fake HOME (FR-54) — the
        # grader is harness-side tooling, not a candidate under test,
        # so it shares the same auth context as the executor it grades.
        return grader_spawner(cmd, cwd=run_dir, env=r["env"])

    outcome = grade_with_retries(
        invoke, expected_task_outcome=task_outcome_enum, assertion_ids=assertion_ids
    )

    if outcome.ok:
        grading_payload = dict(outcome.grading)
    else:
        grading_payload = {
            "error_class": outcome.error_class,
            "reason": outcome.reason,
            "task_outcome": scoring.task_outcome,
        }
    grading_payload["retries"] = outcome.retries_used

    summary = scoring.audit_summary
    grading_payload["audit"] = {
        "chain_ok": scoring.chain_ok,
        "error_class": scoring.error_class,
        "tool_counts": summary.tool_counts if summary else None,
        "audit_total": summary.audit_total if summary else None,
        "violation_attempted": len(summary.violation_attempted) if summary else None,
        "violation_completed": len(summary.violation_completed) if summary else None,
    }
    d = scoring.self_report_divergence
    grading_payload["self_report_divergence"] = (
        {
            "audit_total": d.audit_total,
            "reported_total": d.reported_total,
            "delta": d.delta,
            "delta_pct": d.delta_pct,
            "suspect": d.suspect,
        }
        if d is not None
        else None
    )

    (run_dir / "grading.json").write_text(
        json.dumps(grading_payload, indent=2, sort_keys=True) + "\n"
    )
    r["grading"] = grading_payload


# ---------------------------------------------------------------- run


def run_comparison(
    ns,
    *,
    parent_env: dict | None = None,
    spawner=None,
    grader_spawner=None,
    comparator_spawner=None,
    judging_seed=None,
) -> int:
    parent_env = dict(parent_env) if parent_env is not None else dict(os.environ)
    spawner = spawner or default_spawner
    grader_spawner = grader_spawner or default_grader_spawner
    comparator_spawner = comparator_spawner or default_comparator_spawner
    dev = parent_env.get("VERSUS_DEV") == "1"

    try:
        fixture_dir = resolve_fixture_dir(ns.fixture, dev=dev)
        meta = load_fixture(fixture_dir)
        unverified = check_discrimination(
            meta, unverified_ok=getattr(ns, "unverified_fixture", False)
        )

        if ns.self_calibrate:
            ca = cb = resolve_candidate(ns.candidates[0])
        else:
            ca, cb = resolve_pair(ns.candidates[0], ns.candidates[1])
    except FixtureError as e:
        raise ComparisonRefused(str(e)) from e

    def enforcement(c: Candidate):
        if c.kind is CandidateKind.AGENT:
            return resolve_enforcement(c.agent["tools"], c.agent["disallowedTools"])
        return resolve_enforcement(None, None)

    enf_a, enf_b = enforcement(ca), enforcement(cb)

    workspace = Path(ns.workspace) if ns.workspace else Path.home() / ".versus"
    # `comparison_id` may be pre-assigned by a caller that needs to know
    # it in advance (calibrate.py: it must read report.json back out of
    # `<workspace>/<comparison_id>/` once this call returns, and the id
    # is otherwise generated and lost inside this function). Absent for
    # every CLI-driven `run`, which keeps the random default.
    comparison_id = getattr(ns, "comparison_id", None) or "vc-" + uuid.uuid4().hex[:12]
    cmp_dir = workspace / comparison_id
    workspace.mkdir(parents=True, exist_ok=True)
    # same-uid private: run artifacts, transcripts, and (later) the
    # seal live under here at a predictable default path
    workspace.chmod(0o700)
    cmp_dir.mkdir()

    marker = cmp_dir / ".vc-run-state.json"

    def set_phase(phase: str) -> None:
        marker.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "started": True,
                    "fixture_id": meta["fixture_id"],
                    "clone_path": str(cmp_dir / "clone"),
                    "phase": phase,
                }
            )
        )

    set_phase("setup")

    n = ns.runs
    try:
        prepare_worktree(fixture_dir, cmp_dir / "clone")
        worktrees = create_worktrees(
            cmp_dir / "clone",
            meta["head_sha"],
            count=2 * n,
            base_dir=cmp_dir / "worktrees",
        )
    except (FixtureError, RunnerError) as e:
        shutil.rmtree(cmp_dir, ignore_errors=True)
        raise ComparisonRefused(f"setup failed: {e}") from e

    budget_per_run = ns.max_budget_usd or DEFAULT_RUN_BUDGET_USD
    specs = plan_runs(n=n)
    runs: list[dict] = []
    for i, spec in enumerate(specs):
        candidate = ca if spec.arm == 0 else cb
        run_id = f"pair{spec.pair_index}-arm{spec.arm}"
        run_dir = cmp_dir / "runs" / run_id
        run_dir.mkdir(parents=True)
        fake_home = run_dir / "home"
        fake_home.mkdir()
        wt = worktrees[i]
        # FR-20/FR-21.1: the run's audit FIFO is the sink both hooks
        # write into; the chain-hashed log lives at a sibling path the
        # harness-side AuditCollector owns (0400, created empty before
        # spawn — never before this point).
        audit_fifo = run_dir / "audit.fifo"
        audit_log = run_dir / "audit.jsonl"
        settings = write_run_settings(run_dir, worktree=wt, sink=audit_fifo)
        kwargs = dict(
            prompt=compose_prompt(fixture_dir, meta, candidate),
            model=executor_model(ns, candidate),
            effort=ns.effort,
            settings_path=settings,
            session_id=str(uuid.uuid4()),
            max_budget_usd=budget_per_run,
        )
        if candidate.kind is CandidateKind.SKILL:
            kwargs["plugin_dir"] = synthesize_wrapper(
                candidate.source_path, cmp_dir / "work"
            )
        else:
            kwargs["agents_json"] = agents_payload(candidate)
            kwargs["agent_name"] = candidate.agent["name"]
        cmd = build_run_command(**kwargs)
        env = build_child_env(parent_env, fake_home=fake_home)
        runs.append(
            {
                "spec": spec,
                "run_id": run_id,
                "cmd": cmd,
                "env": env,
                "worktree": wt,
                "transcript": run_dir / "transcript.jsonl",
                "audit_fifo": audit_fifo,
                "audit_log": audit_log,
            }
        )

    judge_cmp_dir = judge_root_for(workspace) / comparison_id

    # NO seed here. `pair_assignment` is a pure public function of
    # (seed, pair_index), and executors run with Bash whose deny checks
    # are network-only — a seed on disk before the executors exit would
    # let a hostile candidate compute its own A/B slot per pair and
    # embed slot-targeted bias no scrub can see (review finding,
    # 2026-07-29). The seed is generated at the top of the judging
    # phase and appended to this record then; T-I-4 replay reads it
    # from comparison.json/judging.json afterwards as before.
    record = {
        "comparison_id": comparison_id,
        "judge_root": str(judge_cmp_dir),
        "fixture_id": meta["fixture_id"],
        "fixture_dir": str(fixture_dir),
        "fixture_version": meta["fixture_version"],
        "fixture_unverified": unverified,
        "runs": ns.runs,
        "execution_path": "subprocess",
        "model_confounded": bool(ns.respect_candidate_model),
        "self_calibrate": bool(ns.self_calibrate),
        "env_allowlist": sorted(runs[0]["env"].keys()),
        "candidates": [
            {
                "kind": c.kind.value,
                "source_path": c.source_path,
                "head_sha": c.head_sha,
                "enforcement": e.to_record(),
            }
            for c, e in ((ca, enf_a), (cb, enf_b))
        ],
    }
    (cmp_dir / "comparison.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n"
    )

    if ns.dry_run:
        # FR-60: full setup happened above; print, spawn nothing.
        for r in runs:
            print(f"[{r['run_id']}] cwd={r['worktree']}")
            print("  " + " ".join(str(x) for x in r["cmd"]))
            print("  env keys: " + ",".join(sorted(r["env"])))
        # DR-11: executors (2N) + graders (2N) + comparators (N, ×2
        # under --double-judge); the real spend is bounded above by
        # this, since FR-30/33/34 pairs skip their comparator.
        comparators = n * (2 if ns.double_judge else 1)
        print(
            f"total invocations: {len(runs) * 2 + comparators} "
            f"(executors {len(runs)} + graders {len(runs)} + "
            f"comparators {comparators}); "
            f"budget ceiling: ${budget_per_run * len(runs):.2f} "
            f"(${budget_per_run:.2f}/run)"
        )
        marker.unlink(missing_ok=True)
        return 0

    set_phase("executing")
    for r in runs:
        provision_executor_auth(cmp_dir / "runs" / r["run_id"] / "home")
    failures = 0
    try:
        for batch in batch_pairs(specs, parallel_pairs=ns.parallel):
            batch_ids = {(s.pair_index, s.arm) for s in batch}
            for r in runs:
                if (r["spec"].pair_index, r["spec"].arm) not in batch_ids:
                    continue
                # FR-21.1/.4: the collector creates the log 0400 empty
                # and starts draining the FIFO BEFORE the subprocess
                # this run audits exists. hmac_key lives only in this
                # collector instance's memory for the rest of this
                # process (FR-21.2) — kept on `r` for the grading
                # phase later in this same call, never persisted.
                collector = AuditCollector(
                    log_path=r["audit_log"], fifo_path=r["audit_fifo"]
                )
                collector.start()
                rc = None
                # Wall clock for the retained timing.json (ISO-8601, matches
                # the schema-compat wire shape); monotonic for the duration
                # itself, since wall clock can jump backward under NTP and a
                # negative efficiency.wall_clock reading would be nonsense.
                started_at = datetime.now(timezone.utc)
                perf_start = time.monotonic()
                try:
                    rc = spawner(
                        r["cmd"],
                        cwd=r["worktree"],
                        env=r["env"],
                        transcript_path=r["transcript"],
                    )
                finally:
                    collector.stop(
                        terminal_reason="completed" if rc == 0 else "crashed"
                    )
                duration_seconds = time.monotonic() - perf_start
                ended_at = datetime.now(timezone.utc)
                r["timing"] = write_timing(
                    Path(r["audit_log"]).parent,
                    started_at=started_at.isoformat().replace("+00:00", "Z"),
                    ended_at=ended_at.isoformat().replace("+00:00", "Z"),
                    duration_seconds=duration_seconds,
                    cost_usd=extract_cost_usd(r["transcript"]),
                )
                if rc != 0:
                    failures += 1

                grade_run(
                    r,
                    hmac_key=collector.hmac_key,
                    fixture_dir=fixture_dir,
                    meta=meta,
                    grader_spawner=grader_spawner,
                )

        # ---- Phase 3: blind judging (FR-28..FR-35, FR-57, FR-58) ----
        # Inside the try so the comparator still has the runs' auth'd
        # fake homes; the finally below deletes the credentials.
        set_phase("judging")
        # Every executor subprocess has exited: the seed may now touch
        # disk (see the comparison.json comment above). `judging_seed`
        # is a TEST-ONLY injection point — the pinned-assignment tests
        # need a known seed; production callers must leave it None.
        seed = judging_seed or uuid.uuid4().hex
        record["seed"] = seed
        (cmp_dir / "comparison.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n"
        )
        by_pair: dict[int, dict] = {}
        for r in runs:
            arm_key = "candidate_a" if r["spec"].arm == 0 else "candidate_b"
            by_pair.setdefault(r["spec"].pair_index, {})[arm_key] = {
                "worktree": r["worktree"],
                "task_outcome": r["grading"]["task_outcome"],
            }
        pairs = [{"pair_index": k, **arms} for k, arms in sorted(by_pair.items())]
        denylist = derive_denylist(meta, [ca, cb])
        eval_dir = cmp_dir / "eval-0"
        judge_env = runs[0]["env"]
        brief_text = COMPARATOR_BRIEF_PATH.read_text()
        assertions_path = fixture_dir / "assertions.json"
        judge_assertions = (
            json.loads(assertions_path.read_text()).get("assertions", [])
            if assertions_path.is_file()
            else []
        )

        def invoke_comparator(pair_dir, task_message):
            # This closure never touches assignment.json: it receives a
            # staged pair dir and a scrubbed message, nothing else
            # (FR-28, DR-3).
            settings = write_judge_settings(
                eval_dir / "judge-settings",
                pair_dir=pair_dir,
                pair_name=Path(pair_dir).name,
            )
            cmd = build_run_command(
                prompt=task_message,
                model=DEFAULT_COMPARATOR_MODEL,
                effort=None,
                settings_path=settings,
                session_id=str(uuid.uuid4()),
                max_budget_usd=DEFAULT_COMPARATOR_BUDGET_USD,
                agents_json=build_comparator_agents_payload(brief_text),
                agent_name="vc-comparator",
            )
            return comparator_spawner(cmd, cwd=pair_dir, env=judge_env)

        judging = run_judging(
            eval_dir=eval_dir,
            judge_cmp_dir=judge_cmp_dir,
            pairs=pairs,
            denylist=denylist,
            seed=seed,
            task_prompt=(fixture_dir / meta["prompt_file"]).read_text(),
            assertions=judge_assertions,
            invoke_comparator=invoke_comparator,
            required_content=meta.get("required_content", ()),
            double_judge=bool(ns.double_judge),
        )
    except BaseException:
        # a crashed comparison must not advertise itself as "done" to
        # `clean --list` (review finding, 2026-07-29)
        set_phase("aborted")
        raise
    else:
        # FR-50/FR-56: build the report and sweep the whole comparison
        # directory for credentials while this process still holds the
        # real values (a later, standalone `report` regeneration cannot
        # — see report.generate's docstring). Runs before the `finally`
        # strips each run's fake-HOME credentials file, which is a
        # different, narrower cleanup than this sweep. Only on the
        # success path — a crashed comparison has nothing coherent to
        # report on, and `except` above already re-raises before this.
        from report import generate as generate_report

        safe_env_keys = {"PATH", "LANG", "TZ", "HOME"} | set(GIT_IDENTITY)
        credentials = {
            k: v for k, v in runs[0]["env"].items() if k not in safe_env_keys
        }
        generate_report(
            cmp_dir,
            quick=ns.quick,
            eval_name=meta["fixture_id"],
            credentials=credentials,
        )
        set_phase("done")
    finally:
        for r in runs:
            cred = (
                cmp_dir
                / "runs"
                / r["run_id"]
                / "home"
                / ".claude"
                / ".credentials.json"
            )
            cred.unlink(missing_ok=True)

    marker.unlink(missing_ok=True)
    if failures:
        print(f"{failures}/{len(runs)} runs exited non-zero", file=sys.stderr)
    if judging["harness_invalid"]:
        # an automation caller must be able to detect an invalid
        # harness run mechanically, not by parsing judging.json
        print(f"HARNESS_INVALID: {judging['harness_invalid_reason']}", file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------- clean


def clean_workspaces(ns) -> int:
    """FR-61 (Phase 1 slice): list by default, remove nothing without an
    explicit target; removal paths come from `git worktree list
    --porcelain` on the comparison's clone plus its own recorded
    workspace dir — never from a computed naming convention."""
    workspace = Path(ns.workspace) if ns.workspace else Path.home() / ".versus"
    if not workspace.is_dir():
        print(f"no workspace at {workspace}")
        return 0

    comparisons = sorted(
        d
        for d in workspace.iterdir()
        if d.is_dir()
        and ((d / "comparison.json").is_file() or (d / ".vc-run-state.json").is_file())
    )

    if ns.list_only:
        for d in comparisons:
            marker = d / ".vc-run-state.json"
            state = ""
            if marker.is_file():
                try:
                    phase = json.loads(marker.read_text()).get("phase")
                    state = f" [marker: phase={phase}]"
                except ValueError:
                    state = " [marker: unreadable]"
            print(f"{d.name}{state}")
        return 0

    targets = (
        comparisons
        if ns.clean_all
        else [d for d in comparisons if d.name == ns.comparison_id]
    )
    for d in targets:
        clone = d / "clone"
        if clone.is_dir():
            porcelain = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=clone,
                capture_output=True,
                text=True,
            )
            for line in porcelain.stdout.splitlines():
                if not line.startswith("worktree "):
                    continue
                wt = Path(line.split(" ", 1)[1])
                if wt.resolve() == clone.resolve():
                    continue
                if ns.dry_run:
                    print(f"would remove worktree {wt}")
                else:
                    subprocess.run(
                        ["git", "worktree", "remove", "--force", str(wt)],
                        cwd=clone,
                        capture_output=True,
                    )
        # NFR-3/FR-28: two roots exist; the judge root is removed only
        # via the path the comparison itself RECORDED, never one
        # computed from a naming convention (FR-61).
        judge_root = None
        cj = d / "comparison.json"
        if cj.is_file():
            try:
                judge_root = json.loads(cj.read_text()).get("judge_root")
            except ValueError:
                judge_root = None
        if ns.dry_run:
            print(f"would remove {d}")
            if judge_root and Path(judge_root).is_dir():
                print(f"would remove {judge_root}")
        else:
            if judge_root and Path(judge_root).is_dir():
                shutil.rmtree(judge_root, ignore_errors=True)
            shutil.rmtree(d, ignore_errors=True)
            print(f"removed {d.name}")
    return 0
