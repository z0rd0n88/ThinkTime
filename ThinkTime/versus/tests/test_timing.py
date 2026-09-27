"""Executor timing/cost capture — FR-36 (efficiency.wall_clock, .cost), FR-51.

`timing.json` did not exist before Phase 4: neither wall clock nor
`total_cost_usd` was ever captured for an executor run. These tests pin
the new capture against the upstream-compatible wire shape the schema
corpus already asserts (`tests/corpus/eval-0/*/run-1/timing.json`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from run_comparison import extract_cost_usd, write_timing  # noqa: E402


def test_extract_cost_usd_reads_the_last_result_message(tmp_path):
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps({"type": "assistant", "text": "..."})
        + "\n"
        + json.dumps({"type": "result", "total_cost_usd": 0.1732, "is_error": False})
        + "\n"
    )
    assert extract_cost_usd(transcript) == 0.1732


def test_extract_cost_usd_takes_the_last_result_line(tmp_path):
    """A retried CLI call can emit more than one `result` message; the
    final one is the one that actually completed."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps({"type": "result", "total_cost_usd": 0.02, "is_error": True})
        + "\n"
        + json.dumps({"type": "result", "total_cost_usd": 0.19, "is_error": False})
        + "\n"
    )
    assert extract_cost_usd(transcript) == 0.19


def test_extract_cost_usd_returns_none_without_a_result_message(tmp_path):
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps({"type": "assistant", "text": "no result here"}) + "\n"
    )
    assert extract_cost_usd(transcript) is None


def test_extract_cost_usd_returns_none_for_a_stubbed_fake_transcript(tmp_path):
    """FakeSpawner (Tier 0) writes a bare `{"type":"result"}` with no cost key."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text('{"type":"result"}\n')
    assert extract_cost_usd(transcript) is None


def test_extract_cost_usd_returns_none_for_a_missing_file(tmp_path):
    assert extract_cost_usd(tmp_path / "does-not-exist.jsonl") is None


def test_extract_cost_usd_skips_malformed_lines(tmp_path):
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "not json at all\n"
        + json.dumps({"type": "result", "total_cost_usd": 0.05})
        + "\n"
    )
    assert extract_cost_usd(transcript) == 0.05


def test_write_timing_matches_the_schema_compat_wire_shape(tmp_path):
    payload = write_timing(
        tmp_path,
        started_at="2026-07-29T00:00:00Z",
        ended_at="2026-07-29T00:01:00Z",
        duration_seconds=60.0,
        cost_usd=0.31,
    )
    on_disk = json.loads((tmp_path / "timing.json").read_text())
    assert on_disk == payload
    # the three upstream-pinned fields must be present with the right shape
    assert on_disk["started_at"] == "2026-07-29T00:00:00Z"
    assert on_disk["ended_at"] == "2026-07-29T00:01:00Z"
    assert on_disk["duration_seconds"] == 60.0


def test_write_timing_carries_cost_usd_as_none_when_unavailable(tmp_path):
    payload = write_timing(
        tmp_path,
        started_at="2026-07-29T00:00:00Z",
        ended_at="2026-07-29T00:00:01Z",
        duration_seconds=1.0,
        cost_usd=None,
    )
    assert payload["cost_usd"] is None
