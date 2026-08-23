"""P1-12 r2 hardening regressions (PORTING-NOTES §P1-12 "Hardening (r2 named gap)").

Closes the three r2 named gaps against the landed serve UI:

- Y-1 (MED): `status` reached `class="status {…}"` RAW — guarded elsewhere by
  NoteMeta StrEnum + schema CHECK, but the sink now defends itself (defense in
  depth, identical treatment to the word_count sink). Normal writes cannot
  produce a hostile status, so the test constructs the hostile input AT THE
  SINK BOUNDARY: a proxy over the handler's cached connection swaps the
  note-page SELECT's result row for a crafted mapping — standing in for a
  committed DB whose notes table lacks the CHECK constraint.
- Y-2 (FUNCTIONAL, inherited from upstream): the link markdown pattern ran
  BEFORE the image pattern, so `![alt](url)` was consumed as a literal `!`
  plus a `[alt](url)` link — images could never render. Fixed ordering;
  the scheme gate now provably applies to img src as well.
"""

from __future__ import annotations

import sqlite3
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path
from typing import Any

import pytest

from hyperresearch.core.note import slugify, write_note
from hyperresearch.core.sync import compute_sync_plan, execute_sync
from hyperresearch.core.vault import Vault
from hyperresearch.serve.renderer import _is_safe_url, render_markdown
from hyperresearch.serve.server import HyperresearchHandler

NOTE_TITLE = "R2 Hardening Note"
NOTE_BODY = (
    "See [the docs](https://example.com/docs) and:\n"
    "\n"
    "![flow chart](https://example.com/chart.png)\n"
)


def _note_id() -> str:
    return slugify(NOTE_TITLE)


def _get(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url) as resp:
        return resp.status, resp.read().decode("utf-8")


@pytest.fixture
def r2_vault(tmp_path: Path):
    vault = Vault.init(tmp_path / "r2-vault")
    write_note(
        vault.notes_dir,
        NOTE_TITLE,
        body=NOTE_BODY,
        tags=["r2"],
        status="evergreen",
        summary="hardening fixture",
    )
    plan = compute_sync_plan(vault, force=True)
    execute_sync(vault, plan)
    return vault


@pytest.fixture
def r2_http(r2_vault, monkeypatch: pytest.MonkeyPatch):
    """HyperresearchHandler over a real socket on an ephemeral port."""
    monkeypatch.setattr(HyperresearchHandler, "vault", r2_vault)
    monkeypatch.setattr(HyperresearchHandler, "_db", None)
    httpd = HTTPServer(("127.0.0.1", 0), HyperresearchHandler)
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        if HyperresearchHandler._db is not None:
            HyperresearchHandler._db.close()


class TestImageRendering:
    """Y-2: images render as <img>, links stay <a>, hostile img srcs drop."""

    def test_safe_image_renders_img_tag(self):
        out = render_markdown("![alt text](https://example.com/x.png)")
        assert '<img src="https://example.com/x.png" alt="alt text">' in out

    def test_safe_link_still_renders_anchor(self):
        out = render_markdown("[label](https://example.com/page)")
        assert '<a href="https://example.com/page">label</a>' in out
        assert "<img" not in out

    def test_mixed_body_renders_both(self):
        out = render_markdown(
            "see [docs](https://e.com/d) then ![pic](https://e.com/p.png)"
        )
        assert '<a href="https://e.com/d">docs</a>' in out
        assert '<img src="https://e.com/p.png" alt="pic">' in out

    @pytest.mark.parametrize(
        "url",
        [
            "/local/pic.png",
            "../relative/pic.png",
            "#anchor-not-an-image",
            "//cdn.example.com/pic.png",
            "ftp://files.example.com/pic.png",
        ],
    )
    def test_other_allowed_urls_render_as_images(self, url: str):
        assert f'<img src="{url}" alt="pic">' in render_markdown(f"![pic]({url})")

    @pytest.mark.parametrize(
        "payload",
        [
            "javascript:alert(4)",
            "JaVaScRiPt:alert(4)",
            "  javascript:alert(4)",
            "java\tscript:alert(4)",
            "data:text/html;base64,PHNjcmlwdD4=",
            "vbscript:msgbox(1)",
        ],
    )
    def test_hostile_img_src_dropped_alt_kept_as_text(self, payload: str):
        out = render_markdown(f"![pwn]({payload})")
        assert "<img" not in out
        assert "src=" not in out
        assert "pwn" in out

    @pytest.mark.parametrize(
        "payload",
        [
            "javascript:alert(1)",
            "&#106;avascript:alert(1)",  # entity-encoded (single decode)
            "java\tscript:alert(1)",  # control-split scheme
            "java\nscript:alert(1)",
            "\x01javascript:alert(1)",
        ],
    )
    def test_img_sink_scheme_gate_rejects_encoded_and_split_variants(
        self, payload: str
    ):
        """_image delegates to _is_safe_url; pin the img path's gate on the
        entity-encoded and control-split forms a browser normalizes."""
        assert not _is_safe_url(payload)

    def test_note_page_serves_real_img_over_http(self, r2_http: str):
        """End-to-end: the rendered NOTE PAGE carries the <img> element."""
        _, body = _get(f"{r2_http}/note/{_note_id()}")
        assert '<img src="https://example.com/chart.png" alt="flow chart">' in body
        assert '<a href="https://example.com/docs">the docs</a>' in body


