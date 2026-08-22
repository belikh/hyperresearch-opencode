"""Tests for the pipeline profile system (core/profiles.py + `hpr profile`).

Delta vs upstream (P1-7): ModelMap defaults are EMPTY-INHERIT — an unset or
"" role means "run this agent on the session model" (opencode behavior), not
upstream's Claude-facing sonnet/opus pins. The assertions that pinned those
defaults were adapted; a vault-global `[models]` alias table was added
(TestModelsAliasTable). Everything else is byte-faithful.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hyperresearch.core.profiles import (
    BUILTIN_PROFILES,
    ProfileError,
    list_profiles,
    resolve_profile,
)


class TestBuiltins:
    def test_full_matches_shipped_pipeline_values(self):
        p = resolve_profile("full")
        # These pins mirror the V8 skill prose; the render golden tests depend
        # on them staying in lockstep with the templates.
        assert p.steps == tuple(range(1, 17))
        assert p.source_min == 45
        assert p.source_target == (55, 80)
        assert p.batch_count == (10, 12)
        assert p.batch_size == (8, 12)
        assert p.wave1_fetchers == (10, 12)
        assert p.adversarial_searches_min == 5
        assert p.source_analyst_cap == 6
        assert p.source_analyst_word_trigger == 5000
        assert p.loci_analysts == 2
        assert p.loci_max == 6
        assert p.depth_budget_total == 40
        assert p.depth_budget_brackets == ((30, 15), (20, 10), (10, 5), (0, 3))
        assert p.investigator_max == 6
        assert p.claims_cap == (80, 120)
        assert p.claims_min == 30
        assert p.draft_count == 3
        assert p.must_read["argumentative"] == (35, 50)
        assert p.word_targets["argumentative"] == (5000, 10000)
        assert p.critic_finding_caps == {"dialectic": 12, "depth": 12, "width": 10, "instruction": 15}
        assert p.gap_fetch_cap == 5
        assert p.readability_rec_cap == 50
        # Delta vs upstream (P1-7): "" = inherit the session model; upstream
        # pinned sonnet/opus here. The [models] table sets real values.
        assert p.models.fetcher == ""
        assert p.models.synthesizer == ""

    def test_light_matches_shipped_pipeline_values(self):
        p = resolve_profile("light")
        assert p.steps == (1, 2, 10, 15, 16)
        assert p.source_min == 10
        assert p.source_target == (15, 25)
        assert p.wave1_fetchers == (3, 5)
        assert p.utility_scoring is False
        assert p.draft_count == 1
        assert p.single_draft_reads == (8, 15)

    def test_list_builtins(self):
        # Ascending scale order — `hpr profile list` follows this.
        assert list_profiles() == ["light", "full", "premier", "dissertation"]

    def test_all_builtins_validate(self):
        for name in BUILTIN_PROFILES:
            resolve_profile(name)  # must not raise

    def test_all_builtins_have_descriptions(self):
        for name in BUILTIN_PROFILES:
            assert resolve_profile(name).description, f"{name} needs a description"

    def test_premier_scales_up_the_flat_pipeline(self):
        p = resolve_profile("premier")
        full = resolve_profile("full")
        # Same step sequence as full — premier is a scale gear, not a tier.
        assert p.steps == full.steps
        assert p.chapters == (0, 0)  # unchaptered
        # Width roughly doubles
        assert p.source_min == 90
        assert p.source_target == (100, 130)
        assert p.wave1_fetchers == (14, 18)
        assert p.adversarial_searches_min == 8
        # Depth doubles
        assert p.loci_max == 10
        assert p.depth_budget_total == 80
        assert p.investigator_max == 10
        # The downstream funnel widens too — raising only fetch targets would
        # strand the extra corpus in the vault.
        assert p.claims_cap == (150, 220)
        assert p.must_read["argumentative"] == (50, 70)
        assert p.word_targets["argumentative"] == (8000, 16000)
        assert p.citation_totals["argumentative"] == (120, 220)
        # Every scale knob is >= full's
        assert p.source_min > full.source_min
        assert p.depth_budget_total > full.depth_budget_total
        assert p.critic_finding_caps["dialectic"] > full.critic_finding_caps["dialectic"]

    def test_gear_profiles_are_valid_builtins(self):
        from hyperresearch.core.profiles import GEAR_PROFILES

        assert GEAR_PROFILES == ("full", "premier")
        for name in GEAR_PROFILES:
            assert name in BUILTIN_PROFILES

    def test_modelmap_covers_every_installed_agent(self):
        from hyperresearch.core.profiles import ModelMap

        # One field per installed agent role (the four critics share `critics`).
        # If an agent is added to hooks.py, it needs a ModelMap field too —
        # otherwise its `model: << p.models.X >>` template line can't render.
        assert set(ModelMap.model_fields) == {
            "fetcher", "source_analyst", "loci_analyst", "depth_investigator",
            "corpus_critic", "cite_checker", "browser_fetcher",
            "draft_orchestrator", "synthesizer", "critics", "patcher",
            "polish_auditor", "readability_recommender",
        }

    def test_no_cost_estimates_anywhere(self):
        from hyperresearch.core.profiles import Profile

        # Dollar-cost estimates were removed deliberately: on subscription
        # billing they are not a bill, and stating them as costs contradicts
        # how most users run the pipeline. Time estimates remain.
        assert "cost_estimate" not in Profile.model_fields
        assert "time_estimate" in Profile.model_fields


class TestUserOverlay:
    def _write(self, tmp_path: Path, body: str) -> Path:
        p = tmp_path / "config.toml"
        p.write_text(body, encoding="utf-8")
        return p

    def test_override_builtin_key(self, tmp_path: Path):
        cfg = self._write(tmp_path, "[profile.full]\nsource_min = 60\n")
        p = resolve_profile("full", cfg)
        assert p.source_min == 60
        # untouched keys keep built-in values
        assert p.source_target == (55, 80)

    def test_new_profile_extends_full_by_default(self, tmp_path: Path):
        cfg = self._write(
            tmp_path,
            "[profile.megareview]\nsource_min = 250\nloci_max = 20\n",
        )
        p = resolve_profile("megareview", cfg)
        assert p.name == "megareview"
        assert p.extends == "full"
        assert p.source_min == 250
        assert p.loci_max == 20
        assert p.draft_count == 3  # inherited from full

    def test_new_profile_extends_light(self, tmp_path: Path):
        cfg = self._write(
            tmp_path,
            '[profile.micro]\nextends = "light"\nsource_min = 5\n',
        )
        p = resolve_profile("micro", cfg)
        assert p.extends == "light"
        assert p.source_min == 5
        assert p.steps == (1, 2, 10, 15, 16)

    def test_range_overrides_from_toml_arrays(self, tmp_path: Path):
        cfg = self._write(
            tmp_path,
            "[profile.full]\nsource_target = [100, 150]\n"
            "depth_budget_brackets = [[35, 20], [0, 5]]\n",
        )
        p = resolve_profile("full", cfg)
        assert p.source_target == (100, 150)
        assert p.depth_budget_brackets == ((35, 20), (0, 5))

    def test_char_targets_no_word_boundary_overridable_for_non_cjk_scripts(
        self, tmp_path: Path
    ):
        """The shipped char_targets_no_word_boundary values are calibrated
        for CJK -- the only non-word-boundary script this project has real
        usage data for. A deployment serving a different such script (Thai,
        Lao, Khmer, ...) must be able to supply its own calibration through
        the same profile-overlay mechanism as every other tunable, with no
        code changes."""
        cfg = self._write(
            tmp_path,
            "[profile.full]\n"
            "char_targets_no_word_boundary = "
            "{ argumentative = [30000, 45000] }\n",
        )
        p = resolve_profile("full", cfg)
        assert p.char_targets_no_word_boundary == {"argumentative": (30000, 45000)}
        # Unrelated keys are untouched by the override.
        assert p.word_targets["argumentative"] == (5000, 10000)

    def test_listing_includes_user_profiles(self, tmp_path: Path):
        cfg = self._write(tmp_path, "[profile.dissertation]\nsource_min = 250\n")
        assert list_profiles(cfg) == ["light", "full", "premier", "dissertation"]

    def test_missing_config_is_fine(self, tmp_path: Path):
        p = resolve_profile("full", tmp_path / "nope.toml")
        assert p.source_min == 45

    def test_models_overlay_swaps_one_agent(self, tmp_path: Path):
        cfg = self._write(tmp_path, '[profile.full]\nmodels = { fetcher = "haiku" }\n')
        p = resolve_profile("full", cfg)
        assert p.models.fetcher == "haiku"
        # Delta vs upstream (P1-7): unspecified roles stay empty-inherit;
        # upstream asserted their sonnet/opus defaults here.
        assert p.models.source_analyst == ""
        assert p.models.synthesizer == ""

    def test_models_overlay_accepts_full_model_ids(self, tmp_path: Path):
        cfg = self._write(
            tmp_path,
            '[profile.premier]\nmodels = { fetcher = "claude-haiku-4-5-20251001" }\n',
        )
        p = resolve_profile("premier", cfg)
        assert p.models.fetcher == "claude-haiku-4-5-20251001"


class TestModelsAliasTable:
    """Delta vs upstream (P1-7): the vault-global `[models]` alias table.

    Decided default: model aliases inherit the session model when a role is
    unset anywhere; `[models]` pins roles globally, and a profile's own
    `models` overlay wins over it per role.
    """

    def _write(self, tmp_path: Path, body: str) -> Path:
        p = tmp_path / "config.toml"
        p.write_text(body, encoding="utf-8")
        return p

    def test_unset_roles_inherit_by_default(self):
        from hyperresearch.core.profiles import ModelMap

        p = resolve_profile("full")
        for field_name in ModelMap.model_fields:
            assert getattr(p.models, field_name) == "", field_name

    def test_models_table_pins_role_across_profiles(self, tmp_path: Path):
        cfg = self._write(tmp_path, '[models]\nfetcher = "gpt-mini"\n')
        for name in ("light", "full", "premier"):
            assert resolve_profile(name, cfg).models.fetcher == "gpt-mini", name
        # roles the table doesn't mention keep inheriting
        assert resolve_profile("full", cfg).models.synthesizer == ""

    def test_profile_overlay_beats_models_table_per_role(self, tmp_path: Path):
        cfg = self._write(
            tmp_path,
            '[models]\nfetcher = "table-model"\ncritics = "table-critic"\n'
            '\n[profile.full]\nmodels = { fetcher = "overlay-model" }\n',
        )
        p = resolve_profile("full", cfg)
        assert p.models.fetcher == "overlay-model"  # most specific layer wins
        assert p.models.critics == "table-critic"  # falls through to [models]
        # a profile without its own models overlay still sees the table
        assert resolve_profile("light", cfg).models.fetcher == "table-model"

    def test_explicit_empty_assignment_means_inherit(self, tmp_path: Path):
        # Delta vs upstream (P1-7): upstream rejected ""; it is now the
        # explicit inherit-session-model sentinel.
        cfg = self._write(tmp_path, '[profile.full]\nmodels = { fetcher = "" }\n')
        assert resolve_profile("full", cfg).models.fetcher == ""
        # ...and an explicit "" in a profile overlay cannot re-pin a role the
        # [models] table set for other profiles — but for THIS profile it
        # falls through to the table only when the key is ABSENT, so ""
        # genuinely inherits even over a global pin.
        cfg2 = self._write(
            tmp_path, '[models]\nfetcher = "pinned"\n[profile.full]\nmodels = { fetcher = "" }\n'
        )
        assert resolve_profile("full", cfg2).models.fetcher == ""
        assert resolve_profile("light", cfg2).models.fetcher == "pinned"

    def test_whitespace_only_assignment_normalizes_to_inherit(self, tmp_path: Path):
        cfg = self._write(tmp_path, '[models]\nfetcher = "   "\n')
        assert resolve_profile("full", cfg).models.fetcher == ""

    def test_unknown_role_in_models_table_rejected(self, tmp_path: Path):
        cfg = self._write(tmp_path, '[models]\nfetchr = "haiku"\n')
        with pytest.raises(ProfileError, match="invalid profile"):
            resolve_profile("full", cfg)

    def test_non_string_value_in_models_table_rejected(self, tmp_path: Path):
        cfg = self._write(tmp_path, "[models]\nfetcher = 5\n")
        with pytest.raises(ProfileError, match="invalid profile"):
            resolve_profile("full", cfg)

    def test_models_table_survives_vault_config_save_round_trip(self, tmp_path: Path):
        from hyperresearch.core.config import VaultConfig

        p = self._write(tmp_path, '[models]\nfetcher = "haiku"\n')
        cfg = VaultConfig.load(p)
        assert cfg.model_overrides == {"fetcher": "haiku"}
        cfg.save(p)
        reloaded = VaultConfig.load(p)
        assert reloaded.model_overrides == {"fetcher": "haiku"}
        # and still resolves through profiles after the round trip
        assert resolve_profile("full", p).models.fetcher == "haiku"

    def test_empty_models_section_is_fine(self, tmp_path: Path):
        p = self._write(tmp_path, "[models]\n")
        assert resolve_profile("full", p).models.fetcher == ""

    def test_non_table_models_section_rejected(self, tmp_path: Path):
        # TOML also allows a bare scalar key (`models = 5`, no brackets) —
        # the loader rejects it loudly instead of failing obscurely later.
        p = self._write(tmp_path, "models = 5\n")
        with pytest.raises(ProfileError, match=r"\[models\] must be a table"):
            resolve_profile("full", p)


class TestValidation:
    def _write(self, tmp_path: Path, body: str) -> Path:
        p = tmp_path / "config.toml"
        p.write_text(body, encoding="utf-8")
        return p

    def test_unknown_profile(self):
        with pytest.raises(ProfileError, match="unknown profile"):
            resolve_profile("nope")

    def test_unknown_extends(self, tmp_path: Path):
        cfg = self._write(tmp_path, '[profile.x]\nextends = "nope"\n')
        with pytest.raises(ProfileError, match="extends unknown base"):
            resolve_profile("x", cfg)

    def test_typo_key_rejected(self, tmp_path: Path):
        cfg = self._write(tmp_path, "[profile.full]\nsource_minn = 60\n")
        with pytest.raises(ProfileError, match="invalid profile"):
            resolve_profile("full", cfg)

    def test_inverted_range_rejected(self, tmp_path: Path):
        cfg = self._write(tmp_path, "[profile.full]\nsource_target = [80, 55]\n")
        with pytest.raises(ProfileError, match="invalid profile"):
            resolve_profile("full", cfg)

    def test_step_out_of_range_rejected(self, tmp_path: Path):
        cfg = self._write(tmp_path, "[profile.full]\nsteps = [1, 2, 99]\n")
        with pytest.raises(ProfileError, match="invalid profile"):
            resolve_profile("full", cfg)

    # Delta vs upstream (P1-7): upstream's test_empty_model_assignment_rejected
    # was replaced by TestModelsAliasTable.test_explicit_empty_assignment_means_
    # inherit — "" became the legal inherit sentinel.

    def test_unknown_model_agent_rejected(self, tmp_path: Path):
        cfg = self._write(tmp_path, '[profile.full]\nmodels = { fetchr = "haiku" }\n')
        with pytest.raises(ProfileError, match="invalid profile"):
            resolve_profile("full", cfg)


class TestP17Remediation:
    """P1-7 remediation regressions (evidence/gauntlet/P1-7-verdict-r1.md).

    D1 non-table `models` overlay escaped the ProfileError wrapper; D2 ordering
    validation missed the dict-of-Range fields; D3 no non-negativity check on
    scalar knobs. Each test here failed against pre-fix code (falsification
    round captured in PORTING-NOTES.md §P1-7 remediation).
    """

    def _write(self, tmp_path: Path, body: str) -> Path:
        p = tmp_path / "config.toml"
        p.write_text(body, encoding="utf-8")
        return p

    # -- D1: non-table models overlay -------------------------------------

    @pytest.mark.parametrize("bad", ['"haiku"', "5", "true", "[1, 2]"])
    def test_non_table_models_overlay_rejected_as_profile_error(
        self, tmp_path: Path, bad: str
    ):
        cfg = self._write(tmp_path, f"[profile.full]\nmodels = {bad}\n")
        with pytest.raises(ProfileError, match=r"models.*must be a table"):
            resolve_profile("full", cfg)

    # -- D2: dict-of-Range fields must be ordered per entry ---------------

    @pytest.mark.parametrize(
        ("field", "key"),
        [
            ("must_read", "short"),
            ("word_targets", "short"),
            ("char_targets_no_word_boundary", "structured"),
            ("citation_totals", "argumentative"),
        ],
    )
    def test_inverted_dict_range_rejected(self, tmp_path: Path, field: str, key: str):
        cfg = self._write(tmp_path, f"[profile.full]\n{field} = {{ {key} = [9000, 200] }}\n")
        with pytest.raises(ProfileError, match=f"'{key}'.*low 9000 > high 200"):
            resolve_profile("full", cfg)

    # -- D3: scalar knobs must be non-negative ----------------------------

    def test_negative_scalar_knob_rejected(self, tmp_path: Path):
        cfg = self._write(tmp_path, "[profile.full]\nsource_min = -5\n")
        with pytest.raises(ProfileError, match=r"source_min.*non-negative"):
            resolve_profile("full", cfg)

    def test_negative_cap_value_rejected(self, tmp_path: Path):
        cfg = self._write(
            tmp_path, "[profile.full]\ncritic_finding_caps = { dialectic = -3 }\n"
        )
        with pytest.raises(ProfileError, match="non-negative"):
            resolve_profile("full", cfg)

    def test_negative_range_element_rejected(self, tmp_path: Path):
        cfg = self._write(tmp_path, "[profile.full]\nsource_target = [-10, 20]\n")
        with pytest.raises(ProfileError, match="non-negative"):
            resolve_profile("full", cfg)

    def test_negative_float_knob_rejected(self, tmp_path: Path):
        cfg = self._write(tmp_path, "[profile.full]\nwave_done_ratio = -0.5\n")
        with pytest.raises(ProfileError, match=r"wave_done_ratio.*non-negative"):
            resolve_profile("full", cfg)

    def test_zero_stays_legal_where_designed(self, tmp_path: Path):
        # Upstream semantics check: zero is load-bearing in three places —
        # chapters == (0, 0) means UNCHAPTERED, depth_budget_brackets bottom
        # out at score threshold 0, and a 0 interval/cap means "off"/"always".
        # No knob anywhere in upstream V8 values is negative by design.
        cfg = self._write(
            tmp_path,
            "[profile.full]\nvault_check_interval_s = 0\n"
            "depth_budget_brackets = [[30, 15], [0, 3]]\n"
            "chapters = [0, 0]\n",
        )
        p = resolve_profile("full", cfg)
        assert p.vault_check_interval_s == 0
        assert p.depth_budget_brackets == ((30, 15), (0, 3))
        assert p.chapters == (0, 0)


@pytest.mark.skip(reason="hpr profile CLI lands with the CLI piece (PARITY §15); restore these five tests verbatim then")
class TestProfileCli:
    def test_profile_show_json(self, tmp_vault, monkeypatch):
        import json

        from typer.testing import CliRunner

        from hyperresearch.cli import app

        monkeypatch.chdir(tmp_vault.root)
        runner = CliRunner()
        result = runner.invoke(app, ["profile", "show", "full", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["data"]["source_min"] == 45

    def test_profile_list_json(self, tmp_vault, monkeypatch):
        import json

        from typer.testing import CliRunner

        from hyperresearch.cli import app

        monkeypatch.chdir(tmp_vault.root)
        runner = CliRunner()
        result = runner.invoke(app, ["profile", "list", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        names = [p["name"] for p in payload["data"]["profiles"]]
        assert "full" in names and "light" in names and "premier" in names

    def test_profile_list_marks_current_gear(self, tmp_vault, monkeypatch):
        import json

        from typer.testing import CliRunner

        from hyperresearch.cli import app

        monkeypatch.chdir(tmp_vault.root)
        runner = CliRunner()
        result = runner.invoke(app, ["profile", "list", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["data"]["current_gear"] == "full"
        rows = {p["name"]: p for p in payload["data"]["profiles"]}
        assert rows["full"]["current_gear"] is True
        assert rows["premier"]["current_gear"] is False
        # Friendly metadata is present for every built-in
        for name in ("light", "full", "premier", "dissertation"):
            assert rows[name]["description"]
            assert rows[name]["kind"] in ("gear", "tier")
        assert rows["premier"]["kind"] == "gear"
        assert rows["dissertation"]["kind"] == "tier"

    def test_profile_validate_catches_bad_overlay(self, tmp_vault, monkeypatch):
        cfg_path = tmp_vault.config_path
        cfg_path.write_text(
            cfg_path.read_text(encoding="utf-8") + "\n[profile.full]\nsource_minn = 1\n",
            encoding="utf-8",
        )
        from typer.testing import CliRunner

        from hyperresearch.cli import app

        monkeypatch.chdir(tmp_vault.root)
        runner = CliRunner()
        result = runner.invoke(app, ["profile", "validate", "--json"])
        assert result.exit_code == 1

    def test_profile_show_unknown_errors(self, tmp_vault, monkeypatch):
        from typer.testing import CliRunner

        from hyperresearch.cli import app

        monkeypatch.chdir(tmp_vault.root)
        runner = CliRunner()
        result = runner.invoke(app, ["profile", "show", "bogus", "--json"])
        assert result.exit_code == 1
