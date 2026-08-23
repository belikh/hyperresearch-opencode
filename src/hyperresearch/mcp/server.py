"""hyperresearch MCP server — thin protocol layer over existing hyperresearch functions.

Exposes 13 tools for agents: search_notes, read_note, read_many, list_notes,
get_backlinks, get_hubs, vault_status, lint_vault, check_source, list_sources,
fetch_url, create_note, update_note. Mostly-read navigation plus three
write-capable tools (fetch_url, create_note, update_note) that mutate the
vault directly.
"""

# Delta vs upstream (P1-11 remediation M-5): the module docstring and the
# FastMCP instructions said "Exposes 8 tools ... Read-only by design" — stale
# against this module's own registration (13 @server.tool() functions, three
# of them mutating the vault). Corrected faithfully above/below; supersedes
# the PARITY survey note 2 "kept verbatim" decision (PORTING-NOTES.md §P1-11).

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import FastMCP

if TYPE_CHECKING:
    # Delta vs upstream: annotation-only import for strict-mypy signatures.
    # Runtime imports stay lazy exactly as upstream (vault is only touched on
    # first tool call), so importing this module still requires nothing but
    # the `mcp` package.
    from hyperresearch.core.vault import Vault

server = FastMCP("hyperresearch", instructions=(
    "hyperresearch is an agent-driven research knowledge base. Use these tools to search, read, "
    "and navigate research notes with wiki-links, tags, and summaries. Notes live in the research/ "
    "directory as markdown files with YAML frontmatter. Create or edit notes with create_note / "
    "update_note, and save web sources as notes with fetch_url; files written directly are still "
    "indexed by the next auto-sync."
))

# Delta vs upstream: `_vault = None` → annotated (strict mypy: Vault | None).
_vault: Vault | None = None


def _get_vault() -> Vault:
    global _vault
    if _vault is None:
        from hyperresearch.core.vault import Vault
        _vault = Vault.discover()
        _vault.auto_sync()
    return _vault


@server.tool()
def search_notes(query: str, tag: str = "", status: str = "", parent: str = "", limit: int = 10) -> str:
    """Search the research base by text. Returns matching notes with titles, summaries, and full bodies.

    Args:
        query: Search query (supports natural language, FTS5 with porter stemming)
        tag: Filter by tag (comma-separated for multiple, AND logic)
        status: Filter by status (draft, review, evergreen, stale, deprecated, archive)
        parent: Filter by parent topic (e.g. "ml/deep-learning")
        limit: Max results to return (default 10)
    """
    vault = _get_vault()
    vault.auto_sync()
    # Delta vs upstream (P1-11 remediation M-1): untrusted fencing import,
    # hoisted to handler top per M-5 (was per-loop in read_many upstream-style
    # deltas; every body-emitting tool now imports once at its top).
    from hyperresearch.core.untrusted import is_untrusted, wrap_body
    from hyperresearch.search.filters import SearchFilters
    from hyperresearch.search.fts import SearchQueryError, search_fts
    tags = [t.strip() for t in tag.split(",") if t.strip()] or None
    filters = SearchFilters(tags=tags, status=status or None, parent=parent or None)
    ranking = {
        "title_weight": vault.config.search_title_weight,
        "body_weight": vault.config.search_body_weight,
        "tags_weight": vault.config.search_tags_weight,
        "aliases_weight": vault.config.search_aliases_weight,
        "boost_evergreen": vault.config.search_boost_evergreen,
        "penalize_deprecated": vault.config.search_penalize_deprecated,
        "penalize_stale": vault.config.search_penalize_stale,
    }
    try:
        results = search_fts(vault.db, query, filters=filters, limit=limit, ranking=ranking)
    except SearchQueryError as e:
        return f"Invalid search query: {e}"
    for r in results:
        # Delta vs upstream (P1-11 remediation M-1): join n.source alongside
        # the body (same shape as cli/search.py's body attach) so untrusted
        # provenance is classifiable. Pre-fix this loop emitted stored bodies
        # RAW — the one body-emitting tool that bypassed the fence.
        row = vault.db.execute(
            "SELECT nc.body, n.source FROM note_content nc "
            "JOIN notes n ON n.id = nc.note_id WHERE nc.note_id = ?",
            (r["id"],),
        ).fetchone()
        r["body"] = row["body"] if row else ""
        source = row["source"] if row else None
        if r["body"] and is_untrusted(source, r["type"]):
            r["body"] = wrap_body(r["body"], str(source))
            r["untrusted"] = True
    return json.dumps(results, default=str)


