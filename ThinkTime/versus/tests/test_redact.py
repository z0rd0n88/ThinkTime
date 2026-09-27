"""Credential redaction over retained artifacts — FR-56 (T-U-23)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import redact  # noqa: E402

CREDS = {"GH_TOKEN": "ghp_realSecretValue0123456789abcd"}


def test_known_credential_value_is_replaced_with_its_key_name():
    out, counts = redact.redact_text(
        "export GH_TOKEN=ghp_realSecretValue0123456789abcd", CREDS
    )
    assert "ghp_realSecretValue0123456789abcd" not in out
    assert "[REDACTED:GH_TOKEN]" in out
    assert counts["GH_TOKEN"] == 1


def test_github_token_shape_is_caught_without_being_in_the_allowlist():
    out, counts = redact.redact_text("saw ghs_AAAAAAAAAAAAAAAAAAAAAA in the log")
    assert "ghs_AAAAAAAAAAAAAAAAAAAAAA" not in out
    assert counts["github_token"] == 1


def test_sk_api_key_shape_is_caught():
    out, counts = redact.redact_text("key sk-abcdefghijklmnopqrstuvwxyz012345")
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in out
    assert counts["api_key"] == 1


def test_labelled_hex_run_is_caught_and_the_label_survives():
    out, counts = redact.redact_text('"secret": "0123456789abcdef0123456789abcdef"')
    assert "0123456789abcdef0123456789abcdef" not in out
    assert "secret" in out  # the label stays readable
    assert counts["labelled_secret"] == 1


def test_unlabelled_sha256_is_left_alone():
    """Chain digests, bundle hashes and the assignment seal are long hex runs.

    Redacting those would destroy the audit trail this pass exists to keep.
    """
    digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    out, counts = redact.redact_text(f'"assignment_sha256": "{digest}"')
    assert digest in out
    assert counts == {}


def test_ordinary_text_is_untouched():
    text = "the candidate wrote OUTPUT.md and exited 0\n"
    out, counts = redact.redact_text(text, CREDS)
    assert out == text
    assert counts == {}


def test_longest_value_is_redacted_first():
    """A short secret that prefixes a longer one must not orphan its tail."""
    creds = {"SHORT": "ghp_AAAAAAAAAAAAAAAA", "LONG": "ghp_AAAAAAAAAAAAAAAABBBBBBBB"}
    out, _ = redact.redact_text("value=ghp_AAAAAAAAAAAAAAAABBBBBBBB", creds)
    assert out == "value=[REDACTED:LONG]"


def test_empty_credential_value_is_not_a_wildcard():
    """The env allowlist can carry an empty credential slot (FR-54)."""
    out, counts = redact.redact_text("harmless text", {"EMPTY": "", "BLANK": "   "})
    assert out == "harmless text"
    assert counts == {}


def test_redaction_is_idempotent():
    once, _ = redact.redact_text("token: ghp_AAAAAAAAAAAAAAAAAAAA", CREDS)
    twice, counts = redact.redact_text(once, CREDS)
    assert twice == once
    assert counts == {}


def _seed_comparison(tmp_path: Path) -> Path:
    cmp_dir = tmp_path / "vc-abc123"
    run = cmp_dir / "runs" / "pair0-arm0"
    (run / "outputs").mkdir(parents=True)
    (run / "transcript.jsonl").write_text(
        json.dumps(
            {"type": "assistant", "text": "using ghp_realSecretValue0123456789abcd"}
        )
        + "\n"
    )
    (run / "audit.jsonl").write_text(
        json.dumps(
            {"tool_input": {"command": "curl -H 'token: ghp_AAAAAAAAAAAAAAAAAAAA'"}}
        )
        + "\n"
    )
    (run / "outputs" / "OUTPUT.md").write_text(
        "see sk-abcdefghijklmnopqrstuvwxyz012345\n"
    )
    (cmp_dir / "report.json").write_text(
        json.dumps({"note": "ghp_realSecretValue0123456789abcd"})
    )
    (cmp_dir / "report.md").write_text(
        "# Report\n\nghp_realSecretValue0123456789abcd\n"
    )
    (cmp_dir / "benchmark.json").write_text(json.dumps({"eval_name": "clean"}))
    (cmp_dir / "benchmark.md").write_text("# Benchmark\n")
    return cmp_dir


def test_every_named_artifact_class_is_swept(tmp_path):
    cmp_dir = _seed_comparison(tmp_path)
    report = redact.redact_comparison(cmp_dir, CREDS)

    blob = "".join(p.read_text() for p in sorted(cmp_dir.rglob("*")) if p.is_file())
    assert "ghp_realSecretValue0123456789abcd" not in blob
    assert "ghp_AAAAAAAAAAAAAAAAAAAA" not in blob
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in blob
    assert report.total >= 5
    assert report.files_modified == 5
    assert report.to_json()["credential_matches"] == report.total


def test_binary_artifacts_are_not_rewritten(tmp_path):
    cmp_dir = _seed_comparison(tmp_path)
    blob = cmp_dir / "runs" / "pair0-arm0" / "outputs" / "image.bin"
    payload = b"\x00\x01ghp_realSecretValue0123456789abcd\x00"
    blob.write_bytes(payload)
    redact.redact_comparison(cmp_dir, CREDS)
    assert blob.read_bytes() == payload


def test_redaction_record_is_written(tmp_path):
    cmp_dir = _seed_comparison(tmp_path)
    report = redact.redact_comparison(cmp_dir, CREDS)
    path = redact.write_redaction_record(cmp_dir, report)
    on_disk = json.loads(path.read_text())
    assert on_disk["credential_matches"] == report.total
    assert set(on_disk) == {
        "credential_matches",
        "by_label",
        "files_scanned",
        "files_modified",
    }


def test_counts_are_stable_across_repeated_walks(tmp_path):
    first = redact.redact_comparison(_seed_comparison(tmp_path / "a"), CREDS).to_json()
    second = redact.redact_comparison(_seed_comparison(tmp_path / "b"), CREDS).to_json()
    assert first == second


def test_underscore_joined_env_var_names_are_caught():
    """A bare `\\btoken\\b` never finds a boundary inside `BOT_TOKEN` since
    `_` is a word character — this project names exactly these shapes
    (DISCORD_BOT_TOKEN, RUNPOD_API_KEY) in CLAUDE.md."""
    out, counts = redact.redact_text(
        "DISCORD_BOT_TOKEN=abcdefghijklmnopqrstuvwxyz0123456789"
    )
    assert "abcdefghijklmnopqrstuvwxyz0123456789" not in out
    assert counts["labelled_secret"] == 1

    out, counts = redact.redact_text(
        "RUNPOD_API_KEY=abcdefghijklmnopqrstuvwxyz0123456789"
    )
    assert "abcdefghijklmnopqrstuvwxyz0123456789" not in out
    assert counts["labelled_secret"] == 1


def test_dot_segmented_token_is_caught():
    """Some bot-token formats join base64url segments with dots; the value
    charset must tolerate `.` without needing a real token shape to test it."""
    token = "aaaaaaaaaaaaaaaaaaaaaaaa.bbbbbb.cccccccccccccccccccccccccccccccc"
    out, counts = redact.redact_text(f"labelled_token: {token}")
    assert token not in out
    assert counts["labelled_secret"] == 1


def test_prose_containing_a_label_word_without_a_secret_shape_is_untouched():
    out, counts = redact.redact_text(
        "monkey business: this is not a secret value at all"
    )
    assert counts == {}
    out, counts = redact.redact_text("please rotate the token like we discussed")
    assert counts == {}
