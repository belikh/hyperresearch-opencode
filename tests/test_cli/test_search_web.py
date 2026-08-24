"""P4-C search-web verb acceptance matrix (tests/test_cli/test_search_web.py).

Covers the piece's mission criteria through the registered root verb:

(a) GATE — flag off (the default): LANE_DISABLED envelope, exit 1, actionable
    enable text, in BOTH json and human modes;
(b) HAPPY PATH — flag on, mocked provider returning known WebResults: ok
    envelope whose ``data`` is a list of {url, title, content, provider} rows
    (+``metadata`` only when non-empty), query joined from positional args,
    ``-n`` plumbed to ``search(max_results=...)`` (default 5);
(c) PROVIDER OVERRIDE — ``--provider NAME`` reaches resolve_web_provider as a
    single string; no override passes the configured value verbatim (str OR
    chain list);
(d) NO PERSISTENCE — zero rows in notes AND sources after a successful
    search; the fetch path is never touched;
(e) FAILURE — a provider error surfaces as SEARCH_ERROR with exit 1;
(f) PER-PROFILE OVERRIDE (P4-C closure) — effective lane = `[web]
    parallel_search_lane` OR the resolved profile's `parallel_search_lane`
    overlay: profile true + web false works, profile false + web true works,
    both absent gates, explicit --profile overrides the gear, an unknown
    --profile fails cleanly before any provider work — EVEN when the global
    flag already enables the lane (explicit --profile validates up front,
    FIX-F2; the lazy short-circuit covers only the implicit/default gear) —
    and the ENABLING direction holds too: an explicit --profile whose own
    overlay sets the key opens the lane with the global flag false;
(g) NEGATIVE PATHS (GAUNTLET r2 FIX-L5) — EMPTY_QUERY, NO_VAULT, `-n 0`
    rejected by typer, human-mode UNKNOWN_PROFILE naming the profile, plus
    the FIX-L4 code discrimination (unknown name vs invalid overlay).

Zero network throughout: the provider seam is monkeypatched at
``hyperresearch.web.base.resolve_web_provider`` (the same seam
tests/test_cli/test_fetch_batch.py uses), so nothing beyond the fake runs.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app
from hyperresearch.web.base import WebResult

runner = CliRunner()

LANE_ENABLE_HINT = "hpr config set web.parallel_search_lane true"


class _FakeSearchProvider:
    """Records calls; returns two known results; must never fetch."""

    name = "fake-parallel"

    def __init__(self) -> None:
        self.search_calls: list[tuple[str, int]] = []

    def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        self.search_calls.append((query, max_results))
        return [
            WebResult(
                url="https://a.test/one",
                title="Result One",
                content="Body one.",
                metadata={"provider": "parallel", "published_date": "2026-01-02"},
            ),
            WebResult(url="https://b.test/two", title="", content="Body two."),
        ]

    def fetch(self, url: str) -> WebResult:  # pragma: no cover - tripwire
        raise AssertionError(f"search-web must never fetch ({url})")


@pytest.fixture
def vault_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh vault, cwd pinned to it."""
    result = runner.invoke(app, ["init", str(tmp_path / "kb"), "--name", "Lane Test"])
    assert result.exit_code == 0, result.output
    root = tmp_path / "kb"
    monkeypatch.chdir(root)
    return root