@server.tool()
def read_note(note_id: str) -> str:
    """Read a single note by ID. Returns full metadata and body content.

    Args:
        note_id: The note's slug ID (e.g. "transformer-architecture")
    """
    # Delta vs upstream (P1-11 remediation M-5): untrusted import hoisted from
    # mid-handler to handler top (lazy discipline unchanged — still not a
    # module-level import, so bare `import hyperresearch.mcp.server` still
    # needs nothing but the mcp package).
    from hyperresearch.core.untrusted import is_untrusted, wrap_body

    vault = _get_vault()
    vault.auto_sync()
    row = vault.db.execute(
        "SELECT n.*, nc.body FROM notes n JOIN note_content nc ON n.id = nc.note_id WHERE n.id = ?",
        (note_id,),
    ).fetchone()
    if not row:
        return json.dumps({"error": f"Note not found: {note_id}"})
    tag_row = vault.db.execute("SELECT GROUP_CONCAT(tag, ',') as tl FROM tags WHERE note_id = ?", (note_id,)).fetchone()
    tags = tag_row["tl"].split(",") if tag_row and tag_row["tl"] else []
    # Delta vs upstream (P1-11): external-source bodies are fenced through
    # core.untrusted before leaving the server, mirroring the other
    # body-emitting consumers (cli/note.py::show, cli/search.py). Upstream
    # returns stored bodies raw here; see PORTING-NOTES.md §P1-11.

    data = {
        "id": row["id"], "title": row["title"], "path": row["path"],
        "status": row["status"], "type": row["type"], "tags": tags,
        "created": row["created"], "updated": row["updated"],
        "word_count": row["word_count"], "summary": row["summary"],
        "source": row["source"], "parent": row["parent"], "body": row["body"],
    }
    if is_untrusted(data.get("source"), data.get("type")):
        data["body"] = wrap_body(data["body"], str(data["source"]))
        data["untrusted"] = True
    return json.dumps(data, default=str)


@server.tool()
def read_many(note_ids: str) -> str:
    """Read multiple notes at once. Pass comma-separated IDs.

    Args:
        note_ids: Comma-separated note IDs (e.g. "auth-flow,session-mgmt,jwt-tokens")
    """
    # Delta vs upstream (P1-11 remediation M-5): untrusted import hoisted from
    # inside the per-note loop to handler top.
    from hyperresearch.core.untrusted import is_untrusted, wrap_body

    vault = _get_vault()
    vault.auto_sync()
    ids = [nid.strip() for nid in note_ids.split(",") if nid.strip()]
    # Delta vs upstream: bare lists annotated for strict mypy.
    notes: list[dict[str, Any]] = []
    not_found: list[str] = []
    for nid in ids:
        row = vault.db.execute(
            "SELECT n.*, nc.body FROM notes n JOIN note_content nc ON n.id = nc.note_id WHERE n.id = ?", (nid,)
        ).fetchone()
        if row:
            tag_row = vault.db.execute("SELECT GROUP_CONCAT(tag, ',') as tl FROM tags WHERE note_id = ?", (nid,)).fetchone()
            tags = tag_row["tl"].split(",") if tag_row and tag_row["tl"] else []
            # Delta vs upstream (P1-11): per-note untrusted fencing, same
            # policy as cli/search.py's body-bearing results — see §P1-11.
            note: dict[str, Any] = {
                "id": row["id"], "title": row["title"], "status": row["status"],
                "tags": tags, "word_count": row["word_count"], "summary": row["summary"], "body": row["body"],
            }
            if note["body"] and is_untrusted(row["source"], row["type"]):
                note["body"] = wrap_body(note["body"], str(row["source"]))
                note["untrusted"] = True
            notes.append(note)
        else:
            not_found.append(nid)
    return json.dumps({"notes": notes, "not_found": not_found}, default=str)


