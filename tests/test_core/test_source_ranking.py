"""Phase-2 source-ranking tests: schema v9, PageRank, quality composite.

Delta vs upstream: split out of upstream tests/test_core/test_source_ranking.py
(P1-3 port). Only the classes whose imports resolve in the current tree are
ported, byte-identical; the rest of the upstream file waits on later pieces:

  - TestDoiExtraction -> hyperresearch.core.scholar.extract_doi (P1-5)
  - TestRankedSearch  -> hyperresearch.search.fts + cli app (search/CLI pieces)

TestSchemaV9's imports all resolve today (db/migrations/note/sync landed in
P1-1), so it travels with this file rather than waiting for P1-5.
"""

from __future__ import annotations

from hyperresearch.core.config import RankingSettings
from hyperresearch.core.graphrank import compute_centrality, pagerank
from hyperresearch.core.quality import compute_quality_for_row, compute_quality_scores


class TestSchemaV9:
    def test_new_columns_exist(self, tmp_vault):
        cols = {row[1] for row in tmp_vault.db.execute("PRAGMA table_info(notes)")}
        expected = {
            "doi", "utility_score", "authority_score", "centrality_score",
            "independence", "citation_count", "venue", "is_retracted", "quality_score",
        }
        assert expected <= cols

    def test_new_tables_exist(self, tmp_vault):
        tables = {
            row[0]
            for row in tmp_vault.db.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
            )
        }
        assert "claims" in tables
        assert "api_cache" in tables
        # claims_fts is a virtual table
        assert tmp_vault.db.execute("SELECT count(*) FROM claims_fts").fetchone() is not None

    def test_migration_from_v8_is_idempotent(self, tmp_vault):
        from hyperresearch.core.migrations import _migrate_v9_source_ranking

        _migrate_v9_source_ranking(tmp_vault.db)  # re-run on already-migrated DB
        cols = {row[1] for row in tmp_vault.db.execute("PRAGMA table_info(notes)")}
        assert "quality_score" in cols

    def test_frontmatter_roundtrip(self, tmp_vault):
        from hyperresearch.core.note import write_note
        from hyperresearch.core.sync import compute_sync_plan, execute_sync

        write_note(
            tmp_vault.notes_dir,
            "Ranked Paper",
            body="A paper with ranking metadata.",
            extra_frontmatter={
                "doi": "10.1234/example",
                "utility_score": 14.0,
                "citation_count": 42,
                "venue": "NeurIPS",
                "is_retracted": False,
            },
        )
        plan = compute_sync_plan(tmp_vault, force=True)
        execute_sync(tmp_vault, plan)
        row = tmp_vault.db.execute(
            "SELECT doi, utility_score, citation_count, venue, is_retracted "
            "FROM notes WHERE id = 'ranked-paper'"
        ).fetchone()
        assert row["doi"] == "10.1234/example"
        assert row["utility_score"] == 14.0
        assert row["citation_count"] == 42
        assert row["venue"] == "NeurIPS"
        assert row["is_retracted"] == 0

    def test_derived_scores_survive_resync(self, seeded_vault):
        conn = seeded_vault.db
        conn.execute(
            "UPDATE notes SET quality_score = 0.9, centrality_score = 0.5 "
            "WHERE id = 'concurrency'"
        )
        conn.commit()
        from hyperresearch.core.sync import compute_sync_plan, execute_sync

        plan = compute_sync_plan(seeded_vault, force=True)
        execute_sync(seeded_vault, plan)
        row = conn.execute(
            "SELECT quality_score, centrality_score FROM notes WHERE id = 'concurrency'"
        ).fetchone()
        assert row["quality_score"] == 0.9
        assert row["centrality_score"] == 0.5


class TestPageRank:
    def test_hub_ranks_highest(self):
        nodes = ["hub", "a", "b", "c"]
        edges = [("a", "hub"), ("b", "hub"), ("c", "hub"), ("hub", "a")]
        scores = pagerank(nodes, edges)
        assert scores["hub"] == max(scores.values())

    def test_empty_graph(self):
        assert pagerank([], []) == {}

    def test_dangling_nodes_handled(self):
        scores = pagerank(["a", "b"], [("a", "b")])
        assert abs(sum(scores.values()) - 1.0) < 0.01

    def test_compute_centrality_on_seeded_vault(self, seeded_vault):
        n = compute_centrality(seeded_vault.db)
        assert n > 0
        rows = seeded_vault.db.execute(
            "SELECT id, centrality_score FROM notes ORDER BY centrality_score DESC"
        ).fetchall()
        assert rows[0]["centrality_score"] == 1.0  # normalized by max
        # The MOC/hub notes are linked from multiple notes → should outrank the orphan
        by_id = {r["id"]: r["centrality_score"] for r in rows}
        assert by_id["concurrency"] > by_id["orphan-note"]


class TestQualityComposite:
    R = RankingSettings()

    def test_retraction_floors_everything(self):
        q = compute_quality_for_row(self.R, "ground_truth", 18.0, 1.0, 1.0, True)
        assert q == self.R.retraction_floor

    def test_tier_only_renormalizes(self):
        q = compute_quality_for_row(self.R, "ground_truth", None, None, None, False)
        assert q == 1.0  # single component, full weight on tier weight 1.0

    def test_no_components_gives_none(self):
        assert compute_quality_for_row(self.R, None, None, None, None, False) is None

    def test_full_composite_weighting(self):
        q = compute_quality_for_row(self.R, "commentary", 9.0, 0.5, 0.5, False)
        # (0.35*0.4 + 0.2*0.5 + 0.25*0.5 + 0.2*0.5) / 1.0
        assert abs(q - (0.35 * 0.4 + 0.2 * 0.5 + 0.25 * 0.5 + 0.2 * 0.5)) < 1e-9

    def test_ground_truth_beats_commentary(self):
        gt = compute_quality_for_row(self.R, "ground_truth", None, None, None, False)
        com = compute_quality_for_row(self.R, "commentary", None, None, None, False)
        assert gt > com

    def test_compute_all(self, seeded_vault):
        conn = seeded_vault.db
        conn.execute("UPDATE notes SET tier = 'ground_truth' WHERE id = 'concurrency'")
        conn.execute("UPDATE notes SET tier = 'commentary' WHERE id = 'orphan-note'")
        conn.commit()
        updated = compute_quality_scores(conn, self.R)
        assert updated >= 4
        rows = {
            r["id"]: r["quality_score"]
            for r in conn.execute("SELECT id, quality_score FROM notes")
        }
        assert rows["concurrency"] > rows["orphan-note"]
