"""Credential redaction over retained artifacts (FR-56).

Distinct from FR-29's blinding scrub, and deliberately not shared with it:
that one removes *identity* from judge inputs before judging, this one
removes *credentials* from retained output after it. Different times,
different file sets, different failure modes — a shared implementation
would couple a blinding bug to a credential leak.

FR-49 retains transcripts, audit logs, `outputs/` and every JSON artifact
regardless of `--keep-worktrees`, which is what makes this pass mandatory
rather than optional.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# The artifact set FR-56 names. Directories are walked; missing entries are
# skipped rather than erroring, because a degraded comparison legitimately
# lacks some of them.
REDACTED_ARTIFACTS = (
    "transcript.jsonl",
    "audit.jsonl",
    "outputs",
    "report.json",
    "report.md",
    "benchmark.json",
    "benchmark.md",
)

# Secret-shaped patterns, each with the label its replacement carries.
# Ordered longest-match-first at application time; the labels are part of
# the output contract, so renaming one changes redacted artifacts.
SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"gh[pousr]_[A-Za-z0-9]{16,}", "github_token"),
    (r"sk-[A-Za-z0-9]{20,}", "api_key"),
    # A long hex/base64/dotted run *adjacent to a label*. The adjacency is
    # what keeps this from eating every sha256 the harness legitimately
    # records — chain digests, bundle hashes and the assignment seal are
    # all long hex runs, and redacting those would destroy the audit trail
    # this pass exists to preserve.
    #
    # The label itself allows a leading `[a-z0-9_]*` so an underscore-joined
    # env-var name like `DISCORD_BOT_TOKEN` or `RUNPOD_API_KEY` still
    # matches: `_` is a word character, so a bare `\btoken\b` never finds a
    # boundary between `BOT` and `TOKEN` in `BOT_TOKEN` and silently missed
    # every real credential this project actually names in CLAUDE.md (only
    # GH_TOKEN happened to also match the gh[pousr]_ shape pattern above).
    # The value charset includes `.` for Discord-style dot-segmented tokens.
    (
        r"(?i)\b[a-z0-9_]*(?:token|key|secret|password|passwd|bearer)\b"
        r"[\"'\s:=]+([A-Za-z0-9+/_.-]{20,}={0,2})",
        "labelled_secret",
    ),
)

_BINARY_SNIFF_BYTES = 8192


@dataclass
class RedactionReport:
    """FR-56: matches are counted so `report.json.redactions` can carry them."""

    counts: dict[str, int] = field(default_factory=dict)
    files_scanned: int = 0
    files_modified: int = 0

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def record(self, label: str, n: int = 1) -> None:
        if n:
            self.counts[label] = self.counts.get(label, 0) + n

    def to_json(self) -> dict:
        return {
            "credential_matches": self.total,
            "by_label": dict(sorted(self.counts.items())),
            "files_scanned": self.files_scanned,
            "files_modified": self.files_modified,
        }


def placeholder(label: str) -> str:
    return f"[REDACTED:{label}]"


def redact_text(
    text: str, credentials: dict[str, str] | None = None
) -> tuple[str, dict]:
    """Redact a single string. Returns (redacted, counts_by_label).

    Known credential *values* are replaced first and longest-first, so a
    short secret that is a substring of a longer one cannot leave the
    longer one's tail behind — the same overlap hazard the FR-29 scrub
    handles, for the same reason.
    """
    counts: dict[str, int] = {}
    out = text

    for key, value in sorted(
        (credentials or {}).items(), key=lambda kv: (-len(kv[1]), kv[0])
    ):
        # An empty or whitespace value would match everywhere; the env
        # allowlist can legitimately carry one (this box has no executor
        # credential at all), so guard rather than assume.
        if not value or not value.strip():
            continue
        n = out.count(value)
        if n:
            out = out.replace(value, placeholder(key))
            counts[key] = counts.get(key, 0) + n

    for pattern, label in SECRET_PATTERNS:
        compiled = re.compile(pattern)

        def _sub(match: re.Match, _label: str = label) -> str:
            # A pattern with a capture group redacts only the secret, not
            # the label that identified it — keeping "token: [REDACTED:...]"
            # readable rather than erasing the surrounding context.
            if match.lastindex:
                start = match.start(1) - match.start(0)
                return match.group(0)[:start] + placeholder(_label)
            return placeholder(_label)

        out, n = compiled.subn(_sub, out)
        if n:
            counts[label] = counts.get(label, 0) + n

    return out, counts


def _looks_binary(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(_BINARY_SNIFF_BYTES)
    except OSError:
        return True
    return b"\x00" in chunk


def redact_file(
    path: Path, credentials: dict[str, str] | None, report: RedactionReport
) -> bool:
    """Redact one file in place. Returns True when it changed."""
    if not path.is_file() or _looks_binary(path):
        return False
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    report.files_scanned += 1
    redacted, counts = redact_text(original, credentials)
    for label, n in counts.items():
        report.record(label, n)
    if redacted != original:
        path.write_text(redacted, encoding="utf-8")
        report.files_modified += 1
        return True
    return False


def redact_comparison(
    cmp_dir: Path,
    credentials: dict[str, str] | None = None,
    report: RedactionReport | None = None,
) -> RedactionReport:
    """Walk a comparison directory and redact every retained artifact.

    Run before the comparison directory is considered complete. Paths are
    visited in sorted order so the counts are bit-stable for a fixed tree.
    """
    report = report or RedactionReport()
    cmp_dir = Path(cmp_dir)
    names = set(REDACTED_ARTIFACTS)
    targets: list[Path] = []
    for path in sorted(cmp_dir.rglob("*")):
        if path.is_dir():
            continue
        if path.name in names or any(part in names for part in path.parts):
            targets.append(path)
    for path in targets:
        redact_file(path, credentials, report)
    return report


def write_redaction_record(cmp_dir: Path, report: RedactionReport) -> Path:
    """Persist the counts next to the artifacts they describe."""
    path = Path(cmp_dir) / "redactions.json"
    path.write_text(json.dumps(report.to_json(), indent=2, sort_keys=True) + "\n")
    return path
