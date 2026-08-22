"""Tests for SearchFilters SQL generation.

Filter semantics regressions from the P1-2 hardening wave
(evidence/gauntlet/P1-2-verdict-r1.md F2/F4).
"""

from __future__ import annotations

import pytest

from hyperresearch.search.filters import SearchFilters


class TestBeforeDateBoundary:
    def test_bare_date_before_covers_entire_final_day(self):
        """`before=2024-01-15` must include a note created at
        2024-01-15T23:59:59. ISO timestamps sort lexicographically AFTER
        their own date prefix, so `created <= '2024-01-15'` excluded the
        whole final day. A bare date now compiles to an EXCLUSIVE bound at
        midnight next day (covers the day up to 23:59:59.999)."""
        where, params = SearchFilters(before="2024-01-15").to_sql("n")
        assert where == "n.created < ?"
        assert params == ["2024-01-16"]

    def test_datetime_before_stays_exact_inclusive_bound(self):
        """Full timestamps keep the exact inclusive `<=` bound."""
        where, params = SearchFilters(before="2024-01-15T12:00:00").to_sql("n")
        assert where == "n.created <= ?"
        assert params == ["2024-01-15T12:00:00"]

    def test_date_shaped_but_invalid_before_raises_clearly(self):
        """A YYYY-MM-DD-shaped string that isn't a real date fails loudly,
        not with a confusing SQLite type error downstream."""
        with pytest.raises(ValueError, match="before"):
            SearchFilters(before="2024-13-45").to_sql("n")

    def test_after_semantics_unchanged(self):
        """Mirror-check: `after` keeps its inclusive >= bound verbatim
        (a bare date already covers its own first instant)."""
        where, params = SearchFilters(after="2024-01-15").to_sql("n")
        assert where == "n.created >= ?"
        assert params == ["2024-01-15"]


class TestHasBacklinks:
    def test_false_raises_not_implemented_rather_than_silent_ignore(self):
        """F4: has_backlinks=False used to collapse into '1=1' silently.
        Upstream intent is truthy-only — the reference CLI normalizes with
        `has_backlinks or None` before constructing SearchFilters — so False
        is a programming error here and must fail loudly."""
        with pytest.raises(NotImplementedError, match="has_backlinks"):
            SearchFilters(has_backlinks=False).to_sql()

    def test_true_keeps_positive_subquery(self):
        where, _params = SearchFilters(has_backlinks=True).to_sql("n")
        assert "n.id IN (SELECT DISTINCT target_id FROM links" in where

    def test_none_stays_unconstrained(self):
        where, params = SearchFilters().to_sql()
        assert where == "1=1"
        assert params == []
