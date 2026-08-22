"""P1-4 hardening: SSRF containment for fetch lanes + exact-host arXiv checks.

Every regression here was demonstrated to FAIL against pre-fix code
(git-stash round): pre-fix, `_fetch_pdf` and the builtin HTML lanes fetched
any scheme at any address and auto-followed redirects into loopback
(`follow_redirects=True`, urllib default handler), and
`notarxiv.org.evil.com` lane-chose as arXiv via substring matching.

Offline throughout: DNS is stubbed per-test (same pattern as
tests/test_core/test_oa_recovery.py) and httpx.get is replaced with canned
responses — no packet leaves the machine.
"""

from __future__ import annotations

import logging
import urllib.request

import pytest

from hyperresearch.web import _netguard, builtin
from hyperresearch.web._netguard import UnsafeUrlError
from hyperresearch.web.crawl4ai_provider import _fetch_pdf, _is_pdf_url

# ---------------------------------------------------------------------------
# Offline stubs
# ---------------------------------------------------------------------------


def _info(addr: str):
    """A getaddrinfo result tuple shaped like the real thing."""
    if ":" in addr:
        return (10, 1, 6, "", (addr, 0, 0, 0))
    return (2, 1, 6, "", (addr, 0))


def resolve_everything_to(monkeypatch, *addresses: str):
    """Pin THE SAME getaddrinfo answer(s) for every hostname — deterministic,
    no network. Multiple addresses model multi-record hosts."""
    infos = [_info(a) for a in addresses]
    monkeypatch.setattr(_netguard.socket, "getaddrinfo", lambda host, port: list(infos))


def resolve_hosts(monkeypatch, overrides: dict[str, str]):
    """Per-host canned answers; any unlisted host resolves to a public IP."""
    table = dict(overrides)

    def fake(host, port):
        return [_info(table.get(host, "93.184.216.34"))]

    monkeypatch.setattr(_netguard.socket, "getaddrinfo", fake)


class _Resp:
    """Minimal httpx.Response stand-in covering every consumer shape here."""

    def __init__(self, url: str, status_code: int = 200, headers: dict | None = None,
                 content: bytes = b"", text: str = ""):
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content
        self._text = text

    @property
    def text(self) -> str:
        return self._text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def httpx_stub(monkeypatch):
    """Script httpx.get responses; records every requested URL.

    Asserts follow_redirects=False on every call — manual hop validation is
    the whole point of the fix.
    """
    calls: list[str] = []
    script: list[_Resp] = []

    def fake_get(url, **kwargs):
        calls.append(str(url))
        assert kwargs.get("follow_redirects") is False, "redirects must be manual"
        if not script:
            pytest.fail(f"unexpected httpx request to {url}")
        return script.pop(0)

    monkeypatch.setattr("httpx.get", fake_get)

    class _Stub:
        @property
        def calls(self) -> list[str]:
            return calls

        def enqueue(self, *responses: _Resp) -> None:
            script.extend(responses)

    return _Stub()


# ---------------------------------------------------------------------------
# validate_url_public
# ---------------------------------------------------------------------------


