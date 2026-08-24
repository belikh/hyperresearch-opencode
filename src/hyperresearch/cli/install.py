"""Install command — one-step opencode setup (P2-16).

Port of upstream ``cli/install.py`` (flags/UX shape) retargeted from the
Claude Code renderer (``core/hooks.py``, deliberately NOT ported) to this
repo's opencode renderers:

- ``core/opencode_install.render_agents``  -> 15 subagent roster files
  (``.opencode/agents/hyperresearch-*.md``)
- ``core/opencode_skills.render_skills``   -> 19 skill chain dirs
  (``.opencode/skills/<name>/SKILL.md``)
- ``core/opencode_skills.render_command``  -> ``.opencode/commands/hyperresearch.md``
- ``core/opencode_plugin.write_plugin``    -> ``.opencode/plugins/`` lockdown JS
- ``core/opencode_skills.inject_agents_md``-> marked idempotent ops section

Modes (mirroring the three upstream branches):

- **default (project)**: full install into ``<PATH>/.opencode/`` plus vault
  creation/ensure (``.hyperresearch/`` layout + SQLite DB via the existing
  ``Vault.init`` machinery — an existing vault is NEVER clobbered) and the
  ``AGENTS.md`` injection at the project root.
- **--global**: the same artifact set into opencode's global config root
  (``~/.config/opencode/{agents,skills,plugins,commands}`` + the global rules
  file ``~/.config/opencode/AGENTS.md``). No vault is created — global makes
  the pipeline available everywhere; per-project state still belongs to
  per-project installs.
- **--steps-only**: pipeline steps without the locked roster — ONLY skills +
  command + ``AGENTS.md``. No agents, no plugin, no vault (upstream's
  steps-only branch likewise skips vault init).

Flag semantics kept from upstream where they overlap: ``--steps-only`` takes
precedence over ``--global`` (its branch ran first there too); ``--profile``
defaults to the gear persisted by ``hpr profile use`` in the target vault's
config (falling back to ``full``); an unknown profile fails cleanly with an
error envelope BEFORE any artifact is rendered.

IDEMPOTENCE: every renderer is byte-compare-idempotent (already-identical
files are reported under ``unchanged``, never rewritten), the ``AGENTS.md``
injection returns False on an up-to-date section, and a second run therefore
writes nothing new. PRUNING: after rendering, retired artifacts in OUR
managed namespaces are removed — ``agents/hyperresearch-*.md`` not in the
current 15-file roster, ``skills/hyperresearch*`` directories not in the
current 19-name chain (e.g. a leftover ``hyperresearch-browser-fetcher`` lane
dir), and ``plugins/hyperresearch-*.js`` other than the canonical lockdown
file. Pruning runs strictly AFTER rendering (a mid-run failure can never
delete old artifacts before their replacements exist) and matches ONLY
hyperresearch-prefixed names — user files are never touched. The command
namespace is the single managed file ``commands/hyperresearch.md``, so it has
nothing to prune.

Config-root plumbing (the one piece of glue this port had to add; upstream
hardcoded ``~/.claude``): :func:`opencode_config_root` resolves opencode's
global directory exactly like opencode itself does — ``$XDG_CONFIG_HOME`` when
set, else ``~/.config`` — and is a tiny module-level function so tests can
redirect it through the environment or by monkeypatching it directly.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, NoReturn

import typer

from hyperresearch.cli._output import console, output
from hyperresearch.models.output import error, success

# ---------------------------------------------------------------------------
# Layout constants — the managed namespaces under one opencode dir.
# ---------------------------------------------------------------------------

#: Project-level opencode directory (plural form proven by spikes S0-2/S0-4).
OPENCODE_DIRNAME = ".opencode"

#: Roster/skill/plugin/command subdirectory spellings. ``plugins`` plural is
#: the live-proven spelling on opencode 1.18.21 (P2-15 dirspell probes,
#: archived under evidence/p2-15/); ``commands`` plural is opencode's
#: documented project AND global location; ``agents`` plural is the S0-2
#: standardized roster form.
AGENTS_SUBDIR = "agents"
SKILLS_SUBDIR = "skills"
PLUGINS_SUBDIR = "plugins"
COMMANDS_SUBDIR = "commands"

AGENTS_MD_NAME = "AGENTS.md"


def opencode_config_root() -> Path:
    """Resolve opencode's global config dir the way opencode does.

    ``$XDG_CONFIG_HOME/opencode`` when the env var is set, else
    ``~/.config/opencode``. Kept module-level and dependency-free so tests can
    redirect it either via monkeypatched env vars (exercising this real
    resolution logic) or by patching the function itself.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "opencode"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fail(message: str, code: str, json_mode: bool) -> NoReturn:
    """Emit the error envelope (or rich equivalent) and exit 1."""
    if json_mode:
        output(error(message, code), json_mode=True)
    else:
        err_console_print = console
        err_console_print.print(f"[red]Error:[/] {message}")
    raise typer.Exit(1)


