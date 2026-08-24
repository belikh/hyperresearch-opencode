"""search-web command — agent-visible Parallel search lane results (P4-C).

Returns web-search results as a JSON envelope WITHOUT saving any notes: the
calling agent picks URLs from ``data`` and runs ``hpr fetch`` itself through
the normal fetch path. Gated by an EFFECTIVE flag so the lane stays invisible
unless a vault explicitly opts in — the same flag pair that makes the
installer bake the lane sentence into the width-sweep skill and the fetcher
agent.

Effective-lane semantics (P4-C closure): the lane is enabled iff the
vault-global ``[web] parallel_search_lane`` flag is true OR the operation's
resolved profile enables its own ``parallel_search_lane`` key. Profile
resolution follows the repo's verb convention (explicit ``--profile`` >
the gear persisted by ``hpr profile use`` — ``[pipeline] profile``, itself
defaulting to ``full``) through ``core.profiles.resolve_profile`` against the
discovered vault's config path, so ``[profile.<name>]`` overlays in
``<vault>/.hyperresearch/config.toml`` apply exactly as they do for
``hpr install`` / ``hpr run``. Both inputs default to false, so an
unconfigured vault keeps the lane disabled and the LANE_DISABLED error points
at the config-verb enablement path. An EXPLICITLY-PASSED ``--profile`` is
validated UP FRONT — before the OR — so an unknown or invalid name fails
cleanly regardless of whether the global flag already enables the lane
(UNKNOWN_PROFILE for a name that does not exist, PROFILE_ERROR with the
resolver's own message for invalid overlay definitions; FIX-L4); only the
IMPLICIT/default gear resolution stays lazy behind
the OR short-circuit, so a broken persisted overlay can never break a lane
the vault turned on globally.

Zero persistence by design: no note writes, no sources rows, not even
``vault.auto_sync()`` — a search that saves nothing cannot pollute a vault.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import typer

from hyperresearch.cli._output import console, output
from hyperresearch.models.output import error, success

if TYPE_CHECKING:
    # Delta vs upstream: import guarded for mypy --strict annotation support,
    # mirroring cli/fetch.py's TYPE_CHECKING pattern.
    from hyperresearch.web.base import WebResult

app = typer.Typer()

DEFAULT_MAX_RESULTS = 5


def _result_row(result: WebResult, fallback_provider: str) -> dict[str, Any]:
    """One JSON row per WebResult: url/title/content/provider (+metadata).

    ``provider`` prefers the result's own metadata stamp (what actually served
    this result after chain fall-through) and falls back to the provider's
    post-call name. Metadata rides along only when non-empty.
    """
    metadata = result.metadata or {}
    row: dict[str, Any] = {
        "url": result.url,
        "title": result.title,
        "content": result.content,
        "provider": metadata.get("provider", fallback_provider),
    }
    if metadata:
        row["metadata"] = metadata
    return row


@app.command("search-web")
def search_web(
    query: list[str] = typer.Argument(..., help="Query words (joined with spaces)"),
    provider_name: str | None = typer.Option(
        None, "--provider", help="Web provider override (default: [web] provider)"
    ),
    max_results: int = typer.Option(
        DEFAULT_MAX_RESULTS, "--max-results", "-n", min=1, help="Maximum results"
    ),
    profile_name: str | None = typer.Option(
        None,
        "--profile",
        help=(
            "Pipeline profile whose parallel_search_lane overlay feeds the "
            "lane gate (default: the gear persisted by `hpr profile use`, "
            "i.e. [pipeline] profile, else full). See `hpr profile list`."
        ),
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Search the web and print results as JSON — saves NO notes.

    Each row carries exactly url/title/content/provider (+metadata when
    non-empty); fetch-specific/binary fields (fetched_at, raw_html, media,
    links, screenshot, raw_bytes, raw_content_type) are omitted from search
    JSON by design.
    """
    from hyperresearch.core.profiles import (
        ProfileError,
        list_profiles,
        resolve_profile,
    )
    from hyperresearch.core.vault import Vault, VaultError
    from hyperresearch.web.base import resolve_web_provider

    try:
        vault = Vault.discover()
    except VaultError as e:
        if json_output:
            output(error(str(e), "NO_VAULT"), json_mode=True)
        else:
            console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    # Gate FIRST — before any provider construction, so a disabled lane does
    # zero work and the error tells the agent exactly how to flip the flag.
    # Effective lane (P4-C closure): `[web] parallel_search_lane` OR the
    # resolved profile's own `parallel_search_lane`. An EXPLICITLY-PASSED
    # --profile is validated UP FRONT, before the OR, so an unknown name
    # fails UNKNOWN_PROFILE regardless of flag state (invalid overlay
    # definitions surface as PROFILE_ERROR — FIX-L4); the OR short-circuit
    # on the config flag stays lazy ONLY for the implicit/default gear path,
    # so a broken persisted overlay can never break a lane the vault turned
    # on globally.
    explicit_profile = None
    try:
        if profile_name is not None:
            explicit_profile = resolve_profile(profile_name, vault.config_path)
        lane_enabled = vault.config.web_parallel_search_lane or (
            explicit_profile.parallel_search_lane
            if explicit_profile is not None
            else resolve_profile(
                vault.config.pipeline_profile, vault.config_path
            ).parallel_search_lane
        )
    except ProfileError as e:
        msg = str(e)
        # FIX-L4: only an unknown NAME is UNKNOWN_PROFILE; every other
        # ProfileError (invalid overlay shapes/values, broken [profile]
        # tables) keeps the resolver's message under PROFILE_ERROR.
        # Classification is by membership against list_profiles(), never by
        # sniffing message text. The candidate name is the explicitly passed
        # --profile when present, else the implicit gear the lazy OR path
        # would have resolved ([pipeline] profile). A config so corrupt that
        # even listing profiles fails routes to PROFILE_ERROR — correctly,
        # because nothing about a NAME was wrong there.
        candidate = (
            profile_name
            if profile_name is not None
            else vault.config.pipeline_profile
        )
        try:
            unknown_name = candidate not in list_profiles(vault.config_path)
        except ProfileError:
            unknown_name = False
        code = "UNKNOWN_PROFILE" if unknown_name else "PROFILE_ERROR"
        if json_output:
            output(error(msg, code), json_mode=True)
        else:
            console.print(f"[red]Error:[/] {msg}")
        raise typer.Exit(1)

    if not lane_enabled:
        msg = (
            "The parallel search lane is disabled for this vault. Enable it "
            "with: hpr config set web.parallel_search_lane true — then re-run "
            "`hpr install` so installed skills/agents pick up the lane "
            "instructions."
        )
        if json_output:
            output(error(msg, "LANE_DISABLED"), json_mode=True)
        else:
            console.print(f"[red]Lane disabled:[/] {msg}")
        raise typer.Exit(1)

    q = " ".join(query).strip()
    if not q:
        msg = "Empty search query."
        if json_output:
            output(error(msg, "EMPTY_QUERY"), json_mode=True)
        else:
            console.print(f"[red]Error:[/] {msg}")
        raise typer.Exit(1)

    # resolve_web_provider (P4-B): config may name ONE provider or an ordered
    # fallback chain; a --provider override stays single-candidate.
    try:
        prov = resolve_web_provider(
            provider_name or vault.config.web_provider,
            profile=vault.config.web_profile,
            magic=vault.config.web_magic,
            settings=vault.config.fetch,
            gates=vault.config.junk,
        )
        results = prov.search(q, max_results=max_results)
    except Exception as e:
        msg = f"web search failed: {e}"
        if json_output:
            output(error(msg, "SEARCH_ERROR"), json_mode=True)
        else:
            console.print(f"[red]Search failed:[/] {e}")
        raise typer.Exit(1)

    rows = [_result_row(r, prov.name) for r in results]
    if json_output:
        output(success(rows, count=len(rows), vault=str(vault.root)), json_mode=True)
    else:
        console.print(
            f"[bold]Web search:[/] {q} [dim]({prov.name}, {len(rows)} results)[/]"
        )
        for i, row in enumerate(rows, 1):
            title = row["title"] or "(untitled)"
            console.print(f"  {i}. [cyan]{row['url']}[/] — {title}")
