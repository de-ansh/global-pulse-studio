"""Tests for wire-copy merging, reliability weighting, and fact-check lookup."""
import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.factcheck import build_fact_check_query, parse_fact_checks
from app.services.scorer import assign_origins, evaluate_triangulation, verification_label


def test_wire_copies_count_as_one_origin():
    reports = [
        ("hindu", "NEW DELHI (Reuters) - India and China held border talks on Monday."),
        ("express", "India, China hold border talks, Reuters reports officials said."),
        ("mint", "Different analysis of Himalayan logistics corridors and supply depots."),
    ]
    origins = assign_origins(reports)
    assert origins[0] == origins[1] == "Reuters"
    assert len(set(origins)) == 2


def test_near_identical_rewrites_count_as_one_origin():
    text = "Naval patrols expanded near Andaman islands after surveillance vessels spotted operating nearby"
    origins = assign_origins([("a", text), ("b", text + " today"), ("c", "Unrelated budget debate in parliament")])
    assert origins[0] == origins[1]
    assert len(set(origins)) == 2


def test_low_reliability_sources_cannot_triangulate():
    level, conf, checks = evaluate_triangulation(3, ["domestic_mainstream"], reliabilities=[0.5, 0.5, 0.6])
    assert level == "corroborated"
    assert conf < 0.75
    assert not next(c for c in checks if c["id"] == "source_reliability")["passed"]

    level_hi, conf_hi, _ = evaluate_triangulation(3, ["domestic_mainstream"], reliabilities=[0.9, 0.9, 0.9])
    assert level_hi == "triangulated"
    assert conf_hi == round(0.92 * 0.9, 2)


def test_verification_label_wording():
    assert verification_label("unverified", 1, False).startswith("Unconfirmed claim")
    assert "not yet confirmed" in verification_label("corroborated", 2, False)
    assert verification_label("triangulated", 3, True) == "Confirmed by 3 independent origins across media ecosystems"


def test_fact_check_parsing_and_query():
    assert build_fact_check_query("India says the Chinese troops withdrew from Galwan valley after talks") == \
        "India Chinese troops withdrew Galwan valley"
    rows = parse_fact_checks({
        "claims": [{
            "text": "Video shows warship sinking",
            "claimant": "Social media",
            "claimReview": [{"publisher": {"name": "AFP Fact Check"}, "url": "https://x/1", "textualRating": "False"}],
        }]
    })
    assert rows == [{
        "claim": "Video shows warship sinking", "claimant": "Social media", "claim_date": None,
        "publisher": "AFP Fact Check", "rating": "False", "title": None, "url": "https://x/1", "review_date": None,
    }]
    assert parse_fact_checks({}) == []


async def _make_cluster(client: AsyncClient, monkeypatch) -> str:
    from app.services.ingester import IngestionEngine

    rss = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
      <item><title>Strait of Hormuz tanker seized by naval forces</title>
      <link>https://example.com/a</link><description>d</description>
      <pubDate>Mon, 20 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>"""

    async def mock_fetch(self, http_client, feed_url):
        return rss

    monkeypatch.setattr(IngestionEngine, "fetch_feed_content", mock_fetch)
    await client.post("/api/radar/sources/seed")
    await client.post("/api/radar/scan")
    return (await client.get("/api/radar/clusters")).json()[0]["id"]


@pytest.mark.asyncio
async def test_fact_check_endpoint(client: AsyncClient, monkeypatch):
    cluster_id = await _make_cluster(client, monkeypatch)

    monkeypatch.setattr(settings, "FACTCHECK_API_KEY", "")
    assert (await client.get(f"/api/radar/clusters/{cluster_id}/factchecks")).status_code == 503

    async def fake_search(query, api_key):
        assert "Hormuz" in query
        return [{"claim": "c", "publisher": "Reuters Fact Check", "rating": "Misleading", "url": "https://x"}]

    monkeypatch.setattr(settings, "FACTCHECK_API_KEY", "test-key")
    monkeypatch.setattr("app.services.factcheck.search_fact_checks", fake_search)
    res = await client.get(f"/api/radar/clusters/{cluster_id}/factchecks")
    assert res.status_code == 200
    assert res.json()[0]["rating"] == "Misleading"

    assert (await client.get("/api/radar/clusters/nope/factchecks")).status_code == 404


@pytest.mark.asyncio
async def test_cluster_exposes_claim_status(client: AsyncClient, monkeypatch):
    await _make_cluster(client, monkeypatch)
    cluster = (await client.get("/api/radar/clusters")).json()[0]
    assert cluster["independent_origin_count"] >= 1
    assert cluster["verification_label"]
