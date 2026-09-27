#!/usr/bin/env bash
# versus audit hook — FR-20, FR-21.1, DR-7.
#
# Usage (wired per run in the generated --settings file, on BOTH
# PreToolUse and PostToolUse, matcher ".*"):
#   audit-tool.sh <fifo-path>
#
# Contract: ALWAYS exits 0 (DR-7's "two hooks with opposite exit
# contracts") — this hook can never alter a run, only observe it. It
# does NOT write the audit log (FR-21.1): it forwards one UNSTAMPED
# record to the harness-owned FIFO, where the harness collector is the
# sole writer and computes seq/prev_hash on receipt (FR-21.2). No
# hmac_key reaches this script by argv, env, or settings file — a keyed
# hook would hand the key to the candidate via `ps auxww` or
# /proc/<pid>/environ and make the chain forgeable.
#
# Reads the tool payload as stdin JSON via jq. $CLAUDE_FILE_PATH does
# not exist.

set -u

FIFO="${1:-}"
[ -n "$FIFO" ] || exit 0
[ -p "$FIFO" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

PAYLOAD="$(cat)"
[ -n "$PAYLOAD" ] || exit 0

# FR-20: hook_event_name, tool_name, the operative tool_input slice
# (file_path/command/pattern), session_id, cwd, wall-clock ts.
RECORD="$(printf '%s' "$PAYLOAD" | jq -c '{
  type: "tool_call",
  hook_event_name: (.hook_event_name // null),
  tool_name: (.tool_name // null),
  tool_input: {
    file_path: (.tool_input.file_path // null),
    command:   (.tool_input.command   // null),
    pattern:   (.tool_input.pattern   // null)
  },
  session_id: (.session_id // null),
  cwd: (.cwd // null),
  ts: (now)
}' 2>/dev/null)" || exit 0
[ -n "$RECORD" ] || exit 0

# FR-20: PIPE_BUF (4096 bytes on Linux) is the atomic-write bound for a
# FIFO under POSIX. A record that would exceed it has its tool_input
# slice truncated and carries truncated:true, rather than risking an
# interleaved write — the collector has no lock file (FR-20).
#
# The bound is in BYTES, so the length test must be too. `${#RECORD}`
# counts CHARACTERS under a UTF-8 locale: a payload of ~1500 CJK or
# emoji characters measures ~1500 but writes ~4500 bytes, sails past a
# character-based check, and lands a non-atomic write — defeating the
# very guarantee this branch exists to provide. `wc -c` is the byte
# count. The `+ 1` accounts for the trailing newline `printf` adds.
record_bytes() { printf '%s' "$1" | wc -c; }

if [ "$(( $(record_bytes "$RECORD") + 1 ))" -gt 4096 ]; then
  RECORD="$(printf '%s' "$PAYLOAD" | jq -c '{
    type: "tool_call",
    hook_event_name: (.hook_event_name // null),
    tool_name: (.tool_name // null),
    tool_input: {},
    session_id: (.session_id // null),
    cwd: (.cwd // null),
    ts: (now),
    truncated: true
  }' 2>/dev/null)" || exit 0
  [ -n "$RECORD" ] || exit 0

  # The truncated record still carries `cwd`, which is a run-worktree
  # path of unbounded length — so the fallback can itself exceed the
  # bound and reintroduce the hazard. Drop the free-text fields down to
  # a minimal record that cannot: every remaining field is either a
  # fixed literal or a bounded identifier.
  if [ "$(( $(record_bytes "$RECORD") + 1 ))" -gt 4096 ]; then
    RECORD="$(printf '%s' "$PAYLOAD" | jq -c '{
      type: "tool_call",
      hook_event_name: (.hook_event_name // null),
      tool_name: (.tool_name // null),
      tool_input: {},
      session_id: (.session_id // null),
      cwd: null,
      ts: (now),
      truncated: true
    }' 2>/dev/null)" || exit 0
    [ -n "$RECORD" ] || exit 0
  fi
fi

# Best-effort forward: a plain `> "$FIFO"` blocks until a reader opens
# the other end, which is expected (the collector is already blocked
# reading before spawn) — but a `timeout` bounds it so a dead collector
# loses an audit record rather than hanging the tool call, since this
# hook must never be the thing that alters a run (DR-7).
( timeout 2 bash -c 'printf "%s\n" "$1" >"$2"' _ "$RECORD" "$FIFO" ) >/dev/null 2>&1 || true

exit 0
