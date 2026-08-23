"""Server-level tests for hyperresearch.serve — real HTTP on ephemeral ports.

Upstream ships only renderer-level XSS tests (test_xss.py). These tests drive
the actual HyperresearchHandler over real sockets bound to an ephemeral port,
per the P1-12 mission: route smoke, 404 behavior, content-type sanity, and a
full-server XSS battery against a hostile vault whose note title/body/tags/
summary all carry payloads.

Threat model (mirrors upstream's own comments): note bodies are fetched REMOTE
pages, so titles/bodies/tags/summaries are attacker-influenced; the viewer's
browser must never receive them as live markup.
"""

from __future__ import annotations

import json
import socket
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer
from pathlib import Path
from typing import Any

import pytest

from hyperresearch.core.note import slugify, write_note
from hyperresearch.core.sync import compute_sync_plan, execute_sync
from hyperresearch.core.vault import Vault
from hyperresearch.serve.server import HyperresearchHandler, run_server

# -- Hostile vault fixture data -------------------------------------------------

HOSTILE_TITLE = '<script>alert("title")</script> Hostile Note'
HOSTILE_TAGS = [
    "<script>alert('tag')</script>",
    "<img src=x onerror=alert(9)>",
    "plain-tag",
]
HOSTILE_SUMMARY = '<script>alert("summary")</script> hostile summary'

# Body payloads: raw script tags, broken img with event handler, javascript:
# link/image schemes, a quote-smuggling attribute breakout attempt, hostile
# wiki-link target AND display, plus search-snippet marker bait placed
# mid-line (leading text so strip_markdown cannot eat it as a blockquote).
HOSTILE_BODY = (
    "# <script>alert(1)</script>\n"
    "\n"
    "<img src=x onerror=alert(document.domain)>\n"
    "\n"
    "<script>alert(2)</script>\n"
    "\n"
    "[click me](javascript:alert(3))\n"
    "\n"
    "![pwn](javascript:alert(4))\n"
    "\n"
    '[attr](https://example.com/x" onmouseover="alert(5))\n'
    "\n"
    "[[<img src=x onerror=alert(6)>]]\n"
    "\n"
    "[[plain-target|<script>alert(7)</script>]]\n"
    "\n"
    "context >>>hit<<< <img src=x onerror=alert(8) text\n"
    "\n"
    "ordinary prose for the snippet window.\n"
)


def _sync(vault: Vault) -> None:
    plan = compute_sync_plan(vault, force=True)
    execute_sync(vault, plan)


@pytest.fixture
def hostile_vault(tmp_path: Path) -> Vault:
    """A vault whose notes carry XSS payloads in every free-text field."""
    vault = Vault.init(tmp_path / "serve-vault")
    hid = slugify(HOSTILE_TITLE)
    write_note(
        vault.notes_dir,
        HOSTILE_TITLE,
        body=HOSTILE_BODY,
        tags=list(HOSTILE_TAGS),
        status="evergreen",
        summary=HOSTILE_SUMMARY,
    )
    # A benign note linking at the hostile one → backlink section rendering.
    write_note(
        vault.notes_dir,
        "Benign Anchor",
        body=f"See [[{hid}]] for the hostile note.\n",
        tags=["benign"],
        summary="benign",
    )
    _sync(vault)
    return vault


