#!/usr/bin/env python3
"""Collect behavioural signals about how this machine actually uses Claude Code.

Read-only. No network. Emits one compact JSON document on stdout so a single
reasoning context can rank findings over *derived numbers* instead of trying to
read 2000+ session transcripts.

    python3 collect_signals.py --days 30 > signals.json
    python3 collect_signals.py --days 90 --repos /home/alex/BotHaus

Every section degrades independently: an unreadable source records an "errors"
entry and the rest of the run continues.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
CLAUDE = Path(os.environ.get("CLAUDE_CONFIG_DIR", HOME / ".claude"))

DEFAULT_REPOS = [
    CLAUDE,
    HOME / "BotHaus",
    HOME / "VistaMobileBE",
    HOME / "TradingBots",
    HOME / "ClaudesMods",
]

# --------------------------------------------------------------------------
# TUNABLE — these encode what *you* consider evidence of your own friction.
# The defaults are generic. Edit them to match how you actually phrase things:
# a pattern that never fires produces a silently empty lens, and a pattern that
# over-fires inflates the rework rate into noise.
# --------------------------------------------------------------------------
REWORK_PATTERNS = re.compile(
    r"\b(no,|nope|actually|you forgot|i said|that'?s wrong|revert|undo|"
    r"not what i|try again|still (broken|failing|wrong)|you missed|stop|"
    r"why (did|are) you|don'?t do that|again\b)",
    re.I,
)

# Behaviours the user's own CLAUDE.md forbids. Matched against Bash commands
# actually executed, so a hit is a measured violation, not an inferred one.
RULE_PROBES = {
    "git_add_all": re.compile(r"git\s+add\s+(-A|--all|\.)(\s|$)"),
    "git_commit_all": re.compile(r"git\s+commit\b[^|;]*\s-[a-zA-Z]*a"),
    "no_verify": re.compile(r"--no-verify"),
    "force_push": re.compile(r"git\s+push\b[^|;]*(--force|-f)(\s|$)"),
    "hooks_bypass": re.compile(r"core\.hooksPath=/dev/null"),
    "hard_reset": re.compile(r"git\s+reset\s+--hard"),
    "bare_python": re.compile(r"(^|[|;&]\s*)python\s"),
    "windows_path": re.compile(r"(/mnt/c/Users/sneak|C:\\\\Users\\\\sneak)"),
}

DENIAL_PATTERNS = re.compile(
    r"(requested permissions to use|haven'?t granted it|user (rejected|denied)|"
    r"doesn'?t want to (take|proceed)|permission denied by|operation not permitted "
    r"by (the )?(user|policy))",
    re.I,
)

INTERRUPT_MARKER = "Request interrupted by user"


def _err(bag: dict, where: str, exc: Exception) -> None:
    bag.setdefault("errors", []).append(f"{where}: {type(exc).__name__}: {exc}")


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 25) -> str:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
        return p.stdout
    except Exception:
        return ""


def _iter_jsonl(path: Path):
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except Exception:
        return


# ==========================================================================
# Lens: typed-prompt history  (what you asked for, and how often you re-asked)
# ==========================================================================
def analyse_prompts(cutoff: float) -> dict:
    out: dict = {}
    path = CLAUDE / "history.jsonl"
    if not path.exists():
        return {"errors": [f"missing {path}"]}
    try:
        rows = [r for r in _iter_jsonl(path) if isinstance(r, dict)]
    except Exception as exc:  # pragma: no cover
        _err(out, "history", exc)
        return out

    def ts(r):  # history timestamps are epoch millis
        v = r.get("timestamp") or 0
        return v / 1000.0 if v > 1e11 else float(v)

    recent = [r for r in rows if ts(r) >= cutoff]
    out["total_all_time"] = len(rows)
    out["in_window"] = len(recent)
    if not recent:
        return out

    texts = [(r.get("display") or "") for r in recent]
    rework = [t for t in texts if REWORK_PATTERNS.search(t)]
    out["rework_prompts"] = len(rework)
    out["rework_rate_pct"] = round(100 * len(rework) / len(texts), 1)
    out["rework_samples"] = [t[:120] for t in rework[:12]]

    out["short_prompt_rate_pct"] = round(
        100 * sum(1 for t in texts if len(t.split()) <= 3) / len(texts), 1
    )

    slash = collections.Counter()
    for t in texts:
        m = re.match(r"/([a-zA-Z0-9:_-]+)", t.strip())
        if m:
            slash[m.group(1)] += 1
    out["slash_commands_used"] = dict(slash.most_common(40))
    out["distinct_slash_commands"] = len(slash)

    # consecutive near-identical prompts in one session = a retry after failure
    retries = 0
    by_sess: dict = collections.defaultdict(list)
    for r in recent:
        by_sess[r.get("sessionId")].append((r.get("display") or "").strip())
    for seq in by_sess.values():
        for a, b in zip(seq, seq[1:]):
            if a and a == b:
                retries += 1
    out["identical_consecutive_reprompts"] = retries
    out["sessions_in_window"] = len(by_sess)
    return out


# ==========================================================================
# Lens: session transcripts  (what actually happened — the baseline's blind spot)
# ==========================================================================
def analyse_transcripts(cutoff: float, max_files: int) -> dict:
    out: dict = {}
    root = CLAUDE / "projects"
    if not root.is_dir():
        return {"errors": [f"missing {root}"]}

    files = []
    for p in root.glob("*/*.jsonl"):
        try:
            if p.stat().st_mtime >= cutoff:
                files.append(p)
        except OSError:
            continue
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    truncated = len(files) > max_files
    files = files[:max_files]

    tools = collections.Counter()
    tool_errors = collections.Counter()
    err_samples: dict = collections.defaultdict(list)
    denials: list = []
    interrupts = 0
    bash_heads = collections.Counter()
    bash_fail = collections.Counter()
    rule_hits = collections.Counter()
    rule_samples: dict = collections.defaultdict(list)
    skills_used = collections.Counter()
    agents_used = collections.Counter()
    reads = collections.Counter()

    for f in files:
        names: dict = {}  # tool_use_id -> tool name
        inputs: dict = {}  # tool_use_id -> input dict
        for rec in _iter_jsonl(f):
            if not isinstance(rec, dict):
                continue
            msg = rec.get("message") or {}
            content = msg.get("content")

            if isinstance(content, str) and INTERRUPT_MARKER in content:
                interrupts += 1
            if not isinstance(content, list):
                continue

            for blk in content:
                if not isinstance(blk, dict):
                    continue
                btype = blk.get("type")

                if btype == "tool_use":
                    name = blk.get("name") or "?"
                    tools[name] += 1
                    names[blk.get("id")] = name
                    inp = blk.get("input") if isinstance(blk.get("input"), dict) else {}
                    inputs[blk.get("id")] = inp
                    if name == "Bash":
                        cmd = str(inp.get("command", ""))
                        head = cmd.strip().split()[0] if cmd.strip() else "?"
                        bash_heads[head] += 1
                        for rule, pat in RULE_PROBES.items():
                            if pat.search(cmd):
                                rule_hits[rule] += 1
                                if len(rule_samples[rule]) < 5:
                                    rule_samples[rule].append(cmd[:160])
                    elif name == "Skill":
                        skills_used[str(inp.get("skill", "?"))] += 1
                    elif name == "Agent":
                        agents_used[str(inp.get("subagent_type", "?"))] += 1
                    elif name in ("Read", "Edit", "Write"):
                        fp = inp.get("file_path")
                        if fp:
                            reads[str(fp)] += 1

                elif btype == "tool_result":
                    tid = blk.get("tool_use_id")
                    tname = names.get(tid, "?")
                    body = blk.get("content")
                    text = body if isinstance(body, str) else json.dumps(body)[:1500]
                    if blk.get("is_error"):
                        tool_errors[tname] += 1
                        if tname == "Bash":
                            cmd = str((inputs.get(tid) or {}).get("command", ""))
                            h = cmd.strip().split()[0] if cmd.strip() else "?"
                            bash_fail[h] += 1
                        if len(err_samples[tname]) < 6:
                            err_samples[tname].append(text[:200].replace("\n", " "))
                    if DENIAL_PATTERNS.search(text):
                        cmd = str((inputs.get(tid) or {}).get("command", ""))
                        denials.append(
                            {
                                "tool": tname,
                                "command": cmd[:160],
                                "excerpt": text[:160].replace("\n", " "),
                            }
                        )

    out["files_scanned"] = len(files)
    out["file_cap_hit"] = truncated
    out["tool_use_counts"] = dict(tools.most_common(25))
    out["tool_error_counts"] = dict(tool_errors.most_common(15))
    out["tool_error_rate_pct"] = {
        k: round(100 * tool_errors[k] / tools[k], 1)
        for k in tools
        if tools[k] >= 20 and tool_errors.get(k)
    }
    out["tool_error_samples"] = {k: v for k, v in err_samples.items()}
    out["user_interrupts"] = interrupts
    out["permission_denials"] = len(denials)
    out["permission_denial_details"] = denials[:25]
    out["bash_command_heads"] = dict(bash_heads.most_common(25))
    out["bash_failure_by_head"] = dict(bash_fail.most_common(15))
    out["own_rule_violations"] = dict(rule_hits)
    out["own_rule_violation_samples"] = dict(rule_samples)
    out["skills_invoked"] = dict(skills_used.most_common(40))
    out["agents_dispatched"] = dict(agents_used.most_common(25))
    out["most_touched_files"] = dict(reads.most_common(15))
    return out


# ==========================================================================
# Lens: capability dead-weight  (what you pay for every session and never use)
# ==========================================================================
def analyse_capability(prompts: dict, transcripts: dict) -> dict:
    out: dict = {}
    used = set(transcripts.get("skills_invoked", {}))
    for name in prompts.get("slash_commands_used", {}):
        used.add(name)
        if ":" in name:
            used.add(name.split(":", 1)[1])

    installed: list = []
    for base in (CLAUDE / "skills", CLAUDE / "plugins"):
        if not base.is_dir():
            continue
        try:
            for sk in base.rglob("SKILL.md"):
                if "/disabled/" in str(sk):
                    continue
                installed.append(sk.parent.name)
        except Exception as exc:
            _err(out, f"scan {base}", exc)
    installed_set = sorted(set(installed))
    out["skills_installed"] = len(installed_set)
    out["skills_used_in_window"] = len(used & set(installed_set))
    out["skills_never_used"] = sorted(set(installed_set) - used)[:80]

    try:
        parked = CLAUDE / "agents-parked"
        agents = {p.stem for p in parked.glob("*.md")} if parked.is_dir() else set()
        out["agents_parked"] = len(agents)
        out["agents_dispatched_in_window"] = len(
            transcripts.get("agents_dispatched", {})
        )
    except Exception as exc:
        _err(out, "agents", exc)

    # settings.json plugin registry: keys explicitly disabled
    try:
        cfg = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))
        plugins = cfg.get("enabledPlugins", {}) or {}
        out["plugins_enabled"] = sorted(k for k, v in plugins.items() if v)
        out["plugins_disabled"] = sorted(k for k, v in plugins.items() if not v)
        out["permissions_allow_count"] = len(
            (cfg.get("permissions", {}) or {}).get("allow", [])
        )
        out["permissions_deny_count"] = len(
            (cfg.get("permissions", {}) or {}).get("deny", [])
        )
        out["hook_events_wired"] = sorted((cfg.get("hooks", {}) or {}).keys())
    except Exception as exc:
        _err(out, "settings.json", exc)

    now = time.time()
    for label, sub, pat in (("plans", "plans", "*.md"), ("tasks", "tasks", "*")):
        d = CLAUDE / sub
        if not d.is_dir():
            continue
        items = list(d.glob(pat))
        stale = [p for p in items if now - p.stat().st_mtime > 14 * 86400]
        out[f"{label}_total"] = len(items)
        out[f"{label}_untouched_14d"] = len(stale)
    return out


# ==========================================================================
# Lens: git / own-rules conformance across the flagship repos
# ==========================================================================
def analyse_repos(repos: list[Path], days: int) -> dict:
    out: dict = {}
    for repo in repos:
        if not (repo / ".git").exists():
            continue
        r: dict = {}
        default = "main"
        head = _run(
            ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], repo
        ).strip()
        if head:
            default = head.rsplit("/", 1)[-1]
        r["default_branch"] = default

        # Conformance MUST be window-scoped. A lifetime sample reaches back into
        # eras when the rule did not exist yet (this repo allowed direct commits
        # to main until the worktree+PR rule superseded that carve-out), so a
        # lifetime ratio measures the user against a standard they never agreed
        # to at the time. The lifetime figure is kept only as context, and is
        # explicitly labelled as such.
        def _first_parent(extra: list[str]) -> list[list[str]]:
            log = _run(
                ["git", "log", "--first-parent", "--no-merges", "--pretty=%h|%s"]
                + extra
                + [default],
                repo,
            )
            return [ln.split("|", 1) for ln in log.splitlines() if "|" in ln]

        since = f"--since={days}.days.ago"
        win = _first_parent([since])
        life = _first_parent(["-n", "200"])
        win_no_pr = [s for s in win if not re.search(r"\(#\d+\)", s[1])]

        r["window_commits_on_default"] = len(win)
        r["window_commits_without_pr_ref"] = len(win_no_pr)
        r["window_commits_without_pr_samples"] = [
            f"{h} {s[:70]}" for h, s in win_no_pr[:8]
        ]
        r["lifetime_sample_context_only"] = {
            "sampled": len(life),
            "without_pr_ref": sum(1 for s in life if not re.search(r"\(#\d+\)", s[1])),
            "caveat": "spans pre-policy history; NOT a conformance measure",
        }
        subjects = win or life

        conv = sum(
            1
            for _, s in subjects
            if re.match(
                r"(feat|fix|refactor|docs|test|chore|perf|ci)(\([^)]*\))?!?:", s
            )
        )
        r["conventional_commit_rate_pct"] = (
            round(100 * conv / len(subjects), 1) if subjects else None
        )

        wt = _run(["git", "worktree", "list", "--porcelain"], repo)
        paths = [
            l.split(" ", 1)[1] for l in wt.splitlines() if l.startswith("worktree ")
        ]
        r["worktrees_live"] = max(len(paths) - 1, 0)
        r["worktree_paths"] = [p for p in paths[1:]][:10]

        merged = [
            b.strip().lstrip("* ")
            for b in _run(["git", "branch", "--merged", default], repo).splitlines()
        ]
        r["merged_branches_not_deleted"] = [b for b in merged if b and b != default][
            :10
        ]

        r["commits_in_window"] = len(
            _run(["git", "log", since, "--no-merges", "--pretty=%h"], repo).splitlines()
        )
        r["reverts_in_window"] = len(
            _run(
                ["git", "log", since, "--pretty=%s", "--grep=^Revert"], repo
            ).splitlines()
        )
        out[repo.name or str(repo)] = r
    return out


# ==========================================================================
# Lens: recurring gotchas  (documented 3+ times == a fix you never automated)
# ==========================================================================
def analyse_gotchas() -> dict:
    out: dict = {}
    headings = collections.Counter()
    sources = 0
    roots = [CLAUDE / "summaries", CLAUDE / "guides"]
    roots += (
        list((CLAUDE / "projects").glob("*/memory"))
        if (CLAUDE / "projects").is_dir()
        else []
    )
    for root in roots:
        if not root.is_dir():
            continue
        for md in root.rglob("*.md"):
            sources += 1
            try:
                for line in md.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines():
                    m = re.match(r"#{2,4}\s+(.{4,80})", line.strip())
                    if m:
                        key = re.sub(r"[^a-z0-9 ]", "", m.group(1).lower()).strip()
                        key = re.sub(r"\s+", " ", key)
                        if key and not key.startswith(
                            ("session summary", "context", "what was")
                        ):
                            headings[key] += 1
            except Exception:
                continue
    out["markdown_sources_scanned"] = sources
    out["repeated_headings_3plus"] = {
        k: v for k, v in headings.most_common(60) if v >= 3
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=30, help="analysis window (default 30)")
    ap.add_argument(
        "--max-files",
        type=int,
        default=250,
        help="cap on transcripts parsed, newest first (default 250)",
    )
    ap.add_argument("--repos", nargs="*", default=None, help="override repo list")
    args = ap.parse_args()

    cutoff = time.time() - args.days * 86400
    repos = [Path(r) for r in args.repos] if args.repos else DEFAULT_REPOS

    prompts = analyse_prompts(cutoff)
    transcripts = analyse_transcripts(cutoff, args.max_files)

    doc = {
        "meta": {
            "generated_epoch": int(time.time()),
            "window_days": args.days,
            "claude_dir": str(CLAUDE),
            "repos_examined": [str(r) for r in repos if (r / ".git").exists()],
            "note": "Counts are measured, not inferred. A zero may mean "
            "'never happened' OR 'pattern never matched' — check the "
            "TUNABLE block before treating a zero as clean.",
        },
        "prompts": prompts,
        "transcripts": transcripts,
        "capability": analyse_capability(prompts, transcripts),
        "repos": analyse_repos(repos, args.days),
        "gotchas": analyse_gotchas(),
    }
    json.dump(doc, sys.stdout, indent=1, sort_keys=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
