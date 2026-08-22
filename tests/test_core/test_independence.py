"""Independence-audit tests.

Delta vs upstream: TestIndependence is ported byte-identical out of upstream
tests/test_core/test_verification.py (P1-3 port) because every import it
needs resolves in the current tree. The remainder of that upstream file
(TestCiteCheckExtraction, TestVerificationLints, TestCJKLengthCheck,
TestTelemetryAndVerify, TestFinishGate, TestCiteCheckerAgentInstall) waits on
later pieces: core/citecheck.py, core/runs.py, core/hooks.py and the CLI.
"""

from __future__ import annotations

import pytest

from hyperresearch.core.independence import canonical_url, compute_independence


class TestIndependence:
    def test_canonical_url(self):
        assert canonical_url("https://www.Example.com/a/?utm_source=x") == canonical_url("http://example.com/a")

    def test_wire_cluster_discounts_members(self, tmp_vault):
        from hyperresearch.core.note import write_note
        from hyperresearch.core.sync import compute_sync_plan, execute_sync

        pr = "NEW YORK, PRNewswire — MegaCorp announces quantum widget breakthrough today."
        for i, (title, when) in enumerate([("MegaCorp Breakthrough", "2026-01-01"),
                                           ("MegaCorp Announces Widget", "2026-01-02"),
                                           ("Quantum Widget from MegaCorp", "2026-01-03")]):
            write_note(
                tmp_vault.notes_dir, title, body=pr + f" Outlet {i} adds a sentence.",
                source=f"https://outlet{i}.com/story", tags=["ind-run"],
                extra_frontmatter={"created": when + "T00:00:00+00:00"},
            )
        write_note(
            tmp_vault.notes_dir, "Independent Analysis",
            body="A genuinely independent, differently-worded long analysis of quantum widgets and their many limitations in practice.",
            source="https://analyst.com/deep-dive", tags=["ind-run"],
        )
        plan = compute_sync_plan(tmp_vault, force=True)
        execute_sync(tmp_vault, plan)

        result = compute_independence(tmp_vault, tag="ind-run")
        assert len(result["clusters"]) == 1
        cluster = result["clusters"][0]
        assert cluster["size"] == 3
        assert "wire" in cluster["kind"]

        scores = {r["id"]: r["independence"] for r in tmp_vault.db.execute(
            "SELECT id, independence FROM notes WHERE independence IS NOT NULL"
        )}
        assert scores[cluster["root"]] == 1.0
        assert scores["independent-analysis"] == 1.0
        for member in cluster["members"]:
            assert scores[member] == pytest.approx(1 / 3, abs=0.001)

    def test_same_canonical_url_clusters(self, tmp_vault):
        from hyperresearch.core.note import write_note
        from hyperresearch.core.sync import compute_sync_plan, execute_sync

        write_note(tmp_vault.notes_dir, "Copy A", body="Some words here for the body.",
                   source="https://www.site.com/story?utm_source=feed")
        write_note(tmp_vault.notes_dir, "Copy B", body="Entirely different words in this body text.",
                   source="https://site.com/story/")
        plan = compute_sync_plan(tmp_vault, force=True)
        execute_sync(tmp_vault, plan)
        result = compute_independence(tmp_vault)
        assert any(c["kind"] == "url" for c in result["clusters"])