def _ensure_vault(root: Path, name: str) -> tuple[Path, str]:
    """Create/ensure the vault at ``root``; returns ``(vault_root, action)``.

    Reuses the existing init machinery: a missing ``.hyperresearch/`` triggers
    ``Vault.init`` (action ``"created"``). An existing vault is discovered
    walk-up style (upstream behavior) or completed in place when only a
    partial ``.hyperresearch/`` skeleton exists — config.toml is NEVER
    rewritten here, so a user-tuned vault survives every install.
    """
    from hyperresearch.core.vault import HYPERRESEARCH_DIR, Vault, VaultError

    try:
        return Vault.discover(root).root, "existing"
    except VaultError:
        pass

    hr_dir = root / HYPERRESEARCH_DIR
    if hr_dir.exists():
        if not hr_dir.is_dir():
            raise VaultError(f"{hr_dir} exists but is not a directory")
        # Partial hidden-layout state (e.g. interrupted init): finish it via
        # the same pieces Vault.init uses, without clobbering anything.
        vault = Vault(root)
        (vault.hyperresearch_dir / "templates").mkdir(parents=True, exist_ok=True)
        (vault.hyperresearch_dir / "exports").mkdir(parents=True, exist_ok=True)
        _ = vault.db  # opens (creating if needed) + runs idempotent init_schema
        return vault.root, "existing"
    return Vault.init(root, name=name).root, "created"


def _resolve_profile_name(explicit: str | None, config_path: Path | None) -> str:
    """Explicit --profile > gear persisted by `hpr profile use` > "full"."""
    if explicit is not None:
        return explicit
    if config_path is not None and config_path.exists():
        from hyperresearch.core.config import VaultConfig

        persisted = VaultConfig.load(config_path).pipeline_profile
        if persisted:
            return persisted
    return "full"


def _counts(written: int, unchanged: int, pruned: int) -> dict[str, int]:
    return {"written": written, "unchanged": unchanged, "pruned": pruned}


def _prune_retired_agents(agents_dir: Path, keep_filenames: set[str]) -> list[Path]:
    """Remove managed-namespace agent files our spec no longer emits."""
    if not agents_dir.is_dir():
        return []
    pruned: list[Path] = []
    for candidate in sorted(agents_dir.glob("hyperresearch-*.md")):
        if candidate.is_file() and candidate.name not in keep_filenames:
            candidate.unlink()
            pruned.append(candidate)
    return pruned


def _prune_retired_skills(skills_dir: Path, keep_names: set[str]) -> list[Path]:
    """Remove managed-namespace skill DIRECTORIES our spec no longer emits."""
    if not skills_dir.is_dir():
        return []
    pruned: list[Path] = []
    for candidate in sorted(skills_dir.iterdir()):
        # Namespace = directories named ``hyperresearch*`` (the chain prefix).
        # Plain files and non-hyperresearch dirs are never ours to touch.
        if (
            candidate.name.startswith("hyperresearch")
            and candidate.is_dir()
            and candidate.name not in keep_names
        ):
            shutil.rmtree(candidate)
            pruned.append(candidate)
    return pruned


def _prune_retired_plugins(plugins_dir: Path, keep_filename: str) -> list[Path]:
    """Remove managed-namespace plugin scripts our spec no longer emits."""
    if not plugins_dir.is_dir():
        return []
    pruned: list[Path] = []
    for candidate in sorted(plugins_dir.glob("hyperresearch-*.js")):
        if candidate.is_file() and candidate.name != keep_filename:
            candidate.unlink()
            pruned.append(candidate)
    return pruned


# ---------------------------------------------------------------------------
# The verb
# ---------------------------------------------------------------------------


