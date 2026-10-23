"""Tests for on-demand article full-text fetching (network mocked)."""
from datetime import datetime, timezone

import httpx
import pytest

from app.models.source import Article
from app.services import fulltext

PARA = "The tanker was halted near the strait after mines were reported by the navy on Monday morning."
PAGE = f"""<html><body><nav><p>{'Menu item that is long enough to pass the filter ' * 2}</p></nav>
<article><h1>Title</h1><p>{PARA}</p><p>short</p><p>{PARA} Again.</p><script>track()</script></article>
<footer><p>{'Copyright notice that is long enough to pass the filter ' * 2}</p></footer></body></html>"""


def test_extract_main_text_keeps_article_paragraphs_only():
    text = fulltext.extract_main_text(PAGE)
    assert text == f"{PARA}\n\n{PARA} Again."


def _art(i, url):
    return Article(id=f"a{i}", source_id="s", canonical_hash=f"h{i}", title="t", url=url, summary="summary only",
                   clean_text="summary only", published_at=datetime.now(timezone.utc), entities={"actors": ["Iran"]})


@pytest.mark.asyncio
async def test_ensure_full_text_stores_text_records_failures_and_skips_attempted(monkeypatch):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if "paywall" in str(request.url):
            return httpx.Response(200, html="<html><body><p>Subscribe</p></body></html>")
        if "broken" in str(request.url):
            return httpx.Response(500)
        return httpx.Response(200, html=PAGE.replace("<p>short</p>", f"<p>{PARA}</p>" * 3))

    real = httpx.AsyncClient
    # skip DNS-based private-host check (no network in tests); it is covered in test_ingester
    monkeypatch.setattr(fulltext, "web_client", lambda: real(transport=httpx.MockTransport(handler), follow_redirects=True))

    good, paywall, broken = _art(1, "https://n.example/ok"), _art(2, "https://n.example/paywall"), _art(3, "https://n.example/broken")
    assert await fulltext.ensure_full_text([good, paywall, broken]) == 1

    assert PARA in good.clean_text and good.entities == {"actors": ["Iran"], "fulltext": "ok"}
    assert paywall.clean_text == "summary only" and paywall.entities["fulltext"].startswith("failed: ValueError: no article text")
    assert broken.entities["fulltext"].startswith("failed: HTTPStatusError")

    calls.clear()
    assert await fulltext.ensure_full_text([good, paywall, broken]) == 0
    assert calls == []  # already attempted: no refetch


def test_script_sources_prefer_full_text():
    from types import SimpleNamespace
    from app.services.scriptwriter import build_sources
    art = SimpleNamespace(title="t", summary="short summary", clean_text="FULL TEXT " * 10, url="https://x.example", source_id="s",
                          published_at=datetime.now(timezone.utc), source=SimpleNamespace(name="W"), entities={"fulltext": "ok"})
    assert build_sources([art], [])[0]["text"].startswith("FULL TEXT") and build_sources([art], [])[0]["full_text"] is True
    art.entities = {"fulltext": "failed: x"}
    assert build_sources([art], [])[0]["text"] == "short summary"


def test_extract_drops_account_boilerplate_but_keeps_long_reporting():
    login = "Subscribed with another email? Logout and Login with that one."
    long_para = "Readers who subscribe to the newsletter " + PARA * 4  # long reporting paragraph that happens to say 'subscribe'
    page = f"<article><p>{login}</p><p>{PARA}</p><p>{long_para}</p></article>"
    assert fulltext.extract_main_text(page) == f"{PARA}\n\n{long_para}"
