"""P4-B: `[web] provider` accepts a string OR an ordered fallback chain.

Covers the shared coercion helper (core.config.coerce_web_provider), TOML
round-trip fidelity (list stays list, str stays str), invalid-shape
rejection, and the `config set/get/show` verbs. The CLI tests follow the
CliRunner + tmp_vault pattern of test_core/test_escalation.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app
from hyperresearch.core.config import VaultConfig, coerce_web_provider
from hyperresearch.core.vault import Vault

# ---------------------------------------------------------------------------
# Shared coercion helper
# ---------------------------------------------------------------------------


class TestCoerceWebProvider:
    def test_plain_string_passes_through(self) -> None:
        assert coerce_web_provider("parallel") == "parallel"
        assert isinstance(coerce_web_provider("builtin"), str)

    def test_bare_string_is_stripped(self) -> None:
        # F5: surrounding whitespace must not be stored as part of the name.
        assert coerce_web_provider("  parallel  ") == "parallel"

    def test_list_entries_are_stripped_verbatim_inside(self) -> None:
        # F5: entries lose surrounding whitespace, inner content stays put.
        assert coerce_web_provider([" parallel ", "\tbuiltin\n"]) == [
            "parallel",
            "builtin",
        ]
        assert coerce_web_provider(["a b"]) == ["a b"]  # inner spaces preserved

    def test_json_quoted_scalar_is_rejected_actionably(self) -> None:
        # F5: '"parallel"' (literal quotes) is a quoting mistake, not a
        # provider name — reject cleanly instead of storing quote characters.
        with pytest.raises(ValueError, match="JSON-quoted"):
            coerce_web_provider('"parallel"')

    def test_malformed_quoted_scalar_is_rejected_actionably(self) -> None:
        with pytest.raises(ValueError, match="without quotes"):
            coerce_web_provider('"parallel')

    def test_json_array_string_becomes_list(self) -> None:
        assert coerce_web_provider('["parallel", "builtin"]') == ["parallel", "builtin"]

    def test_real_list_of_strings_passes_through(self) -> None:
        assert coerce_web_provider(["exa", "tavily"]) == ["exa", "tavily"]

    def test_single_element_list_stays_a_list(self) -> None:
        # Round-trip fidelity: never collapse to the bare string.
        coerced = coerce_web_provider(["parallel"])
        assert coerced == ["parallel"]
        assert isinstance(coerced, list)

    def test_malformed_json_array_raises_with_position(self) -> None:
        with pytest.raises(ValueError, match="does not parse"):
            coerce_web_provider('["parallel", ')

    def test_empty_list_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="chain is empty"):
            coerce_web_provider([])

    def test_non_string_entry_names_the_offender(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            coerce_web_provider(["parallel", 1])

        message = str(excinfo.value)
        assert "position 1" in message
        assert "1" in message

    def test_empty_string_entry_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="position 0"):
            coerce_web_provider([""])

    def test_whitespace_only_string_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            coerce_web_provider("   ")

    def test_wrong_type_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="expected a string or a list"):
            coerce_web_provider(42)


# ---------------------------------------------------------------------------
# TOML load/save round-trip
# ---------------------------------------------------------------------------


class TestTomlRoundTrip:
    def test_string_stays_string(self, tmp_path: Path) -> None:
        cfg = VaultConfig(web_provider="crawl4ai")
        p = tmp_path / "config.toml"

        cfg.save(p)

        loaded = VaultConfig.load(p)
        assert loaded.web_provider == "crawl4ai"
        assert isinstance(loaded.web_provider, str)

    def test_list_stays_list(self, tmp_path: Path) -> None:
        providers = ["parallel", "crawl4ai", "builtin"]
        cfg = VaultConfig(web_provider=providers)
        p = tmp_path / "config.toml"

        cfg.save(p)

        loaded = VaultConfig.load(p)
        assert loaded.web_provider == providers
        assert isinstance(loaded.web_provider, list)

    def test_round_trip_is_byte_stable(self, tmp_path: Path) -> None:
        """load -> save -> load must not drift the serialized value."""
        cfg = VaultConfig(web_provider=["parallel", "builtin"])
        p = tmp_path / "config.toml"
        cfg.save(p)
        first_bytes = p.read_bytes()

        reloaded = VaultConfig.load(p)
        reloaded.save(p)

        assert p.read_bytes() == first_bytes

    def test_toml_file_with_list_loads_directly(self, tmp_path: Path) -> None:
        # Hand-written TOML (what a user types), not produced by save().
        p = tmp_path / "config.toml"
        p.write_text(
            '[web]\nprovider = ["parallel", "builtin"]\n',
            encoding="utf-8",
        )

        assert VaultConfig.load(p).web_provider == ["parallel", "builtin"]

    def test_default_config_yields_builtin(self, tmp_path: Path) -> None:
        assert VaultConfig().web_provider == "builtin"
        assert VaultConfig.load(tmp_path / "nope.toml").web_provider == "builtin"

        p = tmp_path / "config.toml"
        VaultConfig().save(p)
        assert 'provider = "builtin"' in p.read_text(encoding="utf-8")
        assert VaultConfig.load(p).web_provider == "builtin"

    @pytest.mark.parametrize(
        ("toml_body", "expected_fragment"),
        [
            ("provider = [1]\n", "position 0"),
            ('provider = [""]\n', "position 0"),
            ("provider = []\n", "chain is empty"),
            ("provider = 5\n", "expected a string or a list"),
        ],
    )
    def test_invalid_toml_shapes_are_rejected(
        self, tmp_path: Path, toml_body: str, expected_fragment: str
    ) -> None:
        p = tmp_path / "config.toml"
        p.write_text(f"[web]\n{toml_body}", encoding="utf-8")

        with pytest.raises(ValueError, match=expected_fragment):
            VaultConfig.load(p)


# ---------------------------------------------------------------------------
# Config verbs (`hyperresearch config set/get/show`)
# ---------------------------------------------------------------------------

runner = CliRunner()


class TestConfigVerbs:
    def _invoke(self, monkeypatch: pytest.MonkeyPatch, tmp_vault: Vault, *args: str):
        monkeypatch.chdir(tmp_vault.root)
        return runner.invoke(app, list(args))

    def test_set_json_array_persists_and_reads_back_as_list(
        self, tmp_vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = self._invoke(
            monkeypatch,
            tmp_vault,
            "config", "set", "web.provider", '["parallel", "builtin"]', "--json",
        )
        assert result.exit_code == 0

        persisted = VaultConfig.load(tmp_vault.config_path).web_provider
        assert persisted == ["parallel", "builtin"]

        got = self._invoke(monkeypatch, tmp_vault, "config", "get", "web.provider", "--json")
        assert got.exit_code == 0
        payload = json.loads(got.stdout)
        assert payload["data"]["value"] == ["parallel", "builtin"]

        shown = self._invoke(monkeypatch, tmp_vault, "config", "show", "--json")
        assert shown.exit_code == 0
        assert json.loads(shown.stdout)["data"]["web_provider"] == ["parallel", "builtin"]

    def test_set_bare_word_persists_as_string(
        self, tmp_vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = self._invoke(
            monkeypatch, tmp_vault, "config", "set", "web.provider", "parallel", "--json"
        )
        assert result.exit_code == 0
        assert json.loads(result.stdout)["data"]["value"] == "parallel"

        persisted = VaultConfig.load(tmp_vault.config_path).web_provider
        assert persisted == "parallel"
        assert isinstance(persisted, str)

    def test_get_returns_list_verbatim_in_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Seed the file directly, then read it back through the verb.
        vault_dir = tmp_path / "seeded-vault"
        vault = Vault.init(vault_dir)
        cfg = VaultConfig(web_provider=["exa", "builtin"])
        cfg.save(vault.config_path)
        monkeypatch.chdir(vault_dir)

        result = runner.invoke(app, ["config", "get", "web.provider", "--json"])

        assert result.exit_code == 0
        assert json.loads(result.stdout)["data"]["value"] == ["exa", "builtin"]

    def test_malformed_json_array_fails_clean_without_partial_write(
        self, tmp_vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_vault.config_path
        before = config_path.read_bytes()

        result = self._invoke(
            monkeypatch, tmp_vault, "config", "set", "web.provider", '["parallel', "--json"
        )

        assert result.exit_code == 1
        combined = result.stdout + (result.stderr or "")
        assert "does not parse" in combined
        assert config_path.read_bytes() == before  # no partial write

    def test_invalid_entries_fail_clean_without_partial_write(
        self, tmp_vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_vault.config_path
        before = config_path.read_bytes()

        result = self._invoke(
            monkeypatch, tmp_vault, "config", "set", "web.provider", "[1]", "--json"
        )

        assert result.exit_code == 1
        assert config_path.read_bytes() == before

    def test_show_displays_list_verbatim_for_humans(
        self, tmp_vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert (
            self._invoke(
                monkeypatch,
                tmp_vault,
                "config", "set", "web.provider", '["parallel", "builtin"]',
            ).exit_code
            == 0
        )

        shown = self._invoke(monkeypatch, tmp_vault, "config", "show")

        assert shown.exit_code == 0
        # Human output renders the chain verbatim as a JSON-ish list.
        assert "'parallel'" in shown.output and "'builtin'" in shown.output
