#!/usr/bin/env bash
# Deterministic gate for review-round2-carryforward. Exit 0 = pass.
#
# Requires .vc-out/review.md to exist and to contain at least one severity-tagged
# finding anchored at the start of a line — i.e. an actual finding entry, not the
# word "low" occurring in prose. The review target has two live defects planted in
# it, so a finding-free review is wrong by construction here and must not reach
# the graded assertions.
#
# Everything about WHICH findings were raised is graded by assertions.json.
set -u
R="${1:-.}/.vc-out/review.md"
test -s "$R" || exit 1
grep -qE '^[[:space:]]*(#{1,6}[[:space:]]*|[-*+][[:space:]]+|\*\*)?(CRITICAL|HIGH|MEDIUM|LOW)\b' "$R"
