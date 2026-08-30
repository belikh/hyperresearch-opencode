"""Junk-detection regression tests.

`looks_like_junk()` previously counted every `ord(c) > 127` character as
"binary/non-printable", so any page in a non-Latin script — and plenty of
accented Latin text — was silently discarded as binary garbage.
"""

# ruff: noqa: RUF001
# RUF001/RUF003 flag fullwidth punctuation as "ambiguous" ASCII lookalikes.
# Here it is the correct punctuation for the language being tested, and real
# non-ASCII text is the entire point of this file — substituting ASCII commas
# would defeat the regression these fixtures exist to catch.

from __future__ import annotations

import pytest

from hyperresearch.web.base import WebResult, binary_garbage_ratio

# Real prose, not placeholder shapes — a filter that passes on `"x" * 500`
# but discards actual Chinese text would still be broken.
CHINESE = (
    "锂离子电池的能量密度持续提升，但热失控风险仍然是电动汽车安全的核心问题。"
    "研究人员正在开发固态电解质，以降低易燃性并提高循环寿命。"
    "本文综述了近年来固态电池在材料、界面工程和规模化生产方面的进展，"
    "并讨论了当前技术路线在成本与产能爬坡方面面临的主要挑战。"
) * 3

JAPANESE = (
    "半導体産業におけるサプライチェーンの再編は、地政学的な要因によって加速している。"
    "各国政府は国内での生産能力の拡大を支援するために大規模な補助金を導入しており、"
    "製造装置メーカーは需要の急増に対応するため生産体制の見直しを迫られている。"
) * 3

ARABIC = (
    "تشهد صناعة الطاقة المتجددة نموًا سريعًا في منطقة الشرق الأوسط، "
    "حيث تستثمر الحكومات مبالغ كبيرة في مشاريع الطاقة الشمسية وطاقة الرياح "
    "بهدف تنويع مصادر الدخل وتقليل الاعتماد على الوقود الأحفوري."
) * 3

RUSSIAN = (
    "Исследования в области квантовых вычислений продвигаются быстрее, чем ожидалось. "
    "Основной проблемой остаётся коррекция ошибок, требующая значительного числа "
    "физических кубитов для кодирования одного логического кубита."
) * 3

ACCENTED_LATIN = (
    "L'évolution des systèmes énergétiques européens dépend fortement des "
    "investissements dans les réseaux électriques transfrontaliers. "
    "Les décideurs doivent équilibrer sécurité d'approvisionnement, coûts et "
    "objectifs climatiques — un arbitrage particulièrement délicat."
) * 3


@pytest.mark.parametrize(
    "name,text",
    [
        ("chinese", CHINESE),
        ("japanese", JAPANESE),
        ("arabic", ARABIC),
        ("russian", RUSSIAN),
        ("accented_latin", ACCENTED_LATIN),
    ],
)
def test_non_english_pages_are_not_junk(name: str, text: str):
    """Non-Latin and accented text is real content, not binary garbage."""
    result = WebResult(url=f"https://example.com/{name}", title=name, content=text)
    assert result.looks_like_junk() is None, (
        f"{name} page was rejected as junk: {result.looks_like_junk()}"
    )


def test_binary_content_is_still_rejected():
    """The filter must still catch genuinely binary content."""
    binary = "".join(chr(i % 32) for i in range(2000))
    result = WebResult(url="https://example.com/bin", title="bin", content=binary)
    assert result.looks_like_junk() == "High ratio of binary/non-printable content"


def test_mojibake_is_still_rejected():
    """U+FFFD means decoding already failed — that content is not trustworthy."""
    broken = "�" * 400 + "some readable text " * 20
    result = WebResult(url="https://example.com/bad", title="bad", content=broken)
    assert result.looks_like_junk() == "High ratio of binary/non-printable content"


def test_pdf_structure_markers_still_rejected():
    """Raw PDF internals must not be saved as article text."""
    pdf_junk = "%PDF-1.4\n" + "endobj endstream /FlateDecode " * 100
    result = WebResult(url="https://example.com/x.pdf", title="x", content=pdf_junk)
    assert result.looks_like_junk() == "Binary PDF garbage in content"


def test_binary_garbage_ratio_ignores_script():
    """The ratio must not depend on whether text happens to be ASCII."""
    assert binary_garbage_ratio(CHINESE) == 0.0
    assert binary_garbage_ratio("plain ascii text") == 0.0
    assert binary_garbage_ratio("\x00\x01\x02\x03") == 1.0


