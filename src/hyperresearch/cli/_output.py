"""Dual-mode output: rich terminal for humans, JSON for LLM agents."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from hyperresearch.cli._jq import JqError, evaluate, format_results
from hyperresearch.models.output import Envelope

console = Console()
err_console = Console(stderr=True)

# Global --jq program (set once by the root typer callback, read by every
# output() call). Process-wide by design: the flag is a per-invocation
# projection applied uniformly to whatever envelope a command prints.
_jq_program: str | None = None


def set_jq_program(program: str | None) -> None:
    """Record the --jq program for this process run."""
    global _jq_program
    _jq_program = program


def output(data: Any, *, json_mode: bool = False, **kwargs: Any) -> None:
    """Output data in either JSON or rich terminal format."""
    if json_mode:
        _output_json(data)
    else:
        _output_rich(data, **kwargs)


def _envelope_dict(data: Envelope) -> dict[str, Any]:
    """Envelope as the dict agents parse — with the stable-key guarantee.

    ``data`` is ALWAYS present (None on errors). The historical dump used
    ``exclude_none=True`` wholesale, so error responses omitted ``data``
    entirely and downstream ``d['data']`` raised KeyError — the single most
    common transcript failure (74 hits). None-valued keys other than
    ``data`` stay excluded to keep success responses byte-compatible.
    """
    d = data.model_dump(exclude_none=True)
    if "data" not in d:
        rebuilt: dict[str, Any] = {}
        for field in ("ok", "data", "error", "error_code", "count", "vault", "timestamp"):
            if field == "data":
                rebuilt["data"] = None
            elif field in d:
                rebuilt[field] = d[field]
        return rebuilt
    return d


def _output_json(data: Any) -> None:
    """Output as JSON. Uses sys.stdout with UTF-8 to avoid Windows encoding issues."""
    import sys

    if _jq_program is not None:
        if not isinstance(data, Envelope):
            raise typer.Exit(code=2)
        doc = _envelope_dict(data)
        try:
            results = evaluate(_jq_program, doc)
        except JqError as e:
            err_console.print(f"[red]--jq error:[/] {e}")
            raise typer.Exit(code=2) from e
        text = format_results(results)
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
        return

    if isinstance(data, Envelope):
        text = json.dumps(_envelope_dict(data), indent=2, default=str)
    elif hasattr(data, "model_dump_json"):
        text = data.model_dump_json(indent=2, exclude_none=True)
    else:
        text = json.dumps(data, indent=2, default=str)

    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


def _output_rich(data: Any, **kwargs: Any) -> None:
    """Output in rich terminal format."""
    if isinstance(data, Envelope):
        if not data.ok:
            err_console.print(f"[red bold]Error:[/] {data.error}")
            raise typer.Exit(1)
        _output_rich(data.data, **kwargs)
        return

    if isinstance(data, dict):
        _print_dict(data, **kwargs)
    elif isinstance(data, list):
        _print_list(data, **kwargs)
    elif isinstance(data, str):
        console.print(data)
    else:
        console.print(str(data))


def _print_dict(data: dict[str, Any], **kwargs: Any) -> None:  # Delta vs upstream: bare `dict` parameterized for mypy --strict
    """Pretty-print a dict."""
    for key, value in data.items():
        if isinstance(value, dict):
            console.print(f"[bold]{key}:[/]")
            _print_dict(value)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            console.print(f"\n[bold]{key}:[/]")
            _print_list(value)
        else:
            console.print(f"  [dim]{key}:[/] {value}")


def _print_list(data: list[Any], **kwargs: Any) -> None:  # Delta vs upstream: bare `list` parameterized for mypy --strict
    """Pretty-print a list of items, as a table if they're dicts."""
    if not data:
        console.print("  [dim](none)[/]")
        return

    if isinstance(data[0], dict):
        table = Table(show_header=True, header_style="bold")
        cols = list(data[0].keys())
        for col in cols:
            table.add_column(col)
        for item in data:
            table.add_row(*(str(item.get(c, "")) for c in cols))
        console.print(table)
    else:
        for item in data:
            console.print(f"  - {item}")


def print_note_summary(notes: list[dict[str, Any]], title: str = "Notes") -> None:  # Delta vs upstream: bare `list[dict]` parameterized for mypy --strict
    """Print a table of notes."""
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Status", style="yellow")
    table.add_column("Tags", style="green")
    table.add_column("Words", justify="right", style="dim")
    for n in notes:
        tags = ", ".join(n.get("tags", []))
        table.add_row(
            n.get("id", ""),
            n.get("title", ""),
            n.get("status", ""),
            tags,
            str(n.get("word_count", "")),
        )
    console.print(table)


def print_vault_status(data: dict[str, Any]) -> None:  # Delta vs upstream: bare `dict` parameterized for mypy --strict
    """Print vault status in a nice tree format."""
    tree = Tree(f"[bold]{data.get('vault_name', 'Vault')}[/]")
    notes = tree.add("[bold]Notes[/]")
    nd = data.get("notes", {})
    notes.add(f"Total: {nd.get('total', 0)}")
    for status, count in nd.get("by_status", {}).items():
        notes.add(f"{status}: {count}")

    tags = tree.add("[bold]Tags[/]")
    tags.add(f"Unique: {data.get('tags', {}).get('total_unique', 0)}")

    graph = tree.add("[bold]Graph[/]")
    gd = data.get("graph", {})
    graph.add(f"Links: {gd.get('total_links', 0)}")
    graph.add(f"Broken: {gd.get('broken_links', 0)}")
    graph.add(f"Orphans: {gd.get('orphan_notes', 0)}")

    tree.add(f"[dim]Words: {data.get('total_words', 0):,}[/]")
    console.print(tree)


# ---------------------------------------------------------------------------
# Field projection + TSV (transcript audit R3): agents burned 667 python
# calls extracting id/word_count/tier from list outputs. --fields projects
# dict items; --format tsv renders grep/cut-friendly tabular text.
# ---------------------------------------------------------------------------

def project_fields(items: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    """Project each item to the requested fields. Unknown fields error with
    the available field list so the retry is informed, not a guess."""
    if not fields:
        return items
    if items:
        available = sorted(items[0].keys())
        unknown = [f for f in fields if f not in available]
        if unknown:
            raise ValueError(
                f"unknown field(s) {', '.join(unknown)}; available: {', '.join(available)}"
            )
    return [{f: item.get(f) for f in fields} for item in items]


def render_tsv(items: list[dict[str, Any]], fields: list[str]) -> str:
    """Header row + one TSV line per item. Lists join with commas, None is
    empty — stable column count regardless of values."""

    def _cell(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, list):
            return ",".join(str(x) for x in v)
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v).replace("\t", " ").replace("\n", " ")

    lines = ["\t".join(fields)]
    for item in items:
        lines.append("\t".join(_cell(item.get(f)) for f in fields))
    return "\n".join(lines)
