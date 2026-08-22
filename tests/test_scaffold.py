"""Scaffold smoke tests: package imports and version contract."""

import tomllib
from pathlib import Path

import hyperresearch

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_version_matches_pyproject() -> None:
    """`hyperresearch.__version__` must equal the pyproject.toml version."""
    with PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    assert hyperresearch.__version__ == data["project"]["version"]
