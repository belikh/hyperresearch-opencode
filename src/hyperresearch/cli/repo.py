"""`hpr repo` command group — repository-understanding source lane (P5).

Three verbs, one gate. The gate is the EFFECTIVE repo source lane:
vault-global ``[web] repo_source_lane`` OR the resolved profile's own
``repo_source_lane`` overlay — the exact effective-lane semantics P4-C
established for ``parallel_search_lane`` (an explicitly-passed ``--profile``
is validated up front; the implicit gear resolution stays lazy behind the
OR so a broken persisted overlay can never break a lane the vault turned
on globally). Disabled by default: a vault that never opted in sees
LANE_DISABLED with the exact enablement incantation, and the rendered
width-sweep skill stays byte-identical to the pre-P5 goldens.

Verbs:

* ``hpr repo wiki <owner/repo>`` — pull the repo's DeepWiki (official MCP
  endpoint, no auth) into the vault as research notes: one MOC-style
  source note with the full wiki text (long-source delegation applies
  downstream) PLUS one note per wiki page (page-level summaries, tags,
  wiki-links). All notes carry ``tier: practitioner`` /
  ``content_type: code`` semantics via frontmatter tags so the source
  ranking treats them as code artefacts.

* ``hpr repo map [PATH]`` — build a structural map of a LOCAL checkout
  (tree-sitter or regex lane, Aider-style PageRank) and save it as one
  research note. The map makes the repository a citable source for
  questions like "which files implement X".

* ``hpr repo ask <owner/repo>... --question "..."`` — grounded Q&A over
  up to 10 indexed repos via DeepWiki's ask_question; prints the answer
  (JSON with --json). Saves NO notes by design — same zero-persistence
  contract as ``hpr search-web``: the calling agent cites the wiki note
  (from ``repo wiki``), not a raw answer floating free of provenance.

Persistence provenance: ``repo wiki`` notes record ``fetch_provider:
deepwiki`` and ``source: https://deepwiki.com/<owner>/<repo>``, so the
sources table and every provenance check treats them exactly like any
fetched web source.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

from hyperresearch.cli._output import console, output
from hyperresearch.models.output import error, success

app = typer.Typer()


def _effective_repo_lane(
    vault: Any,
    profile_name: str | None,
    json_output: bool,
) -> bool:
    """Gate: `[web] repo_source_lane` OR the resolved profile's overlay.

    Mirrors cli/search_web.py's gate verbatim (UNKNOWN_PROFILE for an
    unknown explicitly-passed name; PROFILE_ERROR for a broken overlay;
    lazy implicit-gear resolution behind the OR short-circuit).
    """
    from hyperresearch.core.profiles import (
        ProfileError,
        list_profiles,
        resolve_profile,
    )

    explicit_profile = None
    try:
        if profile_name is not None:
            explicit_profile = resolve_profile(profile_name, vault.config_path)
        return vault.config.web_repo_source_lane or (
            explicit_profile.repo_source_lane
            if explicit_profile is not None
            else resolve_profile(
                vault.config.pipeline_profile, vault.config_path
            ).repo_source_lane
        )
    except ProfileError as e:
        msg = str(e)
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


def _lane_disabled(json_output: bool) -> None:
    msg = (
        "The repository source lane is disabled for this vault. Enable it "
        "with: hpr config set web.repo_source_lane true — then re-run "
        "`hpr install` so installed skills/agents pick up the Lens-E "
        "repository-sources instructions."
    )
    if json_output:
        output(error(msg, "LANE_DISABLED"), json_mode=True)
    else:
        console.print(f"[red]Lane disabled:[/] {msg}")
    raise typer.Exit(1)


def _discover_vault(json_output: bool) -> Any:
    from hyperresearch.core.vault import Vault, VaultError

    try:
        return Vault.discover()
    except VaultError as e:
        if json_output:
            output(error(str(e), "NO_VAULT"), json_mode=True)
        else:
            console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)


def _sync(vault: Any) -> None:
    from hyperresearch.core.sync import compute_sync_plan, execute_sync

    plan = compute_sync_plan(vault)
    if plan.to_add or plan.to_update:
        execute_sync(vault, plan)


_REPO_SLUG_RE = None  # compiled lazily to keep import time flat


def _parse_repo_slug(slug: str) -> tuple[str, str]:
    """`owner/repo` → (owner, repo). Raises ValueError with guidance."""
    import re

    global _REPO_SLUG_RE
    if _REPO_SLUG_RE is None:
        _REPO_SLUG_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")
    m = _REPO_SLUG_RE.match(slug.strip())
    if not m:
        raise ValueError(
            f"expected owner/repo format, got {slug!r} "
            "(e.g. langchain-ai/openwiki)"
        )
    return m.group(1), m.group(2)


# ---------------------------------------------------------------------------
# repo wiki
# ---------------------------------------------------------------------------


@app.command("wiki")
def repo_wiki(
    repo: str = typer.Argument(..., help="Repository in owner/repo form"),
    tags: list[str] = typer.Option(
        [], "--tag", "-t", help="Tags for the created notes (repo-source is added)"
    ),
    parent: str | None = typer.Option(None, "--parent", "-p", help="Parent note id"),
    save_pages: bool = typer.Option(
        True,
        "--save-pages/--no-save-pages",
        help="Also write one note per wiki page (page-level provenance). "
        "Disable for a single monolithic source note only.",
    ),
    profile_name: str | None = typer.Option(
        None,
        "--profile",
        help="Pipeline profile whose repo_source_lane overlay feeds the gate.",
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Pull a repo's DeepWiki into the vault as research notes."""
    from hyperresearch.web.deepwiki_provider import (
        DeepwikiProvider,
        split_wiki_pages,
    )

    vault = _discover_vault(json_output)
    vault.auto_sync()
    if not _effective_repo_lane(vault, profile_name, json_output):
        _lane_disabled(json_output)

    try:
        owner, name = _parse_repo_slug(repo)
    except ValueError as e:
        if json_output:
            output(error(str(e), "BAD_REPO_SLUG"), json_mode=True)
        else:
            console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    repo_name = f"{owner}/{name}"
    source_url = f"https://deepwiki.com/{repo_name}"

    # Already fetched? Same-URL dedup contract as every fetch path.
    conn = vault.db
    existing = conn.execute(
        "SELECT note_id FROM sources WHERE url = ?", (source_url,)
    ).fetchone()
    if existing and not json_output:
        console.print(
            f"[yellow]Already fetched:[/] {source_url} -> note {existing['note_id']}"
        )

    try:
        prov = DeepwikiProvider()
        wiki_text = prov.read_contents(repo_name)
    except Exception as e:
        if json_output:
            output(error(f"DeepWiki fetch failed: {e}", "REPO_FETCH_ERROR"), json_mode=True)
        else:
            console.print(f"[red]Error:[/] DeepWiki fetch failed: {e}")
        raise typer.Exit(1)

    if not wiki_text.strip():
        if json_output:
            output(
                error(
                    f"DeepWiki returned empty contents for {repo_name} — the "
                    "repo may not be indexed. Submit it at https://deepwiki.com "
                    "or use `hpr repo map` on a local checkout.",
                    "REPO_NOT_INDEXED",
                ),
                json_mode=True,
            )
        else:
            console.print(
                f"[red]Error:[/] DeepWiki returned empty contents for {repo_name} "
                "— the repo may not be indexed (submit at https://deepwiki.com, "
                "or `hpr repo map` a local checkout)."
            )
        raise typer.Exit(1)

    from hyperresearch.core.note import write_note

    now_iso = datetime.now(UTC).isoformat()
    base_tags = list(dict.fromkeys([*tags, "repo-source", "deepwiki"]))

    # --- 1. The monolithic source note (full wiki; long-source delegation
    # applies downstream — >5000 words triggers the source-analyst path).
    wiki_note_path = write_note(
        vault.notes_dir,
        title=f"DeepWiki: {repo_name}",
        body=wiki_text,
        tags=base_tags,
        status="draft",
        note_type="note",
        parent=parent,
        source=source_url,
        tier="practitioner",
        content_type="code",
        extra_frontmatter={
            "source": source_url,
            "source_domain": "deepwiki.com",
            "fetched_at": now_iso,
            "fetch_provider": "deepwiki",
            "repo": repo_name,
        },
    )
    _sync(vault)
    wiki_note_id = wiki_note_path.stem
    _record_source(conn, source_url, wiki_note_id, "deepwiki", wiki_text)

    created: list[dict[str, Any]] = [
        {
            "note_id": wiki_note_id,
            "title": f"DeepWiki: {repo_name}",
            "url": source_url,
            "kind": "wiki",
        }
    ]

    # --- 2. Per-page notes (page-level provenance + wiki-links between
    # pages so the vault graph reflects the wiki's own structure).
    if save_pages:
        for title, body in split_wiki_pages(wiki_text):
            page_path = write_note(
                vault.notes_dir,
                title=f"{repo_name} — {title}",
                body=body,
                tags=[*base_tags, "wiki-page"],
                status="draft",
                note_type="note",
                parent=wiki_note_id,
                source=source_url,
                tier="practitioner",
                content_type="code",
                extra_frontmatter={
                    "source": source_url,
                    "source_domain": "deepwiki.com",
                    "fetched_at": now_iso,
                    "fetch_provider": "deepwiki",
                    "repo": repo_name,
                    "wiki_page": title,
                },
            )
            _sync(vault)
            created.append(
                {
                    "note_id": page_path.stem,
                    "title": f"{repo_name} — {title}",
                    "url": source_url,
                    "kind": "page",
                }
            )

    # --- 3. Link pages to the wiki note (body wiki-links -> links table
    # via sync), surfacing the wiki note as the hub.
    if save_pages and len(created) > 1:
        from hyperresearch.core.note import read_note

        page_ids = [c["note_id"] for c in created[1:]]
        links_md = "\n".join(f"- [[{pid}]]" for pid in page_ids[:200])
        wiki_text_final = wiki_note_path.read_text(encoding="utf-8")
        marker = "\n---\n\n## Wiki pages\n\n"
        wiki_text_final = (
            wiki_text_final.rstrip() + marker + links_md + "\n"
        )
        wiki_note_path.write_text(wiki_text_final, encoding="utf-8")
        _sync(vault)
        # read_note only to validate the note parses post-edit.
        read_note(wiki_note_path, vault.root)

    data = {
        "repo": repo_name,
        "provider": "deepwiki",
        "notes_created": created,
        "total_notes": len(created),
        "wiki_word_count": len(wiki_text.split()),
    }
    if json_output:
        output(success(data, count=len(created), vault=str(vault.root)), json_mode=True)
    else:
        console.print(
            f"[green]Repo wiki saved:[/] {repo_name} — {len(created)} notes "
            f"({data['wiki_word_count']} words). Start with: "
            f"hpr note show {wiki_note_id} -j"
        )


