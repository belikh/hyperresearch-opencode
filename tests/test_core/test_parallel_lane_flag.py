"""P4-C `[web] parallel_search_lane` config flag (tests/test_core/test_parallel_lane_flag.py).

Covers the flag's full configuration surface, mirroring the P4-B pattern in
test_config_chain.py:

- TOML parse + serialize keeps the bool (true stays true, false stays false,
  re-save is byte-stable);
- default is False when the key or the whole file is missing;
- `config set web.parallel_search_lane true|false` persists through the real
  coercion path; an unrecognized value fails cleanly with exit 1 and NO
  partial write — rich message in human mode (FIX-F8), INVALID_VALUE error
  envelope under --json, TOML byte-stable either way;
- `config get` returns the bool verbatim; `config show` displays it;
- a hand-written `[profile.*] parallel_search_lane` of invalid TYPE fails
  pydantic validation cleanly through resolve_profile's ProfileError wrapper
  (FIX-F8 wrap-through pin).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app
from hyperresearch.core.config import VaultConfig
from hyperresearch.core.vault import Vault

runner = CliRunner()


# ---------------------------------------------------------------------------
# TOML load/save round-trip
# ---------------------------------------------------------------------------


class TestTomlRoundTrip:
    def test_true_stays_true(self, tmp_path: Path) -> None:
        cfg = VaultConfig(web_parallel_search_lane=True)
        p = tmp_path / "config.toml"

        cfg.save(p)

        assert "parallel_search_lane = true" in p.read_text(encoding="utf-8")
        assert VaultConfig.load(p).web_parallel_search_lane is True

    def test_false_stays_false(self, tmp_path: Path) -> None:
        cfg = VaultConfig(web_parallel_search_lane=False)
        p = tmp_path / "config.toml"

        cfg.save(p)

        assert "parallel_search_lane = false" in p.read_text(encoding="utf-8")
        assert VaultConfig.load(p).web_parallel_search_lane is False

    def test_round_trip_is_byte_stable(self, tmp_path: Path) -> None:
        """load -> save -> load must not drift the serialized value."""
        cfg = VaultConfig(web_parallel_search_lane=True)
        p = tmp_path / "config.toml"
        cfg.save(p)
        first_bytes = p.read_bytes()

        reloaded = VaultConfig.load(p)
        reloaded.save(p)

        assert p.read_bytes() == first_bytes

    def test_hand_written_toml_loads_directly(self, tmp_path: Path) -> None:
        # What a user types, not what save() produces.
        p = tmp_path / "config.toml"
        p.write_text(
            "[web]\nprovider = \"parallel\"\nparallel_search_lane = true\n",
            encoding="utf-8",
        )

        loaded = VaultConfig.load(p)
        assert loaded.web_parallel_search_lane is True

    @pytest.mark.parametrize("missing", ["key", "section", "file"])
    def test_default_is_false(self, tmp_path: Path, missing: str) -> None:
        assert VaultConfig().web_parallel_search_lane is False

        if missing == "key":
            p = tmp_path / "config.toml"
            p.write_text("[web]\nprovider = \"builtin\"\n", encoding="utf-8")
            assert VaultConfig.load(p).web_parallel_search_lane is False
        elif missing == "section":
            p = tmp_path / "config.toml"
            p.write_text("[vault]\nname = \"X\"\n", encoding="utf-8")
            assert VaultConfig.load(p).web_parallel_search_lane is False
        else:
            assert VaultConfig.load(tmp_path / "nope.toml").web_parallel_search_lane is False


# ---------------------------------------------------------------------------
# Config verbs
# ---------------------------------------------------------------------------


@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    return Vault.init(tmp_path / "lane-vault", name="Lane Vault")


class TestConfigVerbs:
    def _invoke(self, monkeypatch: pytest.MonkeyPatch, vault: Vault, *args: str):
        monkeypatch.chdir(vault.root)
        return runner.invoke(app, list(args))

    @pytest.mark.parametrize(("raw", "expected"), [("true", True), ("false", False)])
    def test_set_persists_bool(
        self, vault: Vault, monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
    ) -> None:
        result = self._invoke(
            monkeypatch, vault, "config", "set", "web.parallel_search_lane", raw, "--json"
        )
        assert result.exit_code == 0
        assert json.loads(result.stdout)["data"]["value"] is expected

        persisted = VaultConfig.load(vault.config_path).web_parallel_search_lane
        assert persisted is expected

    @pytest.mark.parametrize(("spelling", "expected"), [("1", True), ("yes", True), ("0", False), ("no", False)])
    def test_set_accepts_common_bool_spellings(
        self, vault: Vault, monkeypatch: pytest.MonkeyPatch, spelling: str, expected: bool
    ) -> None:
        result = self._invoke(
            monkeypatch, vault, "config", "set", "web.parallel_search_lane", spelling, "--json"
        )
        assert result.exit_code == 0
        assert json.loads(result.stdout)["data"]["value"] is expected

    def test_set_bad_value_fails_clean_without_partial_write(
        self, vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = vault.config_path
        before = config_path.read_bytes()

        result = self._invoke(
            monkeypatch,
            vault,
            "config", "set", "web.parallel_search_lane", "bananas",
        )

        assert result.exit_code == 1
        combined = result.stdout + (result.stderr or "")
        assert "expects true or false" in combined
        assert "bananas" in combined
        # No partial write — the config on disk is untouched.
        assert config_path.read_bytes() == before

    def test_set_bad_value_json_envelope_and_toml_byte_stability(
        self, vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FIX-F8: under --json the bad-value path emits the same error
        envelope shape every other verb uses (ok=false + error_code), and
        the TOML on disk stays byte-identical."""
        config_path = vault.config_path
        before = config_path.read_bytes()

        result = self._invoke(
            monkeypatch,
            vault,
            "config", "set", "web.parallel_search_lane", "bananas", "--json",
        )

        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is False
        assert envelope["error_code"] == "INVALID_VALUE"
        assert "expects true or false" in envelope["error"]
        assert "bananas" in envelope["error"]
        # Byte-stable: a rejected set must not touch the TOML.
        assert config_path.read_bytes() == before

    def test_get_returns_bool_verbatim(
        self, vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert (
            self._invoke(
                monkeypatch,
                vault, "config", "set", "web.parallel_search_lane", "true",
            ).exit_code
            == 0
        )

        got = self._invoke(
            monkeypatch, vault, "config", "get", "web.parallel_search_lane", "--json"
        )
        assert got.exit_code == 0
        payload = json.loads(got.stdout)
        assert payload["data"] == {"key": "web.parallel_search_lane", "value": True}

    def test_show_displays_the_flag(
        self, vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert (
            self._invoke(
                monkeypatch,
                vault, "config", "set", "web.parallel_search_lane", "true",
            ).exit_code
            == 0
        )

        shown = self._invoke(monkeypatch, vault, "config", "show", "--json")
        assert shown.exit_code == 0
        data = json.loads(shown.stdout)["data"]
        assert data["web_parallel_search_lane"] is True

    def test_unknown_key_still_rejected(
        self, vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = self._invoke(
            monkeypatch, vault, "config", "set", "web.parallel_lane", "true"
        )
        assert result.exit_code == 1

    def test_unknown_key_json_envelope_shape(
        self, vault: Vault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FIX-L6: the unknown-key rejection follows the same error-envelope
        discipline as the bad-value path — under --json it emits ok=false +
        error_code (UNKNOWN_KEY) instead of bare rich-console output."""
        config_path = vault.config_path
        before = config_path.read_bytes()

        result = self._invoke(
            monkeypatch,
            vault,
            "config", "set", "web.parallel_lane", "true", "--json",
        )

        assert result.exit_code == 1
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is False
        assert envelope["error_code"] == "UNKNOWN_KEY"
        assert "web.parallel_lane" in envelope["error"]
        assert "Valid keys" in envelope["error"]
        # Nothing was written either way.
        assert config_path.read_bytes() == before


# ---------------------------------------------------------------------------
# Profile-overlay wrap-through (FIX-F8)
# ---------------------------------------------------------------------------


class TestProfileOverlayTypeSafety:
    def test_invalid_overlay_type_fails_pydantic_validation_cleanly(
        self, vault: Vault
    ) -> None:
        """Wrap-through pin: a hand-written `[profile.full]
        parallel_search_lane = "yes-string"` (invalid type) must surface as a
        clean ProfileError from resolve_profile — the pydantic ValidationError
        is wrapped by the module's error contract, never leaked raw."""
        from hyperresearch.core.profiles import ProfileError, resolve_profile

        cfg_path = vault.config_path
        cfg_path.write_text(
            cfg_path.read_text(encoding="utf-8")
            + '\n[profile.full]\nparallel_search_lane = "yes-string"\n',
            encoding="utf-8",
        )

        with pytest.raises(ProfileError, match="invalid profile 'full'"):
            resolve_profile("full", cfg_path)
