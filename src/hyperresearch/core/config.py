"""Vault configuration management (.hyperresearch/config.toml)."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, TypeVar

_SettingsT = TypeVar("_SettingsT")


def coerce_web_provider(value: object) -> str | list[str]:
    """Validate/coerce a ``[web] provider`` value into ``str | list[str]`` (P4-B).

    Accepts:

    * a plain string (``"parallel"``) — stripped of surrounding whitespace
      and returned;
    * a JSON-array STRING (``'["parallel", "builtin"]'``) — the form
      ``hyperresearch config set web.provider ...`` receives from argv,
      parsed with json.loads;
    * a real list of strings (what tomllib hands :meth:`VaultConfig.load`
      for a TOML array) — each entry stripped of surrounding whitespace,
      otherwise verbatim.

    Every entry must be a non-empty string after stripping; the offending
    entry is named in the error. A JSON-quoted scalar (``'"parallel"'``,
    literal quote characters) is rejected with an actionable error instead
    of storing the quotes as part of the name. Round-trip fidelity: lists
    stay lists (never collapsed to their first element) and strings stay
    strings.

    Raises:
        ValueError: malformed JSON array, a JSON-quoted scalar, wrong entry
            shapes, or an empty spec.
    """
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.startswith("["):
            try:
                parsed: object = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"web.provider: {value!r} looks like a JSON array but does "
                    f"not parse: {exc.msg} (line {exc.lineno}, column {exc.colno})"
                ) from exc
            return coerce_web_provider(parsed)
        if cleaned.startswith('"'):
            # '"parallel"' — a quoting mistake, not a provider name. Reject
            # cleanly instead of storing literal quote characters that fail
            # later at provider resolution.
            try:
                unquoted: object = json.loads(cleaned)
            except json.JSONDecodeError:
                unquoted = None
            raise ValueError(
                "web.provider: got a JSON-quoted scalar "
                f"{value!r}; pass the bare provider name without quotes "
                + (
                    f'(e.g. {unquoted!r})'
                    if isinstance(unquoted, str)
                    else "(e.g. parallel)"
                )
            )
        if not cleaned:
            raise ValueError("web.provider: provider name must be a non-empty string")
        return cleaned
    if isinstance(value, list):
        if not value:
            raise ValueError(
                "web.provider: the provider chain is empty; name at least one "
                'provider, e.g. ["parallel", "builtin"]'
            )
        cleaned_entries: list[str] = []
        for pos, entry in enumerate(value):
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(
                    "web.provider: chain entries must be non-empty strings; "
                    f"got {entry!r} at position {pos}"
                )
            cleaned_entries.append(entry.strip())
        return cleaned_entries
    raise ValueError(
        f"web.provider: expected a string or a list of strings; "
        f"got {type(value).__name__}: {value!r}"
    )


@dataclass(frozen=True)
class FetchSettings:
    """Network/browser behavior for web fetching ([fetch] section)."""

    page_timeout_ms: int = 30000
    pdf_timeout_s: int = 30
    # NOTE: default True is a deliberate 2.0 change — the pre-2.0 code silently
    # disabled TLS verification for PDF downloads. Set to false only for
    # cert-broken mirrors you explicitly trust.
    pdf_verify_tls: bool = True
    min_pdf_bytes: int = 100
    # Smart-wait DOM-stability loop (shared by headless and visible paths)
    wait_initial_ms: int = 2000
    poll_interval_ms: int = 500
    stable_checks: int = 2
    max_checks: int = 16
    image_timeout_s: int = 15
    # Sites that kill headless sessions on first contact → auto-visible browser
    visible_browser_domains: tuple[str, ...] = (
        "linkedin.com", "twitter.com", "x.com", "facebook.com",
        "instagram.com", "tiktok.com",
    )


@dataclass(frozen=True)
class JunkGates:
    """Thresholds for the junk/login-wall content gates ([junk] section)."""

    min_content_chars: int = 300
    login_wall_max_chars: int = 1000
    cookie_wall_max_chars: int = 1500
    binary_garbage_ratio: float = 0.05
    sample_window: int = 2000
    login_sample_chars: int = 500
    # Appended to the built-in signal lists — never replacing them
    extra_login_signals: tuple[str, ...] = ()
    extra_junk_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssetSettings:
    """Screenshot/image saving behavior ([assets] section)."""

    max_images: int = 5
    min_image_bytes: int = 50_000


@dataclass(frozen=True)
class DedupSettings:
    """Near-duplicate detection parameters ([dedup] section)."""

    shingle_size: int = 3
    minhash_perm: int = 128
    lsh_bands: int = 16
    lsh_switchover: int = 200
    default_threshold: float = 0.6


@dataclass(frozen=True)
class ChromeSettings:
    """Browser-lane escalation behavior ([chrome] section).

    The Chrome lane drives the user's real browser (via Claude-in-Chrome)
    for sources headless crawling can't reach. `enabled` gates ENQUEUEING
    of blocked fetches; draining requires the Claude-in-Chrome extension.
    Hard scope boundary: CAPTCHAs/2FA/logins are ALWAYS handed to the human
    (`needs_human`) — never solved automatically.
    """

    enabled: bool = True
    # Blocked URLs below this utility score are abandoned, not escalated —
    # the lane is serial and precious. None-scored URLs are escalated.
    escalation_utility_threshold: float = 8.0
    max_items_per_run: int = 25
    drain_batch_size: int = 10
    scholar_enabled: bool = True


@dataclass(frozen=True)
class RankingSettings:
    """Composite source-quality scoring weights ([ranking] section).

    quality = renormalized weighted sum of the available components
    (tier weight, utility/18, authority percentile, vault centrality).
    Missing components renormalize rather than zeroing. Retracted sources
    are floored at `retraction_floor` regardless of other components.
    """

    w_tier: float = 0.35
    w_utility: float = 0.20
    w_authority: float = 0.25
    w_centrality: float = 0.20
    tier_ground_truth: float = 1.0
    tier_institutional: float = 0.85
    tier_practitioner: float = 0.7
    tier_commentary: float = 0.4
    tier_unknown: float = 0.6
    retraction_floor: float = 0.05
    api_cache_ttl_days: int = 30

    def tier_weight(self, tier: str | None) -> float | None:
        if tier is None:
            return None
        return {
            "ground_truth": self.tier_ground_truth,
            "institutional": self.tier_institutional,
            "practitioner": self.tier_practitioner,
            "commentary": self.tier_commentary,
            "unknown": self.tier_unknown,
        }.get(tier)


@dataclass(frozen=True)
class EmbeddingSettings:
    """Semantic-search embedding provider ([embeddings] section).

    provider "none" (default) disables semantic search entirely — no API key
    needed for any core functionality. "voyage" and "openai" call the
    respective APIs (VOYAGE_API_KEY / OPENAI_API_KEY env vars).
    """

    provider: str = "none"  # none | voyage | openai
    model: str = ""  # provider default when empty
    # How much of each note to embed: title + summary + first N body chars
    body_chars: int = 1500


@dataclass(frozen=True)
class LintSettings:
    """Lint rule thresholds ([lint] section)."""

    extract_min_words: int = 150
    extract_coverage_divisor: int = 3
    stale_review_days: int = 90


@dataclass(frozen=True)
class ScholarSettings:
    """Open-access full-text recovery ([scholar] section).

    When a fetch lands a thin page that carries a DOI — a publisher abstract or
    paywall interstitial — `core/oa.py` asks Unpaywall and Europe PMC for a
    legal open-access copy and stores THAT text in the note body instead. The
    swap is always disclosed: a banner at the top of the body, four `oa_*`
    frontmatter fields, and a line in the fetch output.

    `contact_email` is required by Unpaywall's terms of use. Leave it empty and
    Unpaywall is skipped entirely; Europe PMC needs no key, so biomedical
    recovery still works out of the box.
    """

    oa_recovery: bool = True
    contact_email: str = ""
    # A real paper body runs 20-80k chars; an abstract landing page runs 1-3k.
    oa_min_full_text_chars: int = 6000
    # Prefer the version of record over accepted manuscripts and preprints.
    oa_prefer_published: bool = True
    # Publishers 403 their own open-access PDFs often enough that one attempt
    # loses papers sitting in a repository two candidates down.
    oa_max_attempts: int = 3
    # Also try when the source cannot be read AT ALL (403, login wall, bot
    # wall). Separately switchable because such a note is made entirely of the
    # open-access copy — nothing in it came from the URL that was asked for.
    oa_rescue_blocked: bool = True


# Delta vs upstream: parameter annotations added for mypy --strict; logic identical.
def _build_section(section_cls: type[_SettingsT], data: dict[str, Any]) -> _SettingsT:
    """Build a frozen settings dataclass from a TOML section dict.

    Unknown keys are ignored (forward compatibility); TOML arrays are converted
    to tuples for tuple-typed fields.
    """
    kwargs = {}
    # type-ignore: stdlib dataclasses.fields() stub requires DataclassInstance,
    # which a TypeVar-bounded `type[T]` does not satisfy — a mypy limitation.
    for f in fields(section_cls):  # type: ignore[arg-type]
        if f.name not in data:
            continue
        value = data[f.name]
        if isinstance(value, list):
            value = tuple(value)
        kwargs[f.name] = value
    return section_cls(**kwargs)


@dataclass
class VaultConfig:
    name: str = "Research Base"
    default_status: str = "draft"
    research_dir: str = "research"

    # Search ranking
    search_title_weight: float = 10.0
    search_body_weight: float = 1.0
    search_tags_weight: float = 5.0
    search_aliases_weight: float = 3.0
    search_boost_evergreen: float = 1.5
    search_penalize_deprecated: float = 0.3
    search_penalize_stale: float = 0.7
    # Search output defaults
    search_default_limit: int = 20
    search_chars_per_token: int = 4
    search_snippet_len: int = 200

    # Sync
    auto_sync: bool = True
    exclude_patterns: list[str] = field(
        default_factory=lambda: [
            ".hyperresearch/*", "exports/*", ".git/*", ".venv/*", "node_modules/*", "templates/*",
            "CLAUDE.md", "AGENTS.md", "agents.md", "GEMINI.md", "README.md", "CHANGELOG.md",
        ]
    )

    # Web provider (P4-B): a single name ("builtin") or an ORDERED fallback
    # chain (["parallel", "builtin"]) tried in order on transport errors,
    # HTTP 5xx/429, auth-config errors, and junk/empty results. Resolution
    # semantics: hyperresearch.web.base.resolve_web_provider.
    web_provider: str | list[str] = "builtin"
    web_profile: str = ""  # crawl4ai browser profile name (created via `crwl profiles`)
    web_magic: bool = False  # crawl4ai magic mode (anti-bot stealth)
    # P4-C: agent-visible Parallel search lane. When True, `hpr search-web`
    # works AND the installer bakes one extra sentence into the width-sweep
    # skill + fetcher agent telling agents to run one additional
    # `{hpr_path} search-web ... --provider parallel -j` query per atomic
    # item. Default False: the verb errors with LANE_DISABLED and rendered
    # templates are byte-identical to the pre-P4-C goldens.
    web_parallel_search_lane: bool = False
    # P5: repository-understanding source lane. When True, the `hpr repo`
    # verbs work AND the installer bakes the Lens-E repository-sources
    # paragraph into the width-sweep skill + a `hyperresearch-repo-analyst`
    # agent spawn path, telling agents they can pull a repo's DeepWiki into
    # the vault (`hpr repo wiki`) or map a local checkout (`hpr repo map`)
    # as research sources. Default False: the verbs error with
    # LANE_DISABLED and rendered templates stay byte-identical to the
    # pre-P5 goldens.
    web_repo_source_lane: bool = False

    # Pipeline scale gear ([pipeline] section) — the profile whose numbers are
    # rendered into installed skills/agents. Set via `hpr profile use <name>`.
    pipeline_profile: str = "full"
    # Raw [profile.<name>] overlay tables, round-tripped verbatim on save()
    # so that saving config never destroys user-defined profiles.
    profile_overlays: dict[str, Any] = field(default_factory=dict)
    # Delta vs upstream (P1-7): raw [models] role→model alias table,
    # round-tripped verbatim on save() like profile_overlays. Consumed by
    # core/profiles.resolve_profile as the middle layer of model resolution:
    # profile-overlay `models` > [models] > inherit session model (see
    # core.profiles.ModelMap).
    model_overrides: dict[str, Any] = field(default_factory=dict)

    # Behavior settings sections
    fetch: FetchSettings = field(default_factory=FetchSettings)
    junk: JunkGates = field(default_factory=JunkGates)
    assets: AssetSettings = field(default_factory=AssetSettings)
    dedup: DedupSettings = field(default_factory=DedupSettings)
    lint: LintSettings = field(default_factory=LintSettings)
    ranking: RankingSettings = field(default_factory=RankingSettings)
    embeddings: EmbeddingSettings = field(default_factory=EmbeddingSettings)
    chrome: ChromeSettings = field(default_factory=ChromeSettings)
    scholar: ScholarSettings = field(default_factory=ScholarSettings)

    # Index
    auto_build_index: bool = True
    index_pages: list[str] = field(
        default_factory=lambda: ["_index", "_tags", "_recent", "_orphans", "_stats"]
    )

    @classmethod
    def load(cls, config_path: Path) -> VaultConfig:
        if not config_path.exists():
            return cls()
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        vault = data.get("vault", {})
        sync = data.get("sync", {})
        index = data.get("index", {})
        search = data.get("search", {})
        web = data.get("web", {})
        pipeline = data.get("pipeline", {})

        return cls(
            name=vault.get("name", cls.name),
            default_status=vault.get("default_status", cls.default_status),
            research_dir=vault.get("research_dir", cls.research_dir),
            search_title_weight=search.get("title_weight", cls.search_title_weight),
            search_body_weight=search.get("body_weight", cls.search_body_weight),
            search_tags_weight=search.get("tags_weight", cls.search_tags_weight),
            search_aliases_weight=search.get("aliases_weight", cls.search_aliases_weight),
            search_boost_evergreen=search.get("boost_evergreen", cls.search_boost_evergreen),
            search_penalize_deprecated=search.get("penalize_deprecated", cls.search_penalize_deprecated),
            search_penalize_stale=search.get("penalize_stale", cls.search_penalize_stale),
            search_default_limit=search.get("default_limit", cls.search_default_limit),
            search_chars_per_token=search.get("chars_per_token", cls.search_chars_per_token),
            search_snippet_len=search.get("snippet_len", cls.search_snippet_len),
            web_provider=coerce_web_provider(web.get("provider", cls.web_provider)),
            web_profile=web.get("profile", cls.web_profile),
            web_magic=web.get("magic", cls.web_magic),
            web_parallel_search_lane=web.get(
                "parallel_search_lane", cls.web_parallel_search_lane
            ),
            web_repo_source_lane=web.get(
                "repo_source_lane", cls.web_repo_source_lane
            ),
            pipeline_profile=pipeline.get("profile", cls.pipeline_profile),
            profile_overlays=data.get("profile", {}),
            model_overrides=data.get("models", {}),
            fetch=_build_section(FetchSettings, data.get("fetch", {})),
            junk=_build_section(JunkGates, data.get("junk", {})),
            assets=_build_section(AssetSettings, data.get("assets", {})),
            dedup=_build_section(DedupSettings, data.get("dedup", {})),
            lint=_build_section(LintSettings, data.get("lint", {})),
            ranking=_build_section(RankingSettings, data.get("ranking", {})),
            embeddings=_build_section(EmbeddingSettings, data.get("embeddings", {})),
            chrome=_build_section(ChromeSettings, data.get("chrome", {})),
            scholar=_build_section(ScholarSettings, data.get("scholar", {})),
            auto_sync=sync.get("auto_sync", cls.auto_sync),
            exclude_patterns=sync.get("exclude_patterns", cls().exclude_patterns),
            auto_build_index=index.get("auto_build", cls.auto_build_index),
            index_pages=index.get("pages", cls().index_pages),
        )

    # Delta vs upstream: parameter annotations added for mypy --strict.
    @staticmethod
    def _toml_array(items: Iterable[str]) -> str:
        # Delta vs upstream (P1-1 gauntlet r2 finding 3): items are escaped as
        # proper basic strings, not spliced raw between quotes — an item
        # containing `"` or `\` previously produced invalid TOML.
        quoted = ", ".join(VaultConfig._toml_value(item) for item in items)
        return f"[{quoted}]"

    @staticmethod
    def _toml_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            return "[" + ", ".join(VaultConfig._toml_value(v) for v in value) + "]"
        if isinstance(value, dict):
            inner = ", ".join(f"{k} = {VaultConfig._toml_value(v)}" for k, v in value.items())
            return "{ " + inner + " }"
        if isinstance(value, str):
            # Delta vs upstream (P1-1 gauntlet r2 finding 3, MEDIUM): raw
            # interpolation produced invalid TOML for any string carrying `"`,
            # `\`, or a newline/control char, corrupting the config on
            # save->load round-trips. json.dumps output IS a valid TOML basic
            # string: it escapes exactly the set TOML requires (`\\`,
            # `\"`, `\n`, ... and `\uXXXX` for control/non-ASCII chars).
            return json.dumps(value)
        return str(value)

    def _section_lines(self, header: str, section: Any, preamble: tuple[str, ...] = ()) -> list[str]:
        lines = [f"# {line}" if line else "#" for line in preamble]
        lines.append(f"[{header}]")
        for f in fields(section):
            lines.append(f"{f.name} = {self._toml_value(getattr(section, f.name))}")
        lines.append("")
        return lines

    def save(self, config_path: Path) -> None:
        # Delta vs upstream (P1-1 gauntlet r2 finding 3): every string value
        # is emitted through _toml_value so quotes/backslashes/newlines in
        # e.g. the vault name survive save->load round-trips.
        lines = [
            "[vault]",
            f"name = {self._toml_value(self.name)}",
            f"default_status = {self._toml_value(self.default_status)}",
            f"research_dir = {self._toml_value(self.research_dir)}",
            "",
            "[search]",
            f"title_weight = {self.search_title_weight}",
            f"body_weight = {self.search_body_weight}",
            f"tags_weight = {self.search_tags_weight}",
            f"aliases_weight = {self.search_aliases_weight}",
            f"boost_evergreen = {self.search_boost_evergreen}",
            f"penalize_deprecated = {self.search_penalize_deprecated}",
            f"penalize_stale = {self.search_penalize_stale}",
            f"default_limit = {self.search_default_limit}",
            f"chars_per_token = {self.search_chars_per_token}",
            f"snippet_len = {self.search_snippet_len}",
            "",
            "[web]",
            "# provider: a single name or an ordered fallback chain tried in order",
            '# provider = ["parallel", "builtin"]',
            f"provider = {self._toml_value(self.web_provider)}",
            f"profile = {self._toml_value(self.web_profile)}",
            f"magic = {'true' if self.web_magic else 'false'}",
            # P4-C: opt-in agent-visible Parallel search lane (search-web verb
            # + one conditional template sentence). _toml_value renders bools
            # as bare true/false, so save->load round-trips.
            f"parallel_search_lane = {self._toml_value(self.web_parallel_search_lane)}",
            # P5: opt-in repository-understanding source lane (hpr repo verbs
            # + conditional Lens-E width-sweep paragraph + repo-analyst
            # agent). Same bool round-trip contract as the P4-C flag.
            f"repo_source_lane = {self._toml_value(self.web_repo_source_lane)}",
            "",
            "[pipeline]",
            f"profile = {self._toml_value(self.pipeline_profile)}",
            "",
        ]
        # Delta vs upstream (P1-7): round-trip the [models] alias table
        # verbatim — dropping it on save would silently lose role pins.
        if self.model_overrides:
            lines += ["", "[models]"]
            lines += [f"{k} = {self._toml_value(v)}" for k, v in self.model_overrides.items()]
        lines += self._section_lines("fetch", self.fetch)
        lines += self._section_lines("junk", self.junk)
        lines += self._section_lines("assets", self.assets)
        lines += self._section_lines("dedup", self.dedup)
        lines += self._section_lines("lint", self.lint)
        lines += self._section_lines("ranking", self.ranking)
        lines += self._section_lines("embeddings", self.embeddings)
        lines += self._section_lines("chrome", self.chrome)
        lines += self._section_lines(
            "scholar",
            self.scholar,
            preamble=(
                "Open-access full-text recovery.",
                "",
                "When a fetch lands a thin page carrying a DOI (a publisher abstract or",
                "paywall interstitial), hyperresearch asks Unpaywall and Europe PMC for a",
                "legal open-access copy and stores THAT text in the note body instead.",
                "",
                "The note's `source:` still points at the URL you asked for. The body may",
                "come from somewhere else. Every such note says so in a banner at the top",
                "of its body and in `oa_url` / `oa_source` / `oa_version` frontmatter.",
                "",
                "contact_email: REQUIRED by Unpaywall's terms of use. Leave it empty and",
                "Unpaywall is skipped; Europe PMC needs no key, so recovery over its",
                "open-access subset still works. oa_recovery = false disables everything.",
                "",
                "A recovered copy is only accepted if it is both longer than the page we",
                "already had and long enough to clear oa_min_full_text_chars, so a",
                "repository record page cannot pass for full text.",
                "",
                "oa_rescue_blocked also runs this when the source cannot be read at all —",
                "a 403, a login wall, a bot wall. Those notes are made ENTIRELY of the",
                "open-access copy: the title and authors did not come from the source URL",
                "either. They are marked `oa_recovery_kind: rescued`. Set this to false if",
                "you would rather have no note than a note built from a substitute.",
            ),
        )
        lines += [
            "[sync]",
            f"auto_sync = {'true' if self.auto_sync else 'false'}",
            f"exclude_patterns = {self._toml_array(self.exclude_patterns)}",
            "",
            "[index]",
            f"auto_build = {'true' if self.auto_build_index else 'false'}",
            f"pages = {self._toml_array(self.index_pages)}",
        ]
        # Round-trip user-defined [profile.<name>] overlays verbatim — losing
        # them on save would silently destroy custom pipeline profiles.
        for overlay_name, table in self.profile_overlays.items():
            lines += ["", f"[profile.{overlay_name}]"]
            lines += [f"{k} = {self._toml_value(v)}" for k, v in table.items()]
        config_path.parent.mkdir(parents=True, exist_ok=True)
        # Explicit UTF-8. TOML is UTF-8 by spec and `load` reads it as such, so
        # taking the platform default here (cp1252 on Windows) writes a file
        # this same class cannot read back the moment any value or comment
        # carries a non-ASCII character.
        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