@server.tool()
def list_notes(status: str = "", tag: str = "", parent: str = "", sort: str = "updated", limit: int = 50) -> str:
    """List notes with optional filters. Returns summaries (no bodies).

    Args:
        status: Filter by status
        tag: Filter by tag
        parent: Filter by parent topic
        sort: Sort order (created, updated, title, words)
        limit: Max results (default 50, use 0 for all)
    """
    vault = _get_vault()
    vault.auto_sync()
    # Delta vs upstream: bare containers annotated for strict mypy.
    clauses: list[str] = ["n.type NOT IN ('index')"]
    params: list[Any] = []
    if status:
        clauses.append("n.status = ?")
        params.append(status)
    if tag:
        clauses.append("n.id IN (SELECT note_id FROM tags WHERE tag = ?)")
        params.append(tag.lower())
    if parent:
        clauses.append("(n.parent = ? OR n.parent LIKE ?)")
        params.extend([parent, parent + "/%"])
    where = " AND ".join(clauses)
    sort_map = {"created": "n.created DESC", "updated": "COALESCE(n.updated, n.created) DESC",
                "title": "n.title ASC", "words": "n.word_count DESC"}
    order = sort_map.get(sort, "COALESCE(n.updated, n.created) DESC")
    effective_limit = 999999 if limit == 0 else limit
    rows = vault.db.execute(
        f"SELECT n.*, (SELECT GROUP_CONCAT(t.tag, ',') FROM tags t WHERE t.note_id = n.id) as tag_list "
        f"FROM notes n WHERE {where} ORDER BY {order} LIMIT ?", [*params, effective_limit]
    ).fetchall()
    notes = [{"id": r["id"], "title": r["title"], "status": r["status"],
              "tags": r["tag_list"].split(",") if r["tag_list"] else [],
              "word_count": r["word_count"], "summary": r["summary"]} for r in rows]
    return json.dumps(notes, default=str)


@server.tool()
def get_backlinks(note_id: str) -> str:
    """Get all notes that link TO a given note.

    Args:
        note_id: The target note ID
    """
    vault = _get_vault()
    vault.auto_sync()
    rows = vault.db.execute(
        "SELECT l.source_id, n.title, l.line_number, l.context, n.source, n.type "
        "FROM links l JOIN notes n ON l.source_id = n.id WHERE l.target_id = ? ORDER BY n.title",
        (note_id,),
    ).fetchall()
    # Delta vs upstream (P1-11 remediation M-2): a link's context line is
    # verbatim text lifted from the SOURCE note's body (sync.py stores
    # line.strip()[:200]), so a backlink from a web-fetched note smuggles
    # attacker-controlled text into the payload unfenced. Same policy shape
    # as the body tools — wrap + flag per entry (chosen over omitting the
    # snippet: wrapping IS the established policy; nothing is lost).
    from hyperresearch.core.untrusted import is_untrusted, wrap_body

    backlinks: list[dict[str, Any]] = []
    for r in rows:
        entry: dict[str, Any] = {
            "source_id": r["source_id"], "title": r["title"],
            "line": r["line_number"], "context": r["context"],
        }
        if entry["context"] and is_untrusted(r["source"], r["type"]):
            entry["context"] = wrap_body(entry["context"], str(r["source"]))
            entry["untrusted"] = True
        backlinks.append(entry)
    return json.dumps({"note_id": note_id, "backlinks": backlinks, "count": len(backlinks)})


