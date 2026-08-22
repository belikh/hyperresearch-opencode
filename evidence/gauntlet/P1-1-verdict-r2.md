# P1-1 gauntlet round 2 — VERDICT: ours (treeB) wins blind
Staged full trees, no content mangling (protocol v2). Resolution-proof runs.
- Ours: 90 passed / 2 skipped / 0 failed; mypy --strict: 0 errors (18 files).
- Upstream-in-env: collection abort (unguarded crawl4ai test import) + 13 failed/9 errors without crawl4ai; mypy --strict: 376 errors (57 files).
- Shared latent bugs (inherited by BOTH from upstream, empirically reproduced):
  1. CRITICAL migrations.py:90,156 DROP TABLE notes under foreign_keys=ON -> ON DELETE CASCADE wipes tags/note_content/embeddings/claims/assets on legacy-vault auto-migration (vault.py:44). Silent data destruction.
  2. HIGH migration fragility: rebuild tables lack IF NOT EXISTS; executescript auto-commits pre-run (:53,:121,:155); crash mid-rebuild bricks vault ("table notes_v7 already exists" forever); version stamping papers over dict gaps (:339-349).
  3. MEDIUM config.py:312-313 _toml_value does not escape quotes/backslashes/newlines -> invalid TOML round-trip (reproduced).
  4. LOW-MED models/note.py:127-130 tag validator iterates str char-by-char: tags: research -> ['r','e','s',...] (reproduced).
  5. LOW dead knob exclude_patterns consumed nowhere; TOCTOU in write_note collision loop; slugify symbol-title seed collision.
Disposition: items 1-4 = fix-in-port as documented deltas (data-loss/corruption trumps verbatim); item 5 = file, fix opportunistically.
