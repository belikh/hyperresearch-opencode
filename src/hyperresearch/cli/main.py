"""Root-level commands. (Scaffold placeholder — later pieces port init/status/sync.)"""

from __future__ import annotations

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
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version"
    ),
) -> None:
    pass