def install(
    path: str = typer.Argument(".", help="Path to install in (project mode target)"),
    name: str = typer.Option("Research Base", "--name", "-n", help="Vault name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
    global_install: bool = typer.Option(
        False,
        "--global",
        "-g",
        help=(
            "Install the roster, skills, plugin, command, and AGENTS.md into "
            "the global opencode config (~/.config/opencode/) so /hyperresearch "
            "works in every session anywhere. Skips per-project vault init."
        ),
    ),
    steps_only: bool = typer.Option(
        False,
        "--steps-only",
        help=(
            "Install ONLY the 19 pipeline step skills + /hyperresearch command "
            "+ AGENTS.md into <PATH>/.opencode/ — no agent roster, no lockdown "
            "plugin, no vault. For users who want the pipeline steps without "
            "the locked roster."
        ),
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help=(
            "Pipeline profile (scale gear) to bake into the rendered prompts "
            "(built-ins: smoke, light, full, premier, dissertation; plus any "
            "[profile.*] defined in .hyperresearch/config.toml). Defaults to "
            "the gear persisted by `hyperresearch profile use` (or 'full'). "
            "See `hyperresearch profile list`."
        ),
    ),
) -> None:
    """Install hyperresearch into an opencode project (or globally).

    Renders the 15-agent roster, 19-skill chain, lockdown plugin, and
    /hyperresearch command into ``<PATH>/.opencode/``, creates the
    ``.hyperresearch/`` vault if missing, and injects the marked operations
    section into ``AGENTS.md``. Re-running is a no-op unless something drifted;
    retired hyperresearch artifacts are pruned.
    """
    from hyperresearch.core.agent_docs import _resolve_executable
    from hyperresearch.core.opencode_install import AGENT_SPECS, OpencodeInstallError, render_agents
    from hyperresearch.core.opencode_plugin import PLUGIN_FILENAME, write_plugin
    from hyperresearch.core.opencode_skills import (
        COMMAND_NAME,
        SKILL_SPECS,
        inject_agents_md,
        render_command,
        render_skills,
    )
    from hyperresearch.core.profiles import ProfileError, resolve_profile
    from hyperresearch.core.vault import VaultError

    # --- Target resolution -----------------------------------------------
    # Upstream branch order preserved: --steps-only wins over --global.
    full_mode = not steps_only
    if steps_only:
        mode = "steps-only"
        project_root = Path(path).resolve()
        oc_dir = project_root / OPENCODE_DIRNAME
        agents_md_path = project_root / AGENTS_MD_NAME
        vault_root: Path | None = None
        vault_action = "skipped"
        # No vault side effects: read the persisted gear only if present.
        steps_config = project_root / ".hyperresearch" / "config.toml"
        config_path: Path | None = steps_config if steps_config.exists() else None
    elif global_install:
        mode = "global"
        project_root = opencode_config_root()
        oc_dir = project_root
        agents_md_path = oc_dir / AGENTS_MD_NAME
        vault_root = None
        vault_action = "skipped"
        config_path = None  # global installs carry no vault config
    else:
        mode = "project"
        project_root = Path(path).resolve()
        oc_dir = project_root / OPENCODE_DIRNAME
        agents_md_path = project_root / AGENTS_MD_NAME
        try:
            vault_root, vault_action = _ensure_vault(project_root, name=name)
        except VaultError as exc:
            _fail(str(exc), "INIT_ERROR", json_output)
        config_path = vault_root / ".hyperresearch" / "config.toml"

    # --- Profile resolution (validated BEFORE any artifact lands) ---------
    # Deliberate (DOC-F7): install has always required a valid profile — it
    # bakes the gear into every rendered prompt — so a broken [profile.*]
    # overlay aborts the install even when the vault-global
    # [web] parallel_search_lane flag alone would have enabled the lane;
    # unlike search-web there is no lazy-resolution escape hatch here.
    profile_name = _resolve_profile_name(profile, config_path)
    try:
        prof = resolve_profile(profile_name, config_path)
    except ProfileError as exc:
        _fail(str(exc), "UNKNOWN_PROFILE", json_output)

    # P4-C (closure): the Parallel search lane rides an OR of two
    # default-false inputs — the vault's `[web] parallel_search_lane` flag and
    # the resolved profile's own `parallel_search_lane` overlay
    # (`[profile.<name>]` in the vault config, applied by resolve_profile
    # above). Both default False, so an unconfigured install renders
    # byte-identical to the pre-P4-C goldens. Global installs carry no vault
    # config: neither input can be set there, so the lane stays off.
    parallel_lane = prof.parallel_search_lane
    if config_path is not None and config_path.exists():
        from hyperresearch.core.config import VaultConfig

        parallel_lane = (
            VaultConfig.load(config_path).web_parallel_search_lane or parallel_lane
        )

    agents_dir = oc_dir / AGENTS_SUBDIR
    skills_dir = oc_dir / SKILLS_SUBDIR
    plugins_dir = oc_dir / PLUGINS_SUBDIR
    commands_dir = oc_dir / COMMANDS_SUBDIR

    hpr_path = _resolve_executable()

    # --- Render (all byte-compare idempotent) ------------------------------
    agent_written = agent_unchanged = plugin_written = plugin_unchanged = 0
    agents_pruned: list[Path] = []
    plugins_pruned: list[Path] = []
    skills_pruned: list[Path] = []
    try:
        if full_mode:
            agent_manifest = render_agents(
                agents_dir, prof, prof.models, hpr_path=hpr_path, parallel_lane=parallel_lane
            )
            agent_written = len(agent_manifest.written)
            agent_unchanged = len(agent_manifest.unchanged)
            plugin_manifest = write_plugin(plugins_dir)
            plugin_written = 1 if plugin_manifest.written else 0
            plugin_unchanged = 1 if plugin_manifest.unchanged else 0

        # Command file: render_command reports only the path, so diff the bytes
        # around the call for exact written/unchanged accounting.
        cmd_path = commands_dir / f"{COMMAND_NAME}.md"
        cmd_before = cmd_path.read_text(encoding="utf-8") if cmd_path.is_file() else None
        render_command(commands_dir)
        cmd_changed = cmd_path.read_text(encoding="utf-8") != cmd_before

        skill_manifest = render_skills(skills_dir, prof, parallel_lane=parallel_lane)
        agents_md_changed = inject_agents_md(agents_md_path, hpr_path=hpr_path)

        # --- Prune retired artifacts (only AFTER rendering succeeded) -----
        if full_mode:
            agents_pruned = _prune_retired_agents(
                agents_dir, {spec.filename for spec in AGENT_SPECS}
            )
            plugins_pruned = _prune_retired_plugins(plugins_dir, PLUGIN_FILENAME)
        # Skills are managed in EVERY mode (steps-only exists to ship them).
        skills_pruned = _prune_retired_skills(skills_dir, {spec.name for spec in SKILL_SPECS})
    except OpencodeInstallError as exc:
        _fail(str(exc), "INSTALL_ERROR", json_output)

    pruned_paths = [*agents_pruned, *skills_pruned, *plugins_pruned]

    # --- Report -------------------------------------------------------------
    data: dict[str, Any] = {
        "target": str(project_root),
        "opencode_dir": str(oc_dir),
        "mode": mode,
        "profile": prof.name,
        "vault": (
            {"path": str(vault_root), "state": vault_action}
            if vault_root is not None
            else None
        ),
        "agents": _counts(agent_written, agent_unchanged, len(agents_pruned)),
        "skills": _counts(
            len(skill_manifest.written), len(skill_manifest.unchanged), len(skills_pruned)
        ),
        "plugin": _counts(
            plugin_written,
            plugin_unchanged,
            len(plugins_pruned),
        ),
        "command": _counts(1 if cmd_changed else 0, 0 if cmd_changed else 1, 0),
        "agents_md": _counts(
            1 if agents_md_changed else 0, 0 if agents_md_changed else 1, 0
        ),
        "pruned_paths": [str(p) for p in pruned_paths],
    }

    if json_output:
        output(success(data), json_mode=True)
        return

    console.print(f"[green]Installed hyperresearch:[/] {oc_dir}")
    console.print(f"  [dim]mode:[/] {mode}   [dim]profile:[/] {prof.name}")
    if vault_root is not None:
        if vault_action == "created":
            console.print(f"  [green]Vault created:[/] {vault_root}")
        else:
            console.print(f"  [dim]Vault exists:[/] {vault_root}")
    else:
        console.print("  [dim]Vault:[/] skipped (no per-project state in this mode)")
    for label, counts in (
        ("Agents", data["agents"]),
        ("Skills", data["skills"]),
        ("Plugin", data["plugin"]),
        ("Command", data["command"]),
    ):
        console.print(
            f"  {label}: +{counts['written']} ={counts['unchanged']} -{counts['pruned']} pruned"
        )
    console.print(f"  AGENTS.md: {'section injected' if agents_md_changed else 'section current'}")
    for pruned in pruned_paths:
        console.print(f"  [yellow]Pruned:[/] {pruned}")
    total_writes = sum(ns["written"] for ns in (data["agents"], data["skills"], data["plugin"], data["command"]))
    if total_writes == 0 and not pruned_paths:
        console.print("  [dim]All artifacts already current.[/]")
    console.print("\n[bold]Ready.[/] Run `/hyperresearch <query>` in opencode.")
