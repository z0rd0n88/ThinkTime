#!/usr/bin/env bash
# Deterministic gate for review-round2-lens-rotation. Exit 0 = pass.
#
# Requires .vc-out/review.md to exist and to contain at least one severity-tagged
# finding anchored at the start of a line — i.e. an actual finding entry, not the
# word "low" occurring in prose. The review target has three live defects planted
# in it, so a finding-free review is wrong by construction here and must not reach
# the graded assertions.
#
# The accepted prefixes must cover every list shape a reviewer legitimately uses.
# An earlier version allowed only headings, `-*+` bullets and bare `**`, which
# silently rejected ORDERED lists (`1. **CRITICAL** — ...`) and markdown tables.
# That is not a formatting quibble: it scored 12 of 18 otherwise-correct sonnet
# runs as outright failures (0/6 on every assertion), unevenly across arms, and
# voided a whole comparison. Prefer a false accept here over a false reject —
# WHICH findings were raised is graded by assertions.json, so this gate only has
# to answer "did the review report any finding at all".
set -u
R="${1:-.}/.vc-out/review.md"
test -s "$R" || exit 1
grep -qE '^[[:space:]]*(#{1,6}[[:space:]]*|[-*+][[:space:]]+|[0-9]+[.)][[:space:]]+|\|[[:space:]]*)?(\*\*)?(CRITICAL|HIGH|MEDIUM|LOW)\b' "$R"