@server.tool()
def get_hubs(limit: int = 20) -> str:
    """Get the most-linked-to notes in the research base (hub notes).

    Args:
        limit: Max results (default 20)
    """
    vault = _get_vault()
    vault.auto_sync()
    rows = vault.db.execute(
        "SELECT l.target_id as id, n.title, COUNT(*) as inbound "
        "FROM links l JOIN notes n ON l.target_id = n.id "
        "WHERE l.target_id IS NOT NULL GROUP BY l.target_id ORDER BY inbound DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return json.dumps([{"id": r["id"], "title": r["title"], "inbound_links": r["inbound"]} for r in rows])


@server.tool()
def vault_status() -> str:
    """Get vault health overview: note counts, tag distribution, link stats, word count."""
    vault = _get_vault()
    vault.auto_sync()
    conn = vault.db
    total = conn.execute("SELECT COUNT(*) as c FROM notes WHERE type NOT IN ('index')").fetchone()["c"]
    by_status = {r["status"]: r["c"] for r in conn.execute(
        "SELECT status, COUNT(*) as c FROM notes WHERE type NOT IN ('index') GROUP BY status")}
    tag_count = conn.execute("SELECT COUNT(DISTINCT tag) as c FROM tags").fetchone()["c"]
    top_tags = [{"tag": r["tag"], "count": r["count"]} for r in conn.execute(
        "SELECT tag, COUNT(*) as count FROM tags GROUP BY tag ORDER BY count DESC LIMIT 10")]
    total_links = conn.execute("SELECT COUNT(*) as c FROM links").fetchone()["c"]
    broken = conn.execute("SELECT COUNT(*) as c FROM links WHERE target_id IS NULL").fetchone()["c"]
    total_words = conn.execute("SELECT COALESCE(SUM(word_count), 0) as c FROM notes").fetchone()["c"]
    return json.dumps({"vault_name": vault.config.name, "total_notes": total, "by_status": by_status,
                        "unique_tags": tag_count, "top_tags": top_tags, "total_links": total_links,
                        "broken_links": broken, "total_words": total_words})


@server.tool()
def lint_vault(rule: str = "") -> str:
    """Run health checks on the vault. Returns issues found.

    Args:
        rule: Specific rule to check (leave empty for all)
    """
    vault = _get_vault()
    vault.auto_sync()
    conn = vault.db
    # Delta vs upstream: `list[dict]` → `list[dict[str, Any]]` for strict mypy.
    issues: list[dict[str, Any]] = []
    rules = [rule] if rule else ["missing-tags", "missing-summary", "broken-links", "orphaned-notes"]
    if "missing-tags" in rules:
        for r in conn.execute("SELECT id FROM notes WHERE type NOT IN ('index','raw') AND id NOT IN (SELECT DISTINCT note_id FROM tags)"):
            issues.append({"rule": "missing-tags", "severity": "warning", "note_id": r["id"], "message": "No tags"})
    if "missing-summary" in rules:
        for r in conn.execute("SELECT id FROM notes WHERE type NOT IN ('index','raw') AND (summary IS NULL OR LENGTH(TRIM(COALESCE(summary, ''))) = 0)"):
            issues.append({"rule": "missing-summary", "severity": "warning", "note_id": r["id"], "message": "No summary"})
    if "broken-links" in rules:
        for r in conn.execute("SELECT source_id, target_ref FROM links WHERE target_id IS NULL"):
            issues.append({"rule": "broken-links", "severity": "warning", "note_id": r["source_id"], "message": f"Broken: [[{r['target_ref']}]]"})
    if "orphaned-notes" in rules:
        for r in conn.execute("SELECT id FROM notes WHERE type NOT IN ('index','raw') AND id NOT IN (SELECT DISTINCT target_id FROM links WHERE target_id IS NOT NULL) AND id NOT IN (SELECT DISTINCT source_id FROM links)"):
            issues.append({"rule": "orphaned-notes", "severity": "info", "note_id": r["id"], "message": "No links"})
    return json.dumps({"issues": issues, "total": len(issues), "warnings": sum(1 for i in issues if i["severity"] == "warning")})


@server.tool()
def check_source(url: str) -> str:
    """Check if a URL has already been fetched into the research base.

    Args:
        url: The URL to check
    """
    vault = _get_vault()
    row = vault.db.execute(
        "SELECT url, note_id, domain, fetched_at, provider FROM sources WHERE url = ?",
        (url,),
    ).fetchone()
    if row:
        return json.dumps({"exists": True, **dict(row)})
    return json.dumps({"exists": False, "url": url})


@server.tool()
def list_sources(domain: str = "", limit: int = 50) -> str:
    """List fetched web sources, optionally filtered by domain.

    Args:
        domain: Filter by domain (e.g. "arxiv.org"). Leave empty for all.
        limit: Max results (default 50)
    """
    vault = _get_vault()
    if domain:
        rows = vault.db.execute(
            "SELECT url, note_id, domain, fetched_at, provider, status "
            "FROM sources WHERE domain = ? ORDER BY fetched_at DESC LIMIT ?",
            (domain, limit),
        ).fetchall()
    else:
        rows = vault.db.execute(
            "SELECT url, note_id, domain, fetched_at, provider, status "
            "FROM sources ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return json.dumps([dict(r) for r in rows])


@server.tool()
def fetch_url(url: str, tags: str = "", provider: str = "") -> str:
    """Fetch a URL and save it as a research note.

    Args:
        url: The URL to fetch
        tags: Comma-separated tags (e.g. "ml,transformers")
        provider: Web provider override (leave empty for default)
    """
    from hyperresearch.core.fetcher import fetch_and_save

    vault = _get_vault()
    vault.auto_sync()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    try:
        result = fetch_and_save(
            vault, url, tags=tag_list,
            provider_name=provider or None,
        )
        return json.dumps({"ok": True, "data": result})
    except ValueError as e:
        return json.dumps({"ok": False, "error": str(e), "error_code": "DUPLICATE_URL"})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e), "error_code": "FETCH_ERROR"})


