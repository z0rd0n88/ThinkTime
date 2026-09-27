#!/usr/bin/env bash
# Deterministic gate for spec-from-vague-issue: SPEC.md exists at the
# worktree root and is non-empty. Exit 0 = gate passes; non-zero = fails.
set -u
test -s "${1:-.}/SPEC.md"
