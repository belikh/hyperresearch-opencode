"""Behavioral tests for the opencode lockdown-plugin renderer (P2-15).

Covers the piece's acceptance criteria:

(a) ``PLUGIN_SOURCE`` determinism — rendered bytes are identical across
    repeated renders (the canonical template is a frozen constant);
(b) deny-matrix completeness — the Python-side mirror ``PLUGIN_DENY_MATRIX``
    equals the deny-set derived LIVE from
    :data:`hyperresearch.core.opencode_install.AGENT_SPECS`` ``tools_deny``
    (patcher/polish-auditor -> exactly ``{"write"}``; synthesizer ->
    ``{"edit", "bash"}``), and the JS source embeds the same table as strict
    JSON (parsed out of the emitted source, never trusted by string-grep);
(c) atomic-write helper — an injected ``os.replace`` failure leaves no
    partial file and no temp droppings;
(d) idempotent install into a scratch dir — second pass rewrites nothing,
    bytes stay stable, stale prior content is converged on rewrite.

The JS itself is validated by the LIVE probe archived under
``evidence/p2-15/`` (real executed-attempt transcripts through opencode
1.18.21); no node/bun assumption is made in this suite.

Falsification record: this module was written before
``src/hyperresearch/core/opencode_plugin.py`` existed; running it at that
point fails at collection with ImportError (see PORTING-NOTES.md §P2-15).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from hyperresearch.core.opencode_install import AGENT_SPECS
from hyperresearch.core.opencode_plugin import (
    PLUGIN_DENY_MATRIX,
    PLUGIN_FILENAME,
    PLUGIN_SOURCE,
    render_plugin,
    write_plugin,
)

# ---------------------------------------------------------------------------
# (b) expectations — the ORIGINAL S0-3 tool-lock intent, now enforced ONLY by
#     this plugin (F-B1: opencode's permission model groups edit+write+patch
#     under one `edit` key, so AGENT_SPECS frontmatter locks can no longer
#     express the granular split; the specs' tools_deny is empty by design).
#     The intent is pinned here as a literal, not derived from the specs.
# ---------------------------------------------------------------------------

#: The frozen granular tool-lock intent (S0-3 as amended by F-CS2).
EXPECTED_DENY_INTENT: dict[str, frozenset[str]] = {
    "hyperresearch-patcher": frozenset({"write"}),
    "hyperresearch-polish-auditor": frozenset({"write"}),
    "hyperresearch-synthesizer": frozenset({"edit", "bash"}),
}


def test_python_mirror_matches_locked_intent_exactly() -> None:
    assert {
        agent: frozenset(tools) for agent, tools in PLUGIN_DENY_MATRIX.items()
    } == EXPECTED_DENY_INTENT, (
        "PLUGIN_DENY_MATRIX must carry the S0-3 granular tool-lock intent; "
        "it is the only layer that can express the edit-vs-write split"
    )
    # F-B1 belt-and-braces invariant: the frontmatter specs must NOT also
    # lock these tools (a frontmatter `edit`/`write` deny would block BOTH
    # edit and write under opencode's coarse permission grouping).
    for spec in AGENT_SPECS:
        assert not spec.tools_deny, (
            f"{spec.filename}: frontmatter tools_deny must be empty (F-B1); "
            "the granular lock lives in the lockdown plugin only"
        )
        for tool in spec.permission_denies:
            assert tool not in ("edit", "write"), (
                f"{spec.filename}: permission_deny {tool!r} would block the "
                "whole edit+write+patch group under opencode's permission "
                "model; use the lockdown plugin for granular locks"
            )


def test_matrix_covers_exactly_the_three_locked_agents() -> None:
    assert sorted(PLUGIN_DENY_MATRIX) == [
        "hyperresearch-patcher",
        "hyperresearch-polish-auditor",
        "hyperresearch-synthesizer",
    ]


# ---------------------------------------------------------------------------
# (a) source determinism + embedded-table integrity
# ---------------------------------------------------------------------------


def test_render_plugin_is_deterministic_byte_for_byte() -> None:
    assert render_plugin() == render_plugin()
    assert render_plugin() == PLUGIN_SOURCE


def test_embedded_js_table_parses_and_matches_the_mirror() -> None:
    """The JS DENY_MATRIX is emitted as strict JSON and pinned by parsing.

    String-grep pins rot silently; this parses the table OUT of the emitted
    source so any drift between PLUGIN_SOURCE and PLUGIN_DENY_MATRIX fails.
    """
    match = re.search(
        r"DENY_MATRIX\s*=\s*Object\.freeze\((\{.*?\})\)",
        PLUGIN_SOURCE,
        re.DOTALL,
    )
    assert match is not None, (
        "PLUGIN_SOURCE lost its DENY_MATRIX = Object.freeze({...}) table"
    )
    embedded_raw: Any = json.loads(match.group(1))
    assert isinstance(embedded_raw, dict)
    embedded = {agent: frozenset(tools) for agent, tools in embedded_raw.items()}
    assert embedded == {
        agent: frozenset(tools) for agent, tools in PLUGIN_DENY_MATRIX.items()
    }


def test_source_carries_denial_marker_and_session_agent_tracking() -> None:
    # Hard-deny contract: the throw carries the grep-able marker the probes
    # and transcripts key on.
    assert "DENIED_BY_PLUGIN" in PLUGIN_SOURCE
    # Mechanism contract: agent identity comes from tracking chat.params
    # (the tool.execute.before hook input has NO agent field — S0-3/P2-15),
    # and unknown agents must fall through untouched.
    assert '"chat.params"' in PLUGIN_SOURCE
    assert '"tool.execute.before"' in PLUGIN_SOURCE
    assert "Object.hasOwn" in PLUGIN_SOURCE, (
        "matrix lookup must be own-property guarded (prototype-key safety)"
    )


def test_plugin_filename_is_a_safe_project_scoped_js_name() -> None:
    assert PLUGIN_FILENAME.startswith("hyperresearch-")
    assert PLUGIN_FILENAME.endswith(".js")
    assert re.fullmatch(r"[a-z0-9.-]+", PLUGIN_FILENAME), PLUGIN_FILENAME


# ---------------------------------------------------------------------------
# (c)+(d) writer: atomicity, idempotence, convergence
# ---------------------------------------------------------------------------


def test_write_plugin_installs_canonical_bytes(tmp_path: Path) -> None:
    plugins_dir = tmp_path / ".opencode" / "plugins"
    manifest = write_plugin(plugins_dir)
    path = plugins_dir / PLUGIN_FILENAME
    assert manifest.written == path
    assert manifest.path == path
    assert path.read_text(encoding="utf-8") == PLUGIN_SOURCE
    assert path.read_bytes() == PLUGIN_SOURCE.encode("utf-8")


def test_second_write_into_same_tree_rewrites_nothing(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    write_plugin(plugins_dir)
    target = plugins_dir / PLUGIN_FILENAME
    before = target.read_bytes()
    stat_before = target.stat()
    second = write_plugin(plugins_dir)
    assert second.unchanged == target and second.written is None
    assert target.read_bytes() == before, "re-install must be byte-stable"
    stat_after = target.stat()
    assert (stat_before.st_mtime_ns, stat_before.st_size) == (
        stat_after.st_mtime_ns,
        stat_after.st_size,
    ), "idempotent installer must NOT rewrite a byte-identical file"


def test_write_plugin_converges_stale_prior_content(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(parents=True)
    target = plugins_dir / PLUGIN_FILENAME
    target.write_text("// stale hand-edit\n", encoding="utf-8")
    write_plugin(plugins_dir)
    assert target.read_text(encoding="utf-8") == PLUGIN_SOURCE


def test_injected_replace_failure_leaves_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _atomic_write resolves os.replace inside opencode_install — inject there.
    import hyperresearch.core.opencode_install as install_mod

    plugins_dir = tmp_path / "plugins"

    def exploding_replace(src: Any, dst: Any) -> None:
        raise RuntimeError("injected replace failure")

    monkeypatch.setattr(install_mod.os, "replace", exploding_replace)
    with pytest.raises(RuntimeError, match="injected"):
        write_plugin(plugins_dir)

    target = plugins_dir / PLUGIN_FILENAME
    assert not target.exists(), "failed install must not leave a torn file"
    leftovers = [p.name for p in plugins_dir.iterdir()]
    assert leftovers == [], f"temp droppings left behind: {leftovers}"

    # Tree converges on the next run.
    monkeypatch.undo()
    manifest = write_plugin(plugins_dir)
    assert manifest.written == target
    assert target.read_text(encoding="utf-8") == PLUGIN_SOURCE
