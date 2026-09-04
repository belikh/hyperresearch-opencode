"""Note CRUD CLI commands."""

from __future__ import annotations

from datetime import UTC
from typing import Any

import typer

from hyperresearch.cli._output import console, output, print_note_summary
from hyperresearch.models.output import error, success

app = typer.Typer()


@app.command("new")
def note_new(
    title: str = typer.Argument(..., help="Note title"),
    body_text: str | None = typer.Option(None, "--body", "-b", help="Note body content (markdown)"),
    body_file: str | None = typer.Option(None, "--body-file", "-B", help="Read body from file path"),
    body_stdin: bool = typer.Option(False, "--body-stdin", help="Read body from stdin"),
    tags: list[str] = typer.Option([], "--tag", "-t", help="Tags"),
    parent: str | None = typer.Option(None, "--parent", "-p", help="Parent topic"),
    note_type: str = typer.Option("note", "--type", help="Note type"),
    status: str = typer.Option("draft", "--status", "-s", help="Initial status"),
    summary: str | None = typer.Option(None, "--summary", help="One-line summary"),
    source: str | None = typer.Option(None, "--source", help="Source URL or path"),
    tier: str | None = typer.Option(None, "--tier", help="Epistemic tier: ground_truth|institutional|practitioner|commentary|unknown"),
    content_type: str | None = typer.Option(None, "--content-type", help="Artifact kind: paper|docs|article|blog|forum|dataset|policy|code|book|transcript|review|unknown"),
    template: str | None = typer.Option(None, "--template", "-T", help="Template: note|concept|reference|guide|comparison|moc"),
    edit: bool = typer.Option(False, "--edit", "-e", help="Open in $EDITOR"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Create a new note.

    Body content: use --body for short text, --body-file for longer content
    (avoids shell escaping), or --body-stdin to pipe it in.
    """
    import sys
    from pathlib import Path as P

    from hyperresearch.core.note import write_note
    from hyperresearch.core.vault import Vault
    from hyperresearch.models.note import ContentType, Tier, slugify

    # Validate enums up-front so invalid values fail clearly
    if tier is not None:
        try:
            Tier(tier)
        except ValueError:
            valid = ", ".join(t.value for t in Tier)
            if json_output:
                output(error(f"Invalid --tier '{tier}'. Must be one of: {valid}", "INVALID_TIER"), json_mode=True)
            else:
                console.print(f"[red]Invalid --tier '{tier}'.[/] Must be one of: {valid}")
            raise typer.Exit(1)
    if content_type is not None:
        try:
            ContentType(content_type)
        except ValueError:
            valid = ", ".join(c.value for c in ContentType)
            if json_output:
                output(error(f"Invalid --content-type '{content_type}'. Must be one of: {valid}", "INVALID_CONTENT_TYPE"), json_mode=True)
            else:
                console.print(f"[red]Invalid --content-type '{content_type}'.[/] Must be one of: {valid}")
            raise typer.Exit(1)

    vault = Vault.discover()
    vault.auto_sync()

    # Determine body content
    if body_file:
        body = P(body_file).read_text(encoding="utf-8")
    elif body_stdin:
        body = sys.stdin.read()
    elif body_text:
        body = body_text
    else:
        body = f"# {title}\n\n"

    nid = slugify(title)

    # Check for duplicate before creating
    similar = vault.db.execute(
        "SELECT id, title FROM notes WHERE id = ? OR LOWER(title) = LOWER(?)",
        (nid, title),
    ).fetchall()
    if similar:
        existing = [{"id": r["id"], "title": r["title"]} for r in similar]
        if json_output:
            # Warn but still create — agent can decide
            pass  # Will include warning in response below
        else:
            for s in existing:
                console.print(f"[yellow]Similar note exists:[/] {s['id']} — {s['title']}")

    # Use template if specified
    if template:
        from hyperresearch.core.templates import get_template, render_template

        tpl = get_template(template, vault.templates_dir)
        if tpl:
            rendered = render_template(tpl, title, nid, tags)
            target_dir = vault.notes_dir
            if parent:
                target_dir = target_dir / slugify(parent)
            target_dir.mkdir(parents=True, exist_ok=True)
            file_path = target_dir / f"{nid}.md"
            counter = 2
            while file_path.exists():
                file_path = target_dir / f"{nid}-{counter}.md"
                nid = f"{nid}-{counter}"
                counter += 1
            file_path.write_text(rendered, encoding="utf-8")
            path = file_path
        else:
            console.print(f"[yellow]Template '{template}' not found, using default.[/]")
            path = write_note(vault.notes_dir, title, body=body, tags=tags, status=status,
                              note_type=note_type, parent=parent, summary=summary,
                              source=source, tier=tier, content_type=content_type)
    else:
        path = write_note(vault.notes_dir, title, body=body, tags=tags, status=status,
                          note_type=note_type, parent=parent, summary=summary,
                          source=source, tier=tier, content_type=content_type)

    # Sync the new file into the DB so type/tags are indexed immediately
    from hyperresearch.core.sync import compute_sync_plan, execute_sync
    plan = compute_sync_plan(vault)
    execute_sync(vault, plan)

    # Read back the note ID (may have been collision-adjusted)
    from hyperresearch.core.note import read_note
    note = read_note(path, vault.root)
    nid = note.meta.id

    rel = path.relative_to(vault.root).as_posix()

    if json_output:
        # Delta vs upstream: annotated for mypy --strict (heterogeneous dict).
        data: dict[str, Any] = {"id": nid, "path": rel, "title": title}
        if similar:
            data["warning"] = f"Similar note already exists: {similar[0]['id']}"
            data["similar"] = [{"id": r["id"], "title": r["title"]} for r in similar]
        top_tags = vault.db.execute(
            "SELECT tag, COUNT(*) as c FROM tags GROUP BY tag ORDER BY c DESC LIMIT 30"
        ).fetchall()
        if top_tags:
            data["existing_tags"] = [r["tag"] for r in top_tags]
        output(success(data, vault=str(vault.root)), json_mode=True)
    else:
        console.print(f"[green]Created:[/] {rel}")

    if edit:
        import os
        import subprocess

        editor = os.environ.get("EDITOR", "vim")
        subprocess.run([editor, str(path)])


@app.command("show")
def note_show(
    note_ids: list[str] = typer.Argument(..., help="Note ID(s) — pass multiple to read several at once"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show raw markdown"),
    meta: bool = typer.Option(False, "--meta", "-m", help="Show only frontmatter"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Display one or more notes. Pass multiple IDs for batch read."""
    from hyperresearch.core.vault import Vault

    vault = Vault.discover()
    vault.auto_sync()

    def _fetch_note(nid: str) -> dict[str, Any] | None:  # Delta vs upstream: bare `dict` parameterized for mypy --strict
        row = vault.db.execute(
            "SELECT n.*, nc.body FROM notes n JOIN note_content nc ON n.id = nc.note_id WHERE n.id = ?",
            (nid,),
        ).fetchone()
        if not row:
            return None
        tag_list = vault.db.execute(
            "SELECT GROUP_CONCAT(tag, ',') as tl FROM tags WHERE note_id = ?", (nid,)
        ).fetchone()
        tags = tag_list["tl"].split(",") if tag_list and tag_list["tl"] else []
        data = {
            "id": row["id"], "title": row["title"], "path": row["path"],
            "status": row["status"], "type": row["type"], "tags": tags,
            # sqlite3.Row.__contains__ is broken (returns False even for present keys),
            # so use row.keys() explicitly. SIM118 + SIM401 are noqa'd accordingly.
            "tier": row["tier"] if "tier" in row.keys() else None,  # noqa: SIM118
            "content_type": row["content_type"] if "content_type" in row.keys() else None,  # noqa: SIM118
            "created": row["created"], "updated": row["updated"],
            "word_count": row["word_count"], "source": row["source"],
            "parent": row["parent"], "summary": row["summary"],
        }
        # Open-access substitution. Surfaced structurally, not just as the
        # banner in the body, so a reader checking a quotation can tell it is
        # looking at a preprint without having to parse prose. `source` above
        # is still the URL that was requested; `oa_url` is where the body came
        # from. See core/oa.py.
        if "oa_url" in row.keys() and row["oa_url"]:  # noqa: SIM118
            kind = (
                row["oa_recovery_kind"]
                if "oa_recovery_kind" in row.keys()  # noqa: SIM118
                else None
            )
            data["oa"] = {
                "url": row["oa_url"],
                "resolver": row["oa_source"],
                "version": row["oa_version"],
                "license": row["oa_license"],
                "body_is_not_from_source": True,
                # "rescued" is the stronger claim: the source URL was never
                # read, so the title and authors are the open-access copy's
                # too. "substituted" means only the body was replaced.
                "kind": kind,
                "nothing_from_source": kind == "rescued",
            }
        if not meta:
            body = row["body"]
            from hyperresearch.core.untrusted import is_untrusted, wrap_body
            if is_untrusted(data.get("source"), data.get("type")):
                data["body"] = wrap_body(body, data["source"])
                data["untrusted"] = True
            else:
                data["body"] = body
        return data

    # --raw prints the on-disk markdown verbatim (frontmatter included),
    # works for any number of ids, and short-circuits everything else.
    if raw:
        for note_id in note_ids:
            row = vault.db.execute("SELECT path FROM notes WHERE id = ?", (note_id,)).fetchone()
            if not row:
                console.print(f"[red]Note not found:[/] {note_id}")
                raise typer.Exit(1)
            console.print((vault.root / row["path"]).read_text(encoding="utf-8"))
        return

    # Uniform envelope for ANY number of ids (transcript audit F1a): the
    # historical single-note arm returned the bare note dict while the
    # multi arm returned {notes, not_found} — agents guessed the wrong
    # shape 74 times (KeyError: 'notes'). One shape, always.
    notes: list[dict[str, Any]] = []  # Delta vs upstream: empty containers annotated for mypy --strict
    not_found: list[str] = []
    for nid in note_ids:
        data = _fetch_note(nid)
        if data:
            notes.append(data)
        else:
            not_found.append(nid)

    if not notes:
        # Every requested id missed — almost certainly an id typo. Fail
        # loudly (the historical single-note behaviour) instead of a
        # silent ok:true empty batch.
        if json_output:
            output(error(f"Note(s) not found: {', '.join(not_found)}", "NOT_FOUND"), json_mode=True)
        else:
            console.print(f"[red]Note(s) not found:[/] {', '.join(not_found)}")
        raise typer.Exit(1)

    if json_output:
        result = {"notes": notes, "not_found": not_found}
        output(success(result, count=len(notes), vault=str(vault.root)), json_mode=True)
    else:
        for data in notes:
            tags = data.get("tags", [])
            console.print(f"\n[bold]{data['title']}[/]  [dim]({data['id']})[/]")
            console.print(f"[dim]Status: {data['status']} | Tags: {', '.join(tags)}[/]")
            if not meta:
                console.print()
                from rich.markdown import Markdown
                console.print(Markdown(data.get("body", "")))
        if not_found:
            console.print(f"\n[red]Not found:[/] {', '.join(not_found)}")


_FENCE_OPEN_RE: Any = None  # compiled lazily; see note_read --plain


def _strip_untrusted_fence(body: str) -> str:
    """Remove the <untrusted-source> wrapper added by core.untrusted.wrap_body.

    --plain on `note read` exists for windowed reading, where a fence that
    opens in one window and closes 40k chars later in another is noise.
    The NOTE TO READER preamble inside the fence goes with it. This is a
    rendering concern only — the on-disk note and every other command
    keep the fence; the reader is expected to remember fetched bodies are
    data, not instructions.
    """
    global _FENCE_OPEN_RE
    import re as _re

    if _FENCE_OPEN_RE is None:
        _FENCE_OPEN_RE = _re.compile(r'^<untrusted-source url="[^"\n]*">\n')
    text = _FENCE_OPEN_RE.sub("", body)
    if text.rstrip("\n").endswith("</untrusted-source>"):
        head, sep, tail = text.rstrip("\n").rpartition("</untrusted-source>")
        text = head if sep else tail
    # Drop the NOTE TO READER preamble block when it leads the body.
    if text.startswith("[NOTE TO READER:"):
        text = text.split("]\n", 1)[-1] if "]\n" in text[:600] else text
    stripped: str = text.lstrip("\n")
    return stripped


def _parse_window(spec: str) -> tuple[int | None, int | None]:
    """Parse 'A:B' / 'A:' / ':B' / 'B' (to end) window specs."""
    parts = spec.split(":", 1)
    try:
        start = int(parts[0]) if parts[0].strip() else None
        end = int(parts[1]) if len(parts) > 1 and parts[1].strip() else None
    except ValueError as e:
        raise typer.BadParameter(
            f"window must look like START:END (either side optional), got {spec!r}"
        ) from e
    if start is not None and start < 0:
        raise typer.BadParameter("window start must be >= 0")
    if end is not None and start is not None and end <= start:
        raise typer.BadParameter("window end must be > start")
    return start, end


@app.command("read")
def note_read(
    note_ids: list[str] = typer.Argument(..., help="Note ID(s) — batch reads are per-note capped so output never blows the tool limit"),
    chars: str | None = typer.Option(None, "--chars", help="Character window into the body, e.g. 8000:16000 (open ends allowed: 8000: or :3000)"),
    lines: str | None = typer.Option(None, "--lines", help="Line window into the body, e.g. 40:120"),
    plain: bool = typer.Option(False, "--plain", help="Strip the <untrusted-source> fence and NOTE TO READER preamble before windowing"),
    meta_line: bool = typer.Option(False, "--meta-line", help="Prefix each note with '# id | tier | N words | tags' before the body"),
    max_chars: int = typer.Option(8000, "--max-chars", help="Per-note body cap when no explicit --chars window (0 = unlimited)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output (window text + continue offsets instead of raw body)"),
) -> None:
    """Read note BODIES as plain text — the agent-first reader.

    Transcript audit R2: 818 hand-rolled `python3 -c "print(n['body'][13000:21000])"`
    window reads plus 1,827 /tmp staging calls existed only because
    `note show -j` dumps full bodies as JSON that overruns tool output
    limits. `note read` prints bodies as text, caps each note at
    --max-chars, and tells you the exact --chars window to continue with.

    The untrusted-source fence is PRESERVED by default (fetched bodies are
    data, not instructions). Use --plain to strip it for windowed reading.
    """
    import sys

    from hyperresearch.core.vault import Vault

    if chars and lines:
        raise typer.BadParameter("--chars and --lines are mutually exclusive")

    vault = Vault.discover()
    vault.auto_sync()

    c_start, c_end = _parse_window(chars) if chars else (None, None)
    l_start, l_end = _parse_window(lines) if lines else (None, None)

    out_lines: list[str] = []
    json_notes: list[dict[str, Any]] = []
    not_found: list[str] = []

    for nid in note_ids:
        row = vault.db.execute(
            "SELECT n.id, n.tier, n.word_count, n.source, n.type, nc.body "
            "FROM notes n JOIN note_content nc ON n.id = nc.note_id WHERE n.id = ?",
            (nid,),
        ).fetchone()
        if not row:
            not_found.append(nid)
            continue

        body = row["body"] or ""
        if plain:
            from hyperresearch.core.untrusted import is_untrusted

            if is_untrusted(row["source"], row["type"]):
                body = _strip_untrusted_fence(body)

        total = len(body)
        if lines:
            body_lines = body.split("\n")
            lo = l_start or 0
            hi = l_end if l_end is not None else len(body_lines)
            window = "\n".join(body_lines[lo:hi])
            shown = len(window)
            continue_hint = f"--lines {hi}:{hi + (hi - lo)}" if hi < len(body_lines) else None
        else:
            lo = c_start or 0
            if c_end is not None:
                hi = c_end
            elif chars or max_chars <= 0:  # explicit open-ended "A:" — to the end
                hi = total
            else:
                hi = min(total, max_chars)
            window = body[lo:hi]
            shown = len(window)
            continue_hint = f"--chars {lo + shown}:{lo + shown + max(4000, shown)}" if lo + shown < total else None

        if json_output:
            entry: dict[str, Any] = {
                "id": nid,
                "total_chars": total,
                "window": [lo, lo + shown],
                "body": window,
            }
            if continue_hint:
                entry["continue_with"] = continue_hint
            json_notes.append(entry)
        else:
            if meta_line:
                tier = row["tier"] if "tier" in row.keys() else None  # noqa: SIM118
                out_lines.append(f"# {nid} | {tier or '-'} | {row['word_count'] or 0} words")
            out_lines.append(window)
            if continue_hint:
                out_lines.append(f"…[note {nid}: {lo + shown:,} of {total:,} chars shown — continue with {continue_hint}]")
            out_lines.append("")

    if json_output:
        output(
            success({"notes": json_notes, "not_found": not_found}, count=len(json_notes), vault=str(vault.root)),
            json_mode=True,
        )
    else:
        sys.stdout.write("\n".join(out_lines).rstrip("\n") + "\n")

    if not_found:
        if not json_output:
            console.print(f"[red]Not found:[/] {', '.join(not_found)}", style="red")
        if not json_notes:
            raise typer.Exit(1)


@app.command("list")
def note_list(
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status"),
    note_type: str | None = typer.Option(None, "--type", help="Filter by type"),
    tag: list[str] = typer.Option([], "--tag", "-t", help="Filter by tag (repeatable, AND logic)"),
    parent: str | None = typer.Option(None, "--parent", "-p", help="Filter by parent"),
    tier: str | None = typer.Option(None, "--tier", help="Filter by epistemic tier: ground_truth|institutional|practitioner|commentary|unknown"),
    content_type: str | None = typer.Option(None, "--content-type", help="Filter by artifact kind: paper|docs|article|blog|forum|dataset|policy|code|book|transcript|review|unknown"),
    sort: str = typer.Option("updated", "--sort", help="Sort: created|updated|title|words"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results"),
    all_notes: bool = typer.Option(False, "--all", "-a", help="Return all notes (no limit)"),
    fields: str | None = typer.Option(None, "--fields", help="Comma-separated projection, e.g. id,word_count,tier (JSON mode)"),
    fmt: str = typer.Option("text", "--format", help="text|tsv — tsv prints a header + tab-separated rows (works with --fields)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """List notes with optional filters."""
    from hyperresearch.core.vault import Vault
    from hyperresearch.models.note import ContentType, Tier

    # Validate enums up-front
    if tier is not None:
        try:
            Tier(tier)
        except ValueError:
            valid = ", ".join(t.value for t in Tier)
            if json_output:
                output(error(f"Invalid --tier '{tier}'. Must be one of: {valid}", "INVALID_TIER"), json_mode=True)
            else:
                console.print(f"[red]Invalid --tier '{tier}'.[/] Must be one of: {valid}")
            raise typer.Exit(1)
    if content_type is not None:
        try:
            ContentType(content_type)
        except ValueError:
            valid = ", ".join(c.value for c in ContentType)
            if json_output:
                output(error(f"Invalid --content-type '{content_type}'. Must be one of: {valid}", "INVALID_CONTENT_TYPE"), json_mode=True)
            else:
                console.print(f"[red]Invalid --content-type '{content_type}'.[/] Must be one of: {valid}")
            raise typer.Exit(1)

    vault = Vault.discover()
    vault.auto_sync()

    # Delta vs upstream: empty containers annotated for mypy --strict.
    clauses: list[str] = []
    params: list[Any] = []

    if status:
        clauses.append("n.status = ?")
        params.append(status)
    if note_type:
        clauses.append("n.type = ?")
        params.append(note_type)
    if parent:
        clauses.append("n.parent = ?")
        params.append(parent)
    for t in tag:
        clauses.append("n.id IN (SELECT note_id FROM tags WHERE tag = ?)")
        params.append(t.lower())
    if tier:
        clauses.append("n.tier = ?")
        params.append(tier)
    if content_type:
        clauses.append("n.content_type = ?")
        params.append(content_type)

    where = " AND ".join(clauses) if clauses else "1=1"

    sort_map = {
        "created": "n.created DESC",
        "updated": "COALESCE(n.updated, n.created) DESC",
        "title": "n.title ASC",
        "words": "n.word_count DESC",
    }
    order = sort_map.get(sort, "COALESCE(n.updated, n.created) DESC")

    effective_limit = 999999 if all_notes else limit
    rows = vault.db.execute(
        f"""SELECT n.*,
            (SELECT GROUP_CONCAT(t.tag, ',') FROM tags t WHERE t.note_id = n.id) as tag_list
        FROM notes n WHERE {where} ORDER BY {order} LIMIT ?""",
        [*params, effective_limit],
    ).fetchall()

    notes: list[dict[str, Any]] = []  # Delta vs upstream: annotated for mypy --strict
    for row in rows:
        tag_list = row["tag_list"].split(",") if row["tag_list"] else []
        notes.append({
            "id": row["id"],
            "title": row["title"],
            "path": row["path"],
            "status": row["status"],
            "type": row["type"],
            # sqlite3.Row.__contains__ is broken; row.keys() is reliable.
            "tier": row["tier"] if "tier" in row.keys() else None,  # noqa: SIM118
            "content_type": row["content_type"] if "content_type" in row.keys() else None,  # noqa: SIM118
            "tags": tag_list,
            "word_count": row["word_count"],
            "summary": row["summary"],
            "created": row["created"],
            "updated": row["updated"],
        })

    if fields:
        from hyperresearch.cli._output import project_fields

        field_list = [f.strip() for f in fields.split(",") if f.strip()]
        try:
            notes = project_fields(notes, field_list)
        except ValueError as e:
            if json_output:
                output(error(str(e), "INVALID_FIELDS"), json_mode=True)
            else:
                console.print(f"[red]Error:[/] {e}")
            raise typer.Exit(1)

    if fmt == "tsv":
        from hyperresearch.cli._output import render_tsv

        tsv_fields = [f.strip() for f in (fields or "id,title,status,word_count").split(",") if f.strip()]
        import sys as _sys
        _sys.stdout.write(render_tsv(notes, tsv_fields) + "\n")
        return

    if json_output:
        output(
            success(notes, count=len(notes), vault=str(vault.root)),
            json_mode=True,
        )
    else:
        print_note_summary(notes)


@app.command("edit")
def note_edit(
    note_id: str = typer.Argument(..., help="Note ID to edit"),
) -> None:
    """Open a note in $EDITOR."""
    import os
    import subprocess

    from hyperresearch.core.vault import Vault

    vault = Vault.discover()
    vault.auto_sync()

    row = vault.db.execute("SELECT path FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not row:
        console.print(f"[red]Not found:[/] {note_id}")
        raise typer.Exit(1)

    file_path = vault.root / row["path"]
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "notepad" if os.name == "nt" else "vim"))
    subprocess.run([editor, str(file_path)])


@app.command("update")
def note_update(
    note_id: str = typer.Argument(..., help="Note ID"),
    set_status: str | None = typer.Option(None, "--status", "-s", help="Set status"),
    add_tag: list[str] = typer.Option([], "--add-tag", help="Add tag(s)"),
    remove_tag: list[str] = typer.Option([], "--remove-tag", help="Remove tag(s)"),
    set_summary: str | None = typer.Option(None, "--summary", help="Set summary"),
    set_parent: str | None = typer.Option(None, "--parent", "-p", help="Set parent topic"),
    set_source: str | None = typer.Option(None, "--source", help="Set source URL/path"),
    set_tier: str | None = typer.Option(None, "--tier", help="Set epistemic tier: ground_truth|institutional|practitioner|commentary|unknown"),
    set_content_type: str | None = typer.Option(None, "--content-type", help="Set artifact kind: paper|docs|article|blog|forum|dataset|policy|code|book|transcript|review|unknown"),
    deprecate: bool = typer.Option(False, "--deprecate", help="Mark as deprecated"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Update frontmatter fields on a single note."""
    from datetime import datetime

    from hyperresearch.core.frontmatter import parse_frontmatter, serialize_frontmatter
    from hyperresearch.core.sync import compute_sync_plan, execute_sync
    from hyperresearch.core.vault import Vault
    from hyperresearch.models.note import ContentType, Tier

    # Validate enums up-front
    if set_tier is not None:
        try:
            Tier(set_tier)
        except ValueError:
            valid = ", ".join(t.value for t in Tier)
            if json_output:
                output(error(f"Invalid --tier '{set_tier}'. Must be one of: {valid}", "INVALID_TIER"), json_mode=True)
            else:
                console.print(f"[red]Invalid --tier '{set_tier}'.[/] Must be one of: {valid}")
            raise typer.Exit(1)
    if set_content_type is not None:
        try:
            ContentType(set_content_type)
        except ValueError:
            valid = ", ".join(c.value for c in ContentType)
            if json_output:
                output(error(f"Invalid --content-type '{set_content_type}'. Must be one of: {valid}", "INVALID_CONTENT_TYPE"), json_mode=True)
            else:
                console.print(f"[red]Invalid --content-type '{set_content_type}'.[/] Must be one of: {valid}")
            raise typer.Exit(1)

    vault = Vault.discover()
    vault.auto_sync()

    row = vault.db.execute("SELECT path FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not row:
        if json_output:
            output(error(f"Note not found: {note_id}", "NOT_FOUND"), json_mode=True)
        else:
            console.print(f"[red]Not found:[/] {note_id}")
        raise typer.Exit(1)

    file_path = vault.root / row["path"]
    content = file_path.read_text(encoding="utf-8-sig")
    meta, body = parse_frontmatter(content)

    changed: list[str] = []  # Delta vs upstream: annotated for mypy --strict
    # Delta vs upstream (typing only): NoteMeta declares `status`/`tier`/
    # `content_type` as StrEnum-typed fields, but the model runs with
    # use_enum_values=True so the runtime representation is the raw string —
    # exactly what upstream assigns here. The ignores keep that behavior
    # byte-identical under strict mypy.
    if set_status:
        meta.status = set_status  # type: ignore[assignment]
        changed.append(f"status={set_status}")
    for t in add_tag:
        if t.lower() not in meta.tags:
            meta.tags.append(t.lower())
            changed.append(f"+tag:{t}")
    for t in remove_tag:
        if t.lower() in meta.tags:
            meta.tags.remove(t.lower())
            changed.append(f"-tag:{t}")
    if set_summary is not None:
        meta.summary = set_summary
        changed.append("summary")
    if set_parent is not None:
        meta.parent = set_parent
        changed.append(f"parent={set_parent}")
    if set_source is not None:
        meta.source = set_source
        changed.append("source")
    if set_tier is not None:
        meta.tier = set_tier  # type: ignore[assignment]
        changed.append(f"tier={set_tier}")
    if set_content_type is not None:
        meta.content_type = set_content_type  # type: ignore[assignment]
        changed.append(f"content_type={set_content_type}")
    if deprecate:
        meta.deprecated = True
        meta.status = "deprecated"  # type: ignore[assignment]
        changed.append("deprecated")

    if not changed:
        if json_output:
            output(success({"id": note_id, "changed": []}, vault=str(vault.root)), json_mode=True)
        else:
            console.print("[dim]Nothing to update.[/]")
        return

    meta.updated = datetime.now(UTC)
    new_content = serialize_frontmatter(meta) + "\n" + body
    file_path.write_text(new_content, encoding="utf-8")

    plan = compute_sync_plan(vault)
    execute_sync(vault, plan)

    if json_output:
        output(success({"id": note_id, "changed": changed}, vault=str(vault.root)), json_mode=True)
    else:
        console.print(f"[green]Updated {note_id}:[/] {', '.join(changed)}")


@app.command("mv")
def note_mv(
    note_id: str = typer.Argument(..., help="Note ID to move"),
    new_path: str = typer.Argument(..., help="New relative path (e.g. notes/python/renamed.md)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Move/rename a note, updating all references."""
    from hyperresearch.core.sync import compute_sync_plan, execute_sync
    from hyperresearch.core.vault import Vault

    vault = Vault.discover()
    vault.auto_sync()

    row = vault.db.execute("SELECT path FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not row:
        if json_output:
            output(error(f"Note not found: {note_id}", "NOT_FOUND"), json_mode=True)
        else:
            console.print(f"[red]Not found:[/] {note_id}")
        raise typer.Exit(1)

    old_file = vault.root / row["path"]
    new_file = vault.root / new_path

    # Delta vs upstream (P1-9 hardening H-5): upstream joined new_path raw,
    # so an absolute path replaced the vault root outright and '..' segments
    # walked out of the vault; POSIX rename also silently OVERWROTE an
    # existing destination file. Confine destinations to the vault and
    # surface collisions through the structured error envelope.
    if not new_file.resolve().is_relative_to(vault.root):
        if json_output:
            output(error(f"Destination must stay inside the vault: {new_path}", "INVALID_PATH"), json_mode=True)
        else:
            console.print(f"[red]Invalid destination:[/] {new_path}")
        raise typer.Exit(1)
    if new_file.exists():
        if json_output:
            output(error(f"Destination already exists: {new_path}", "DEST_EXISTS"), json_mode=True)
        else:
            console.print(f"[red]Destination already exists:[/] {new_path}")
        raise typer.Exit(1)

    new_file.parent.mkdir(parents=True, exist_ok=True)
    old_file.rename(new_file)

    # Re-sync
    plan = compute_sync_plan(vault, force=True)
    execute_sync(vault, plan)

    if json_output:
        output(success({"old_path": row["path"], "new_path": new_path}, vault=str(vault.root)), json_mode=True)
    else:
        console.print(f"[green]Moved:[/] {row['path']} → {new_path}")


@app.command("rm")
def note_rm(
    note_id: str = typer.Argument(..., help="Note ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Delete a note and its associated raw file and assets.

    Previous versions only unlinked the `.md` file, leaving raw PDFs under
    `research/raw/` and assets under `research/assets/<id>/` as orphans.
    Every fetch-then-delete cycle leaked disk. The current implementation
    also removes:
      - the raw file referenced in the note's `raw_file` frontmatter field
      - any entries in the `assets` table and their files on disk
    """
    import shutil

    from hyperresearch.core.vault import Vault

    vault = Vault.discover()
    row = vault.db.execute(
        "SELECT path FROM notes WHERE id = ?", (note_id,)
    ).fetchone()
    if not row:
        if json_output:
            output(error(f"Note not found: {note_id}", "NOT_FOUND"), json_mode=True)
        else:
            console.print(f"[red]Not found:[/] {note_id}")
        raise typer.Exit(1)

    file_path = vault.root / row["path"]
    if not force and not json_output:
        typer.confirm(f"Delete {row['path']}?", abort=True)

    removed_raw: str | None = None
    removed_assets: list[str] = []

    # Read raw_file straight from the markdown frontmatter — the DB row
    # may not carry that field if the schema was synced before the column
    # existed. File parsing is authoritative.
    if file_path.exists():
        try:
            from hyperresearch.core.frontmatter import parse_frontmatter
            text = file_path.read_text(encoding="utf-8-sig")
            meta, _ = parse_frontmatter(text)
            if meta.raw_file:
                # Resolve and guard against path traversal — a malicious or
                # corrupted frontmatter could set raw_file to "../../etc/passwd".
                # Refuse to unlink anything outside <vault>/research/.
                research_root = (vault.root / "research").resolve()
                raw_path = (vault.root / "research" / meta.raw_file).resolve()
                try:
                    raw_path.relative_to(research_root)
                    inside_vault = True
                except ValueError:
                    inside_vault = False
                if inside_vault and raw_path.exists() and raw_path.is_file():
                    raw_path.unlink()
                    removed_raw = str(raw_path.relative_to(vault.root).as_posix())
        except Exception:
            pass

    # Assets directory
    assets_dir = vault.root / "research" / "assets" / note_id
    if assets_dir.exists() and assets_dir.is_dir():
        for asset_file in assets_dir.iterdir():
            if asset_file.is_file():
                removed_assets.append(asset_file.name)
        shutil.rmtree(assets_dir, ignore_errors=True)

    # Sources row (transcript-audit follow-up): `note rm` used to leave the
    # fetch-provenance row behind with a dangling note_id, after which any
    # re-fetch of the URL claimed duplicate:true pointing at a deleted note.
    # Delete the row when it references the note being removed.
    stale_urls = [
        r["url"]
        for r in vault.db.execute(
            "SELECT url FROM sources WHERE note_id = ?", (note_id,)
        ).fetchall()
    ]
    if stale_urls:
        vault.db.execute("DELETE FROM sources WHERE note_id = ?", (note_id,))
        vault.db.commit()
    removed_source_urls = stale_urls

    # Finally, unlink the .md file
    if file_path.exists():
        file_path.unlink()

    # Re-sync to update DB
    from hyperresearch.core.sync import compute_sync_plan, execute_sync

    plan = compute_sync_plan(vault)
    execute_sync(vault, plan)

    # Delta vs upstream: bare `dict` parameterized for mypy --strict.
    payload: dict[str, Any] = {"deleted": note_id}
    if removed_raw:
        payload["removed_raw"] = removed_raw
    if removed_assets:
        payload["removed_assets"] = removed_assets
    if removed_source_urls:
        payload["removed_source_urls"] = removed_source_urls

    if json_output:
        output(success(payload, vault=str(vault.root)), json_mode=True)
    else:
        msg = f"[red]Deleted:[/] {note_id}"
        if removed_raw:
            msg += f"\n  raw: {removed_raw}"
        if removed_assets:
            msg += f"\n  assets: {len(removed_assets)} file(s)"
        console.print(msg)