@pytest.fixture
def http_server(hostile_vault: Vault, monkeypatch: pytest.MonkeyPatch):
    """HyperresearchHandler over a real socket on an ephemeral port."""
    monkeypatch.setattr(HyperresearchHandler, "vault", hostile_vault)
    monkeypatch.setattr(HyperresearchHandler, "_db", None)
    httpd = HTTPServer(("127.0.0.1", 0), HyperresearchHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        yield base
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        if HyperresearchHandler._db is not None:
            HyperresearchHandler._db.close()


def _get(url: str) -> tuple[int, str, dict[str, str]]:
    """GET a URL; returns (status, body_text, headers). Never raises on 4xx/5xx."""
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, resp.read().decode("utf-8"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), dict(e.headers)


def _note_id() -> str:
    return slugify(HOSTILE_TITLE)


def _assert_payload_inert(page: str) -> None:
    """No payload survives as markup anywhere in a rendered page.

    Escaped forms MUST be present (proof the fixture really flowed through),
    raw markup forms MUST be absent. The page template legitimately contains
    its own <script> blocks (DRAG_JS), so payload signatures are asserted,
    not bare "<script".
    """
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page
    assert "<img src=x" not in page
    assert "&lt;img src=x" in page
    # Attribute breakouts via smuggled quotes must not survive unescaped.
    assert '" onmouseover="alert' not in page


class TestRouteSmoke:
    @pytest.mark.parametrize(
        "route",
        [
            "/",
            "",
            "/tags",
            "/graph",
            "/api/graph",
            "/search?q=prose",
            "/search",
        ],
    )
    def test_routes_answer_200(self, http_server: str, route: str):
        code, _, _ = _get(http_server + route)
        assert code == 200

    def test_note_page_200(self, http_server: str):
        code, body, _ = _get(f"{http_server}/note/{_note_id()}")
        assert code == 200
        assert "hostile" in body.lower()

    def test_tag_page_200(self, http_server: str):
        tag = urllib.parse.quote("plain-tag", safe="")
        code, body, _ = _get(f"{http_server}/tag/{tag}")
        assert code == 200
        assert "Tag: plain-tag" in body

    def test_index_lists_hostile_note_with_escaped_summary(self, http_server: str):
        code, body, _ = _get(http_server + "/")
        assert code == 200
        assert f'href="/note/{_note_id()}"' in body
        # Summary escaped in the index listing.
        assert "&lt;script&gt;alert(&quot;summary&quot;)&lt;/script&gt;" in body
        assert "<script>alert(" not in body


class TestNotFound:
    def test_unknown_route_is_404(self, http_server: str):
        code, body, _ = _get(http_server + "/no-such-route")
        assert code == 404
        assert "<h1>Not Found</h1>" in body

    def test_missing_note_reflects_id_escaped(self, http_server: str):
        payload = "<script>alert(404)</script>"
        quoted = urllib.parse.quote(payload, safe="")
        code, body, _ = _get(f"{http_server}/note/{quoted}")
        assert code == 404
        assert "&lt;script&gt;alert(404)&lt;/script&gt;" in body
        assert "<script>alert(404)" not in body


class TestContentTypes:
    def test_html_pages_declare_utf8(self, http_server: str):
        _, _, headers = _get(http_server + "/")
        assert headers["Content-Type"] == "text/html; charset=utf-8"

    def test_graph_api_is_json(self, http_server: str):
        code, body, headers = _get(http_server + "/api/graph")
        assert code == 200
        assert headers["Content-Type"] == "application/json"
        data: dict[str, Any] = json.loads(body)
        ids = {n["id"] for n in data["nodes"]}
        assert _note_id() in ids


class TestXssBattery:
    def test_note_page_renders_all_payloads_inert(self, http_server: str):
        code, body, _ = _get(f"{http_server}/note/{_note_id()}")
        assert code == 200
        _assert_payload_inert(body)

        # <title> carries the escaped note title.
        assert "<title>&lt;script&gt;alert(&quot;title&quot;)&lt;/script&gt;" in body
        # Status chip: valid enum renders normally inside the class attribute.
        assert 'class="status evergreen"' in body
        # Tag chips escaped in both href and label (' → &#x27;).
        assert '<a href="/tag/&lt;script&gt;alert(&#x27;tag&#x27;)&lt;/script&gt;" class="tag">' in body
        assert "<a href=\"/tag/<script>" not in body

        # javascript: link scheme dropped, label kept as plain text.
        assert 'href="javascript:' not in body
        assert "click me" in body
        # javascript: image scheme dropped too — _is_safe_url gates img src
        # as well (r2 fixed the link-before-image ordering, so images now
        # render; hostile srcs still drop and alt stays as text — see
        # test_r2_hardening.py).
        assert '<img src="javascript:' not in body
        # Wiki-link target arrives escaped (whole-body escape runs before the
        # wiki regex, so even angle-bracket targets are inert entities).
        assert 'href="/note/&lt;img src=x onerror=alert(6)&gt;"' in body
        assert "<a href=\"/note/<img" not in body

    def test_nav_recent_links_escaped(self, http_server: str):
        _, body, _ = _get(http_server + "/tags")
        # The nav sidebar lists recent notes — hostile title must be inert there.
        _assert_payload_inert(body)

    def test_tags_page_escapes_hostile_tag(self, http_server: str):
        code, body, _ = _get(http_server + "/tags")
        assert code == 200
        assert "&lt;script&gt;alert(&#x27;tag&#x27;)&lt;/script&gt;" in body
        assert "&lt;img src=x onerror=alert(9)&gt;" in body
        assert "<a href=\"/tag/<script>" not in body
        assert "<a href=\"/tag/<img" not in body

    def test_tag_page_escapes_url_tag_and_rows(self, http_server: str):
        tag = urllib.parse.quote("<script>alert('tag')</script>", safe="")
        code, body, _ = _get(f"{http_server}/tag/{tag}")
        assert code == 200
        assert "<h1>Tag: &lt;script&gt;alert(&#x27;tag&#x27;)&lt;/script&gt;</h1>" in body
        assert "<script>alert('tag')" not in body
        # The hostile note itself is listed with an escaped title link.
        assert f'<a href="/note/{_note_id()}">' in body

    def test_search_reflection_escaped(self, http_server: str):
        q = urllib.parse.quote("<script>alert(11)</script>", safe="")
        code, body, _ = _get(f"{http_server}/search?q={q}")
        assert code == 200
        # Reflected in both <h1> and <title>, escaped either way.
        assert "<h1>Search: &lt;script&gt;alert(11)&lt;/script&gt;</h1>" in body
        assert "<title>Search: &lt;script&gt;" in body
        assert "<script>alert(11)" not in body

    def test_search_snippet_markers_survive_payload_does_not(self, http_server: str):
        code, body, _ = _get(f"{http_server}/search?q=hit")
        assert code == 200
        assert "<mark>hit</mark>" in body
        # The unterminated-tag bait must not borrow the </mark> closer.
        assert "<img" not in body
        assert "&lt;img src=x onerror=alert(8)" in body

    def test_backlinks_section_escaped(self, http_server: str):
        code, body, _ = _get(f"{http_server}/note/{_note_id()}")
        assert code == 200
        assert "Backlinks" in body
        assert f'<a href="/note/{slugify("Benign Anchor")}">Benign Anchor</a>' in body


class TestDbTamperSinks:
    """Sink audit outcomes against crafted DB bytes.

    Vault directories are git repositories, so a committed hyperresearch.db
    makes another writer's rows this UI's input. Two raw sinks were probed:
    - status (class="" attr): verified NOT injectable — the schema itself
      CHECK-constrains the column, so even direct SQL tampering is refused
      (pinned here as the permanent probe result; upstream-verbatim code).
    - word_count: WAS injectable upstream (no schema guard; SQLite INTEGER
      affinity stores non-numeric text verbatim). Fixed in-port as a
      documented delta; this test FAILS against verbatim-upstream rendering.
    """

    def _tamper(self, monkeypatch: pytest.MonkeyPatch, **cols: str) -> None:
        vault = HyperresearchHandler.vault
        assert vault is not None
        conn = sqlite3.connect(str(vault.db_path))
        assignments = ", ".join(f"{k} = ?" for k in cols)
        conn.execute(
            f"UPDATE notes SET {assignments} WHERE id = ?",
            (*cols.values(), _note_id()),
        )
        conn.commit()
        conn.close()
        # The handler caches its connection; force a reopen against the file.
        if HyperresearchHandler._db is not None:
            HyperresearchHandler._db.close()
        monkeypatch.setattr(HyperresearchHandler, "_db", None)

    def test_hostile_status_is_refused_by_schema_even_under_direct_sql(
        self, http_server: str, monkeypatch: pytest.MonkeyPatch
    ):
        vault = HyperresearchHandler.vault
        assert vault is not None
        conn = sqlite3.connect(str(vault.db_path))
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            conn.execute(
                "UPDATE notes SET status = ? WHERE id = ?",
                ('evergreen" onload="alert(12)', _note_id()),
            )
        conn.close()

    def test_hostile_db_word_count_rendered_inert(
        self, http_server: str, monkeypatch: pytest.MonkeyPatch
    ):
        self._tamper(monkeypatch, word_count='3"><script>alert(13)</script>')
        code, body, _ = _get(f"{http_server}/note/{_note_id()}")
        assert code == 200
        # Pre-fix this page contained the payload as live markup.
        assert "<script>alert(13)" not in body
        assert "&lt;script&gt;alert(13)&lt;/script&gt;" in body


class TestLazyDepsAndBind:
    def test_db_connection_created_lazily_on_first_request(self, http_server: str):
        # Fixture reset it; no request has been served yet.
        assert HyperresearchHandler._db is None
        code, _, _ = _get(http_server + "/api/graph")
        assert code == 200
        assert isinstance(HyperresearchHandler._db, sqlite3.Connection)

    def test_bind_conflict_raises_oserror(self, hostile_vault: Vault):
        blocker = socket.socket()
        try:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen(1)
            busy_port = blocker.getsockname()[1]
            with pytest.raises(OSError):
                run_server(hostile_vault, port=busy_port)
        finally:
            blocker.close()