def _enable_lane(vault_dir: Path) -> None:
    """Flip the flag THROUGH the config verb (exercises the coercion path)."""
    result = runner.invoke(
        app, ["config", "set", "web.parallel_search_lane", "true", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["data"]["value"] is True


def _patch_resolve(
    monkeypatch: pytest.MonkeyPatch,
    provider: _FakeSearchProvider,
) -> dict[str, Any]:
    """Capture the resolve call; returns {'spec': ..., 'kwargs': ...}."""
    captured: dict[str, Any] = {}

    def _fake_resolve(spec: Any, **kwargs: Any) -> _FakeSearchProvider:
        captured["spec"] = spec
        captured["kwargs"] = kwargs
        return provider

    monkeypatch.setattr(
        "hyperresearch.web.base.resolve_web_provider", _fake_resolve
    )
    return captured


# ---------------------------------------------------------------------------
# (a) gate
# ---------------------------------------------------------------------------


class TestLaneDisabledGate:
    def test_json_envelope_shape_and_exit_code(self, vault_dir: Path) -> None:
        result = runner.invoke(app, ["search-web", "anything", "-j"])
        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is False
        assert envelope["error_code"] == "LANE_DISABLED"
        assert LANE_ENABLE_HINT in envelope["error"]

    def test_human_mode_mentions_the_enable_verb(self, vault_dir: Path) -> None:
        result = runner.invoke(app, ["search-web", "anything"])
        assert result.exit_code == 1
        combined = result.stdout + (result.stderr or "")
        # Short fragments only: rich wraps long lines at word boundaries, so
        # the full sentence may be split across captured lines.
        assert "Lane disabled" in combined
        assert "config set" in combined
        assert "web.parallel_search_lane" in combined

    def test_gate_fires_before_any_provider_work(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FIX-F3: the disabled gate must produce the LANE_DISABLED envelope
        AND the resolver must never run — proven by call capture (a bare
        exit_code==1 would also pass for the wrong reason)."""
        calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def _boom(*a: Any, **k: Any) -> None:
            calls.append((a, k))
            raise AssertionError("resolve must not run on a disabled lane")

        monkeypatch.setattr("hyperresearch.web.base.resolve_web_provider", _boom)

        result = runner.invoke(app, ["search-web", "q", "-j"])

        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is False
        assert envelope["error_code"] == "LANE_DISABLED"
        assert calls == []


# ---------------------------------------------------------------------------
# (b) happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_json_shape_rows_and_query_join(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_lane(vault_dir)
        provider = _FakeSearchProvider()
        _patch_resolve(monkeypatch, provider)

        result = runner.invoke(
            app, ["search-web", "solid", "state", "batteries", "-j"]
        )

        assert result.exit_code == 0, result.output
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is True
        assert envelope["count"] == 2
        rows = envelope["data"]
        assert isinstance(rows, list) and len(rows) == 2
        # Row shape: url/title/content/provider always; metadata only when
        # the source result carried any.
        assert rows[0] == {
            "url": "https://a.test/one",
            "title": "Result One",
            "content": "Body one.",
            "provider": "parallel",
            "metadata": {"provider": "parallel", "published_date": "2026-01-02"},
        }
        assert rows[1] == {
            "url": "https://b.test/two",
            "title": "",
            "content": "Body two.",
            "provider": "fake-parallel",
        }
        assert "metadata" not in rows[1]
        # Query words arrive joined with single spaces.
        assert provider.search_calls[0][0] == "solid state batteries"

    def test_max_results_default_is_five_and_flag_plumbs(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_lane(vault_dir)
        provider = _FakeSearchProvider()
        _patch_resolve(monkeypatch, provider)

        assert runner.invoke(app, ["search-web", "q", "-j"]).exit_code == 0
        assert provider.search_calls[-1][1] == 5

        assert runner.invoke(app, ["search-web", "q", "-n", "7", "-j"]).exit_code == 0
        assert provider.search_calls[-1][1] == 7

        long_form = runner.invoke(
            app, ["search-web", "q", "--max-results", "3", "-j"]
        )
        assert long_form.exit_code == 0
        assert provider.search_calls[-1][1] == 3

    def test_human_mode_lists_urls_and_exits_zero(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_lane(vault_dir)
        _patch_resolve(monkeypatch, _FakeSearchProvider())

        result = runner.invoke(app, ["search-web", "q"])

        assert result.exit_code == 0, result.output
        assert "https://a.test/one" in result.stdout
        assert "https://b.test/two" in result.stdout
        # Human mode must NOT print the JSON envelope.
        assert '"ok": true' not in result.stdout


# ---------------------------------------------------------------------------
# (c) provider resolution
# ---------------------------------------------------------------------------


class TestProviderResolution:
    def test_explicit_override_reaches_resolve_as_single_string(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_lane(vault_dir)
        captured = _patch_resolve(monkeypatch, _FakeSearchProvider())

        result = runner.invoke(app, ["search-web", "q", "--provider", "parallel", "-j"])

        assert result.exit_code == 0, result.output
        assert captured["spec"] == "parallel"

    def test_no_override_passes_configured_value_verbatim(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_lane(vault_dir)
        captured = _patch_resolve(monkeypatch, _FakeSearchProvider())

        assert runner.invoke(app, ["search-web", "q", "-j"]).exit_code == 0
        # Default vault [web] provider.
        assert captured["spec"] == "builtin"

    def test_chain_config_flows_through_unmolested(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_lane(vault_dir)
        seeded = runner.invoke(
            app,
            [
                "config", "set", "web.provider",
                '["parallel", "builtin"]', "--json",
            ],
        )
        assert seeded.exit_code == 0
        captured = _patch_resolve(monkeypatch, _FakeSearchProvider())

        assert runner.invoke(app, ["search-web", "q", "-j"]).exit_code == 0
        assert captured["spec"] == ["parallel", "builtin"]


# ---------------------------------------------------------------------------
# (d) persistence boundary
# ---------------------------------------------------------------------------


class TestNoPersistence:
    def test_no_db_rows_after_successful_search(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_lane(vault_dir)
        _patch_resolve(monkeypatch, _FakeSearchProvider())

        result = runner.invoke(app, ["search-web", "q", "-j"])
        assert result.exit_code == 0

        db_path = vault_dir / ".hyperresearch" / "hyperresearch.db"
        assert db_path.exists()
        conn = sqlite3.connect(db_path)
        try:
            for table in ("notes", "sources"):
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                assert count == 0, f"{table} grew — search-web must persist nothing"
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# (e) failure surface
# ---------------------------------------------------------------------------


class TestFailureSurface:
    def test_provider_error_surfaces_as_search_error(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_lane(vault_dir)

        class _Boom(_FakeSearchProvider):
            def search(self, query: str, max_results: int = 5) -> list[WebResult]:
                raise RuntimeError("503 upstream")

        _patch_resolve(monkeypatch, _Boom())

        result = runner.invoke(app, ["search-web", "q", "-j"])
        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is False
        assert envelope["error_code"] == "SEARCH_ERROR"
        assert "503 upstream" in envelope["error"]

    def test_unknown_provider_name_fails_cleanly(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown names fail UP FRONT inside the real resolver — no network,
        no partial state (P4-B semantics inherited by this call site)."""
        _enable_lane(vault_dir)

        result = runner.invoke(app, ["search-web", "q", "--provider", "nope", "-j"])

        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["error_code"] == "SEARCH_ERROR"
        assert "Unknown web provider" in envelope["error"]


# ---------------------------------------------------------------------------
# (f) per-profile lane override (P4-C closure)
# ---------------------------------------------------------------------------


def _append_profile_overlay(vault_dir: Path, body: str) -> None:
    """Hand-write a [profile.*] overlay into the vault config, exactly as a
    user would (VaultConfig.save() round-trips such tables verbatim)."""
    cfg = vault_dir / ".hyperresearch" / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + body, encoding="utf-8")


class TestProfileLaneOverride:
    """Effective lane = `[web] parallel_search_lane` OR the resolved
    profile's own `parallel_search_lane` overlay key. Profile selection
    follows the verb convention: explicit --profile > persisted gear
    ([pipeline] profile) > full."""

    def test_profile_overlay_enables_lane_with_web_flag_false(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _append_profile_overlay(
            vault_dir, "\n[profile.full]\nparallel_search_lane = true\n"
        )
        provider = _FakeSearchProvider()
        captured = _patch_resolve(monkeypatch, provider)

        result = runner.invoke(app, ["search-web", "q", "-j"])

        assert result.exit_code == 0, result.output
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is True
        assert envelope["count"] == 2
        # The provider spec still comes from [web] provider untouched.
        assert captured["spec"] == "builtin"
        assert provider.search_calls[0][0] == "q"

    def test_profile_overlay_false_does_not_veto_web_flag_true(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_lane(vault_dir)
        _append_profile_overlay(
            vault_dir, "\n[profile.full]\nparallel_search_lane = false\n"
        )
        _patch_resolve(monkeypatch, _FakeSearchProvider())

        result = runner.invoke(app, ["search-web", "q", "-j"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["ok"] is True

    def test_both_absent_still_gates(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No web flag AND no overlay: the resolved default gear (full) has
        parallel_search_lane=False, so the LANE_DISABLED gate stands."""
        _patch_resolve(monkeypatch, _FakeSearchProvider())

        result = runner.invoke(app, ["search-web", "q", "-j"])

        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["error_code"] == "LANE_DISABLED"
        assert LANE_ENABLE_HINT in envelope["error"]

    def test_explicit_profile_selection_overrides_the_gear(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The gear's overlay enables the lane, but an explicit --profile at
        an overlay-free profile keeps the gate shut."""
        _append_profile_overlay(
            vault_dir, "\n[profile.full]\nparallel_search_lane = true\n"
        )

        def _boom(*a: Any, **k: Any) -> None:  # pragma: no cover - tripwire
            raise AssertionError("resolve must not run on a disabled lane")

        monkeypatch.setattr("hyperresearch.web.base.resolve_web_provider", _boom)

        result = runner.invoke(app, ["search-web", "q", "--profile", "light", "-j"])

        assert result.exit_code == 1
        assert json.loads(result.stdout)["error_code"] == "LANE_DISABLED"

    def test_unknown_profile_fails_cleanly_before_provider_work(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(*a: Any, **k: Any) -> None:  # pragma: no cover - tripwire
            raise AssertionError("resolve must not run for an unknown profile")

        monkeypatch.setattr("hyperresearch.web.base.resolve_web_provider", _boom)

        result = runner.invoke(app, ["search-web", "q", "--profile", "nope", "-j"])

        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["error_code"] == "UNKNOWN_PROFILE"
        assert "unknown profile 'nope'" in envelope["error"]

    def test_unknown_explicit_profile_fails_even_when_global_lane_on(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FIX-F2: an EXPLICIT --profile is validated up front, BEFORE the
        OR — so `--profile nope` exits UNKNOWN_PROFILE even when the
        vault-global flag already enables the lane. (The lazy short-circuit
        is reserved for the implicit/default gear path.)"""
        _enable_lane(vault_dir)

        calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def _boom(*a: Any, **k: Any) -> None:
            calls.append((a, k))
            raise AssertionError("resolve must not run for an unknown profile")

        monkeypatch.setattr("hyperresearch.web.base.resolve_web_provider", _boom)

        result = runner.invoke(app, ["search-web", "q", "--profile", "nope", "-j"])

        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is False
        assert envelope["error_code"] == "UNKNOWN_PROFILE"
        assert "unknown profile 'nope'" in envelope["error"]
        # The provider seam was never reached either.
        assert calls == []

    def test_valid_explicit_profile_still_gates_on_global_flag_state(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The eager explicit-profile validation changes VALIDATION timing,
        not gate semantics: a valid overlay-free --profile keeps the lane
        shut when the global flag is off."""
        _append_profile_overlay(
            vault_dir, "\n[profile.light]\nparallel_search_lane = false\n"
        )

        def _boom(*a: Any, **k: Any) -> None:  # pragma: no cover - tripwire
            raise AssertionError("resolve must not run on a disabled lane")

        monkeypatch.setattr("hyperresearch.web.base.resolve_web_provider", _boom)

        result = runner.invoke(app, ["search-web", "q", "--profile", "light", "-j"])

        assert result.exit_code == 1
        assert json.loads(result.stdout)["error_code"] == "LANE_DISABLED"

    def test_error_code_discriminates_unknown_name_from_invalid_overlay(
        self, vault_dir: Path
    ) -> None:
        """FIX-L4: both failures exit 1 with the resolver's message intact,
        but the codes differ — an unknown NAME is UNKNOWN_PROFILE while an
        invalid overlay DEFINITION (wrong-typed parallel_search_lane reached
        through the implicit default gear) is PROFILE_ERROR."""
        _append_profile_overlay(
            vault_dir, '\n[profile.full]\nparallel_search_lane = "yes-string"\n'
        )

        bad_overlay = runner.invoke(app, ["search-web", "q", "-j"])
        assert bad_overlay.exit_code == 1
        env = json.loads(bad_overlay.stdout)
        assert env["error_code"] == "PROFILE_ERROR"
        assert "invalid profile 'full'" in env["error"]

        unknown = runner.invoke(
            app, ["search-web", "q", "--profile", "nope", "-j"]
        )
        assert unknown.exit_code == 1
        env_unknown = json.loads(unknown.stdout)
        assert env_unknown["error_code"] == "UNKNOWN_PROFILE"
        assert "unknown profile 'nope'" in env_unknown["error"]

    def test_explicit_profile_overlay_enables_lane_with_global_flag_false(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The explicit-profile ENABLING combination: `--profile <name>`
        whose own overlay sets parallel_search_lane=true opens the lane even
        though the vault-global [web] flag stays false — the explicit profile
        replaces (not merely validates ahead of) the implicit gear in the
        effective-lane OR."""
        _append_profile_overlay(
            vault_dir, "\n[profile.laneon]\nparallel_search_lane = true\n"
        )
        provider = _FakeSearchProvider()
        _patch_resolve(monkeypatch, provider)

        result = runner.invoke(
            app, ["search-web", "q", "--profile", "laneon", "-j"]
        )

        assert result.exit_code == 0, result.output
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is True
        assert envelope["count"] == 2
        assert provider.search_calls[0][0] == "q"


# ---------------------------------------------------------------------------
# (g) negative paths (GAUNTLET r2 FIX-L5)
# ---------------------------------------------------------------------------


class TestNegativePaths:
    def test_empty_query_fails_as_empty_query_envelope(
        self, vault_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An all-whitespace query must fail EMPTY_QUERY AFTER the gate — and
        before any provider work."""
        _enable_lane(vault_dir)

        def _boom(*a: Any, **k: Any) -> None:  # pragma: no cover - tripwire
            raise AssertionError("resolve must not run for an empty query")

        monkeypatch.setattr("hyperresearch.web.base.resolve_web_provider", _boom)

        result = runner.invoke(app, ["search-web", "", " ", "-j"])

        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is False
        assert envelope["error_code"] == "EMPTY_QUERY"
        assert "Empty search query." in envelope["error"]

    def test_no_vault_fails_as_no_vault_envelope(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Outside any vault, discovery fails NO_VAULT — not a traceback, not
        LANE_DISABLED (the gate needs a vault first)."""
        bare = tmp_path / "no-vault-here"
        bare.mkdir()
        monkeypatch.chdir(bare)

        result = runner.invoke(app, ["search-web", "q", "-j"])

        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is False
        assert envelope["error_code"] == "NO_VAULT"
        assert "No hyperresearch vault found" in envelope["error"]

    def test_zero_max_results_rejected_by_typer(
        self, vault_dir: Path
    ) -> None:
        """`-n 0` violates the option's min=1 constraint: typer itself
        rejects it as a usage error (exit != 0) before the body runs."""
        result = runner.invoke(app, ["search-web", "q", "-n", "0", "-j"])

        assert result.exit_code != 0
        # A usage rejection is not an application error envelope.
        assert '"ok": true' not in result.stdout

    def test_human_mode_unknown_profile_output_names_the_profile(
        self, vault_dir: Path
    ) -> None:
        """Human mode carries the same diagnostic payload as the JSON code:
        the resolver's message naming the offending --profile value. Rich may
        wrap long lines, so match short fragments."""
        result = runner.invoke(app, ["search-web", "q", "--profile", "nosuchgear"])

        assert result.exit_code == 1
        combined = result.stdout + (result.stderr or "")
        assert "unknown profile" in combined
        assert "nosuchgear" in combined
