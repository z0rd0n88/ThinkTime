#!/usr/bin/env python3
"""Candidate resolution: FR-1..FR-5 and the FR-62 enforcement chain.

Vocabularies are closed Enums with exhaustive, ordered dispatch — the FR-62
chain is first-match-wins over an ordered branch list, never a partition
(an explicit `tools: []` satisfies two branch predicates; order decides).
Stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# FR-4: entries in tools/disallowedTools are validated against this list
# before launch. Names are the Claude Code tool surface on 2.1.204.
KNOWN_TOOLS: frozenset[str] = frozenset(
    {
        "Agent",
        "Task",
        "Bash",
        "BashOutput",
        "KillShell",
        "Read",
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        "Glob",
        "Grep",
        "LS",
        "WebFetch",
        "WebSearch",
        "TodoWrite",
        "Skill",
        "SlashCommand",
        "ExitPlanMode",
        "AskUserQuestion",
    }
)


class CandidateError(Exception):
    """A candidate failed resolution; the comparison must not launch."""


class ContradictionRefusal(CandidateError):
    """FR-62 fallback (2): the declaration cannot be expressed as an
    allow-list; the candidate is refused with this printed reason rather
    than run with an unenforced disallowedTools."""


class CandidateKind(Enum):
    SKILL = "skill"
    AGENT = "agent"


class RestrictionsDeclared(Enum):
    NONE = "none"
    TOOLS_ONLY_EMPTY = "tools_only_empty"
    DECLARED = "declared"


class EnforcementPath(Enum):
    PASS_THROUGH = "pass_through"
    TRANSLATED = "translated"


@dataclass(frozen=True)
class EnforcementResult:
    """The FR-62 branch outcome, recorded per candidate in comparison.json."""

    path: EnforcementPath
    restrictions_declared: RestrictionsDeclared
    disallowed_tools_enforced: bool = False
    tools_allowlist_enforced: bool = False
    disallowed_tools_translated: bool = False
    effective_allowlist: list[str] | None = None

    def to_record(self) -> dict:
        return {
            "enforcement_path": self.path.value,
            "restrictions_declared": self.restrictions_declared.value,
            "disallowed_tools_enforced": self.disallowed_tools_enforced,
            "tools_allowlist_enforced": self.tools_allowlist_enforced,
            "disallowed_tools_translated": self.disallowed_tools_translated,
            "effective_allowlist": self.effective_allowlist,
        }


def resolve_enforcement(
    tools: list[str] | None,
    disallowed: list[str] | None,
    *,
    known_tools: frozenset[str] = KNOWN_TOOLS,
    disallowed_honoured: bool = True,
) -> EnforcementResult:
    """FR-62 ordered chain, post-observation form (2026-07-29).

    Branches are evaluated in the order written; the first match wins.
    `tools=None` means the key was absent (T defaults to the full known
    list); `tools=[]` is an explicit empty declaration and is a distinct
    shape. `disallowed_honoured=False` is the platform-regression
    contingency: translation fallback, then contradiction refusal.
    """
    # Branch 1 — no restriction declared at all: neither flag is stamped.
    if tools is None and disallowed is None:
        return EnforcementResult(
            path=EnforcementPath.PASS_THROUGH,
            restrictions_declared=RestrictionsDeclared.NONE,
        )

    # Branch 2 — explicit `tools: []` (OQ6(b): restricts to nothing).
    # Satisfies both T ⊆ D and T ∩ D = ∅ for every D; resolves here, first.
    if tools is not None and len(tools) == 0:
        return EnforcementResult(
            path=EnforcementPath.PASS_THROUGH,
            restrictions_declared=RestrictionsDeclared.TOOLS_ONLY_EMPTY,
        )

    t = set(tools) if tools is not None else set(known_tools)
    d = set(disallowed) if disallowed is not None else set()

    if not disallowed_honoured and disallowed is not None:
        return _fallback(
            t, d, tools_declared=tools is not None, known_tools=known_tools
        )

    # Branch 3 — T ⊆ D with non-empty T: effective set is empty; denial
    # and zero-tool collapse are indistinguishable here (task 5).
    if t <= d:
        return EnforcementResult(
            path=EnforcementPath.PASS_THROUGH,
            restrictions_declared=RestrictionsDeclared.DECLARED,
            disallowed_tools_enforced=True,
        )

    # Branch 4 — T ∩ D = ∅: the default shape; enforcement rests on FR-8's
    # observed allow-list contract (task 6), not on disallowedTools.
    if not (t & d):
        return EnforcementResult(
            path=EnforcementPath.PASS_THROUGH,
            restrictions_declared=RestrictionsDeclared.DECLARED,
            tools_allowlist_enforced=True,
        )

    # Branch 5 — genuine partial restriction: denial observed (task 5b),
    # per-tool schema subtraction T − D. The pre-observation refuse gate
    # is history.
    return EnforcementResult(
        path=EnforcementPath.PASS_THROUGH,
        restrictions_declared=RestrictionsDeclared.DECLARED,
        disallowed_tools_enforced=True,
    )


def _fallback(
    t: set[str], d: set[str], *, tools_declared: bool, known_tools: frozenset[str]
) -> EnforcementResult:
    """FR-62 fallback chain for an un-honoured disallowedTools.

    (1) translate to an equivalent allow-list: allow = T − D (well-defined
    because FR-4 validated every entry); (2) refuse a contradiction no
    allow-list can express — an empty translated allow-list over a
    non-empty T is that contradiction."""
    allow = sorted(t - d)
    if not allow:
        raise ContradictionRefusal(
            "candidate refused: disallowedTools is not honoured by the "
            f"platform and the declaration (tools={sorted(t)}, "
            f"disallowedTools={sorted(d)}) leaves an empty allow-list, "
            "which no tools allow-list can express; running it would "
            "leave disallowedTools silently unenforced (FR-62)"
        )
    return EnforcementResult(
        path=EnforcementPath.TRANSLATED,
        restrictions_declared=RestrictionsDeclared.DECLARED,
        disallowed_tools_translated=True,
        effective_allowlist=allow,
    )


# ---------------------------------------------------------------- FR-4 parse


def _parse_list(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("["):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise CandidateError(f"expected a list, got: {value!r}")
        return [str(x) for x in parsed]
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_agent_md(path: Path) -> dict:
    """FR-4: parse an agent .md into
    {name, description, prompt, tools, disallowedTools, model}.

    `prompt` is the body below the closing `---`. Absent tools /
    disallowedTools parse to None (distinct from an explicit empty list —
    the FR-62 chain branches on that difference)."""
    text = Path(path).read_text()
    if not text.startswith("---"):
        raise CandidateError(f"agent file has no frontmatter: {path}")
    try:
        _, front, body = text.split("---", 2)
    except ValueError as e:
        raise CandidateError(f"agent frontmatter is unterminated: {path}") from e

    fields: dict[str, str] = {}
    for line in front.splitlines():
        if ":" not in line or not line.strip():
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()

    def listfield(key: str) -> list[str] | None:
        if key not in fields:
            return None
        return _parse_list(fields[key])

    return {
        "name": fields.get("name", ""),
        "description": fields.get("description", ""),
        "model": fields.get("model") or None,
        "tools": listfield("tools"),
        "disallowedTools": listfield("disallowedTools"),
        "prompt": body.lstrip("\n"),
    }


# ---------------------------------------------------------------- FR-1 kinds


@dataclass(frozen=True)
class Candidate:
    kind: CandidateKind
    source_path: str
    head_sha: str
    agent: dict | None = None  # FR-4 parse, agent kind only


def _source_sha(path: Path) -> str:
    """FR-1: the source repo's HEAD sha, or `uncommitted:<content-hash>`
    when outside a repo or dirty."""
    probe_dir = path if path.is_dir() else path.parent
    res = subprocess.run(
        ["git", "-C", str(probe_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        head = res.stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(probe_dir), "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        if dirty.returncode == 0 and not dirty.stdout.strip():
            return head
    return "uncommitted:" + _content_hash(path)


def _content_hash(path: Path) -> str:
    h = hashlib.sha256()
    if path.is_file():
        h.update(path.read_bytes())
    else:
        for f in sorted(p for p in path.rglob("*") if p.is_file()):
            h.update(str(f.relative_to(path)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def resolve_candidate(spec: str | Path) -> Candidate:
    """FR-1: classify a candidate specifier and record its provenance."""
    path = Path(spec).resolve()
    if not path.exists():
        raise CandidateError(f"candidate does not exist: {spec}")

    if path.is_dir():
        if (path / ".claude-plugin" / "plugin.json").is_file():
            kind = CandidateKind.SKILL
        elif (path / "SKILL.md").is_file():
            kind = CandidateKind.SKILL
        else:
            raise CandidateError(
                f"candidate dir is neither a plugin nor a skill "
                f"(no .claude-plugin/plugin.json, no SKILL.md): {spec}"
            )
        return Candidate(kind=kind, source_path=str(path), head_sha=_source_sha(path))

    if path.suffix == ".md":
        agent = parse_agent_md(path)
        for key in ("tools", "disallowedTools"):
            entries = agent[key] or []
            unknown = [e for e in entries if e not in KNOWN_TOOLS]
            if unknown:
                raise CandidateError(
                    f"agent {path.name}: unknown {key} entries "
                    f"{unknown} (FR-4); known tools: "
                    f"{sorted(KNOWN_TOOLS)}"
                )
        return Candidate(
            kind=CandidateKind.AGENT,
            source_path=str(path),
            head_sha=_source_sha(path),
            agent=agent,
        )

    raise CandidateError(f"candidate is neither a directory nor an agent .md: {spec}")


def resolve_pair(
    a: str | Path, b: str | Path, *, self_calibrate: bool = False
) -> tuple[Candidate, Candidate]:
    """FR-2 (cross-kind refusal) and FR-3 (same-path refusal unless
    --self-calibrate). Refuses before any worktree exists (T-I-7)."""
    ca, cb = resolve_candidate(a), resolve_candidate(b)
    if ca.kind is not cb.kind:
        raise CandidateError(
            f"candidates have different kind: {ca.kind.value} vs "
            f"{cb.kind.value}; cross-kind comparison is deferred (FR-2, DR-6)"
        )
    if ca.source_path == cb.source_path and not self_calibrate:
        raise CandidateError(
            "both candidates resolve to the same path "
            f"({ca.source_path}); A-vs-A requires --self-calibrate (FR-3)"
        )
    return ca, cb


# ---------------------------------------------------------------- FR-5


def synthesize_wrapper(skill_dir: str | Path, work_dir: str | Path) -> Path:
    """FR-5: wrap a bare skill dir in a throwaway plugin so it loads with
    --plugin-dir. A dir that is already a plugin passes through unwrapped."""
    skill_dir = Path(skill_dir).resolve()
    if (skill_dir / ".claude-plugin" / "plugin.json").is_file():
        return skill_dir

    if not (skill_dir / "SKILL.md").is_file():
        raise CandidateError(f"not a skill dir (no SKILL.md): {skill_dir}")

    slug = skill_dir.name
    plugin_dir = Path(work_dir).resolve() / "candidates" / slug
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": f"vc-wrap-{slug}",
                "version": "0.0.0",
                "description": "versus throwaway wrapper (FR-5)",
                "skills": [f"./skills/{slug}"],
            },
            indent=2,
        )
        + "\n"
    )
    dest = plugin_dir / "skills" / slug
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(skill_dir, dest)
    return plugin_dir