def test_tabs_and_newlines_are_not_garbage():
    """Ordinary whitespace is legitimate in extracted text."""
    assert binary_garbage_ratio("a\tb\nc\r\nd\f\ve") == 0.0


def test_single_shared_implementation():
    """crawl4ai's binary check must not drift from the one in base.py again."""
    from hyperresearch.web.crawl4ai_provider import _looks_like_binary

    assert _looks_like_binary(CHINESE) is False
    assert _looks_like_binary("\x00\x01\x02" * 700) is True


# ---------------------------------------------------------------------------
# P1-4 hardening: invisible-padding gate bypass
# ---------------------------------------------------------------------------
#
# Zero-width/invisible characters used to count toward min_content_chars and
# toward login-wall length, and could split signal phrases ("Just a moment")
# so they stopped matching. Every test below fails against pre-fix code.

ZWSP = "\u200b"  # zero-width space
SOFT_HYPHEN = "\u00ad"


class TestInvisiblePadding:
    def test_zwsp_padded_spam_is_junk(self):
        """400 invisible chars + 'hi' must not read as ~400-char content."""
        padded = ZWSP * 400 + "hi"
        result = WebResult(url="https://example.com/spam", title="spam", content=padded)
        assert result.looks_like_junk() == "Empty or near-empty content"

    def test_soft_hyphen_padding_cannot_fake_length(self):
        padded = SOFT_HYPHEN * 400 + "ok"
        result = WebResult(url="https://example.com/pad", title="pad", content=padded)
        assert result.looks_like_junk() == "Empty or near-empty content"

    def test_bot_wall_signal_split_by_zero_width_chars_is_detected(self):
        """'Just\\u200ba\\u200bmoment' must still match the Cloudflare signal."""
        evasive = "Just\u200b a\u200b moment. " * 40
        result = WebResult(url="https://example.com/cf", title="cf", content=evasive)
        reason = result.looks_like_junk()
        assert reason is not None and reason.startswith("Bot detection page")

    def test_login_wall_padding_bypass_closed(self):
        """Same defect class in looks_like_login_wall: padding must not fake
        enough length to keep a login form out of that gate."""
        padded = ZWSP * 995 + "please log in"
        result = WebResult(url="https://example.com/a", title="Article", content=padded)
        assert result.looks_like_login_wall(result.url) is True

    @pytest.mark.parametrize(
        ("name", "text"),
        [
            ("chinese_with_zwsp", CHINESE[:120] + ZWSP + CHINESE[120:] + ZWSP),
            ("accented_latin_with_soft_hyphen", ACCENTED_LATIN + SOFT_HYPHEN),
        ],
    )
    def test_legit_text_with_invisible_chars_is_not_junk(self, name, text):
        """The normalization must strip ONLY invisibles — real text unaffected."""
        result = WebResult(url=f"https://example.com/{name}", title=name, content=text)
        assert result.looks_like_junk() is None, f"{name} was rejected: {result.looks_like_junk()}"

    def test_strip_invisible_removes_only_the_invisible_set(self):
        """Direct pin on the helper: tabs/newlines/CJK survive; ZWSP family goes."""
        from hyperresearch.web.base import strip_invisible

        assert strip_invisible("a\u200bb\u200cc\u200dd\u2060e\ufefff\u00adg") == "abcdefg"
        assert strip_invisible("a\tb\nc 锂") == "a\tb\nc 锂"
        assert strip_invisible("plain") == "plain"


# ---------------------------------------------------------------------------
# P6 hardening: the bare company name is not a bot-wall signal
# ---------------------------------------------------------------------------


class TestCloudflareMentionIsNotJunk:
    """Found live via the Kitesurf lane: the bare word "cloudflare" in the
    bot-wall signal list junk-gated every page ABOUT Cloudflare (their docs,
    blog, community threads) as a "Bot detection page". Real challenge
    pages emit the strong interstitial phrases; the company name alone must
    never be a wall verdict."""

    def test_pages_about_cloudflare_are_not_junk(self):
        from hyperresearch.web.base import WebResult

        result = WebResult(
            url="https://developers.cloudflare.com/browser-run/",
            title="Browser Run · Cloudflare Browser Run docs",
            content="Control headless browsers with Cloudflare's Workers "
            "Browser Run API. " * 30,
        )
        assert result.looks_like_junk() is None

    def test_real_interstitial_still_detected(self):
        from hyperresearch.web.base import WebResult

        result = WebResult(
            url="https://site.com/x",
            title="Just a moment...",
            content="Checking your browser before accessing. " * 30,
        )
        assert result.looks_like_junk() is not None
        assert "Bot detection" in (result.looks_like_junk() or "")
