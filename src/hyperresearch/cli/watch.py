"""Watch mode — auto-sync on file changes."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import typer

from hyperresearch.cli._output import console

if TYPE_CHECKING:
    from hyperresearch.core.vault import (
        Vault,  # Delta vs upstream: needed to annotate _quick_lint for mypy --strict
    )


def watch(
    rebuild_index: bool = typer.Option(False, "--rebuild-index", "-i", help="Rebuild indexes after sync"),
    run_lint: bool = typer.Option(False, "--lint", "-l", help="Run lint after sync"),
) -> None:
    """Watch for file changes and auto-sync."""
    try:
        from watchdog.events import FileSystemEvent, FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        console.print("[red]Watch mode requires: pip install hyperresearch[watch][/]")
        raise typer.Exit(1)

    from hyperresearch.core.sync import compute_sync_plan, execute_sync
    from hyperresearch.core.vault import Vault

    vault = Vault.discover()
    console.print(f"[bold]Watching:[/] {vault.root}")
    console.print("[dim]Press Ctrl+C to stop.[/]\n")

    class DebouncedHandler(FileSystemEventHandler):
        def __init__(self) -> None:  # Delta vs upstream: return annotation for mypy --strict
            self._pending = False
            self._last_event: float = 0.0  # Delta vs upstream: annotated for mypy --strict

        def on_any_event(self, event: FileSystemEvent) -> None:  # Delta vs upstream: return annotation for mypy --strict
            # Delta vs upstream (typing only): newer watchdog stubs type
            # src_path as bytes; coerce so the str suffix check type-checks.
            src_path = str(event.src_path)
            if not src_path.endswith(".md"):
                return
            # Skip .hyperresearch directory
            if ".hyperresearch" in src_path:
                return
            self._pending = True
            self._last_event = time.monotonic()

        def check_and_sync(self) -> bool:  # Delta vs upstream: return annotation already present upstream; kept
            if not self._pending:
                return False
            # Debounce: wait 500ms after last event
            if time.monotonic() - self._last_event < 0.5:
                return False
            self._pending = False

            try:
                plan = compute_sync_plan(vault)
                if plan.to_add or plan.to_update or plan.to_delete:
                    result = execute_sync(vault, plan)
                    console.print(
                        f"[green]Synced:[/] +{result.added} ~{result.updated} "
                        f"-{result.deleted} ({result.duration_ms:.0f}ms)"
                    )
                    for err in result.errors:
                        console.print(f"  [red]Error:[/] {err['path']}: {err['error']}")

                    if rebuild_index:
                        from hyperresearch.indexgen.generator import IndexGenerator
                        gen = IndexGenerator(vault)
                        built = gen.build_all()
                        # Re-sync to index the index pages
                        plan2 = compute_sync_plan(vault)
                        if plan2.to_add or plan2.to_update:
                            execute_sync(vault, plan2)
                        console.print(f"  [dim]Rebuilt {len(built)} indexes[/]")

                    if run_lint:
                        _quick_lint(vault)

                    return True
            except Exception as e:
                console.print(f"[red]Sync error:[/] {e}")
            return False

    handler = DebouncedHandler()
    observer = Observer()
    observer.schedule(handler, str(vault.research_dir), recursive=True)
    observer.start()

    try:
        while True:
            handler.check_and_sync()
            time.sleep(0.2)
    except KeyboardInterrupt:
        observer.stop()
        console.print("\n[dim]Stopped watching.[/]")
    observer.join()


def _quick_lint(vault: Vault) -> None:  # Delta vs upstream: param annotated for mypy --strict
    """Run a quick lint and print summary."""
    conn = vault.db
    broken = conn.execute("SELECT COUNT(*) as c FROM links WHERE target_id IS NULL").fetchone()["c"]
    orphans = conn.execute("""
        SELECT COUNT(*) as c FROM notes n
        WHERE n.type NOT IN ('index', 'raw')
          AND n.id NOT IN (SELECT DISTINCT target_id FROM links WHERE target_id IS NOT NULL)
          AND n.id NOT IN (SELECT DISTINCT source_id FROM links)
    """).fetchone()["c"]
    if broken or orphans:
        parts = []
        if broken:
            parts.append(f"{broken} broken links")
        if orphans:
            parts.append(f"{orphans} orphans")
        console.print(f"  [yellow]Lint: {', '.join(parts)}[/]")
