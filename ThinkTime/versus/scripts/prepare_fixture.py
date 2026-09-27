#!/usr/bin/env python3
"""Fixture loader: materialize a fixture's pinned repo into a run worktree.

Phase 0 seed (spec task 8); grows into the full FR-12..FR-19 module in Phase 1.
Contract implemented here:
- FR-45: recompute sha256(repo.bundle) and abort on mismatch with fixture.json.
- Clone from the bundle only (never a live repo), remove `origin`, detach HEAD
  at the pinned `head_sha`.
Stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


class FixtureError(Exception):
    """A fixture failed validation; the run must not proceed."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str, cwd: Path | None = None) -> str:
    try:
        res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    except OSError as e:
        raise FixtureError(f"cannot run git: {e}") from e
    if res.returncode != 0:
        raise FixtureError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout.strip()


def _contained(fixture_dir: Path, rel: str) -> Path:
    """Resolve a fixture.json-supplied path, refusing escapes from fixture_dir.

    fixture.json is the untrusted artifact this loader guards: an absolute
    path or a `..` traversal in `prompt_file`/`checks` must not reach
    outside the fixture directory.
    """
    if Path(rel).is_absolute():
        raise FixtureError(f"fixture path is absolute: {rel}")
    resolved = (fixture_dir / rel).resolve()
    if not resolved.is_relative_to(fixture_dir.resolve()):
        raise FixtureError(f"fixture path escapes fixture dir: {rel}")
    return resolved


def load_fixture(fixture_dir: Path) -> dict:
    """Read and validate fixture.json; verify the bundle pin (FR-45)."""
    fixture_dir = Path(fixture_dir)
    meta_path = fixture_dir / "fixture.json"
    if not meta_path.is_file():
        raise FixtureError(f"no fixture.json in {fixture_dir}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    for key in (
        "fixture_id",
        "fixture_version",
        "head_sha",
        "bundle_sha256",
        "prompt_file",
        "checks",
    ):
        if key not in meta:
            raise FixtureError(f"fixture.json missing required key: {key}")

    bundle = fixture_dir / "repo.bundle"
    if not bundle.is_file():
        raise FixtureError(f"no repo.bundle in {fixture_dir}")
    actual = _sha256(bundle)
    if actual != meta["bundle_sha256"]:
        raise FixtureError(
            "bundle_sha256 mismatch: fixture.json pins "
            f"{meta['bundle_sha256']}, bundle hashes to {actual} (FR-45)"
        )

    prompt = _contained(fixture_dir, meta["prompt_file"])
    if not prompt.is_file():
        raise FixtureError(f"prompt file missing: {prompt}")
    for check in meta["checks"]:
        if not _contained(fixture_dir, check).is_file():
            raise FixtureError(f"check script missing: {check}")
    return meta


def prepare_worktree(fixture_dir: Path, target: Path) -> dict:
    """Clone the fixture bundle into `target`: no origin, detached at head_sha."""
    fixture_dir = Path(fixture_dir)
    target = Path(target)
    meta = load_fixture(fixture_dir)
    if target.exists():
        if not target.is_dir():
            raise FixtureError(f"target exists and is not a directory: {target}")
        if any(target.iterdir()):
            raise FixtureError(f"target not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)

    _git("clone", "-q", str(fixture_dir / "repo.bundle"), str(target))
    # Detach at the pin before reading HEAD: a bundle without a HEAD ref
    # clones onto an unborn branch, where `rev-parse HEAD` fails.
    _git("checkout", "-q", "--detach", meta["head_sha"], cwd=target)
    head = _git("rev-parse", "HEAD", cwd=target)
    if head != meta["head_sha"]:
        raise FixtureError(f"cloned HEAD {head} != pinned head_sha {meta['head_sha']}")
    _git("remote", "remove", "origin", cwd=target)
    return meta


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: prepare_fixture.py <fixture-dir> <target-worktree>", file=sys.stderr
        )
        return 2
    try:
        meta = prepare_worktree(Path(argv[1]), Path(argv[2]))
    except FixtureError as e:
        print(f"fixture error: {e}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "fixture_id": meta["fixture_id"],
                "fixture_version": meta["fixture_version"],
                "head_sha": meta["head_sha"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
