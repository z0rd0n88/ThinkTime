"""Phase 2 tests: hooks/audit-tool.sh + scripts/audit_tools.py — FR-20,
FR-21, FR-22, FR-23, FR-24, FR-55 (T-U-17 parser, T-U-19 divergence,
T-U-20's audit-hook-exits-0 half, T-C-3's chain PASS predicate).

Tier 0: real FIFOs under tmp_path; no executor is spawned.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_tools import (  # noqa: E402
    AuditCollector,
    DIVERGENCE_SUSPECT_THRESHOLD_PCT,
    compute_self_report_divergence,
    constraints_from_fixture,
    parse_audit_records,
    stamp_record,
    verify_chain,
)

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "audit-tool.sh"


# ---------------------------------------------------------------- T-U-20 (audit half)


class TestAuditHookAlwaysExitsZero:
    def _run(self, fifo: Path | None, payload: dict, cwd: Path):
        cmd = ["bash", str(HOOK)]
        if fifo is not None:
            cmd.append(str(fifo))
        return subprocess.run(
            cmd, input=json.dumps(payload), text=True, capture_output=True, cwd=str(cwd)
        )

    def test_exits_0_with_no_fifo_arg(self, tmp_path):
        res = self._run(
            None,
            {"tool_name": "Bash", "tool_input": {"command": "curl evil"}},
            tmp_path,
        )
        assert res.returncode == 0

    def test_exits_0_when_fifo_path_is_not_a_fifo(self, tmp_path):
        not_a_fifo = tmp_path / "plain"
        not_a_fifo.write_text("")
        res = self._run(not_a_fifo, {"tool_name": "Read"}, tmp_path)
        assert res.returncode == 0

    def test_exits_0_on_unparseable_stdin(self, tmp_path):
        fifo = tmp_path / "audit.fifo"
        os.mkfifo(fifo)
        # No reader present; the hook's own timeout bounds the write, and
        # the malformed-JSON path returns before ever reaching the FIFO.
        cmd = ["bash", str(HOOK), str(fifo)]
        res = subprocess.run(
            cmd, input="not json", text=True, capture_output=True, cwd=str(tmp_path)
        )
        assert res.returncode == 0

    def test_forwards_unstamped_record_to_fifo(self, tmp_path):
        fifo = tmp_path / "audit.fifo"
        os.mkfifo(fifo)

        received = {}

        def reader():
            with open(fifo) as f:
                line = f.readline()
                received["line"] = line

        import threading

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        time.sleep(0.05)  # let the blocking open() start before we write

        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/wt/out.txt",
                "command": None,
                "pattern": None,
            },
            "session_id": "sess-1",
            "cwd": "/wt",
        }
        res = self._run(fifo, payload, tmp_path)
        t.join(timeout=2)

        assert res.returncode == 0
        assert received.get("line"), "hook did not forward a record"
        record = json.loads(received["line"])
        assert record["type"] == "tool_call"
        assert record["tool_name"] == "Write"
        assert record["tool_input"]["file_path"] == "/wt/out.txt"
        assert "seq" not in record  # unstamped — the collector stamps it
        assert "prev_hash" not in record


class TestPipeBufTruncation:
    """FR-20: every emitted record must fit inside PIPE_BUF (4096 bytes
    on Linux) INCLUDING its trailing newline, or the FIFO write is no
    longer atomic and concurrent hook invocations can interleave."""

    def _emit(self, payload: dict, tmp_path) -> dict:
        fifo = tmp_path / "audit.fifo"
        if not fifo.exists():
            os.mkfifo(fifo)
        received = {}

        def reader():
            with open(fifo) as f:
                received["line"] = f.readline()

        import threading

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        time.sleep(0.05)
        res = subprocess.run(
            ["bash", str(HOOK), str(fifo)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=str(tmp_path),
        )
        t.join(timeout=3)
        assert res.returncode == 0
        line = received.get("line", "")
        return {"line": line, "bytes": len(line.encode())}

    def test_ascii_oversize_record_is_truncated(self, tmp_path):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "x" * 8000},
            "session_id": "s1",
            "cwd": "/wt",
        }
        out = self._emit(payload, tmp_path)
        assert out["bytes"] <= 4096
        assert json.loads(out["line"])["truncated"] is True

    def test_multibyte_oversize_record_is_truncated(self, tmp_path):
        """The regression: 1500 CJK characters measure ~1500 under
        `${#RECORD}` (a CHARACTER count) but occupy ~4500 BYTES. A
        character-based bound check skips truncation and emits a
        non-atomic write. The check must be byte-based."""
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "漢" * 1500},
            "session_id": "s1",
            "cwd": "/wt",
        }
        out = self._emit(payload, tmp_path)
        assert out["bytes"] <= 4096, (
            f"emitted {out['bytes']} bytes — a character-based length "
            "check let a multi-byte payload past the PIPE_BUF bound"
        )
        assert json.loads(out["line"])["truncated"] is True

    def test_truncated_record_with_huge_cwd_still_fits(self, tmp_path):
        """The truncated fallback still carries `cwd`, an unbounded
        path — so it can itself breach the bound. A second fallback
        must drop it."""
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "x" * 8000},
            "session_id": "s1",
            "cwd": "/" + "d" * 6000,
        }
        out = self._emit(payload, tmp_path)
        assert out["bytes"] <= 4096
        record = json.loads(out["line"])
        assert record["truncated"] is True
        assert record["cwd"] is None  # dropped by the second fallback

    def test_normal_record_is_not_truncated(self, tmp_path):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/wt/small.txt"},
            "session_id": "s1",
            "cwd": "/wt",
        }
        out = self._emit(payload, tmp_path)
        record = json.loads(out["line"])
        assert "truncated" not in record
        assert record["tool_input"]["file_path"] == "/wt/small.txt"


# ---------------------------------------------------------------- FR-21 collector + chain


def _collector(tmp_path) -> AuditCollector:
    return AuditCollector(
        log_path=tmp_path / "run-1.jsonl", fifo_path=tmp_path / "audit.fifo"
    )


class TestAuditCollector:
    def test_log_created_0400_and_empty_before_any_write(self, tmp_path):
        c = _collector(tmp_path)
        c.create_empty()
        assert c.log_path.exists()
        assert c.log_path.read_bytes() == b""
        assert (os.stat(c.log_path).st_mode & 0o777) == 0o400
        assert c.fifo_path.exists()
        c.stop()

    def test_collector_is_sole_writer_stamps_seq_and_chain(self, tmp_path):
        c = _collector(tmp_path)
        c.start()
        with open(c.fifo_path, "w") as f:
            f.write(json.dumps({"type": "tool_call", "tool_name": "Read"}) + "\n")
        with open(c.fifo_path, "w") as f:
            f.write(json.dumps({"type": "tool_call", "tool_name": "Write"}) + "\n")
        c.stop(terminal_reason="completed")

        v = verify_chain(c.log_path, c.hmac_key)
        assert v.ok, v.reason
        assert [r["seq"] for r in v.records] == [0, 1, 2]
        assert v.records[0]["tool_name"] == "Read"
        assert v.records[1]["tool_name"] == "Write"
        assert v.records[2]["type"] == "terminal"

    def test_hook_and_collector_end_to_end(self, tmp_path):
        """The real hook forwards through a real FIFO into a running
        collector — exercising the exact integration point."""
        c = _collector(tmp_path)
        c.start()
        worktree = tmp_path / "wt"
        worktree.mkdir()
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {},
        }
        res = subprocess.run(
            ["bash", str(HOOK), str(c.fifo_path)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=str(worktree),
        )
        assert res.returncode == 0
        c.stop()

        v = verify_chain(c.log_path, c.hmac_key)
        assert v.ok, v.reason
        assert v.records[0]["tool_name"] == "Read"


class TestChainVerification:
    def test_absent_log_is_audit_integrity(self, tmp_path):
        v = verify_chain(tmp_path / "missing.jsonl", b"key")
        assert not v.ok
        assert v.error_class == "audit_integrity"

    def test_empty_log_is_audit_integrity(self, tmp_path):
        log = tmp_path / "run.jsonl"
        log.write_bytes(b"")
        os.chmod(log, 0o400)
        v = verify_chain(log, b"key")
        assert not v.ok
        assert v.error_class == "audit_integrity"

    def test_wrong_mode_is_audit_integrity(self, tmp_path):
        c = _collector(tmp_path)
        c.start()
        c.stop()
        os.chmod(c.log_path, 0o644)
        v = verify_chain(c.log_path, c.hmac_key)
        assert not v.ok
        assert v.error_class == "audit_integrity"

    def test_missing_terminal_record_is_audit_integrity(self, tmp_path):
        # A run that died mid-flight: one stamped record, no terminal.
        log = tmp_path / "run.jsonl"
        key = b"k" * 32
        rec = stamp_record(
            {"type": "tool_call", "tool_name": "Read"}, seq=0, prev_hash=""
        )
        # Compute the real genesis hash to isolate this test to the
        # missing-terminal defect, not an incidental hash mismatch.
        import hashlib

        rec["prev_hash"] = hashlib.sha256(key + b"").hexdigest()
        log.write_text(json.dumps(rec, sort_keys=True) + "\n")
        os.chmod(log, 0o400)
        v = verify_chain(log, key)
        assert not v.ok
        assert v.error_class == "audit_integrity"
        assert "terminal" in v.reason

    def test_tampered_record_breaks_the_chain(self, tmp_path):
        c = _collector(tmp_path)
        c.start()
        with open(c.fifo_path, "w") as f:
            f.write(json.dumps({"type": "tool_call", "tool_name": "Read"}) + "\n")
        c.stop()

        lines = c.log_path.read_text().splitlines()
        tampered = json.loads(lines[0])
        tampered["tool_name"] = "Write"  # rewrite history
        os.chmod(c.log_path, 0o600)
        lines[0] = json.dumps(tampered, sort_keys=True)
        c.log_path.write_text("\n".join(lines) + "\n")
        os.chmod(c.log_path, 0o400)

        v = verify_chain(c.log_path, c.hmac_key)
        assert not v.ok
        assert v.error_class == "audit_integrity"

    def test_seq_gap_breaks_the_chain(self, tmp_path):
        c = _collector(tmp_path)
        c.start()
        with open(c.fifo_path, "w") as f:
            f.write(json.dumps({"type": "tool_call", "tool_name": "Read"}) + "\n")
        with open(c.fifo_path, "w") as f:
            f.write(json.dumps({"type": "tool_call", "tool_name": "Write"}) + "\n")
        c.stop()

        lines = c.log_path.read_text().splitlines()
        rec1 = json.loads(lines[1])
        rec1["seq"] = 5
        os.chmod(c.log_path, 0o600)
        lines[1] = json.dumps(rec1, sort_keys=True)
        c.log_path.write_text("\n".join(lines) + "\n")
        os.chmod(c.log_path, 0o400)

        v = verify_chain(c.log_path, c.hmac_key)
        assert not v.ok
        assert v.error_class == "audit_integrity"

    def test_wrong_key_cannot_forge_a_valid_chain(self, tmp_path):
        c = _collector(tmp_path)
        c.start()
        with open(c.fifo_path, "w") as f:
            f.write(json.dumps({"type": "tool_call", "tool_name": "Read"}) + "\n")
        c.stop()

        v = verify_chain(c.log_path, b"wrong-key-entirely-different-32b")
        assert not v.ok
        assert v.error_class == "audit_integrity"


# ---------------------------------------------------------------- T-U-17 parser


CONSTRAINTS = constraints_from_fixture(
    {
        "constraints": [
            {
                "id": "C-readonly",
                "type": "forbid_write_paths",
                "tools": ["Edit", "Write", "NotebookEdit"],
                "except_under": ".vc-out/",
            },
            {
                "id": "C-nopush",
                "type": "forbid_bash",
                "patterns": ["git push", "gh pr "],
            },
        ]
    }
)


def tc(
    seq,
    tool,
    tool_input=None,
    *,
    hook_event="PreToolUse",
    denied=False,
    rtype="tool_call",
):
    r = {
        "seq": seq,
        "type": rtype,
        "hook_event_name": hook_event,
        "tool_name": tool,
        "tool_input": tool_input or {},
    }
    if denied:
        r["denied"] = True
    return r


class TestAuditParser:
    def test_per_tool_counts(self):
        records = [
            tc(0, "Read"),
            tc(1, "Read"),
            tc(2, "Write", {"file_path": ".vc-out/x"}),
        ]
        summary = parse_audit_records(records, CONSTRAINTS)
        assert summary.tool_counts == {"Read": 2, "Write": 1}
        assert summary.audit_total == 3

    def test_denied_forbidden_call_is_violation_attempted(self):
        records = [tc(0, "Write", {"file_path": "/etc/passwd"}, denied=True)]
        summary = parse_audit_records(records, CONSTRAINTS)
        assert len(summary.violation_attempted) == 1
        assert summary.violation_attempted[0]["constraint_id"] == "C-readonly"
        assert summary.violation_completed == []

    def test_successful_forbidden_call_is_violation_completed(self):
        records = [tc(0, "Write", {"file_path": "/tmp/escape.txt"})]
        summary = parse_audit_records(records, CONSTRAINTS)
        assert summary.violation_completed[0]["constraint_id"] == "C-readonly"
        assert summary.violation_attempted == []

    def test_write_under_except_under_is_not_a_violation(self):
        records = [tc(0, "Write", {"file_path": ".vc-out/report.md"})]
        summary = parse_audit_records(records, CONSTRAINTS)
        assert summary.violation_completed == []
        assert summary.violation_attempted == []

    def test_forbidden_bash_pattern_is_violation_completed(self):
        records = [tc(0, "Bash", {"command": "git push origin main"})]
        summary = parse_audit_records(records, CONSTRAINTS)
        assert summary.violation_completed[0]["constraint_id"] == "C-nopush"

    def test_containment_denied_excluded_from_constraint_adherence(self):
        records = [
            tc(0, "Bash", rtype="containment_denied"),
            tc(1, "Read"),
        ]
        summary = parse_audit_records(records, CONSTRAINTS)
        assert len(summary.containment_denied) == 1
        assert summary.violation_attempted == []
        assert summary.violation_completed == []
        # a harness event, not a candidate finding — never in tool_counts
        assert "Bash" not in summary.tool_counts

    def test_posttooluse_does_not_double_count(self):
        records = [
            tc(0, "Read", hook_event="PreToolUse"),
            tc(1, "Read", hook_event="PostToolUse"),
        ]
        summary = parse_audit_records(records, CONSTRAINTS)
        assert summary.tool_counts == {"Read": 1}
        assert summary.audit_total == 1

    def test_terminal_record_ignored(self):
        records = [tc(0, "Read"), {"seq": 1, "type": "terminal", "reason": "completed"}]
        summary = parse_audit_records(records, CONSTRAINTS)
        assert summary.audit_total == 1


# ---------------------------------------------------------------- T-U-19 divergence


class TestSelfReportDivergence:
    def test_golden_delta_pct_and_suspect_threshold(self):
        d = compute_self_report_divergence(audit_total=41, reported_total=22)
        assert d.delta == 19
        assert d.delta_pct == 46.3
        assert d.suspect is True

    def test_below_threshold_not_suspect(self):
        d = compute_self_report_divergence(audit_total=10, reported_total=9)
        assert d.delta_pct == 10.0
        assert d.suspect is False

    def test_exactly_at_threshold_not_suspect(self):
        d = compute_self_report_divergence(audit_total=100, reported_total=75)
        assert d.delta_pct == DIVERGENCE_SUSPECT_THRESHOLD_PCT
        assert d.suspect is False

    def test_zero_audit_total_no_divide_by_zero(self):
        d = compute_self_report_divergence(audit_total=0, reported_total=0)
        assert d.delta_pct == 0.0
        assert d.suspect is False

    def test_both_totals_always_present_never_reconciled(self):
        d = compute_self_report_divergence(audit_total=41, reported_total=22)
        assert d.audit_total == 41
        assert d.reported_total == 22

    def test_per_tool_breakdown(self):
        d = compute_self_report_divergence(
            audit_total=5,
            reported_total=3,
            audit_per_tool={"Read": 3, "Write": 2},
            reported_per_tool={"Read": 3},
        )
        assert d.per_tool["Write"] == {"audit": 2, "reported": 0}
