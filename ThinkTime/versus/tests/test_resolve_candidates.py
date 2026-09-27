"""Phase A tests: resolve_candidates.py — FR-1..FR-5, FR-62 (T-U-22 parse
slice, T-U-26 branch matrix, T-I-7 refusals).

Tier 0: stdlib + pytest only, no subprocess spawn, no network.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from resolve_candidates import (  # noqa: E402
    CandidateError,
    CandidateKind,
    ContradictionRefusal,
    EnforcementPath,
    RestrictionsDeclared,
    KNOWN_TOOLS,
    parse_agent_md,
    resolve_candidate,
    resolve_enforcement,
    resolve_pair,
    synthesize_wrapper,
)


# ---------------------------------------------------------------- helpers

AGENT_MD = """---
name: probe
description: test agent
model: haiku
{tools_line}{disallowed_line}---
Body line one.
Body line two.
"""


def write_agent(
    tmp_path: Path, name: str = "agent.md", tools=None, disallowed=None
) -> Path:
    tools_line = f"tools: {json.dumps(tools)}\n" if tools is not None else ""
    dis_line = (
        f"disallowedTools: {json.dumps(disallowed)}\n" if disallowed is not None else ""
    )
    p = tmp_path / name
    p.write_text(AGENT_MD.format(tools_line=tools_line, disallowed_line=dis_line))
    return p


def write_skill(tmp_path: Path, name: str = "myskill") -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: myskill\ndescription: a skill\n---\nDo the thing.\n"
    )
    return d


# ---------------------------------------------------------------- FR-4 parse


class TestAgentParse:
    def test_body_is_below_closing_delimiter(self, tmp_path):
        p = write_agent(tmp_path, tools=["Read"])
        parsed = parse_agent_md(p)
        assert parsed["name"] == "probe"
        assert parsed["description"] == "test agent"
        assert parsed["model"] == "haiku"
        assert parsed["prompt"].startswith("Body line one.")
        assert "---" not in parsed["prompt"]

    def test_tools_parsed_as_list(self, tmp_path):
        p = write_agent(tmp_path, tools=["Read", "Bash"], disallowed=["Bash"])
        parsed = parse_agent_md(p)
        assert parsed["tools"] == ["Read", "Bash"]
        assert parsed["disallowedTools"] == ["Bash"]

    def test_comma_separated_tools_accepted(self, tmp_path):
        p = tmp_path / "a.md"
        p.write_text("---\nname: a\ndescription: d\ntools: Read, Bash\n---\nB\n")
        assert parse_agent_md(p)["tools"] == ["Read", "Bash"]

    def test_absent_tools_is_none_not_empty(self, tmp_path):
        p = write_agent(tmp_path)
        parsed = parse_agent_md(p)
        assert parsed["tools"] is None
        assert parsed["disallowedTools"] is None

    def test_explicit_empty_tools_is_empty_list(self, tmp_path):
        p = write_agent(tmp_path, tools=[])
        assert parse_agent_md(p)["tools"] == []

    def test_unknown_tool_entry_aborts_naming_entry(self, tmp_path):
        p = write_agent(tmp_path, tools=["Read", "Bogus"])
        with pytest.raises(CandidateError) as exc:
            resolve_candidate(p)
        assert "Bogus" in str(exc.value)

    def test_unknown_disallowed_entry_aborts_naming_entry(self, tmp_path):
        p = write_agent(tmp_path, disallowed=["Nope"])
        with pytest.raises(CandidateError) as exc:
            resolve_candidate(p)
        assert "Nope" in str(exc.value)


# ---------------------------------------------------------------- FR-1 kinds


class TestKinds:
    def test_agent_md_is_agent(self, tmp_path):
        c = resolve_candidate(write_agent(tmp_path))
        assert c.kind is CandidateKind.AGENT
        assert Path(c.source_path).is_absolute()

    def test_skill_dir_is_skill(self, tmp_path):
        c = resolve_candidate(write_skill(tmp_path))
        assert c.kind is CandidateKind.SKILL

    def test_plugin_dir_is_skill_kind(self, tmp_path):
        d = tmp_path / "plug"
        (d / ".claude-plugin").mkdir(parents=True)
        (d / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "plug", "version": "0.0.1"})
        )
        (d / "skills" / "s").mkdir(parents=True)
        (d / "skills" / "s" / "SKILL.md").write_text(
            "---\nname: s\ndescription: d\n---\nB\n"
        )
        c = resolve_candidate(d)
        assert c.kind is CandidateKind.SKILL

    def test_nonexistent_path_refused(self, tmp_path):
        with pytest.raises(CandidateError):
            resolve_candidate(tmp_path / "missing")

    def test_uncommitted_source_recorded_with_content_hash(self, tmp_path):
        # tmp_path is not a git repo: head_sha must record uncommitted+hash
        c = resolve_candidate(write_agent(tmp_path))
        assert c.head_sha.startswith("uncommitted:")

    def test_committed_source_records_head_sha(self, tmp_path):
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        p = write_agent(tmp_path)
        env = {
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": "/usr/bin:/bin",
        }
        subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, env=env)
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-qm", "x"], check=True, env=env
        )
        c = resolve_candidate(p)
        assert len(c.head_sha) == 40 and not c.head_sha.startswith("uncommitted")


# ---------------------------------------------------------------- T-I-7


class TestPairRefusals:
    def test_cross_kind_refused_with_reason(self, tmp_path):
        a = write_agent(tmp_path)
        s = write_skill(tmp_path)
        with pytest.raises(CandidateError) as exc:
            resolve_pair(a, s)
        assert "kind" in str(exc.value).lower()

    def test_identical_paths_refused(self, tmp_path):
        a = write_agent(tmp_path)
        with pytest.raises(CandidateError):
            resolve_pair(a, a)

    def test_identical_paths_allowed_under_self_calibrate(self, tmp_path):
        a = write_agent(tmp_path)
        pa, pb = resolve_pair(a, a, self_calibrate=True)
        assert pa.source_path == pb.source_path


# ---------------------------------------------------------------- FR-5


class TestWrapperSynthesis:
    def test_bare_skill_gets_wrapper_plugin(self, tmp_path):
        s = write_skill(tmp_path)
        work = tmp_path / "work"
        plugin_dir = synthesize_wrapper(s, work)
        manifest = plugin_dir / ".claude-plugin" / "plugin.json"
        assert manifest.is_file()
        data = json.loads(manifest.read_text())
        assert data["name"]
        assert (plugin_dir / "skills" / "myskill" / "SKILL.md").is_file()

    def test_plugin_dir_passes_through_unwrapped(self, tmp_path):
        d = tmp_path / "plug"
        (d / ".claude-plugin").mkdir(parents=True)
        (d / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "plug", "version": "0.0.1"})
        )
        work = tmp_path / "work"
        assert synthesize_wrapper(d, work) == d.resolve()


# ---------------------------------------------------------------- T-U-26
# FR-62 ordered chain, post-observation form: all four branches fire; the
# contradiction-refusal and translation fallback remain live code.


def enforce(tools, disallowed, honoured=True):
    return resolve_enforcement(
        tools, disallowed, known_tools=KNOWN_TOOLS, disallowed_honoured=honoured
    )


class TestFR62Chain:
    # -- branch 1: no declaration at all
    def test_no_declaration_records_none_and_no_flags(self):
        r = enforce(None, None)
        assert r.path is EnforcementPath.PASS_THROUGH
        assert r.restrictions_declared is RestrictionsDeclared.NONE
        assert r.disallowed_tools_enforced is False
        assert r.tools_allowlist_enforced is False

    def test_no_declaration_not_stamped_allowlist_regression(self):
        # Without the dedicated branch this shape falls through to
        # T ∩ D = ∅ and is stamped tools_allowlist_enforced on a
        # declaration never made. Assert that regression explicitly.
        r = enforce(None, None)
        assert r.tools_allowlist_enforced is False

    # -- branch order: explicit empty list resolves before T∩D=∅
    def test_explicit_empty_tools_records_tools_only_empty(self):
        r = enforce([], None)
        assert r.restrictions_declared is RestrictionsDeclared.TOOLS_ONLY_EMPTY
        assert r.disallowed_tools_enforced is False
        assert r.tools_allowlist_enforced is False

    def test_explicit_empty_tools_with_nonempty_disallowed_same_branch(self):
        # tools: [] satisfies both T⊆D and T∩D=∅ for every D and must
        # resolve to the first branch (test plan T-U-26 "for every D").
        r = enforce([], ["Bash"])
        assert r.restrictions_declared is RestrictionsDeclared.TOOLS_ONLY_EMPTY
        assert r.disallowed_tools_enforced is False
        assert r.tools_allowlist_enforced is False

    # -- T ⊆ D with non-empty T
    def test_equal_set_singleton_disallowed_enforced(self):
        r = enforce(["Bash"], ["Bash"])
        assert r.path is EnforcementPath.PASS_THROUGH
        assert r.disallowed_tools_enforced is True
        assert r.tools_allowlist_enforced is False

    def test_equal_set_cardinality_generalization(self):
        # tools:["Bash","Read"] + disallowedTools:["Bash","Read"] passes
        # like the observed single-tool case.
        r = enforce(["Bash", "Read"], ["Bash", "Read"])
        assert r.disallowed_tools_enforced is True

    def test_proper_subset_disallowed_enforced(self):
        r = enforce(["Bash"], ["Bash", "Read"])
        assert r.disallowed_tools_enforced is True

    # -- T ∩ D = ∅ (the default shape: tools declared, no disallowed)
    def test_tools_only_allowlist_enforced(self):
        r = enforce(["Read"], None)
        assert r.path is EnforcementPath.PASS_THROUGH
        assert r.tools_allowlist_enforced is True
        assert r.disallowed_tools_enforced is False

    def test_disjoint_sets_allowlist_enforced(self):
        r = enforce(["Read"], ["Bash"])
        assert r.tools_allowlist_enforced is True
        assert r.disallowed_tools_enforced is False

    # -- partial restriction: T∩D≠∅ and T−D≠∅ — NOT refused (gate is history)
    def test_partial_restriction_passes_disallowed_enforced(self):
        r = enforce(["Bash", "Write"], ["Bash"])
        assert r.path is EnforcementPath.PASS_THROUGH
        assert r.disallowed_tools_enforced is True

    def test_tools_absent_nonempty_disallowed_is_partial(self):
        # tools absent → T defaults to full known list; a non-empty D is a
        # partial restriction over it.
        r = enforce(None, ["Bash"])
        assert r.path is EnforcementPath.PASS_THROUGH
        assert r.disallowed_tools_enforced is True

    # -- branch selection is per candidate, never a global flag
    def test_branch_selected_per_candidate(self):
        r1 = enforce(["Read"], None)
        r2 = enforce(["Bash"], ["Bash"])
        assert r1.tools_allowlist_enforced and not r1.disallowed_tools_enforced
        assert r2.disallowed_tools_enforced and not r2.tools_allowlist_enforced

    # -- fallback branches remain live code (T-U-26 iii)
    def test_translation_fallback_when_not_honoured(self):
        r = enforce(["Bash", "Write"], ["Bash"], honoured=False)
        assert r.path is EnforcementPath.TRANSLATED
        assert r.disallowed_tools_translated is True
        assert r.effective_allowlist == ["Write"]

    def test_contradiction_refused_with_printed_reason(self):
        # T ⊆ D under not-honoured: no allow-list can express it (an empty
        # allow-list is the contradiction) → refuse, never run unenforced.
        with pytest.raises(ContradictionRefusal) as exc:
            enforce(["Bash"], ["Bash"], honoured=False)
        assert str(exc.value)  # printed reason is non-empty

    def test_no_path_runs_unenforced_disallowed(self):
        # Every honoured=False outcome is TRANSLATED or a refusal —
        # exhaustive over the chain.
        for tools, dis in [(["Bash", "Write"], ["Bash"]), (None, ["Bash"])]:
            r = enforce(tools, dis, honoured=False)
            assert r.path is EnforcementPath.TRANSLATED

    # -- the chosen path is recorded (comparison.json shape)
    def test_result_serializes_chosen_path(self):
        r = enforce(["Bash", "Write"], ["Bash"])
        d = r.to_record()
        assert d["enforcement_path"] == "pass_through"
        assert d["disallowed_tools_enforced"] is True