class TestValidateUrlPublic:
    def test_accepts_public_https_url(self, monkeypatch):
        resolve_everything_to(monkeypatch, "93.184.216.34")
        assert _netguard.validate_url_public("https://example.org/paper.pdf")

    def test_rejects_non_http_scheme(self):
        with pytest.raises(UnsafeUrlError, match="scheme"):
            _netguard.validate_url_public("file:///etc/passwd")

    def test_rejects_missing_hostname(self):
        with pytest.raises(UnsafeUrlError, match="no hostname"):
            _netguard.validate_url_public("http:///path/x")

    def test_rejects_embedded_credentials(self):
        with pytest.raises(UnsafeUrlError, match="credentials"):
            _netguard.validate_url_public("https://user:pw@example.org/x")

    def test_rejects_loopback_ip_literal(self, monkeypatch):
        # The gauntlet PoC URL, verbatim shape.
        resolve_everything_to(monkeypatch, "127.0.0.1")
        with pytest.raises(UnsafeUrlError, match=r"127\.0\.0\.1 \(loopback\)"):
            _netguard.validate_url_public("http://127.0.0.1:8000/hr/salaries.pdf")

    def test_rejects_ipv6_loopback_literal(self, monkeypatch):
        resolve_everything_to(monkeypatch, "::1")
        with pytest.raises(UnsafeUrlError, match="loopback"):
            _netguard.validate_url_public("http://[::1]/salaries.pdf")

    def test_rejects_dns_name_resolving_to_loopback(self, monkeypatch):
        resolve_everything_to(monkeypatch, "127.0.0.1")
        with pytest.raises(UnsafeUrlError, match="non-public address"):
            _netguard.validate_url_public("https://public-looking.example/hr/salaries.pdf")

    def test_rejects_cloud_metadata_service_address(self, monkeypatch):
        resolve_everything_to(monkeypatch, "169.254.169.254")
        with pytest.raises(UnsafeUrlError, match=r"169\.254\.169\.254 \(link-local\)"):
            _netguard.validate_url_public(
                "https://metadata.internal.example/latest/meta-data/"
            )

    @pytest.mark.parametrize(
        "address",
        [
            "10.1.2.3",  # RFC1918
            "192.168.1.10",
            "172.16.0.9",
            "fdaa::5",  # fc00::/7 unique-local
            "fe80::1",  # fe80::/10 link-local
            "0.0.0.0",  # unspecified
            "::",
            "192.0.2.7",  # documentation (TEST-NET-1)
            "2001:db8::1",  # documentation
        ],
    )
    def test_rejects_non_routable_ranges(self, monkeypatch, address):
        resolve_everything_to(monkeypatch, address)
        with pytest.raises(UnsafeUrlError, match="non-public address"):
            _netguard.validate_url_public(f"https://host.example/fetch?ip={address}")

    def test_every_resolved_address_must_be_public(self, monkeypatch):
        # A mixed record set: one public entry cannot launder a private one.
        resolve_everything_to(monkeypatch, "93.184.216.34", "10.0.0.5")
        with pytest.raises(UnsafeUrlError, match="10\\.0\\.0\\.5"):
            _netguard.validate_url_public("https://dual-homed.example/x")

    def test_rejects_unresolvable_host(self, monkeypatch):
        def boom(host, port):
            raise OSError("[Errno -2] Name or service not known")

        monkeypatch.setattr(_netguard.socket, "getaddrinfo", boom)
        with pytest.raises(UnsafeUrlError, match="DNS resolution failed"):
            _netguard.validate_url_public("https://nowhere.example.org/x")


# ---------------------------------------------------------------------------
# guarded_get — httpx lane with per-hop validation
# ---------------------------------------------------------------------------