def _record_source(
    conn: Any, url: str, note_id: str, provider: str, content: str
) -> None:
    """sources-table row — the same provenance contract as every fetch."""
    import hashlib

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    conn.execute(
        """INSERT OR IGNORE INTO sources (url, note_id, domain, fetched_at, provider, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            url,
            note_id,
            "deepwiki.com",
            datetime.now(UTC).isoformat(),
            provider,
            content_hash,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# repo map
# ---------------------------------------------------------------------------


@app.command("map")
def repo_map_cmd(
    path: str = typer.Argument(".", help="Path to the repository checkout"),
    tags: list[str] = typer.Option(
        [], "--tag", "-t", help="Tags for the created note (repo-source is added)"
    ),
    parent: str | None = typer.Option(None, "--parent", "-p", help="Parent note id"),
    top: int = typer.Option(40, "--top", min=1, max=500, help="Files detailed in the map"),
    no_save: bool = typer.Option(
        False, "--no-save", help="Print the map without writing a vault note"
    ),
    profile_name: str | None = typer.Option(
        None,
        "--profile",
        help="Pipeline profile whose repo_source_lane overlay feeds the gate.",
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Build a structural map of a local checkout and save it as a note."""
    vault = _discover_vault(json_output)
    vault.auto_sync()
    if not _effective_repo_lane(vault, profile_name, json_output):
        _lane_disabled(json_output)

    from hyperresearch.core.repo_map import build_repo_map, render_repo_map

    root = Path(path).expanduser()
    try:
        result = build_repo_map(root)
        map_md = render_repo_map(result, top=top)
    except (FileNotFoundError, ValueError) as e:
        if json_output:
            output(error(str(e), "REPO_MAP_ERROR"), json_mode=True)
        else:
            console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    if no_save:
        if json_output:
            output(
                success(
                    {
                        "path": result.root,
                        "lane": result.lane,
                        "files": len(result.files),
                        "edges": len(result.edges),
                        "symbols": sum(len(f.definitions) for f in result.files),
                        "map": map_md,
                    },
                    vault=str(vault.root),
                ),
                json_mode=True,
            )
        else:
            console.print(map_md)
        return

    from hyperresearch.core.note import write_note

    root_name = Path(result.root).name or "repo"
    map_note_path = write_note(
        vault.notes_dir,
        title=f"Repo map: {root_name}",
        body=map_md,
        tags=list(dict.fromkeys([*tags, "repo-source", "repo-map"])),
        status="draft",
        note_type="note",
        parent=parent,
        source=f"file://{result.root}",
        tier="ground_truth",
        content_type="code",
        extra_frontmatter={
            "source": f"file://{result.root}",
            "repo_map_lane": result.lane,
            "repo_map_files": len(result.files),
            "repo_map_edges": len(result.edges),
            "fetched_at": datetime.now(UTC).isoformat(),
            "fetch_provider": f"repo-map:{result.lane}",
        },
    )
    _sync(vault)
    note_id = map_note_path.stem

    data = {
        "path": result.root,
        "lane": result.lane,
        "files": len(result.files),
        "edges": len(result.edges),
        "symbols": sum(len(f.definitions) for f in result.files),
        "note_id": note_id,
        "top_files": [
            {"path": f.path, "centrality": round(result.scores.get(f.path, 0.0), 3)}
            for f in result.ranked_files[:10]
        ],
    }
    if json_output:
        output(success(data, vault=str(vault.root)), json_mode=True)
    else:
        console.print(
            f"[green]Repo map saved:[/] {result.root} ({result.lane} lane, "
            f"{len(result.files)} files, {len(result.edges)} edges) -> "
            f"hpr note show {note_id} -j"
        )


# ---------------------------------------------------------------------------
# repo ask
# ---------------------------------------------------------------------------


@app.command("ask")
def repo_ask(
    repos: list[str] = typer.Argument(..., help="Repo(s) in owner/repo form (max 10)"),
    question: str = typer.Option(..., "--question", "-q", help="The question to ask"),
    profile_name: str | None = typer.Option(
        None,
        "--profile",
        help="Pipeline profile whose repo_source_lane overlay feeds the gate.",
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Ask a grounded question about up to 10 indexed repos (saves nothing)."""
    vault = _discover_vault(json_output)
    vault.auto_sync()
    if not _effective_repo_lane(vault, profile_name, json_output):
        _lane_disabled(json_output)

    for slug in repos:
        try:
            _parse_repo_slug(slug)
        except ValueError as e:
            if json_output:
                output(error(str(e), "BAD_REPO_SLUG"), json_mode=True)
            else:
                console.print(f"[red]Error:[/] {e}")
            raise typer.Exit(1)

    from hyperresearch.web.deepwiki_provider import DeepwikiProvider

    try:
        prov = DeepwikiProvider()
        answer = prov.ask_question(repos, question)
    except Exception as e:
        if json_output:
            output(error(f"DeepWiki ask failed: {e}", "REPO_ASK_ERROR"), json_mode=True)
        else:
            console.print(f"[red]Error:[/] DeepWiki ask failed: {e}")
        raise typer.Exit(1)

    if json_output:
        output(
            success(
                {"repos": repos, "question": question, "answer": answer},
                vault=str(vault.root),
            ),
            json_mode=True,
        )
    else:
        console.print(f"[bold]Q:[/] {question}")
        console.print(f"[bold]Repos:[/] {', '.join(repos)}")
        console.print("")
        console.print(answer)
