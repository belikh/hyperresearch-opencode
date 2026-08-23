"""AC-7 arm: every registered top-level verb answers `--help` with exit 0.

P1-10 completes the CLI assembly, so the whole registered surface is pinned
here — root commands AND sub-apps — including the lazy `serve`/`mcp` wrappers
whose bodies cannot run until P1-11/P1-12 land their packages but whose
argument surface must answer --help today.

Two mechanisms:
- an introspection test asserting the battery covers exactly what the app has
  registered (a new registration without a smoke entry fails loudly);
- a parametrized --help sweep over every name (exit 0 required).

`install` was intentionally absent until P2-16 (its renderer had not landed);
P2-16 flips that: the verb is registered upstream-first and swept here like
the rest. `show` is registered but hidden and still gets swept.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app

runner = CliRunner()

# Upstream root-level command order (`install` included since P2-16).
EXPECTED_ROOT = [
    "install", "setup", "init", "status", "sync", "search", "fetch",
    "fetch-batch", "research", "tags", "show", "dedup", "archive-run",
    "vault-tag", "import", "repair", "watch", "serve", "mcp",
]

# Sub-apps in upstream add_typer order.
EXPECTED_SUBAPPS = [
    "note", "graph", "index", "lint", "export", "config", "topic", "batch",
    "template", "git", "tag", "profile", "claims", "embed", "run",
    "escalation", "citecheck", "levers", "sources", "assets", "link",
]


def _registered_root_names() -> list[str]:
    return [c.name for c in app.registered_commands]


def _registered_subapp_names() -> list[str]:
    return [g.name for g in app.registered_groups]


def test_battery_covers_every_registered_verb():
    """The --help sweep below must be exhaustive: any newly registered verb
    that is missing from the expected lists fails here, not silently."""
    assert sorted(_registered_root_names()) == sorted(EXPECTED_ROOT)
    assert _registered_subapp_names() == EXPECTED_SUBAPPS


@pytest.mark.parametrize("name", EXPECTED_ROOT)
def test_root_command_help(name: str):
    result = runner.invoke(app, [name, "--help"])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("name", EXPECTED_SUBAPPS)
def test_subapp_help(name: str):
    result = runner.invoke(app, [name, "--help"])
    assert result.exit_code == 0, result.output


def test_install_landed_and_is_registered():
    """P2-16 closed the deferral the old guard pinned: `install` must answer
    today — registered upstream-first, backed by the opencode renderers."""
    assert "install" in _registered_root_names()
    # And it sits in the upstream-first slot, before every other root verb.
    assert _registered_root_names()[0] == "install"
