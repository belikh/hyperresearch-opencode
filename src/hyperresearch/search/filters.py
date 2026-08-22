"""Structured field filter builder for search queries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

# A bare calendar date, as accepted by the search CLI's --after/--before
# ("Created before date (YYYY-MM-DD)").
_BARE_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass
class SearchFilters:
    tags: list[str] | None = None
    status: str | None = None
    note_type: str | None = None
    tier: str | None = None           # Epistemic tier filter
    content_type: str | None = None   # Artifact kind filter
    after: str | None = None
    before: str | None = None
    path_glob: str | None = None
    parent: str | None = None
    min_words: int | None = None
    max_words: int | None = None
    # Graph-aware filters
    linked_from: str | None = None   # Only notes linked FROM this note ID
    linked_to: str | None = None     # Only notes that link TO this note ID
    min_inbound: int | None = None   # Minimum inbound link count
    has_backlinks: bool | None = None # Must have at least one inbound link

    # Delta vs upstream (`-> tuple[str, list]`): strict mypy forbids bare generics.
    def to_sql(self, table_alias: str = "n") -> tuple[str, list[Any]]:
        """Build SQL WHERE clauses and parameters."""
        clauses: list[str] = []
        params: list[Any] = []

        if self.tags:
            for tag in self.tags:
                clauses.append(
                    f"{table_alias}.id IN (SELECT note_id FROM tags WHERE tag = ?)"
                )
                params.append(tag.lower())

        if self.status:
            clauses.append(f"{table_alias}.status = ?")
            params.append(self.status)

        if self.note_type:
            clauses.append(f"{table_alias}.type = ?")
            params.append(self.note_type)

        if self.tier:
            clauses.append(f"{table_alias}.tier = ?")
            params.append(self.tier)

        if self.content_type:
            clauses.append(f"{table_alias}.content_type = ?")
            params.append(self.content_type)

        if self.after:
            clauses.append(f"{table_alias}.created >= ?")
            params.append(self.after)

        if self.before:
            if _BARE_DATE_RE.fullmatch(self.before):
                # A bare date must cover its ENTIRE final day: ISO timestamp
                # strings sort lexicographically after their own date prefix
                # ("2024-01-15T23:59:59" > "2024-01-15"), so `created <= date`
                # silently dropped every note created ON that day. Compile to
                # an exclusive bound at midnight next day instead — includes
                # 23:59:59.999, excludes the next morning.
                try:
                    day_after = date.fromisoformat(self.before) + timedelta(days=1)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid before filter {self.before!r}: expected "
                        "YYYY-MM-DD or a full ISO datetime."
                    ) from exc
                clauses.append(f"{table_alias}.created < ?")
                params.append(day_after.isoformat())
            else:
                # Full timestamps compare exactly, inclusive upper bound.
                clauses.append(f"{table_alias}.created <= ?")
                params.append(self.before)

        if self.path_glob:
            clauses.append(f"{table_alias}.path GLOB ?")
            params.append(self.path_glob)

        if self.parent:
            clauses.append(f"{table_alias}.parent = ?")
            params.append(self.parent)

        if self.min_words is not None:
            clauses.append(f"{table_alias}.word_count >= ?")
            params.append(self.min_words)

        if self.max_words is not None:
            clauses.append(f"{table_alias}.word_count <= ?")
            params.append(self.max_words)

        # Graph-aware filters
        if self.linked_from:
            clauses.append(
                f"{table_alias}.id IN (SELECT target_id FROM links WHERE source_id = ? AND target_id IS NOT NULL)"
            )
            params.append(self.linked_from)

        if self.linked_to:
            clauses.append(
                f"{table_alias}.id IN (SELECT source_id FROM links WHERE target_id = ?)"
            )
            params.append(self.linked_to)

        if self.min_inbound is not None:
            clauses.append(
                f"{table_alias}.id IN (SELECT target_id FROM links WHERE target_id IS NOT NULL "
                f"GROUP BY target_id HAVING COUNT(*) >= ?)"
            )
            params.append(self.min_inbound)

        if self.has_backlinks is False:
            # Upstream intent is truthy-only: the reference CLI (cli/search.py)
            # normalizes with `has_backlinks or None` before building
            # SearchFilters, so upstream never implemented a "no backlinks"
            # query — False was silently ignored ('1=1'). Fail loudly instead
            # of silently ignoring a constraint a caller explicitly asked for.
            raise NotImplementedError(
                "has_backlinks=False is not supported: the filter is "
                "truthy-only by upstream design (the search CLI passes "
                "`has_backlinks or None`). Use None for no constraint, or "
                "True to require at least one inbound link."
            )

        if self.has_backlinks is True:
            clauses.append(
                f"{table_alias}.id IN (SELECT DISTINCT target_id FROM links WHERE target_id IS NOT NULL)"
            )

        where = " AND ".join(clauses) if clauses else "1=1"
        return where, params
