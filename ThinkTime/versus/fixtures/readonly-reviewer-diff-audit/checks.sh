#!/usr/bin/env bash
# Deterministic gate for readonly-reviewer-diff-audit: .vc-out/review.md
# exists and is non-empty. Exit 0 = gate passes; non-zero = gate fails.
set -u
test -s "${1:-.}/.vc-out/review.md"
