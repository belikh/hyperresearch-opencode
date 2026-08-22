"""Hyperresearch CLI — main typer application.

Delta vs upstream (P0-2, kept): the Python-version stderr guard and the
Windows cp1252 UTF-8 reconfigure shim are dropped — 3.14 is supported by
design here and Crawl4AI's rich logger is not a core dependency.

Assembly mirrors upstream `cli/__init__.py` registration order exactly,
minus the research-ops groups owned by P1-10 (install/setup/search/fetch/
fetch-batch/research/import/serve/mcp root commands; config/lint sub-app;
profile/claims/embed/run/escalation/citecheck/levers/sources sub-apps).
Those slots are marked below so the final assembly is a pure insertion.
"""

import typer

from hyperresearch import __version__


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"hyperresearch v{__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="hyperresearch",
    help="Agent-driven research knowledge base.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version"),
) -> None:
    pass


# Root-level commands
from hyperresearch.cli.archive import archive_run as _archive_run
from hyperresearch.cli.dedup import dedup as _dedup
from hyperresearch.cli.main import init as _init
from hyperresearch.cli.main import status as _status
from hyperresearch.cli.main import sync as _sync
from hyperresearch.cli.note import note_show as _show
from hyperresearch.cli.repair import repair as _repair
from hyperresearch.cli.tag import tag_list as _tags
from hyperresearch.cli.vault_tag import vault_tag as _vault_tag
from hyperresearch.cli.watch import watch as _watch

# P1-10 slots: install, setup, search, fetch, fetch-batch, research, import,
# serve, mcp root commands register here in upstream order.
app.command("init")(_init)
app.command("status")(_status)
app.command("sync")(_sync)
# P1-10 slots: search, fetch, fetch-batch, research register here.
app.command("tags")(_tags)
app.command("show", hidden=True)(_show)
app.command("dedup")(_dedup)
app.command("archive-run")(_archive_run)
app.command("vault-tag")(_vault_tag)
# P1-10 slots: import registers here.
app.command("repair")(_repair)
app.command("watch")(_watch)
# P1-10 slots: serve, mcp register here.

# Sub-apps
from hyperresearch.cli.batch import app as batch_app
from hyperresearch.cli.export import app as export_app
from hyperresearch.cli.git_cmd import app as git_app
from hyperresearch.cli.graph import app as graph_app
from hyperresearch.cli.index import app as index_app
from hyperresearch.cli.note import app as note_app
from hyperresearch.cli.tag import app as tag_app
from hyperresearch.cli.template import app as template_app
from hyperresearch.cli.topic import app as topic_app

app.add_typer(note_app, name="note", help="Note CRUD operations.")
app.add_typer(graph_app, name="graph", help="Knowledge graph and link analysis.")
app.add_typer(index_app, name="index", help="Auto-generated index pages.")
# P1-10 slot: lint sub-app adds here.
app.add_typer(export_app, name="export", help="Export notes.")
# P1-10 slot: config sub-app adds here.
app.add_typer(topic_app, name="topic", help="Topic hierarchy.")
app.add_typer(batch_app, name="batch", help="Bulk operations.")
app.add_typer(template_app, name="template", help="Note templates.")
app.add_typer(git_app, name="git", help="Git integration.")
app.add_typer(tag_app, name="tag", help="Tag management.")

from hyperresearch.cli.assets import app as assets_app
from hyperresearch.cli.link import app as link_app

# P1-10 slots: profile, claims, embed, run, escalation, citecheck, levers,
# sources sub-apps add here in upstream order.
app.add_typer(assets_app, name="assets", help="Downloaded images, screenshots, and media.")
app.add_typer(link_app, name="link", help="Auto-discover and insert wiki-links.")
