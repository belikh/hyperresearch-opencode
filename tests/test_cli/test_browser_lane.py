"""P6-B tests: browser-lane escalation-drain semantics through `hpr fetch`.

The contract (issue #2):

* Bot-wall-shaped junk (non-captcha) retries ONCE through the Browser Run
  lane when `[web] browser_lane` is enabled; a successful, non-junk retry
  saves the note with `fetch_provider: browser-run` provenance.
* CAPTCHA junk NEVER takes the lane — a rendered page cannot solve a human
  challenge; it escalates as needs_human-ward `captcha` directly.
* Login walls NEVER take the lane — same policy, the human's.
* Lane-off (default): the pre-P6 escalation behaviour is byte-identical.
* Lane failures (auth/API) degrade to the pre-lane path — the escalation
  still enqueues.

Zero network: the primary provider is faked via resolve_web_provider
monkeypatching (the established fetch-test seam) and the lane via the
provider's _transport through a module-level patch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from hyperresearch.cli import app

runner = CliRunner()


def _init_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "kb"
    result = runner.invoke(app, ["init", str(root), "--name", "P6"])
    assert result.exit_code == 0, result.output
    monkeypatch.chdir(root)
    return root


def _set_config(root: Path, key: str, value: str) -> None:
    from hyperresearch.core.config import VaultConfig
    from hyperresearch.core.vault import Vault

    vault = Vault.discover()
    cfg = vault.config
    setattr(cfg, key, value)
    cfg.save(vault.config_path)


BOT_WALL_BODY = (
    "<html><head><title>Just a moment...</title></head>"
    "<body>Checking your browser before accessing the site. Ray ID: abc123. "
    "Performance and security by the edge network. This process is automatic, "
    "the browser will redirect to the requested page once the checks complete. "
    "DDoS protection by the service provider. Unusual activity pattern matched "
    "by heuristic filters. Enable JavaScript and cookies to continue browsing. "
    "The request will proceed shortly after validation finishes on the edge.</body></html>"
)
CAPTCHA_BODY = (
    "<html><head><title>Security check</title></head>"
    "<body>Please complete the CAPTCHA puzzle below to verify you are human. "
    "Enter the characters you see in the image and submit the form to continue. "
    "The security challenge requires human interaction to solve and cannot be "
    "automated. Complete the verification widget to prove this is not a bot. "
    "If the challenge fails, reload the page for a new puzzle to solve.</body></html>"
)
LOGIN_BODY = (
    "<html><head><title>Sign in</title></head>"
    "<body><form>Log in to your account</form></body></html>"
)
GOOD_BODY = (
    "<html><head><title>Real Page</title></head>"
    "<body><p>Substantive article content with enough text to pass every "
    "junk gate in the pipeline including the length minimum. This body deliberately exceeds the three-hundred-character minimum so the junk gakes see real content: it discusses the article thesis, cites two numbers (42 and 7), and closes with a summary sentence.</p></body></html>"
)


class _FakeResult:
    """Duck-typed WebResult factory for canned primary-provider responses."""

    def __init__(self, url: str, body: str) -> None:
        self._url = url
        self._body = body
        self.served = False

    def __call__(self) -> Any:
        from datetime import UTC, datetime

        from hyperresearch.web.base import WebResult

        self.served = True
        return WebResult(
            url=self._url,
            title="wall",
            content=self._body,
            fetched_at=datetime.now(UTC),
            raw_html=self._body,
        )


def _fake_chain(results: list[Any]):
    """Chain that serves the canned results in order (then repeats the last)."""
    state = {"i": 0}

    class _Fake:
        name = "fake-primary"

        def fetch(self, url: str) -> Any:
            r = results[min(state["i"], len(results) - 1)]
            state["i"] += 1
            return r() if callable(r) else r

    return _Fake()


def _patch_primary(monkeypatch: pytest.MonkeyPatch, fake: Any) -> None:
    # The established seam: cli/fetch imports resolve_web_provider lazily
    # from hyperresearch.web.base, so patch it THERE (test_search_web
    # precedent). The lambda signature swallows the kwargs fetch passes.
    monkeypatch.setattr(
        "hyperresearch.web.base.resolve_web_provider",
        lambda spec, **kwargs: fake,
    )


def _patch_lane(monkeypatch: pytest.MonkeyPatch, body: str | None) -> dict[str, Any]:
    """Patch BrowserRunProvider in the fetch module to a mock-transport lane.

    body=None makes the lane raise BrowserRunApiError (lane unavailable).
    """
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        if body is None:
            return httpx.Response(503, text="lane down")
        return httpx.Response(
            200, json={"success": True, "result": body}
        )

    real_cls = pytest.importorskip(
        "hyperresearch.web.browser_run_provider"
    ).BrowserRunProvider

    class _Lane(real_cls):
        def __init__(self, *a: Any, **kw: Any) -> None:
            super().__init__(*a, _transport=httpx.MockTransport(handler), **kw)

    # The fetch path imports the class lazily from the provider module —
    # one patch covers both import spellings.
    monkeypatch.setattr(
        "hyperresearch.web.browser_run_provider.BrowserRunProvider", _Lane
    )
    monkeypatch.setenv("CLOUDFLARE_BROWSER_RUN_TOKEN", "tok")
    monkeypatch.setenv("CF_ACCOUNT_ID", "acc")
    return seen


# ---------------------------------------------------------------------------
# Bot wall → lane retry succeeds
# ---------------------------------------------------------------------------


def test_bot_wall_retries_via_lane_and_saves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _init_vault(tmp_path, monkeypatch)
    _set_config(root, "web_browser_lane", True)
    _patch_primary(
        monkeypatch, _fake_chain([_FakeResult("https://site.com/article", BOT_WALL_BODY)])
    )
    _patch_lane(monkeypatch, GOOD_BODY)

    result = runner.invoke(app, ["fetch", "https://site.com/article", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)["data"]
    assert data["provider"] == "browser-run"

    # The note carries browser-run provenance in frontmatter.
    note_path = next((root / "research" / "notes").glob("*.md"))
    text = note_path.read_text(encoding="utf-8")
    assert "fetch_provider: browser-run" in text
    assert "Real Page" in text or "Substantive article" in text


def test_bot_wall_lane_off_escalates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default config: byte-identical pre-P6 behaviour — junk + escalation."""
    root = _init_vault(tmp_path, monkeypatch)
    _patch_primary(
        monkeypatch, _fake_chain([_FakeResult("https://site.com/article", BOT_WALL_BODY)])
    )
    seen = _patch_lane(monkeypatch, GOOD_BODY)  # lane available but NOT enabled

    result = runner.invoke(app, ["fetch", "https://site.com/article", "--json"])
    assert result.exit_code == 1
    envelope = json.loads(result.stdout)
    assert envelope["error_code"] == "JUNK_ESCALATED"
    assert "browser-lane escalation" in envelope["error"]
    assert seen == {}  # lane never fired

    # The escalation queue holds the bot_block item.
    q = runner.invoke(app, ["escalation", "list", "--status", "queued", "--json"])
    assert "bot_block" in q.stdout


