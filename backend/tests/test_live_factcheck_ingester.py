"""Tests for live fact-check feed parsing, ingestion, and search integration."""
import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source, Article
from app.services.ingester import extract_factcheck_metadata, IngestionEngine
from app.services.factcheck import search_ingested_factchecks, find_fact_checks


def test_extract_factcheck_metadata_pib():
    # PIB Fact Check fake notice pattern
    title = "Fact Check: A message claiming that Ministry of Defence issued an emergency mobilization order is FAKE"
    summary = "Press Information Bureau clarifies that no such order has been released."
    meta = extract_factcheck_metadata(title, summary, source_type="factcheck", source_id="pib_factcheck")
    assert meta is not None
    assert meta["is_factcheck"] is True
    assert meta["rating"] == "Fake"
    assert "Ministry of Defence" in meta["claim"]


def test_extract_factcheck_metadata_eudisinfo():
    title = "Disinfo: Poland prepares to annex Western Ukraine"
    summary = "Pro-Kremlin narrative claiming Polish military deployment plans."
    meta = extract_factcheck_metadata(title, summary, source_type="factcheck", source_id="euvsdisinfo")
    assert meta is not None
    assert meta["rating"] == "Fake"
    assert "Poland prepares to annex Western Ukraine" in meta["claim"]


def test_extract_factcheck_metadata_misleading_media():
    title = "A video showing fighter jets over Ladakh is misleading: Taiwanese air force drill"
    summary = "Doctored clip from 2020 Taiwanese military rehearsal shared as recent border standoff."
    meta = extract_factcheck_metadata(title, summary, source_type="factcheck")
    assert meta is not None
    assert meta["rating"] == "Misleading"


def test_extract_factcheck_metadata_regular_news_ignored():
    title = "Oil prices climb as OPEC+ confirms output target"
    summary = "Crude oil benchmarks surged on Tuesday after official statement."
    meta = extract_factcheck_metadata(title, summary, source_type="wire")
    assert meta is None


@pytest.mark.asyncio
async def test_search_ingested_factchecks(db_session: AsyncSession):
    # Setup test source
    src = Source(
        id="pib_factcheck_test",
        name="PIB Fact Check Unit",
        feed_url="https://pib.gov.in/test.rss",
        source_type="factcheck",
        governance_type="state_controlled",
        region="India / South Asia",
        reliability_score=0.95,
        is_active=True,
    )
    db_session.add(src)
    await db_session.commit()

    # Add an ingested debunk article
    art = Article(
        id="art_pib_test_1",
        source_id="pib_factcheck_test",
        canonical_hash="pib_hash_1",
        title="Fact Check: Ministry of Defence recruitment scheme message is FAKE",
        url="https://pib.gov.in/PressReleasePage.aspx?PRID=99999",
        summary="Government clarifies that the viral WhatsApp notice is completely bogus.",
        clean_text="Government clarifies that the viral WhatsApp notice is completely bogus.",
        published_at=datetime.now(timezone.utc),
        entities={
            "factcheck": {
                "rating": "Fake",
                "claim": "Ministry of Defence recruitment scheme message",
            }
        },
        topics=["Fact Check", "Defence"],
    )
    db_session.add(art)
    await db_session.commit()

    # Query matching claim
    hits = await search_ingested_factchecks(db_session, "Defence recruitment scheme viral notice", region="India")
    assert len(hits) >= 1
    assert hits[0]["rating"] == "Fake"
    assert hits[0]["publisher"] == "PIB Fact Check Unit"
    assert "pib.gov.in" in hits[0]["url"]

    # Verify integration with find_fact_checks
    results = await find_fact_checks(
        "Defence recruitment scheme viral WhatsApp notice",
        entities=["Ministry of Defence"],
        region="India",
        db=db_session,
    )
    assert len(results) >= 1
    assert any("pib.gov.in" in r["url"] for r in results)
