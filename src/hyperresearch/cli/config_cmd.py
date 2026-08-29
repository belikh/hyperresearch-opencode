"""Configuration CLI commands."""

from __future__ import annotations

import typer

from hyperresearch.cli._output import console, output
from hyperresearch.models.output import error, success

app = typer.Typer()


@app.command("show")
def config_show(
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Display current vault configuration."""
    from hyperresearch.core.vault import Vault

    vault = Vault.discover()
    config = vault.config

    data = {
        "vault_name": config.name,
        "vault_path": str(vault.root),
        "research_dir": config.research_dir,
        "web_provider": config.web_provider,
        "web_profile": config.web_profile or "(none)",
        "web_magic": config.web_magic,
        "web_parallel_search_lane": config.web_parallel_search_lane,
        "web_repo_source_lane": config.web_repo_source_lane,
        "auto_sync": config.auto_sync,
        "auto_build_index": config.auto_build_index,
        "search_boost_evergreen": config.search_boost_evergreen,
        "search_penalize_deprecated": config.search_penalize_deprecated,
    }

    if json_output:
        output(success(data, vault=str(vault.root)), json_mode=True)
    else:
        console.print("[bold]Vault Configuration[/]")
        for k, v in data.items():
            console.print(f"  [dim]{k}:[/] {v}")


@app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key (dot notation: vault.name)"),
    value: str = typer.Argument(..., help="Config value"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Set a configuration value."""
    from hyperresearch.core.vault import Vault

    vault = Vault.discover()
    config = vault.config

    # Map dot-notation keys to config attributes
    key_map = {
        "vault.name": "name",
        "vault.research_dir": "research_dir",
        "web.provider": "web_provider",
        "web.profile": "web_profile",
        "web.magic": "web_magic",
        "web.parallel_search_lane": "web_parallel_search_lane",
        "web.repo_source_lane": "web_repo_source_lane",
        "search.boost_evergreen": "search_boost_evergreen",
        "search.penalize_deprecated": "search_penalize_deprecated",
        "sync.auto_sync": "auto_sync",
        "index.auto_build": "auto_build_index",
    }

    attr = key_map.get(key)
    if not attr:
        msg = (
            f"Unknown config key: {key}. Valid keys: {', '.join(key_map.keys())}"
        )
        # FIX-L6: same envelope discipline as the bad-value path below —
        # JSON consumers get ok=false + error_code, rich console only when
        # NOT --json. Emitted BEFORE any write (nothing was touched anyway).
        if json_output:
            output(error(msg, "UNKNOWN_KEY"), json_mode=True)
        else:
            console.print(f"[red]Unknown config key:[/] {key}")
            console.print(f"[dim]Valid keys: {', '.join(key_map.keys())}[/]")
        raise typer.Exit(1)

    # Type coercion
    # Delta vs upstream (naming only): upstream rebound `value` (str) to a
    # bool; strict mypy rejects the rebinding. Zero behavior change.
    # P4-B: web.provider accepts a bare word ("parallel") or a JSON array
    # string ('["parallel", "builtin"]') via the shared coercion helper, so
    # set and load() accept exactly the same shapes.
    coerced: str | bool | list[str] = value
    if attr in ("auto_sync", "auto_build_index", "web_magic"):
        coerced = value.lower() in ("true", "1", "yes")
    elif attr in ("web_parallel_search_lane", "web_repo_source_lane"):
        # P4-C / P5: strict here (unlike the legacy bool keys above, which
        # map any unrecognized spelling to False) — a typo'd flag must fail
        # loudly, because a silently-disabled lane looks identical to no
        # lane at all.
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes"):
            coerced = True
        elif lowered in ("false", "0", "no"):
            coerced = False
        else:
            msg = (
                f"web.{'parallel_search_lane' if attr == 'web_parallel_search_lane' else 'repo_source_lane'} "
                f"expects true or false; got {value!r}"
            )
            # FIX-F8: JSON consumers get the same error envelope shape as
            # every other verb's failure path — rich console only when not
            # --json. Emitted BEFORE any write, so the TOML is untouched.
            if json_output:
                output(error(msg, "INVALID_VALUE"), json_mode=True)
            else:
                console.print(f"[red]{msg}[/]")
            raise typer.Exit(1)
    elif attr == "web_provider":
        from hyperresearch.core.config import coerce_web_provider

        try:
            coerced = coerce_web_provider(value)
        except ValueError as exc:
            # Clean error BEFORE any write: no partial config state.
            # FIX-L4-adjacent: same envelope discipline as the bad-value and
            # unknown-key paths above — JSON consumers get ok=false +
            # error_code, rich console only when NOT --json.
            if json_output:
                output(error(str(exc), "INVALID_VALUE"), json_mode=True)
            else:
                console.print(f"[red]{exc}[/]")
            raise typer.Exit(1)

    setattr(config, attr, coerced)
    config.save(vault.config_path)

    if json_output:
        output(success({"key": key, "value": coerced}, vault=str(vault.root)), json_mode=True)
    else:
        console.print(f"[green]Set[/] {key} = {coerced}")


@app.command("get")
def config_get(
    key: str = typer.Argument(..., help="Config key"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Get a configuration value."""
    from hyperresearch.core.vault import Vault

    vault = Vault.discover()
    config = vault.config

    key_map = {
        "vault.name": "name",
        "vault.research_dir": "research_dir",
        "web.provider": "web_provider",
        "web.profile": "web_profile",
        "web.magic": "web_magic",
        "web.parallel_search_lane": "web_parallel_search_lane",
        "web.repo_source_lane": "web_repo_source_lane",
        "search.boost_evergreen": "search_boost_evergreen",
        "search.penalize_deprecated": "search_penalize_deprecated",
        "sync.auto_sync": "auto_sync",
        "index.auto_build": "auto_build_index",
    }

    attr = key_map.get(key)
    if not attr:
        # FIX-L4-adjacent: mirror `config set`'s unknown-key envelope — under
        # --json emit ok=false + error_code instead of bare rich output.
        msg = f"Unknown config key: {key}"
        if json_output:
            output(error(msg, "UNKNOWN_KEY"), json_mode=True)
        else:
            console.print(f"[red]Unknown config key:[/] {key}")
        raise typer.Exit(1)

    value = getattr(config, attr)

    if json_output:
        output(success({"key": key, "value": value}, vault=str(vault.root)), json_mode=True)
    else:
        typer.echo(value)


@app.command("agent-docs")
def config_agent_docs(
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Update CLAUDE.md with the latest hyperresearch blurb."""
    from hyperresearch.core.agent_docs import inject_agent_docs
    from hyperresearch.core.vault import Vault

    vault = Vault.discover()
    modified = inject_agent_docs(vault.root)

    if json_output:
        output(success({"modified": modified}, vault=str(vault.root)), json_mode=True)
    else:
        if modified:
            for m in modified:
                console.print(f"  [green]{m}[/]")
        else:
            console.print("[dim]CLAUDE.md already up to date.[/]")