@server.tool()
def create_note(title: str, body: str, tags: str = "", source: str = "", summary: str = "") -> str:
    """Create a new research note.

    Args:
        title: Note title
        body: Note body content (markdown)
        tags: Comma-separated tags
        source: Source URL (if from the web)
        summary: One-line summary (auto-generated if empty)
    """
    from hyperresearch.core.enrich import enrich_note_file
    from hyperresearch.core.note import write_note
    from hyperresearch.core.sync import compute_sync_plan, execute_sync

    vault = _get_vault()
    vault.auto_sync()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Delta vs upstream: bare dict annotated for strict mypy.
    extra: dict[str, str] = {}
    if source:
        extra["source"] = source

    note_path = write_note(
        vault.notes_dir,
        title=title,
        body=body,
        tags=tag_list,
        status="draft",
        source=source or None,
        summary=summary or None,
        extra_frontmatter=extra if extra else None,
    )

    enrich_note_file(note_path, vault.db, tag_list)

    plan = compute_sync_plan(vault)
    if plan.to_add or plan.to_update:
        execute_sync(vault, plan)

    note_id = note_path.stem
    return json.dumps({"ok": True, "data": {
        "note_id": note_id,
        "title": title,
        "path": str(note_path.relative_to(vault.root)),
    }})


@server.tool()
def update_note(note_id: str, status: str = "", add_tags: str = "", remove_tags: str = "", summary: str = "") -> str:
    """Update a note's metadata.

    Args:
        note_id: The note ID to update
        status: New status (draft/review/evergreen/stale/deprecated/archive)
        add_tags: Comma-separated tags to add
        remove_tags: Comma-separated tags to remove
        summary: New summary text
    """
    from hyperresearch.core.frontmatter import parse_frontmatter, serialize_frontmatter
    from hyperresearch.core.sync import compute_sync_plan, execute_sync
    from hyperresearch.models.note import NoteStatus

    # Delta vs upstream (P1-11 remediation M-3): NoteMeta has use_enum_values
    # but no validate_assignment, so any caller-supplied status string stuck
    # in frontmatter verbatim — poisoning status filters downstream, and
    # tripping the notes-table CHECK (core/db.py) as an unhandled
    # IntegrityError at sync time. Validate against the exact enumerated set
    # that CHECK enforces (== NoteStatus), before touching the vault at all;
    # invalid input never reaches discovery/auto-sync.
    valid_statuses = {s.value for s in NoteStatus}
    if status and status not in valid_statuses:
        return json.dumps({
            "ok": False,
            "error": (
                f"Invalid status: {status!r} "
                f"(must be one of: {', '.join(sorted(valid_statuses))})"
            ),
            "error_code": "INVALID_STATUS",
        })

    vault = _get_vault()
    vault.auto_sync()

    row = vault.db.execute("SELECT path FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not row:
        return json.dumps({"ok": False, "error": f"Note not found: {note_id}", "error_code": "NOT_FOUND"})

    file_path = vault.root / row["path"]
    # Delta vs upstream (P1-11 remediation M-4): mirror cli/note.py mv's
    # containment recheck (P1-9 hardening H-5). notes.path is derived cache;
    # a drifted row must not steer a write outside the vault root. Resolve
    # and confine BEFORE any file access.
    if not file_path.resolve().is_relative_to(vault.root):
        return json.dumps({
            "ok": False,
            "error": f"Note path escapes the vault: {row['path']}",
            "error_code": "INVALID_PATH",
        })
    content = file_path.read_text(encoding="utf-8-sig")
    meta, body = parse_frontmatter(content)

    changed: list[str] = []
    if status:
        # Delta vs upstream: `# type: ignore[assignment]` — NoteMeta runs
        # use_enum_values=True so the runtime value IS the raw string; the
        # StrEnum annotation is what mypy objects to (P1-9 precedent).
        meta.status = status  # type: ignore[assignment]
        changed.append(f"status={status}")
    for t in [t.strip() for t in add_tags.split(",") if t.strip()]:
        if t.lower() not in meta.tags:
            meta.tags.append(t.lower())
            changed.append(f"+tag:{t}")
    for t in [t.strip() for t in remove_tags.split(",") if t.strip()]:
        if t.lower() in meta.tags:
            meta.tags.remove(t.lower())
            changed.append(f"-tag:{t}")
    if summary:
        meta.summary = summary
        changed.append("summary")

    if not changed:
        return json.dumps({"ok": True, "data": {"note_id": note_id, "changes": []}})

    file_path.write_text(serialize_frontmatter(meta) + "\n" + body, encoding="utf-8")

    plan = compute_sync_plan(vault)
    if plan.to_add or plan.to_update:
        execute_sync(vault, plan)

    return json.dumps({"ok": True, "data": {"note_id": note_id, "changes": changed}})