# ---------------------------------------------------------------------------
# CAPTCHA + login walls NEVER take the lane
# ---------------------------------------------------------------------------


def test_captcha_never_takes_the_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _init_vault(tmp_path, monkeypatch)
    _set_config(root, "web_browser_lane", True)
    _patch_primary(
        monkeypatch, _fake_chain([_FakeResult("https://site.com/x", CAPTCHA_BODY)])
    )
    seen = _patch_lane(monkeypatch, GOOD_BODY)

    result = runner.invoke(app, ["fetch", "https://site.com/x", "--json"])
    assert result.exit_code == 1
    envelope = json.loads(result.stdout)
    assert envelope["error_code"] == "JUNK_ESCALATED"
    assert seen == {}  # the lane was NEVER called

    # The escalation queue row carries the INTERACTIVE reason — captcha,
    # not bot_block — because the human must solve it (queue shows the
    # reason; the fetch error text is generic by design).
    q = runner.invoke(app, ["escalation", "list", "--status", "queued", "--json"])
    assert "captcha" in q.stdout
    assert "bot_block" not in q.stdout


def test_login_wall_never_takes_the_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _init_vault(tmp_path, monkeypatch)
    _set_config(root, "web_browser_lane", True)
    _patch_primary(
        monkeypatch, _fake_chain([_FakeResult("https://site.com/x", LOGIN_BODY)])
    )
    seen = _patch_lane(monkeypatch, GOOD_BODY)

    result = runner.invoke(app, ["fetch", "https://site.com/x", "--json"])
    assert result.exit_code == 1
    envelope = json.loads(result.stdout)
    assert envelope["error_code"] in ("AUTH_REQUIRED", "AUTH_REQUIRED_ESCALATED")
    assert seen == {}  # human-only, always


# ---------------------------------------------------------------------------
# Lane failures degrade to the escalation path
# ---------------------------------------------------------------------------


def test_lane_failure_degrades_to_escalation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _init_vault(tmp_path, monkeypatch)
    _set_config(root, "web_browser_lane", True)
    _patch_primary(
        monkeypatch, _fake_chain([_FakeResult("https://site.com/article", BOT_WALL_BODY)])
    )
    _patch_lane(monkeypatch, None)  # 503 from the lane

    result = runner.invoke(app, ["fetch", "https://site.com/article", "--json"])
    assert result.exit_code == 1
    envelope = json.loads(result.stdout)
    assert envelope["error_code"] == "JUNK_ESCALATED"
    assert "Browser lane unavailable" in result.stdout or envelope["error_code"] == "JUNK_ESCALATED"


# ---------------------------------------------------------------------------
# Lane retry that returns junk still escalates
# ---------------------------------------------------------------------------


def test_lane_retry_returning_junk_still_escalates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If Kitesurf ALSO gets walled (same wall body), we do not save junk —
    the escalation enqueue runs exactly as if no lane existed."""
    root = _init_vault(tmp_path, monkeypatch)
    _set_config(root, "web_browser_lane", True)
    _patch_primary(
        monkeypatch, _fake_chain([_FakeResult("https://site.com/article", BOT_WALL_BODY)])
    )
    _patch_lane(monkeypatch, BOT_WALL_BODY)  # lane sees the same wall

    result = runner.invoke(app, ["fetch", "https://site.com/article", "--json"])
    assert result.exit_code == 1
    envelope = json.loads(result.stdout)
    assert envelope["error_code"] == "JUNK_ESCALATED"


# ---------------------------------------------------------------------------
# Config keys round-trip
# ---------------------------------------------------------------------------


def test_browser_lane_config_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_vault(tmp_path, monkeypatch)
    r1 = runner.invoke(app, ["config", "set", "web.browser_lane", "true", "--json"])
    assert r1.exit_code == 0, r1.output
    # Direct TOML check — the section keys persist.
    from hyperresearch.core.config import VaultConfig
    from hyperresearch.core.vault import Vault

    cfg = VaultConfig.load(Vault.discover().config_path)
    assert cfg.web_browser_lane is True
    assert cfg.web_browser_lane_engine == "kitesurf"
