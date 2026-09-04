"""Minimal jq-subset evaluator for the global ``--jq`` flag.

Why this exists (transcript audit 2026-09-04): 43% of all bash calls in
hyperresearch sessions were inline ``python3 -c`` adapters hand-written to
parse ``-j`` output — 398 hard errors (KeyError/JSONDecodeError class) and
181 immediate retries. ``--jq`` gives every command a server-side projection
so the canonical read needs zero Python.

Supported grammar (the forms agents actually use):

    .                       identity
    .field.sub              dot paths
    .field[0]               list index
    .field[]                iterate list / object values
    .a[] | .b               pipes between path stages
    length                  array/object/string length (terminal filter)

Anything outside the subset raises :class:`JqError` with a pointer to the
offending token — callers should surface that and point the user at the
real ``jq`` binary for full programs. Keeping this dependency-free also
keeps the CLI import graph unchanged (no libjq binding).

Deliberately NOT supported (fail loudly rather than approximate):
``select()``, ``-r``/``@text``, arithmetic, string interpolation, ``..``.
Approximating those silently would trade a KeyError for a wrong answer.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

_TOKEN_RE = re.compile(
    r"""
    (?P<dot>\.(?P<field>[A-Za-z_][A-Za-z0-9_]*))
  | (?P<idx>\[\s*(?P<number>-?\d+)\s*\])
  | (?P<iterate>\[\s*\])
  | (?P<length>\blength\b)
  | (?P<ws>\s+)
  | (?P<pipe>\|)
    """,
    re.VERBOSE,
)


class JqError(ValueError):
    """Raised for unsupported or malformed --jq programs."""


def _tokenize(stage: str) -> list[tuple[str, Any]]:
    if stage == ".":
        return []  # identity — bare `.` produces no transformations
    tokens: list[tuple[str, Any]] = []
    pos = 0
    while pos < len(stage):
        m = _TOKEN_RE.match(stage, pos)
        if not m:
            raise JqError(
                f"unsupported --jq syntax at {stage[pos:]!r} — this flag "
                "supports dot paths, [index], [] iteration, | pipes and "
                "length; use the jq binary for full programs"
            )
        pos = m.end()
        if m.group("ws"):
            continue
        if m.group("dot"):
            tokens.append(("field", m.group("field")))
        elif m.group("idx"):
            tokens.append(("index", int(m.group("number"))))
        elif m.group("iterate"):
            tokens.append(("iterate", None))
        elif m.group("length"):
            tokens.append(("length", None))
        elif m.group("pipe"):
            tokens.append(("pipe", None))
    return tokens


def _apply_stage(values: list[Any], tokens: list[tuple[str, Any]]) -> list[Any]:
    out = values
    for kind, arg in tokens:
        nxt: list[Any] = []
        for v in out:
            if kind == "field":
                if not isinstance(v, dict):
                    raise JqError(
                        f"cannot index {type(v).__name__} with '.{arg}' "
                        "(value is not an object)"
                    )
                nxt.append(v.get(arg))
            elif kind == "index":
                if not isinstance(v, list):
                    raise JqError(
                        f"cannot index {type(v).__name__} with [{arg}] "
                        "(value is not an array)"
                    )
                if -len(v) <= arg < len(v):
                    nxt.append(v[arg])
                # Out-of-range indexes yield nothing (jq semantics: no null)
            elif kind == "iterate":
                if isinstance(v, list):
                    nxt.extend(v)
                elif isinstance(v, dict):
                    nxt.extend(v.values())
                else:
                    raise JqError(
                        f"cannot iterate {type(v).__name__} (not array/object)"
                    )
            elif kind == "length":
                if isinstance(v, (list, dict, str)):
                    nxt.append(len(v))
                elif v is None:
                    nxt.append(0)
                else:
                    raise JqError(f"length not defined on {type(v).__name__}")
        out = nxt
    return out


def _split_pipeline(program: str) -> list[str]:
    """Split on top-level pipes. No brackets/strings in the subset, so a
    plain split is exact."""
    return [p.strip() for p in program.split("|") if p.strip()]


def evaluate(program: str, document: Any) -> list[Any]:
    """Apply a jq-subset program to a parsed JSON document.

    Returns every result (jq's stream semantics); an empty program is an
    error, not identity — silent no-ops are how quoting bugs hide.
    """
    stages = _split_pipeline(program)
    if not stages:
        raise JqError("empty --jq program")
    values: list[Any] = [document]
    for stage in stages:
        values = _apply_stage(values, _tokenize(stage))
    return values


def format_results(results: Iterator[Any] | list[Any]) -> str:
    """Render results one per line; scalars bare, containers compact JSON."""
    lines: list[str] = []
    for r in results:
        if isinstance(r, str):
            lines.append(r)
        else:
            lines.append(json.dumps(r, default=str, separators=(",", ":")))
    return "\n".join(lines)
