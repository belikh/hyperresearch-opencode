"""Regression tests for the MinHash/LSH half of core.similarity.

Upstream ships no dedicated test file for this module. These arrive with the
P1-2 gauntlet side-fix G13-LSH-BANDING (evidence/gauntlet/P1-3-verdict-r1.md):
unguarded `num_perm // bands` made `bands > num_perm` return all-pairs
candidates; it must now raise ValueError.
"""

from __future__ import annotations

import pytest

from hyperresearch.core.similarity import (
    jaccard,
    lsh_candidates,
    minhash_signature,
    shingle,
)


def _three_sigs() -> dict[str, list[int]]:
    """Two identical docs + one unrelated doc, default num_perm=128."""
    dup = "the quick brown fox jumps over the lazy dog"
    other = "completely unrelated text about quantum flux capacitors"
    return {
        "a": minhash_signature(shingle(dup)),
        "b": minhash_signature(shingle(dup)),
        "c": minhash_signature(shingle(other)),
    }


class TestLshBandingGuard:
    def test_bands_exceeding_num_perm_raises(self):
        # Pre-fix this silently returned ALL pairs as candidates.
        with pytest.raises(ValueError, match="bands"):
            lsh_candidates(_three_sigs(), bands=200)

    def test_bands_below_one_raises(self):
        with pytest.raises(ValueError, match="bands"):
            lsh_candidates(_three_sigs(), bands=0)

    def test_error_message_names_both_values(self):
        with pytest.raises(ValueError, match=r"bands=200.*num_perm=128"):
            lsh_candidates(_three_sigs(), bands=200)

    def test_identical_docs_still_candidates_within_valid_bands(self):
        candidates = lsh_candidates(_three_sigs(), bands=16)
        assert ("a", "b") in candidates

    def test_unrelated_doc_never_a_candidate(self):
        candidates = lsh_candidates(_three_sigs(), bands=16)
        assert all("c" not in pair for pair in candidates)

    def test_empty_signatures_still_return_empty(self):
        assert lsh_candidates({}, bands=16) == set()


class TestSimilarityBasics:
    """Positive controls so the guard cannot hide a broken pipeline."""

    def test_jaccard_identical_shingles(self):
        s = shingle("alpha beta gamma delta epsilon")
        assert jaccard(s, set(s)) == 1.0

    def test_minhash_signatures_of_equal_sets_are_equal(self):
        s = shingle("alpha beta gamma delta epsilon")
        assert minhash_signature(s) == minhash_signature(set(s))

    def test_minhash_empty_shingles_full_max_hash(self):
        assert minhash_signature(set(), num_perm=8) == [(1 << 32) - 1] * 8
