"""Unit tests for feed ingestion, HTML sanitization, and deduplication."""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source, Article
from app.services.ingester import (
    clean_html_text,
    compute_canonical_hash,
    IngestionEngine,
)

SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Global Defense Wire</title>
    <link>https://example.com</link>
    <description>International defense news</description>
    <item>
      <title>Naval exercise announced in Taiwan Strait amid semiconductor export row</title>
      <link>https://example.com/news/article-1?utm_source=rss</link>
      <description><![CDATA[<p>China announces patrols as <b>sanctions</b> take effect.<script>alert('track')</script></p>]]></description>
      <pubDate>Mon, 19 Oct 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_clean_html_text():
    """Verify HTML cleaning strips script tags and collapses whitespace."""
    raw = "<div><p>Crisis in   <b>Corridor</b>.</p><script>tracker()</script></div>"
    cleaned = clean_html_text(raw)
    assert cleaned == "Crisis in Corridor."


def test_canonical_hash_deduplication():
    """Ensure URL tracking params and punctuation variations produce identical hashes."""
    url1 = "https://news.com/article?utm_source=twitter"
    url2 = "https://news.com/article"
    title1 = "NATO, Russia Deploy Forces to Border!"
    title2 = "nato russia deploy forces to border"

    hash1 = compute_canonical_hash(url1, title1)
    hash2 = compute_canonical_hash(url2, title2)
    assert hash1 == hash2


@pytest.mark.asyncio
async def test_ingest_source_and_deduplicate(db_session: AsyncSession):
    """Verify ingestion parses RSS feed, stores article, and skips duplicates on second run."""
    source = Source(
        id="test_feed",
        name="Test Wire",
        feed_url="https://example.com/feed.xml",
        source_type="wire",
        region="Asia-Pacific",
        reliability_score=0.9,
    )
    db_session.add(source)
    await db_session.commit()

    ingester = IngestionEngine(db_session)

    # Mock fetch_feed_content to return static XML
    with patch.object(ingester, "fetch_feed_content", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = SAMPLE_RSS_XML

        # First scan: should insert 1 new article
        result1 = await ingester.run_scan()
        assert result1.new_articles_ingested == 1
        assert result1.duplicate_articles_skipped == 0

        # Verify article was stored properly
        stmt = select(Article).where(Article.source_id == "test_feed")
        res = await db_session.execute(stmt)
        articles = list(res.scalars().all())
        assert len(articles) == 1
        assert "Taiwan Strait" in articles[0].title
        assert "Taiwan Strait" in articles[0].entities["chokepoints"]
        assert "China" in articles[0].entities["actors"]

        # Second scan: should detect duplicate and skip
        result2 = await ingester.run_scan()
        assert result2.new_articles_ingested == 0
        assert result2.duplicate_articles_skipped == 1


@pytest.mark.asyncio
async def test_ingest_skips_non_http_links(db_session: AsyncSession):
    """Feed links become clickable hrefs, so javascript:/data: links must never be stored."""
    xml = SAMPLE_RSS_XML.replace(
        "https://example.com/news/article-1?utm_source=rss", "javascript:alert(document.cookie)"
    )
    source = Source(id="evil_feed", name="Evil", feed_url="https://evil.example/feed.xml")
    db_session.add(source)
    await db_session.commit()

    ingester = IngestionEngine(db_session)
    with patch.object(ingester, "fetch_feed_content", new_callable=AsyncMock, return_value=xml):
        result = await ingester.run_scan()

    assert result.new_articles_ingested == 0
    assert (await db_session.execute(select(Article))).first() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["http://127.0.0.1:8001/api/health", "http://169.254.169.254/latest/meta-data", "http://localhost/"])
async def test_fetch_refuses_internal_addresses(url):
    """Feeds must not be usable to reach loopback, link-local (cloud metadata) or private hosts."""
    import httpx
    from app.services.ingester import block_private_hosts

    async with httpx.AsyncClient(event_hooks={"request": [block_private_hosts]}) as client:
        with pytest.raises(httpx.ConnectError, match="non-public"):
            await client.get(url)


@pytest.mark.asyncio
async def test_scan_downloads_feeds_concurrently_and_isolates_failures(db_session: AsyncSession):
    import asyncio
    db_session.add_all([
        Source(id=f"f{i}", name=f"F{i}", feed_url=f"https://f{i}.example/rss") for i in range(3)
    ])
    await db_session.commit()

    in_flight = peak = 0

    async def fake_fetch(client, url):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        if url.startswith("https://f1."):
            raise ValueError("feed down")
        return SAMPLE_RSS_XML.replace("article-1", url.split("//")[1].split(".")[0])

    ingester = IngestionEngine(db_session)
    with patch.object(ingester, "fetch_feed_content", side_effect=fake_fetch):
        result = await ingester.run_scan()

    assert peak > 1
    assert result.new_articles_ingested == 2
    assert result.errors == [{"source_id": "f1", "error": "feed down"}]
