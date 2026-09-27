#!/usr/bin/env bash
# versus PreToolUse deny hook — FR-53, FR-17.
#
# Usage (wired per run in the generated --settings file):
#   deny.sh <worktree-root> [containment-record-sink]
#
# Contract: BLOCK by exiting 2 — PreToolUse does NOT block on exit 1; a
# hook returning 1 fails OPEN (FR-53). Every internal failure here
# (missing arg, missing jq, unparseable stdin) therefore denies rather
# than permits. Reads the tool payload as stdin JSON via jq —
# $CLAUDE_FILE_PATH does not exist.
#
# Scope per FR-53: (1) tokenized network-binary matching over each
# pipeline/list segment (no substring scan: mycurl.sh is not a false
# positive, /usr/bin/curl is not a false negative) plus FR-17's git-remote
# layer; (2) realpath containment of structured path arguments — sound for
# file_path/path/notebook_path, best-effort for Bash by design (see the
# spec's stated soundness bound); (3) writes to .claude/ inside the
# worktree.

set -u

WT_RAW="${1:-}"
SINK="${2:-}"

deny() {
  local reason="$1" tool="${2:-unknown}" record
  if [ -n "$SINK" ]; then
    record="$(printf '{"type":"containment_denied","tool_name":"%s","reason":"%s"}' \
      "$tool" "$reason")"
    # $SINK is the run's audit FIFO (Phase 2): open-for-write blocks
    # until the harness collector's reader is present, which is the
    # desired rendezvous (T-U-17). Bound it with a timeout so a dead
    # collector cannot make containment itself hang — this hook still
    # MUST exit 2 promptly regardless of whether the record lands.
    ( timeout 1 bash -c 'printf "%s\n" "$1" >>"$2"' _ "$record" "$SINK" ) \
      >/dev/null 2>&1 || true
  fi
  printf 'versus deny hook: %s\n' "$reason" >&2
  exit 2
}

[ -n "$WT_RAW" ] || deny "worktree root argument missing" ""
command -v jq >/dev/null 2>&1 || deny "jq unavailable; failing closed" ""
WT="$(realpath -- "$WT_RAW" 2>/dev/null)" || deny "worktree root unresolvable: $WT_RAW" ""

PAYLOAD="$(cat)"
TOOL="$(printf '%s' "$PAYLOAD" | jq -r '.tool_name // empty' 2>/dev/null)" \
  || deny "unparseable stdin payload" ""
[ -n "$TOOL" ] || deny "payload has no tool_name" ""

# ---------------------------------------------------------------- helpers

contained() {
  # 0 iff $1, resolved against the worktree for relative paths and
  # canonicalized (symlinks resolved), is a descendant of $WT.
  local p="$1" abs
  case "$p" in
    /*) abs="$p" ;;
    *) abs="$WT/$p" ;;
  esac
  abs="$(realpath -m -- "$abs" 2>/dev/null)" || return 1
  case "$abs/" in
    "$WT"/*) return 0 ;;
    *) return 1 ;;
  esac
}

in_dot_claude() {
  local p="$1" abs
  case "$p" in
    /*) abs="$p" ;;
    *) abs="$WT/$p" ;;
  esac
  abs="$(realpath -m -- "$abs" 2>/dev/null)" || return 1
  case "$abs/" in
    "$WT/.claude"/*) return 0 ;;
    *) return 1 ;;
  esac
}

check_bash_command() {
  local cmd="$1" seg
  # Split into pipeline/list segments; tokenized matching happens per
  # segment head, never as a substring scan.
  while IFS= read -r seg; do
    local -a toks=()
    read -ra toks <<<"$seg" || true
    local i=0 t head sub
    while [ "$i" -lt "${#toks[@]}" ]; do
      t="${toks[$i]}"
      case "$t" in
        env | command | nohup | time | exec) i=$((i + 1)) ;;
        [A-Za-z_]*=*) i=$((i + 1)) ;;
        *) break ;;
      esac
    done
    [ "$i" -ge "${#toks[@]}" ] && continue
    # Strip quote characters the executing shell would remove before
    # resolving the binary: cu''rl and "curl" both execute curl, so both
    # must match (review finding 1). This is still tokenized matching —
    # `echo 'curl is a tool'` keeps curl in a non-head position.
    t="${toks[$i]}"
    t="${t//\'/}"
    t="${t//\"/}"
    head="$(basename -- "$t")"
    case "$head" in
      curl | wget | nc | ncat | netcat | ssh | scp | sftp | telnet)
        deny "network-capable command '$head' (FR-53.1)" "Bash"
        ;;
      gh)
        sub="${toks[$((i + 1))]:-}"
        case "$sub" in
          api | pr | repo) deny "gh $sub reaches a remote (FR-17/FR-53.1)" "Bash" ;;
        esac
        ;;
      git)
        sub="${toks[$((i + 1))]:-}"
        if [ "$sub" = "push" ]; then
          deny "git push reaches a remote (FR-17)" "Bash"
        fi
        if [ "$sub" = "remote" ] && [ "${toks[$((i + 2))]:-}" = "add" ]; then
          deny "git remote add reintroduces a remote (FR-17)" "Bash"
        fi
        ;;
      bash | sh | zsh | dash | ksh)
        # Recurse into `<shell> -c '<cmd>'` strings: the inner command
        # runs with the full shell, so it gets the full check. Skip
        # leading flags; any flag cluster containing `c` (-c, -lc)
        # introduces the command string.
        local j=$((i + 1)) has_c=0 tj rest
        while [ "$j" -lt "${#toks[@]}" ]; do
          tj="${toks[$j]}"
          case "$tj" in
            -*c*)
              has_c=1
              j=$((j + 1))
              break
              ;;
            -*) j=$((j + 1)) ;;
            *) break ;;
          esac
        done
        if [ "$has_c" -eq 1 ] && [ "$j" -lt "${#toks[@]}" ]; then
          rest="${toks[*]:$j}"
          rest="${rest//\'/}"
          rest="${rest//\"/}"
          check_bash_command "$rest"
        fi
        ;;
    esac
  done < <(printf '%s\n' "$cmd" | sed -E 's/\|\||&&|;|\|/\n/g')
}

# ---------------------------------------------------------------- dispatch

case "$TOOL" in
  Bash)
    CMD="$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.command // empty')"
    [ -n "$CMD" ] && check_bash_command "$CMD"
    ;;
  Read | Write | Edit | MultiEdit | NotebookEdit | Glob | Grep)
    while IFS= read -r p; do
      [ -n "$p" ] || continue
      contained "$p" || deny "path outside the run worktree: $p (FR-53.2)" "$TOOL"
      case "$TOOL" in
        Write | Edit | MultiEdit | NotebookEdit)
          if in_dot_claude "$p"; then
            deny "write into worktree .claude/: $p (FR-53.3)" "$TOOL"
          fi
          ;;
      esac
    done < <(printf '%s' "$PAYLOAD" | jq -r \
      '.tool_input | (.file_path // empty), (.path // empty), (.notebook_path // empty)')
    ;;
esac

exit 0