class TestGuardedGet:
    def test_returns_terminal_response_without_following(self, monkeypatch, httpx_stub):
        resolve_everything_to(monkeypatch, "93.184.216.34")
        final = _Resp("https://example.org/paper.pdf", content=b"%PDF-1.4 rest")
        httpx_stub.enqueue(final)

        resp = _netguard.guarded_get("https://example.org/paper.pdf", timeout=30)

        assert resp is final
        assert httpx_stub.calls == ["https://example.org/paper.pdf"]

    def test_follows_relative_public_redirect(self, monkeypatch, httpx_stub):
        resolve_everything_to(monkeypatch, "93.184.216.34")
        httpx_stub.enqueue(
            _Resp("https://example.org/d/1", status_code=302,
                  headers={"location": "/real/paper.pdf"}),
            _Resp("https://example.org/real/paper.pdf", content=b"%PDF-1.4"),
        )

        resp = _netguard.guarded_get("https://example.org/d/1", timeout=30)

        assert resp.status_code == 200
        assert httpx_stub.calls == [
            "https://example.org/d/1",
            "https://example.org/real/paper.pdf",
        ]

    def test_redirect_into_loopback_never_requested(self, monkeypatch, httpx_stub):
        """The verdict's public-shaped 302 -> loopback PoC, now dead."""
        resolve_hosts(monkeypatch, {"127.0.0.1": "127.0.0.1"})
        httpx_stub.enqueue(
            _Resp("https://public.example/landing", status_code=302,
                  headers={"location": "http://127.0.0.1/vault/salaries.pdf"}),
        )

        with pytest.raises(UnsafeUrlError, match="loopback"):
            _netguard.guarded_get("https://public.example/landing", timeout=30)

        assert httpx_stub.calls == ["https://public.example/landing"], (
            "the loopback hop must be rejected BEFORE its request is issued"
        )

    def test_redirect_to_new_host_is_revalidated(self, monkeypatch, httpx_stub):
        resolve_hosts(monkeypatch, {"intranet.internal": "192.168.0.44"})
        httpx_stub.enqueue(
            _Resp("https://public.example/r", status_code=302,
                  headers={"location": "http://intranet.internal/vault"}),
        )

        with pytest.raises(UnsafeUrlError, match="192\\.168\\.0\\.44"):
            _netguard.guarded_get("https://public.example/r", timeout=30)

    def test_non_http_location_scheme_rejected(self, monkeypatch, httpx_stub):
        resolve_everything_to(monkeypatch, "93.184.216.34")
        httpx_stub.enqueue(
            _Resp("https://public.example/r", status_code=302,
                  headers={"location": "file:///etc/passwd"}),
        )

        with pytest.raises(UnsafeUrlError, match="scheme"):
            _netguard.guarded_get("https://public.example/r", timeout=30)

    def test_more_than_five_hops_raises(self, monkeypatch, httpx_stub):
        resolve_everything_to(monkeypatch, "93.184.216.34")
        chain = [
            _Resp(f"https://example.org/hop{i}", status_code=302,
                  headers={"location": f"https://example.org/hop{i + 1}"})
            for i in range(6)
        ]
        httpx_stub.enqueue(*chain)

        with pytest.raises(UnsafeUrlError, match="more than 5 redirects"):
            _netguard.guarded_get("https://example.org/hop0", timeout=30)


# ---------------------------------------------------------------------------
# GuardedRedirectHandler — the stdlib fallback lane
# ---------------------------------------------------------------------------


class TestGuardedRedirectHandler:
    @staticmethod
    def _hop(handler, newurl):
        req = urllib.request.Request("https://origin.example/start")
        return handler.redirect_request(req, None, 302, "Found", {}, newurl)

    def test_handler_blocks_loopback_hop(self, monkeypatch):
        resolve_everything_to(monkeypatch, "127.0.0.1")
        with pytest.raises(UnsafeUrlError, match="loopback"):
            self._hop(_netguard.GuardedRedirectHandler(),
                      "http://127.0.0.1/vault/salaries.pdf")

    def test_handler_passes_public_hop_through(self, monkeypatch):
        resolve_everything_to(monkeypatch, "93.184.216.34")
        followed = self._hop(_netguard.GuardedRedirectHandler(),
                             "https://dest.example/paper")
        assert isinstance(followed, urllib.request.Request)
        assert followed.full_url == "https://dest.example/paper"


# ---------------------------------------------------------------------------
# Lane integration: the verdict's PoCs end-to-end through the real provider
# functions (network fully stubbed).
# ---------------------------------------------------------------------------


class TestFetchPdfContainment:
    def test_loopback_literal_blocked_with_clear_log(self, monkeypatch, httpx_stub, caplog):
        resolve_everything_to(monkeypatch, "127.0.0.1")

        with caplog.at_level(logging.WARNING, logger="hyperresearch.pdf"):
            assert _fetch_pdf("http://127.0.0.1:8000/hr/salaries.pdf") is None

        assert "blocked by SSRF guard" in caplog.text
        assert "loopback" in caplog.text
        assert httpx_stub.calls == [], "nothing may be requested at a blocked URL"

    def test_public_shaped_redirect_into_loopback_blocked(
        self, monkeypatch, httpx_stub, caplog
    ):
        """Verdict PoC: attacker page answers 302 -> http://127.0.0.1/..."""
        resolve_hosts(monkeypatch, {"127.0.0.1": "127.0.0.1"})
        httpx_stub.enqueue(
            _Resp("https://attacker.example/open-this.pdf", status_code=302,
                  headers={"location": "http://127.0.0.1:8000/hr/salaries.pdf"}),
        )

        with caplog.at_level(logging.WARNING, logger="hyperresearch.pdf"):
            assert _fetch_pdf("https://attacker.example/open-this.pdf") is None

        assert "blocked by SSRF guard" in caplog.text
        assert httpx_stub.calls == ["https://attacker.example/open-this.pdf"], (
            "the redirect target must die at validation, not at connect time"
        )


