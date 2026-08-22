"""Hyperresearch CLI — main typer application.

Scaffold: the real app assembles command modules here (mirroring upstream
`cli/__init__.py`); for now it re-exports the placeholder app from
`cli/main.py` so the `hyperresearch` / `hpr` entry points resolve. Later
pieces replace this file's assembly, not the `hyperresearch.cli:app`
contract.
"""

from hyperresearch.cli.main import app

__all__ = ["app"]
