"""Tests for embeddings (WS6) — fully offline.

Split from upstream `tests/test_core/test_claims_and_embed.py`: the
TestEmbeddings class is byte-identical; TestClaimsIngest stays deferred with
its owner (core/claims.py + the CLI app, later pieces).
"""

from __future__ import annotations

import pytest

from hyperresearch.core import embed
from hyperresearch.core.embed import (
    EmbeddingError,
    cosine,
    reciprocal_rank_fusion,
)


class TestEmbeddings:
    def _fake_embedder(self, monkeypatch):
        """Deterministic fake: vector derived from text hash. Counts calls."""
        calls = {"batches": 0, "texts": 0}

        def fake(provider, model, texts):
            calls["batches"] += 1
            calls["texts"] += len(texts)
            out = []
            for t in texts:
                h = sum(ord(c) for c in t) % 97
                out.append([float(h), 1.0, float(len(t) % 13)])
            return out

        monkeypatch.setattr(embed, "_http_embed", fake)
        return calls

    def test_provider_none_raises_cleanly(self, seeded_vault):
        with pytest.raises(EmbeddingError, match="disabled"):
            embed.embed_sync(seeded_vault)

    def test_embed_sync_and_incremental(self, seeded_vault, monkeypatch):
        calls = self._fake_embedder(monkeypatch)
        cfg_path = seeded_vault.config_path
        cfg_path.write_text(
            cfg_path.read_text(encoding="utf-8").replace(
                'provider = "none"', 'provider = "openai"'
            ),
            encoding="utf-8",
        )
        # Fresh Vault object so the edited config is re-read
        vault = type(seeded_vault).discover(seeded_vault.root)

        r1 = embed.embed_sync(vault)
        assert r1["embedded"] >= 4
        assert r1["provider"] == "openai"
        assert calls["texts"] == r1["embedded"]

        r2 = embed.embed_sync(vault)
        assert r2["embedded"] == 0  # unchanged content -> no re-embedding
        assert r2["skipped"] >= 4

        hits = embed.semantic_search(vault, "concurrency patterns", limit=3)
        assert len(hits) == 3
        assert all("id" in h and "score" in h for h in hits)

    def test_cosine(self):
        assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
        assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
        assert cosine([], []) == 0.0

    def test_rrf_fusion(self):
        fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]])
        ids = [x[0] for x in fused]
        # a and b appear in both lists -> outrank c and d
        assert set(ids[:2]) == {"a", "b"}

    def test_vector_pack_roundtrip(self):
        vec = [0.5, -1.25, 3.0]
        assert embed._unpack(embed._pack(vec)) == vec