class TestBuiltinLaneContainment:
    def test_fetch_blocks_loopback_start(self, monkeypatch, httpx_stub):
        resolve_everything_to(monkeypatch, "127.0.0.1")
        with pytest.raises(UnsafeUrlError, match="loopback"):
            builtin.BuiltinProvider().fetch("http://127.0.0.1/x")
        assert httpx_stub.calls == []

    def test_httpx_html_lane_redirect_to_loopback_blocked(self, monkeypatch, httpx_stub):
        resolve_hosts(monkeypatch, {"127.0.0.1": "127.0.0.1"})
        httpx_stub.enqueue(
            _Resp("https://public.example/article", status_code=302,
                  headers={"location": "http://127.0.0.1/admin"}),
        )
        with pytest.raises(UnsafeUrlError, match="loopback"):
            builtin.BuiltinProvider().fetch("https://public.example/article")
        assert httpx_stub.calls == ["https://public.example/article"]

    def test_stdlib_fallback_lane_routes_through_guarded_urlopen(self, monkeypatch):
        """Without httpx, the urllib fallback must go through the validating
        opener (guarded_urlopen), not raw urlopen."""
        resolve_everything_to(monkeypatch, "93.184.216.34")
        seen: list[str] = []

        class _FakeResponse:
            url = "https://plain.example/page"

            def read(self):
                return b"<html><title>Page</title><body>hello body</body></html>"

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_open(url, *, timeout):
            seen.append(url)
            return _FakeResponse()

        def no_httpx(*args, **kwargs):
            raise ImportError("forced off for the stdlib-lane test")

        monkeypatch.setattr(builtin, "guarded_get", no_httpx)
        monkeypatch.setattr(builtin, "guarded_urlopen", fake_open)

        html, final = builtin.BuiltinProvider()._download("https://plain.example/page")

        assert seen == ["https://plain.example/page"]
        assert final == "https://plain.example/page"
        assert "hello body" in html


# ---------------------------------------------------------------------------
# arXiv exact-host matching (LOW finding)
# ---------------------------------------------------------------------------


class TestArxivExactHost:
    def test_spoofed_suffix_does_not_lane_choose(self):
        assert _is_pdf_url("https://notarxiv.org.evil.com/abs/2401.00123") is False

    def test_spoofed_prefix_does_not_lane_choose(self):
        assert _is_pdf_url("https://arxiv.org.evil.com/notarxiv.org/abs/1") is False

    def test_real_arxiv_still_lane_chooses(self):
        assert _is_pdf_url("https://arxiv.org/pdf/2401.12345v2") is True

    def test_arxiv_subdomain_still_lane_chooses(self):
        assert _is_pdf_url("https://export.arxiv.org/abs/2401.12345") is True

    def test_abs_rewrite_requires_arxiv_host(self, monkeypatch, httpx_stub):
        resolve_everything_to(monkeypatch, "93.184.216.34")
        evil = "https://notarxiv.org.evil.com/arxiv.org/abs/2401.00123"
        httpx_stub.enqueue(_Resp(evil, content=b"<html>not a pdf</html>"))

        _fetch_pdf(evil)

        assert httpx_stub.calls == [evil], (
            "non-arXiv hosts must NOT get the /abs/ -> /pdf/ rewrite"
        )

    def test_legit_abs_link_still_rewritten(self, monkeypatch, httpx_stub):
        resolve_everything_to(monkeypatch, "93.184.216.34")
        expected = "https://arxiv.org/pdf/2401.00123.pdf"
        httpx_stub.enqueue(_Resp(expected, content=b"%PDF-1.4"))

        _fetch_pdf("https://arxiv.org/abs/2401.00123")

        assert httpx_stub.calls == [expected]
