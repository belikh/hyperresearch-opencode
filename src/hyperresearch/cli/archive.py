"""archive-run: move prior per-run artifacts so the next run starts clean.

When `/hyperresearch` runs a second time in the same vault, it overwrites the
unnamespaced scaffold / loci / comparisons / critic-findings / patch-log /
polish-log / prompt-decomposition + the entire research/temp/ scratch tree.
Final reports and canonical query files are namespaced by vault_tag and stay
in place; everything else gets clobbered. This command preserves the prior
run's artifacts before the next run's bootstrap writes over them.

Limitations: this protects sequential runs. Two `/hyperresearch` invocations
that overlap in time still race on the new files they both write.
"""

from __future__ import annotations

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

from hyperresearch.cli._output import console, output
from hyperresearch.models.output import error, success

# Per-run artifacts the orchestrator and step skills write at research/ root.
# Final reports (final_report_<tag>.md) and queries (query-<tag>.md) are
# already namespaced and stay in place.
_ROOT_ARTIFACTS: tuple[str, ...] = (
    "scaffold.md",
    "prompt-decomposition.json",
    "wrapper_contract.json",
    "loci.json",
    "loci-a.json",
    "loci-b.json",
    "comparisons.md",
    "corpus-critic-gaps.json",
    "critic-findings-dialectic.json",
    "critic-findings-depth.json",
    "critic-findings-width.json",
    "critic-findings-instruction.json",
    "patch-log.json",
    "polish-log.json",
    "readability-recommendations.json",
    "readability-decisions.json",
    "audit_findings.json",
    "orchestrator-restructure-log.md",
)

# Whole-tree per-run scratch.
_SUBDIRS: tuple[str, ...] = ("temp",)

_QUERY_RE = re.compile(r"^query-(.+)\.md$")
_VAULT_TAG_RE = re.compile(
    r"vault[_\- ]?tag[:\s=]+`?([a-z0-9][a-z0-9-]*)`?", re.IGNORECASE
)


def _infer_previous_vault_tag(research_dir: Path) -> str | None:
    """Look up the most recently-touched query-*.md and return its slug.
    Fall back to grepping scaffold.md if no query files exist.
    """
    candidates = sorted(
        research_dir.glob("query-*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for c in candidates:
        m = _QUERY_RE.match(c.name)
        if m:
            return m.group(1)
    scaffold = research_dir / "scaffold.md"
    if scaffold.exists():
        try:
            text = scaffold.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        m = _VAULT_TAG_RE.search(text)
        if m:
            return m.group(1)
    return None


def _unique_archive_dir(base: Path) -> Path:
    """Append `-2`, `-3`, ... until the path is free."""
    if not base.exists():
        return base
    counter = 2
    while True:
        candidate = base.with_name(f"{base.name}-{counter}")
        if not candidate.exists():
            return candidate
        counter += 1


def archive_run(
    json_output: bool = typer.Option(False, "--json", "-j", help="JSON output"),
) -> None:
    """Archive prior per-run artifacts to research/runs/archive-*/.

    Run this BEFORE starting a new /hyperresearch session to preserve any
    in-progress or completed prior run's scaffold, loci, comparisons,
    critic findings, patch/polish logs, and the entire research/temp/
    scratch tree. Without this step, the next run silently overwrites them.

    Final reports (research/notes/final_report_<tag>.md) and canonical query
    files (research/query-<tag>.md) are already namespaced by vault_tag and
    are left in place.
    """
    from hyperresearch.core.vault import Vault, VaultError

    try:
        vault = Vault.discover()
    except VaultError as e:
        if json_output:
            output(error(str(e), "NO_VAULT"), json_mode=True)
        else:
            console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    research_dir = vault.research_dir
    # Delta vs upstream: annotated for mypy --strict (heterogeneous dict reused
    # across branches).
    data: dict[str, Any]
    if not research_dir.exists():
        data = {"archived": False, "files_moved": 0, "previous_vault_tag": None}
        if json_output:
            output(success(data, vault=str(vault.root)), json_mode=True)
        else:
            console.print("[dim]Nothing to archive: research/ does not exist.[/]")
        return

    to_move: list[Path] = []
    for name in _ROOT_ARTIFACTS:
        p = research_dir / name
        if p.exists() and p.is_file():
            to_move.append(p)
    for sub in _SUBDIRS:
        d = research_dir / sub
        if d.is_dir() and any(d.iterdir()):
            to_move.append(d)

    if not to_move:
        data = {"archived": False, "files_moved": 0, "previous_vault_tag": None}
        if json_output:
            output(success(data, vault=str(vault.root)), json_mode=True)
        else:
            console.print("[dim]No prior run artifacts found.[/]")
        return

    prev_tag = _infer_previous_vault_tag(research_dir)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"{prev_tag}-{timestamp}" if prev_tag else timestamp
    archive_dir = _unique_archive_dir(research_dir / "runs" / f"archive-{suffix}")
    archive_dir.mkdir(parents=True)

    moved: list[dict[str, str]] = []  # Delta vs upstream: bare `list[dict]` parameterized for mypy --strict
    for src in to_move:
        dest = archive_dir / src.name
        shutil.move(str(src), str(dest))
        moved.append({
            "from": src.relative_to(vault.root).as_posix(),
            "to": dest.relative_to(vault.root).as_posix(),
        })

    # Recreate the now-empty research/temp/ so subsequent skill steps don't
    # need to remember to mkdir it.
    (research_dir / "temp").mkdir(exist_ok=True)

    data = {
        "archived": True,
        "archive_dir": archive_dir.relative_to(vault.root).as_posix(),
        "files_moved": len(moved),
        "moved": moved,
        "previous_vault_tag": prev_tag,
    }
    if json_output:
        output(success(data, vault=str(vault.root)), json_mode=True)
    else:
        console.print(
            f"[green]Archived[/] {len(moved)} items to "
            f"{archive_dir.relative_to(vault.root).as_posix()}"
        )
        if prev_tag:
            console.print(f"  previous vault_tag: [cyan]{prev_tag}[/]")
