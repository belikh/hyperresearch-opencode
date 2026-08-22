"""Search result models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SearchResult(BaseModel):
    id: str
    title: str
    path: str
    status: str
    tags: list[str]
    created: str
    updated: str | None
    score: float
    snippet: str = ""


class SearchResponse(BaseModel):
    query: str
    # Delta vs upstream: `filters: dict` — type parameters added for mypy --strict.
    filters: dict[str, Any]
    total: int
    results: list[SearchResult]