class _CraftedRow:
    """sqlite3.Row stand-in: row["col"] access over a plain mapping."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]


class _SingleRowResult:
    def __init__(self, row: _CraftedRow) -> None:
        self._row = row

    def fetchone(self) -> _CraftedRow:
        return self._row


class _StatusInjectionDb:
    """Proxy over the handler's cached connection.

    Every query runs against the REAL vault DB except the note-page SELECT,
    whose result row is replaced with a hand-crafted mapping carrying a
    status value no CHECK constraint would ever accept. This models the
    threat honestly: normal writes cannot store such a value (both guards
    hold — re-pinned in test_server.py::TestDbTamperSinks), so the hostile
    input is constructed AT THE SINK BOUNDARY instead, standing in for a
    committed DB whose notes table lacks the CHECK."""

    _NOTE_SQL_MARK = "nc.body FROM notes n"

    def __init__(self, real: sqlite3.Connection, crafted: dict[str, Any]) -> None:
        self._real = real
        self._crafted = crafted

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        if self._NOTE_SQL_MARK in sql:
            return _SingleRowResult(_CraftedRow(self._crafted))
        return self._real.execute(sql, params)

    def close(self) -> None:
        self._real.close()


HOSTILE_STATUS = 'evergreen" onload="alert(21)"><script>alert(20)</script>'


class TestStatusSinkEscape:
    """Y-1: class="status {…}" escapes at the sink regardless of the schema
    CHECK / StrEnum guards upstream relies on (defense in depth)."""

    def test_hostile_status_cannot_break_out_of_the_class_attribute(
        self, r2_http: str, monkeypatch: pytest.MonkeyPatch
    ):
        vault = HyperresearchHandler.vault
        assert vault is not None
        real = sqlite3.connect(str(vault.db_path), check_same_thread=False)
        real.row_factory = sqlite3.Row
        base = real.execute(
            "SELECT n.*, nc.body FROM notes n "
            "JOIN note_content nc ON n.id = nc.note_id WHERE n.id = ?",
            (_note_id(),),
        ).fetchone()
        # zip, not `for k in base`: sqlite3.Row iteration yields VALUES.
        crafted: dict[str, Any] = dict(zip(base.keys(), base, strict=True))
        crafted["status"] = HOSTILE_STATUS
        monkeypatch.setattr(
            HyperresearchHandler, "_db", _StatusInjectionDb(real, crafted)
        )

        code, body = _get(f"{r2_http}/note/{_note_id()}")

        assert code == 200
        # No raw quote breakout: the smuggled attribute cannot survive.
        assert '" onload="' not in body
        assert "<script>alert(20)" not in body
        # The payload arrives as entities INSIDE the class attribute…
        assert '<span class="status evergreen&quot; onload=&quot;alert(21)' in body
        assert "&lt;script&gt;alert(20)&lt;/script&gt;" in body

    def test_legal_enum_still_renders_plainly_in_class(self, r2_http: str):
        _, body = _get(f"{r2_http}/note/{_note_id()}")
        assert 'class="status evergreen"' in body
