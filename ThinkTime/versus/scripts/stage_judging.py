#!/usr/bin/env python3
"""Blind judging: FR-28..FR-35, FR-57, FR-58 (judging half). Stdlib only.

Blinding is a FILESYSTEM-BOUNDARY claim, not a prompt claim (DR-3): the
judge root is a sibling of the workspace, the comparator's cwd is
`pair-k/`, and the unblinding key — `assignment.json` — plus the scrub
logs live workspace-side, unreachable by any relative path from the
judge root.

The seal's invariant, stated precisely: the launching PROCESS holds the
assignment in memory throughout (staging needs it — that is unavoidable
and not what the seal protects). What the seal + `_read_seal_bytes`
funnel guarantee is (a) the seal FILE is opened only to unseal, after
every comparator invocation has completed, and (b) the comparator
SUBPROCESS's context and reachable filesystem never carry the mapping.
`_read_seal_bytes` is the one funnel through which sealed bytes are
ever read, so a test can assert the ordering.

The scrub's threat model, stated precisely: it removes EXPLICIT
identity strings (literal, NFC-normalized, zero-width-stripped, and
UTF-16-encoded forms of the denylist terms). It does not — cannot —
remove stylometric identity: format, phrasing, or structure a judge
might recognize. That residual is mitigated only by the brief's
`identity_inferred` self-report protocol.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grading import extract_json_candidates  # noqa: E402

REDACTED = "[REDACTED]"
SCRUB_MAX_REMOVAL = 0.02  # FR-30
STAGED_MTIME = 946684800  # 2000-01-01T00:00:00Z — mtime ordering is a decoder (DR-3)
JUDGE_RETRY_BUDGET = 2  # FR-58: two ADDITIONAL attempts (three total)
COMPARISON_INVALID_RETRY_RATE = 0.20  # FR-58 comparison-level guard
DEFAULT_COMPARATOR_MODEL = "haiku"
DEFAULT_COMPARATOR_BUDGET_USD = 0.5
COMPARATOR_TIMEOUT_SECONDS = 300
COMPARATOR_BRIEF_PATH = (
    Path(__file__).resolve().parent.parent / "briefs" / "vc-comparator.md"
)

VALID_WINNERS = ("A", "B", "TIE")


class SealBroken(Exception):
    """FR-57: a tampered (or double-written) seal — the caller must
    surface HARNESS_INVALID, never an unsealed result."""


class JudgeTimeout(Exception):
    """Raised by an injected comparator invoke to represent a timeout."""


class JudgeBudgetExceeded(Exception):
    """Raised by an injected comparator invoke for a budget overrun."""


class JudgeErrorClass(Enum):
    CRASHED = "judge_crashed"
    MALFORMED_JSON = "judge_malformed_json"
    INVALID_WINNER = "judge_invalid_winner"
    BUDGET_EXCEEDED = "judge_budget_exceeded"
    TIMEOUT = "judge_timeout"
    PROTOCOL_VIOLATION = "judge_protocol_violation"


# ---------------------------------------------------------------- FR-28 roots


def judge_root_for(workspace: Path) -> Path:
    """The judge root is a SIBLING of the workspace, never a descendant
    (FR-28): `~/.versus` → `~/.versus-judge`. No `..` chain from a
    pair dir reaches the workspace."""
    workspace = Path(workspace)
    return workspace.with_name(workspace.name + "-judge")


# ---------------------------------------------------------------- FR-29 denylist


_AUTHOR_LINE = re.compile(
    r"^authors?\s*:\s*(?:\[(?P<list>[^\]]*)\]|(?P<one>.+))$", re.IGNORECASE
)
_NAME_LINE = re.compile(r"^name\s*:\s*(?P<one>.+)$", re.IGNORECASE)


def _author_terms(source_path: Path) -> set[str]:
    """FR-29 names authors, slugs, plugin names, and command names in
    the denylist — none of which `Candidate` carries structurally
    (FR-4 does not parse them), so this reads the carriers directly:

    - `author:`/`authors:` AND `name:` frontmatter lines in the
      candidate's own .md (or a dir candidate's SKILL.md/README.md) —
      the registered `name:` may differ from the directory basename,
      and a skill routinely PRINTS its own registered name into output
      ("Using the X skill…"), so omitting it is a probable literal
      leak (review finding, 2026-07-29);
    - `plugin.json`'s top-level `name` and `author.name`;
    - basenames of anything under a sibling `commands/` dir."""
    terms: set[str] = set()
    md_files = []
    if source_path.is_file():
        md_files.append(source_path)
    elif source_path.is_dir():
        md_files.extend(
            p
            for p in (source_path / "SKILL.md", source_path / "README.md")
            if p.is_file()
        )
        pj = source_path / "plugin.json"
        if pj.is_file():
            try:
                pj_data = json.loads(pj.read_text())
            except ValueError:
                pj_data = {}
            author = pj_data.get("author")
            if isinstance(author, dict):
                author = author.get("name")
            if isinstance(author, str) and author:
                terms.add(author)
            plugin_name = pj_data.get("name")
            if isinstance(plugin_name, str) and plugin_name:
                terms.add(plugin_name)
        commands_dir = source_path / "commands"
        if commands_dir.is_dir():
            for cmd in commands_dir.iterdir():
                if cmd.is_file():
                    terms.add(cmd.stem)
    for md in md_files:
        try:
            head = md.read_text(errors="replace")[:4000]
        except OSError:
            continue
        for line in head.splitlines():
            m = _AUTHOR_LINE.match(line.strip())
            if not m:
                m = _NAME_LINE.match(line.strip())
            if not m:
                continue
            groups = m.groupdict()
            if groups.get("list") is not None:
                for item in groups["list"].split(","):
                    terms.add(item.strip().strip("'\""))
            else:
                terms.add(groups["one"].strip().strip("'\""))
    return {t for t in terms if t}


def derive_denylist(fixture_meta: dict, candidates) -> list[str]:
    """FR-29's term set: `fixture.json.denylist[]` plus, per candidate,
    its file/dir basename (stem for files), its parent directory
    basename, its agent name, and the registered names / plugin name /
    command names / author names its own files declare
    (`_author_terms`). Sorted longest-first so an overlapping shorter
    term can never pre-empt a longer one."""
    terms = {t for t in fixture_meta.get("denylist", []) if t}
    for c in candidates:
        src = Path(
            getattr(c, "source_path", c["source_path"] if isinstance(c, dict) else "")
        )
        if not str(src):
            continue
        terms.add(src.stem if src.suffix else src.name)
        terms.add(src.name)
        terms.add(src.parent.name)
        agent = getattr(c, "agent", None) or (
            c.get("agent") if isinstance(c, dict) else None
        )
        if agent and agent.get("name"):
            terms.add(agent["name"])
        terms |= _author_terms(src)
    terms.discard("")
    return sorted(terms, key=lambda t: (-len(t), t))


def denylist_in_required_content(denylist, required_content) -> bool:
    """FR-30's second gate: a denylist term inside the fixture's
    REQUIRED content cannot be scrubbed without corrupting the
    artifact, so the pair (in practice: every pair) is unjudgeable."""
    lowered = [t.lower() for t in denylist]
    return any(t in req.lower() for req in required_content for t in lowered)


# ---------------------------------------------------------------- FR-28 assignment


def pair_assignment(seed: str, pair_index: int) -> dict:
    """Seeded per-pair {A,B} → candidate map. sha256-derived rather than
    `random.Random` so the mapping depends on nothing but these bytes —
    it is on the must-be-bit-stable list, and T-I-4 replay recovers it
    from the recorded seed alone."""
    digest = hashlib.sha256(f"{seed}:pair-{pair_index}".encode()).digest()
    a_first = (digest[0] & 1) == 0
    return {
        "A": "candidate_a" if a_first else "candidate_b",
        "B": "candidate_b" if a_first else "candidate_a",
    }


def invert_assignment(mapping: dict) -> dict:
    return {"A": mapping["B"], "B": mapping["A"]}


# ---------------------------------------------------------------- FR-57 seal


@dataclass(frozen=True)
class SealedAssignment:
    path: Path
    sha256: str


def _read_seal_bytes(path: Path) -> bytes:
    """The ONLY route through which sealed bytes are read back. Tests
    monkeypatch this to (a) assert the launch path never calls it
    before judging completes and (b) simulate external tampering."""
    return Path(path).read_bytes()


def seal_assignment(eval_dir: Path, assignments: dict) -> SealedAssignment:
    """FR-28/FR-57: written ONCE, mode 0400, sha256 recorded by the
    harness at write time. Never re-read to decide anything before
    judging completes."""
    path = Path(eval_dir) / "assignment.json"
    if path.exists():
        raise SealBroken(f"assignment.json already exists at {path} (write-once seal)")
    data = json.dumps(assignments, indent=2, sort_keys=True) + "\n"
    path.write_text(data)
    path.chmod(0o400)
    return SealedAssignment(path=path, sha256=hashlib.sha256(data.encode()).hexdigest())


def verify_seal(path: Path, expected_sha256: str) -> None:
    actual = hashlib.sha256(_read_seal_bytes(path)).hexdigest()
    if actual != expected_sha256:
        raise SealBroken(
            f"assignment seal mismatch: recorded {expected_sha256}, "
            f"on-disk hashes to {actual} (FR-57 — the blinding cannot be "
            "shown to have held)"
        )


def unseal_assignment(path: Path, expected_sha256: str) -> dict:
    raw = _read_seal_bytes(path)
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise SealBroken(
            f"assignment seal mismatch: recorded {expected_sha256}, "
            f"on-disk hashes to {actual} (FR-57)"
        )
    return json.loads(raw)


# ---------------------------------------------------------------- FR-29 scrub


def _scrub_pattern(denylist) -> re.Pattern | None:
    if not denylist:
        return None
    ordered = sorted(denylist, key=lambda t: (-len(t), t))
    return re.compile("|".join(re.escape(t) for t in ordered), re.IGNORECASE)


def scrub_text(text: str, denylist) -> tuple[str, list[dict]]:
    """Replace every denylist occurrence (case-insensitive) with
    `[REDACTED]`; longest term wins on overlap. Substitutions carry the
    offset in the ORIGINAL text and the canonical denylist term."""
    pattern = _scrub_pattern(denylist)
    if pattern is None:
        return text, []
    canonical = {t.lower(): t for t in denylist}
    subs: list[dict] = []

    def _replace(m: re.Match) -> str:
        subs.append(
            {
                "offset": m.start(),
                "term": canonical.get(m.group(0).lower(), m.group(0)),
            }
        )
        return REDACTED

    return pattern.sub(_replace, text), subs


def removal_fraction(original: str, subs: list[dict]) -> float:
    """Fraction of the artifact's characters the scrub removed (FR-30's
    2% gate input). Measured on matched characters over original
    length, not on the delta after `[REDACTED]` insertion."""
    if not original:
        return 0.0
    removed = sum(len(s["term"]) for s in subs)
    return removed / len(original)


# ---------------------------------------------------------------- extraction


def extract_outputs(
    worktree: Path, *, ignored_out: list[str] | None = None
) -> list[str]:
    """The run's extracted outputs: every file the run added or
    modified relative to the pinned baseline, from `git status
    --porcelain` — never `.git`, never unchanged baseline files (which
    are byte-identical in both arms and carry no signal).

    Output is decoded with `surrogateescape`, never strictly: a
    hostile candidate creating one non-UTF-8-named file must not be
    able to crash judging (same DoS class as the circular-symlink
    guard — review finding, 2026-07-29).

    Gitignored files a run wrote are NOT outputs here (the grader
    reads the worktree directly, so the two would otherwise silently
    diverge on their evidence base); `--ignored=matching` surfaces
    them, and callers passing `ignored_out` receive their rels so the
    divergence can be LOGGED rather than invisible."""
    res = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "-z",
            "--untracked-files=all",
            "--ignored=matching",
        ],
        cwd=worktree,
        capture_output=True,
    )
    if res.returncode != 0:
        stderr = res.stderr.decode("utf-8", errors="surrogateescape")
        raise RuntimeError(f"git status failed in {worktree}: {stderr.strip()}")
    rels: list[str] = []
    stdout = res.stdout.decode("utf-8", errors="surrogateescape")
    entries = stdout.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue
        status, path = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            i += 1  # -z renames/copies carry the origin path as the next record
        if "D" in status:
            continue
        if status == "!!":
            if ignored_out is not None:
                ignored_out.append(path)
            continue
        rels.append(path)
    return sorted(rels)


# ---------------------------------------------------------------- FR-28 staging


@dataclass
class StagedPair:
    pair_dir: Path
    log_path: Path
    unjudgeable_blind: bool = False
    reasons: list[str] = field(default_factory=list)
    substitutions: int = 0


def _normalize_mtimes(root: Path) -> None:
    for p in [root, *root.rglob("*")]:
        os.utime(p, (STAGED_MTIME, STAGED_MTIME), follow_symlinks=False)


# zero-width characters a candidate could interleave through its own
# name to defeat a literal scrub match
_ZERO_WIDTH = dict.fromkeys(
    map(ord, "\u200b\u200c\u200d\u2060\ufeff")
)  # ZWSP ZWNJ ZWJ WJ BOM


def _normalize_for_scrub(text: str) -> str:
    """NFC-normalize and strip zero-width characters before scrubbing —
    closes the lowest-effort encoding evasions (a term split by
    zero-width joiners, or written in a decomposed Unicode form, would
    otherwise pass the literal match; review finding 2026-07-29).
    Scrub-log offsets refer to THIS normalized text. Beyond it the
    scrub remains a literal-match bound: homoglyphs and heavier
    encodings are the documented residual (module docstring)."""
    return unicodedata.normalize("NFC", text).translate(_ZERO_WIDTH)


def _reserve_dest(
    pair_dir: Path, slot: str, dest_rel: Path, reserved: set[Path]
) -> tuple[Path, Path, bool]:
    """Post-scrub destination paths can collide (two names differing
    only in scrubbed terms both become `[REDACTED]…`, or a genuine
    file is literally named `[REDACTED]…`). A silent overwrite would
    show the judge an incomplete arm — so collisions disambiguate
    deterministically (`-2`, `-3`, … before the suffix, in sorted
    source order) and the caller logs a `filename_collision` entry
    (review finding, 2026-07-29)."""
    dest = pair_dir / slot / dest_rel
    if dest not in reserved and not dest.exists():
        reserved.add(dest)
        return dest_rel, dest, False
    n = 2
    while True:
        cand = dest_rel.with_name(f"{dest_rel.stem}-{n}{dest_rel.suffix}")
        d = pair_dir / slot / cand
        if d not in reserved and not d.exists():
            reserved.add(d)
            return cand, d, True
        n += 1


def stage_pair(
    *,
    pair_dir: Path,
    eval_dir: Path,
    pair_name: str,
    mapping: dict,
    worktrees: dict,
    denylist,
) -> StagedPair:
    """Copy each arm's extracted outputs into neutral `A/`/`B/` under
    the judge root, scrubbed (FR-29), with symlinks dereferenced-or-
    dropped and mtimes normalized (DR-3). The scrub log — the cleartext
    key to the blinding — is written to `<eval_dir>/scrub/<pair>.log`,
    workspace-side, ALWAYS (even for a pair that ends unjudgeable).
    Log entries carry `file` (original `slot/rel`) and, where the
    artifact was staged, `staged_as` (post-scrub path) — one spelling
    per key, never mixed."""
    pair_dir = Path(pair_dir)
    eval_dir = Path(eval_dir)
    # the neutral slots exist even for an arm that produced nothing —
    # an empty B/ is itself evidence the judge should see, and the
    # comparator's cwd must exist regardless
    (pair_dir / "A").mkdir(parents=True, exist_ok=True)
    (pair_dir / "B").mkdir(parents=True, exist_ok=True)
    log_entries: list[dict] = []
    result = StagedPair(
        pair_dir=pair_dir, log_path=eval_dir / "scrub" / f"{pair_name}.log"
    )

    # binary term scan covers ASCII and both UTF-16 byte orders: a
    # UTF-16 text file fails the UTF-8 decode and would otherwise
    # carry NUL-interleaved identity bytes straight past an ASCII-only
    # scan (review finding, 2026-07-29)
    lowered_terms = [t.lower().encode() for t in denylist]
    lowered_terms += [t.lower().encode("utf-16-le") for t in denylist]
    lowered_terms += [t.lower().encode("utf-16-be") for t in denylist]
    reserved: set[Path] = set()
    for slot in ("A", "B"):
        src_wt = Path(worktrees[mapping[slot]]).resolve()
        ignored: list[str] = []
        rels = extract_outputs(src_wt, ignored_out=ignored)
        rel_set = set(rels)
        for ig in ignored:
            # not staged (the grader sees the worktree directly, the
            # judge sees only extracted outputs) — logged so the
            # evidence-base divergence is visible, not silent
            log_entries.append(
                {
                    "file": f"{slot}/{ig}",
                    "offset": None,
                    "term": None,
                    "action": "ignored_output_skipped",
                }
            )
        for rel in rels:
            src = src_wt / rel
            if src.is_symlink():
                try:
                    target = src.resolve()
                # Python 3.12 pathlib raises RuntimeError on a symlink
                # loop, not OSError
                except (OSError, RuntimeError):
                    # a circular symlink is a hostile-candidate DoS
                    # vector; degrade to dropped, never crash judging
                    log_entries.append(
                        {
                            "file": f"{slot}/{rel}",
                            "offset": None,
                            "term": None,
                            "action": "symlink_dropped",
                        }
                    )
                    continue
                # DR-3: materialize ONLY a target that is itself a
                # member of this arm's extracted outputs — not merely
                # inside the worktree. A linked worktree's `.git` is a
                # regular FILE naming the workspace path and run index
                # (arm parity), and unchanged baseline files are
                # outside the extraction criterion; both drop (review
                # finding, 2026-07-29).
                if (
                    target.is_file()
                    and target.is_relative_to(src_wt)
                    and target.relative_to(src_wt).as_posix() in rel_set
                ):
                    data = target.read_bytes()
                    log_entries.append(
                        {
                            "file": f"{slot}/{rel}",
                            "offset": None,
                            "term": None,
                            "action": "symlink_materialized",
                        }
                    )
                else:
                    # an escaping (or non-output-targeting) symlink
                    # defeats the boundary (F-6)
                    log_entries.append(
                        {
                            "file": f"{slot}/{rel}",
                            "offset": None,
                            "term": None,
                            "action": "symlink_dropped",
                        }
                    )
                    continue
            elif src.is_file():
                data = src.read_bytes()
            else:
                continue

            # filename scrub: a path component carrying identity is the
            # same channel as content (FR-29, DR-3)
            name_parts = []
            for part in Path(rel).parts:
                new_part, part_subs = scrub_text(_normalize_for_scrub(part), denylist)
                for s in part_subs:
                    log_entries.append(
                        {
                            "file": f"{slot}/{rel}",
                            "offset": s["offset"],
                            "term": s["term"],
                            "action": "filename",
                        }
                    )
                name_parts.append(new_part)
            dest_rel = Path(*name_parts)

            try:
                text = data.decode("utf-8")
                # BOM-less UTF-16 of ASCII text decodes as VALID UTF-8
                # (NUL-interleaved), so it would sail past the binary
                # path and the literal scrub both; no legitimate text
                # artifact contains NUL — route it to the binary term
                # scan (review finding, 2026-07-29)
                if "\x00" in text:
                    raise UnicodeDecodeError(
                        "utf-8", data[:1], 0, 1, "NUL byte in text artifact"
                    )
            except UnicodeDecodeError:
                lowered = data.lower()
                if any(t in lowered for t in lowered_terms):
                    # a term inside bytes the scrub cannot rewrite —
                    # the artifact cannot be blinded (FR-30 by analogy)
                    result.unjudgeable_blind = True
                    result.reasons.append(
                        f"denylist term inside binary artifact {slot}/{rel}"
                    )
                    log_entries.append(
                        {
                            "file": f"{slot}/{rel}",
                            "offset": None,
                            "term": None,
                            "action": "binary_unscrubbable",
                        }
                    )
                    continue  # never staged
                dest_rel, dest, collided = _reserve_dest(
                    pair_dir, slot, dest_rel, reserved
                )
                if collided:
                    log_entries.append(
                        {
                            "file": f"{slot}/{rel}",
                            "staged_as": f"{slot}/{dest_rel}",
                            "offset": None,
                            "term": None,
                            "action": "filename_collision",
                        }
                    )
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                continue

            text = _normalize_for_scrub(text)
            scrubbed, subs = scrub_text(text, denylist)
            dest_rel, dest, collided = _reserve_dest(pair_dir, slot, dest_rel, reserved)
            if collided:
                log_entries.append(
                    {
                        "file": f"{slot}/{rel}",
                        "staged_as": f"{slot}/{dest_rel}",
                        "offset": None,
                        "term": None,
                        "action": "filename_collision",
                    }
                )
            for s in subs:
                log_entries.append(
                    {
                        "file": f"{slot}/{rel}",
                        "staged_as": f"{slot}/{dest_rel}",
                        "offset": s["offset"],
                        "term": s["term"],
                    }
                )
            if removal_fraction(text, subs) > SCRUB_MAX_REMOVAL:
                result.unjudgeable_blind = True
                result.reasons.append(
                    f"scrub would remove >{SCRUB_MAX_REMOVAL:.0%} of {slot}/{rel}"
                )
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(scrubbed)

    if pair_dir.exists():
        _normalize_mtimes(pair_dir)

    result.substitutions = len(log_entries)
    result.log_path.parent.mkdir(parents=True, exist_ok=True)
    result.log_path.write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in log_entries)
    )
    return result


# ---------------------------------------------------------------- comparator


def build_comparator_agents_payload(brief_text: str) -> dict:
    """DR-8/DR-10: inline `--agents`, no registration — same transport
    as the grader, with one load-bearing difference: a `tools`
    ALLOWLIST. The deny hook's path containment is sound only for the
    structured-path tools (Read/Glob/Grep); its Bash checks are
    network-only, "best-effort by design" — so a comparator with Bash
    could `cat` the sealed assignment (0400 does not bind the same
    uid) and unblind itself (review finding, 2026-07-29). The `tools`
    allowlist is enforcement the platform was OBSERVED to apply
    (FR-8/OQ6, 2026-07-29), so the comparator gets exactly the three
    tools whose containment is sound, and no shell at all. No Write
    either: the HARNESS writes verdict.json."""
    return {
        "vc-comparator": {
            "description": "versus-compare blind pairwise quality judge",
            "prompt": brief_text,
            "tools": ["Read", "Glob", "Grep"],
        }
    }


def build_comparator_task_message(*, task_prompt: str, assertions: list[dict]) -> str:
    """FR-31: the comparator receives the eval prompt, the assertions,
    and the two neutral dirs — nothing else. The caller scrubs
    `task_prompt`/`assertions` before building this."""
    return json.dumps(
        {
            "task_prompt": task_prompt,
            "assertions": assertions,
            "artifact_dirs": ["A/", "B/"],
        },
        indent=2,
    )


@dataclass
class JudgeOutcome:
    ok: bool
    verdict: dict | None = None
    error_class: str | None = None
    reason: str | None = None
    retries_used: int = 0


def validate_comparator_response(raw: str) -> JudgeOutcome:
    """FR-58 judging half. The extraction leniency (prose/fences) is the
    Phase 2 lesson applied forward: discarding a usable verdict skews
    the quality denominator. The vocabulary has no `schema_invalid`
    member — a parseable response missing `winner` is malformed, a
    present-but-foreign `winner` is `judge_invalid_winner`, and a
    self-reported identity inference is `judge_protocol_violation`
    (checked FIRST: a judge that saw through the blinding has no valid
    verdict whatever its winner says).

    Unlike the grader, the comparator path examines EVERY parseable
    span, not just the last well-shaped one (review finding,
    2026-07-29): the grader's last-wins rationale assumed a quoted
    foreign blob lacks the grading shape, but the comparator's shape
    collapses to the single forgeable key `winner`. So: an
    `identity_inferred: true` in ANY span poisons the whole response;
    spans carrying DISAGREEING winner values are malformed (→ retry —
    a judge that quoted a planted blob after its own verdict must not
    hand the planted value the win); and among agreeing spans the last
    FULL-shape one (winner + rationale + identity_inferred) is
    preferred over a bare `{"winner": …}` fragment."""
    parsed = extract_json_candidates(raw)
    if not parsed:
        return JudgeOutcome(
            False,
            error_class=JudgeErrorClass.MALFORMED_JSON.value,
            reason="response contains no parseable JSON object",
        )
    if any(span.get("identity_inferred") is True for span in parsed):
        return JudgeOutcome(
            False,
            error_class=JudgeErrorClass.PROTOCOL_VIOLATION.value,
            reason="comparator reports having inferred candidate identity",
        )
    winner_spans = [s for s in parsed if "winner" in s]
    if not winner_spans:
        return JudgeOutcome(
            False,
            error_class=JudgeErrorClass.MALFORMED_JSON.value,
            reason="response carries no winner field",
        )
    distinct = {json.dumps(s["winner"], sort_keys=True) for s in winner_spans}
    if len(distinct) > 1:
        return JudgeOutcome(
            False,
            error_class=JudgeErrorClass.MALFORMED_JSON.value,
            reason="response carries multiple spans with disagreeing winners",
        )
    full_shape = [
        s for s in winner_spans if "rationale" in s and "identity_inferred" in s
    ]
    data = (full_shape or winner_spans)[-1]
    flag = data.get("identity_inferred")
    if flag is not None and not isinstance(flag, bool):
        # a string "false"/"true" is neither a confession nor a clean
        # bill — malformed, so the retry path gets another attempt
        return JudgeOutcome(
            False,
            error_class=JudgeErrorClass.MALFORMED_JSON.value,
            reason=f"identity_inferred is {flag!r}, not a boolean",
        )
    winner = data["winner"]
    if winner not in VALID_WINNERS:
        return JudgeOutcome(
            False,
            error_class=JudgeErrorClass.INVALID_WINNER.value,
            reason=f"winner {winner!r} outside {{A, B, TIE}}",
        )
    return JudgeOutcome(
        True,
        verdict={
            "winner": winner,
            "rationale": str(data.get("rationale") or ""),
            "identity_inferred": False,
        },
    )


def judge_with_retries(
    invoke, *, max_retries: int = JUDGE_RETRY_BUDGET
) -> JudgeOutcome:
    """FR-58: two ADDITIONAL attempts, same inputs, fresh `--session-id`
    per call (owned by `invoke`). On exhaustion the outcome carries an
    `error_class` and NO verdict — never a silent `TIE` (which would
    shrink n_eff without a trace) and never a silent slot `A` (which
    would be harness-injected positional bias) — T-F-3."""
    last = JudgeOutcome(
        False, error_class=JudgeErrorClass.CRASHED.value, reason="no attempts made"
    )
    for attempt in range(max_retries + 1):
        try:
            raw = invoke()
        except JudgeTimeout:
            last = JudgeOutcome(
                False,
                error_class=JudgeErrorClass.TIMEOUT.value,
                reason="comparator timed out",
            )
            continue
        except JudgeBudgetExceeded:
            last = JudgeOutcome(
                False,
                error_class=JudgeErrorClass.BUDGET_EXCEEDED.value,
                reason="comparator exceeded its budget",
            )
            continue
        except Exception as e:  # noqa: BLE001 - any other failure is a crash
            last = JudgeOutcome(
                False, error_class=JudgeErrorClass.CRASHED.value, reason=str(e)
            )
            continue
        outcome = validate_comparator_response(raw)
        outcome.retries_used = attempt
        if outcome.ok:
            return outcome
        last = outcome
    last.retries_used = max_retries
    return last


def comparison_judging_invalid(*, total: int, retry_exhausted_count: int) -> bool:
    """FR-58: >20% of comparators exhausting retries ⇒ HARNESS_INVALID."""
    if total == 0:
        return False
    return (retry_exhausted_count / total) > COMPARISON_INVALID_RETRY_RATE


# ---------------------------------------------------------------- settings


def write_judge_settings(settings_dir: Path, *, pair_dir: Path, pair_name: str) -> Path:
    """Per-pair comparator --settings: the same deny hook as the runs,
    with the pair dir as its containment root — reads confined to the
    staged tree (T-B-3). Denied attempts land in a workspace-side plain
    log (the FIFO rendezvous is a run-collector concern, not a judging
    one). The settings file itself lives WORKSPACE-side: it names
    workspace paths, so it must not sit where the comparator can read."""
    settings_dir = Path(settings_dir)
    settings_dir.mkdir(parents=True, exist_ok=True)
    deny = Path(__file__).resolve().parent.parent / "hooks" / "deny.sh"
    sink = settings_dir / f"{pair_name}-denies.log"
    deny_cmd = " ".join(
        shlex.quote(str(x)) for x in ("bash", deny, Path(pair_dir), sink)
    )
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": deny_cmd}],
                }
            ]
        }
    }
    path = settings_dir / f"{pair_name}.json"
    path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n")
    return path


# ---------------------------------------------------------------- orchestration


def _map_slot_winner(winner: str | None, mapping: dict) -> str | None:
    """A slot verdict (`A`/`B`/`TIE`/None) mapped through an unsealed
    assignment to a candidate outcome (or `TIE`/None)."""
    if winner is None:
        return None
    if winner == "TIE":
        return "TIE"
    return mapping[winner]


def _invalid_judging_record(eval_dir: Path, *, seed: str, reason: str) -> dict:
    """FR-57's contract is 'surface HARNESS_INVALID, never crash the
    record away' — this is the judging.json emitted when the pipeline
    cannot even establish its seal (review finding, 2026-07-29)."""
    judging = {
        "seed": seed,
        "assignment_sha256": None,
        "double_judge": False,
        "pairs": {},
        "invocations": 0,
        "retries": 0,
        "retry_exhausted": 0,
        "harness_invalid": True,
        "harness_invalid_reason": reason,
    }
    (Path(eval_dir) / "judging.json").write_text(
        json.dumps(judging, indent=2, sort_keys=True) + "\n"
    )
    return judging


def run_judging(
    *,
    eval_dir: Path,
    judge_cmp_dir: Path,
    pairs: list[dict],
    denylist,
    seed: str,
    task_prompt: str,
    assertions: list[dict],
    invoke_comparator,
    required_content=(),
    double_judge: bool = False,
) -> dict:
    """The Phase 3 pipeline for one comparison: seal → short-circuit →
    stage → judge → unseal → record. `pairs` entries carry
    `pair_index` and per-arm `{worktree, task_outcome}`;
    `invoke_comparator(pair_dir, task_message) -> raw str` is injected
    (the real one is a `claude -p` with cwd at the pair dir).

    Ordering is load-bearing (FR-28/DR-3): assignments are computed in
    memory and sealed BEFORE any staging; every comparator invocation
    completes before `_read_seal_bytes` runs for the first time."""
    eval_dir = Path(eval_dir)
    judge_cmp_dir = Path(judge_cmp_dir)
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "scrub").mkdir(exist_ok=True)
    # the judge ROOT (parent of the per-comparison dir) is same-uid
    # private: staged artifacts, even scrubbed, are candidate work
    # product at a predictable path
    judge_cmp_dir.parent.mkdir(parents=True, exist_ok=True)
    judge_cmp_dir.parent.chmod(0o700)
    judge_cmp_dir.mkdir(exist_ok=True)

    assignments = {
        "seed": seed,
        "pairs": {
            f"pair-{p['pair_index']}": pair_assignment(seed, p["pair_index"])
            for p in pairs
        },
    }
    try:
        seal = seal_assignment(eval_dir, assignments)
    except SealBroken as e:
        # a pre-existing assignment.json (replay against a used
        # eval_dir, or an external write) must surface as
        # HARNESS_INVALID, not a crash with no record
        return _invalid_judging_record(
            eval_dir, seed=seed, reason=f"assignment seal broken (FR-57): {e}"
        )

    globally_unjudgeable = denylist_in_required_content(denylist, required_content)
    scrubbed_prompt, _ = scrub_text(task_prompt, denylist)
    # every STRING field of an assertion is scrubbed, not just `text` —
    # a fixture-authored `id`/`hint` carrying a candidate name would
    # otherwise unblind through the one channel the walk never
    # inspects: the prompt (review finding, 2026-07-29)
    scrubbed_assertions = [
        {
            k: scrub_text(v, denylist)[0] if isinstance(v, str) else v
            for k, v in a.items()
        }
        for a in assertions
    ]
    task_message = build_comparator_task_message(
        task_prompt=scrubbed_prompt, assertions=scrubbed_assertions
    )

    results: dict[str, dict] = {}
    retry_exhausted = 0
    retries_total = 0
    invocations = 0

    for p in pairs:
        name = f"pair-{p['pair_index']}"
        a_fail = p["candidate_a"]["task_outcome"] == "failure"
        b_fail = p["candidate_b"]["task_outcome"] == "failure"
        if a_fail and b_fail:
            # FR-33: NO_CONTEST on every dimension, no comparator, no
            # staging — there is nothing to blind
            results[name] = {
                "quality_outcome": "NO_CONTEST",
                "reason": "double_failure",
                "comparator_spawned": False,
            }
            continue
        if a_fail != b_fail:
            # FR-34: correctness awarded mechanically, quality
            # NO_CONTEST, no comparator
            results[name] = {
                "quality_outcome": "NO_CONTEST",
                "reason": "one_sided_failure",
                "comparator_spawned": False,
                "correctness_awarded_to": ("candidate_b" if a_fail else "candidate_a"),
            }
            continue

        if globally_unjudgeable:
            # FR-30's required-content gate: known before any staging,
            # so no copy/scrub I/O is spent on a comparison that can
            # never be blinded
            results[name] = {
                "quality_outcome": "NO_CONTEST",
                "reason": "unjudgeable_blind",
                "unjudgeable_blind": True,
                "comparator_spawned": False,
                "detail": ["denylist term in fixture required content"],
            }
            continue

        mapping = assignments["pairs"][name]
        worktrees = {
            "candidate_a": p["candidate_a"]["worktree"],
            "candidate_b": p["candidate_b"]["worktree"],
        }
        # a corrupted worktree (e.g. a candidate deleting its own
        # `.git`) is the same hostile-candidate DoS class as the
        # circular symlink: degrade to a recorded per-pair failure,
        # never crash the whole comparison's record away (review
        # finding, 2026-07-29)
        try:
            staged = stage_pair(
                pair_dir=judge_cmp_dir / name,
                eval_dir=eval_dir,
                pair_name=name,
                mapping=mapping,
                worktrees=worktrees,
                denylist=denylist,
            )
        except (RuntimeError, OSError) as e:
            results[name] = {
                "quality_outcome": "NO_CONTEST",
                "reason": "staging_failed",
                "comparator_spawned": False,
                "detail": [str(e)],
            }
            continue
        if staged.unjudgeable_blind:
            # FR-30: quality NO_CONTEST, mechanical dimensions
            # untouched, no comparator spawned; the scrub log already
            # landed workspace-side (T-B-6)
            results[name] = {
                "quality_outcome": "NO_CONTEST",
                "reason": "unjudgeable_blind",
                "unjudgeable_blind": True,
                "comparator_spawned": False,
                "detail": staged.reasons,
            }
            continue

        judge_dirs = [("slot_winner", judge_cmp_dir / name)]
        if double_judge:
            # FR-35: judge again with swapped positions; quality only.
            # The dir basename is the comparator's cwd, so it must not
            # say "swap" — that would tell the judge it is seeing the
            # counterbalanced presentation (review finding, 2026-07-29).
            swap_name = f"{name}-b"
            try:
                stage_pair(
                    pair_dir=judge_cmp_dir / swap_name,
                    eval_dir=eval_dir,
                    pair_name=swap_name,
                    mapping=invert_assignment(mapping),
                    worktrees=worktrees,
                    denylist=denylist,
                )
            except (RuntimeError, OSError) as e:
                results[name] = {
                    "quality_outcome": "NO_CONTEST",
                    "reason": "staging_failed",
                    "comparator_spawned": False,
                    "detail": [str(e)],
                }
                continue
            judge_dirs.append(("slot_winner_swapped", judge_cmp_dir / swap_name))

        rec: dict = {"comparator_spawned": True, "retries": 0}
        for key, pdir in judge_dirs:
            invocations += 1
            outcome = judge_with_retries(
                lambda d=pdir: invoke_comparator(d, task_message)
            )
            rec["retries"] += outcome.retries_used
            retries_total += outcome.retries_used
            if outcome.ok:
                (pdir / "verdict.json").write_text(
                    json.dumps(outcome.verdict, indent=2, sort_keys=True) + "\n"
                )
                rec[key] = outcome.verdict["winner"]
            else:
                # FR-58: the recorded error_class satisfies
                # judging_complete; NO verdict.json, never a default
                retry_exhausted += 1
                rec[key] = None
                # first failure's diagnostics win the top-level slot;
                # every failure is kept in `errors` (double-judge can
                # fail twice with different classes)
                rec.setdefault("error_class", outcome.error_class)
                rec.setdefault("error_reason", outcome.reason)
                rec.setdefault("errors", []).append(
                    {
                        "slot": key,
                        "error_class": outcome.error_class,
                        "reason": outcome.reason,
                    }
                )
        results[name] = rec

    # ---- unseal: the FIRST read of the sealed bytes in this process
    harness_invalid = False
    harness_invalid_reason = None
    try:
        unsealed = unseal_assignment(seal.path, seal.sha256)
    except SealBroken as e:
        harness_invalid = True
        harness_invalid_reason = f"assignment seal broken (FR-57): {e}"
        unsealed = None

    for name, rec in results.items():
        if not rec.get("comparator_spawned"):
            continue
        if unsealed is None:
            rec["quality_outcome"] = None
            continue
        mapping = unsealed["pairs"][name]
        primary = _map_slot_winner(rec.get("slot_winner"), mapping)
        if not double_judge:
            rec["quality_outcome"] = primary if primary is not None else "NO_CONTEST"
            continue
        # FR-35: BOTH orientations reconcile into quality_outcome. A
        # disagreement is the positional-bias signal double-judging
        # exists to expose — publishing the primary orientation's
        # answer would silently inherit its bias (review finding,
        # 2026-07-29). Phase 4 gets both mapped outcomes.
        swapped = _map_slot_winner(
            rec.get("slot_winner_swapped"), invert_assignment(mapping)
        )
        rec["quality_outcome_swapped"] = swapped
        if primary is None and swapped is None:
            rec["quality_outcome"] = "NO_CONTEST"
        elif primary is None or swapped is None:
            rec["quality_outcome"] = primary if primary is not None else swapped
        elif primary == swapped:
            rec["quality_outcome"] = primary
        else:
            rec["quality_outcome"] = None
            rec["orientation_disagreement"] = True
            rec["reason"] = "orientation_disagreement"

    if comparison_judging_invalid(
        total=invocations, retry_exhausted_count=retry_exhausted
    ):
        harness_invalid = True
        harness_invalid_reason = harness_invalid_reason or (
            f"{retry_exhausted}/{invocations} comparators exhausted their "
            "retry budget (>20%, FR-58)"
        )

    judging = {
        "seed": seed,
        "assignment_sha256": seal.sha256,
        "double_judge": double_judge,
        "pairs": results,
        "invocations": invocations,
        "retries": retries_total,
        "retry_exhausted": retry_exhausted,
        "harness_invalid": harness_invalid,
        "harness_invalid_reason": harness_invalid_reason,
    }
    (eval_dir / "judging.json").write_text(
        json.dumps(judging, indent=2, sort_keys=True) + "\n"
    )
    return judging
