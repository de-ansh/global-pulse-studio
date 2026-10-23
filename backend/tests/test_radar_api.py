"""Integration tests for radar endpoints and source management."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_seed_and_list_sources(client: AsyncClient):
    """Verify seeding default intelligence sources works idempotently."""
    seed_res = await client.post("/api/radar/sources/seed")
    assert seed_res.status_code == 201
    seeded_sources = seed_res.json()
    assert len(seeded_sources) >= 3

    # Fetch list
    list_res = await client.get("/api/radar/sources")
    assert list_res.status_code == 200
    sources = list_res.json()
    assert len(sources) >= 3
    source_ids = [s["id"] for s in sources]
    assert "bbc_world" in source_ids


@pytest.mark.asyncio
async def test_create_custom_source(client: AsyncClient):
    """Verify adding a custom intelligence feed."""
    payload = {
        "id": "isw_updates",
        "name": "Institute for the Study of War",
        "feed_url": "https://understandingwar.org/rss.xml",
        "homepage_url": "https://understandingwar.org",
        "source_type": "think_tank",
        "region": "Eastern Europe",
        "reliability_score": 0.95,
        "is_active": True,
    }
    create_res = await client.post("/api/radar/sources", json=payload)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["id"] == "isw_updates"
    assert data["source_type"] == "think_tank"

    # Duplicate creation must return 409
    dup_res = await client.post("/api/radar/sources", json=payload)
    assert dup_res.status_code == 409


@pytest.mark.asyncio
async def test_trigger_radar_scan_end_to_end(client: AsyncClient, monkeypatch):
    """Verify triggering scan ingests articles and clusters them without 500 error."""
    # Seed sources first
    seed_res = await client.post("/api/radar/sources/seed")
    assert seed_res.status_code == 201

    sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>BBC World News</title>
        <link>https://www.bbc.com/news/world</link>
        <item>
          <title>Strait of Hormuz tensions flare as oil tankers diverted</title>
          <link>https://www.bbc.com/news/world-123456</link>
          <description>Maritime authorities issue security alerts across Persian Gulf waterways.</description>
          <pubDate>Mon, 20 Oct 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    from app.services.ingester import IngestionEngine

    async def mock_fetch(self, http_client, feed_url):
        return sample_rss

    monkeypatch.setattr(IngestionEngine, "fetch_feed_content", mock_fetch)

    scan_res = await client.post("/api/radar/scan")
    assert scan_res.status_code == 200
    data = scan_res.json()
    assert "sources_scanned" in data
    assert "clusters_created_or_updated" in data
    assert data["new_articles_ingested"] >= 1
    assert data["clusters_created_or_updated"] >= 1

    # Verify cluster list endpoint now returns the new cluster
    cluster_res = await client.get("/api/radar/clusters")
    assert cluster_res.status_code == 200
    clusters = cluster_res.json()
    assert len(clusters) >= 1
    assert any("Hormuz" in c["headline"] or "Hormuz" in c["chokepoints"] for c in clusters)


@pytest.mark.asyncio
async def test_india_desk_endpoint(client: AsyncClient, monkeypatch):
    """Verify dedicated India Strategic Desk endpoint and multi-source triangulation."""
    # Seed default feeds (including The Hindu, Indian Express, Livemint)
    seed_res = await client.post("/api/radar/sources/seed")
    assert seed_res.status_code == 201

    sample_india_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>The Hindu</title>
        <link>https://www.thehindu.com</link>
        <item>
          <title>India and Quad bolster naval patrols near Andaman and Nicobar gateway</title>
          <link>https://www.thehindu.com/news/national/andaman-patrols-101</link>
          <description>Strategic autonomy and maritime domain awareness underscored in response to regional chokepoint friction.</description>
          <pubDate>Mon, 20 Oct 2026 14:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    from app.services.ingester import IngestionEngine

    async def mock_fetch(self, http_client, feed_url):
        return sample_india_rss

    monkeypatch.setattr(IngestionEngine, "fetch_feed_content", mock_fetch)

    # Ingest the report
    scan_res = await client.post("/api/radar/scan")
    assert scan_res.status_code == 200

    # Query India desk endpoint
    india_res = await client.get("/api/radar/india")
    assert india_res.status_code == 200
    clusters = india_res.json()
    assert len(clusters) >= 1

    target = clusters[0]
    assert target["is_india_relevant"] is True
    assert "triangulation_level" in target
    assert "verification_checklist" in target
    assert len(target["verification_checklist"]) >= 3
    assert any("Andaman" in chk for chk in target["chokepoints"]) or "India" in target["key_actors"]


@pytest.mark.asyncio
async def test_toggle_and_delete_source(client: AsyncClient):
    """Verify a source can be paused and then removed."""
    await client.post("/api/radar/sources/seed")

    patch_res = await client.patch("/api/radar/sources/bbc_world", json={"is_active": False})
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is False

    del_res = await client.delete("/api/radar/sources/bbc_world")
    assert del_res.status_code == 204
    ids = [s["id"] for s in (await client.get("/api/radar/sources")).json()]
    assert "bbc_world" not in ids

    assert (await client.delete("/api/radar/sources/bbc_world")).status_code == 404


@pytest.mark.asyncio
async def test_fact_check_error_does_not_leak_api_key(client: AsyncClient, db_session, monkeypatch):
    """Upstream errors embed the request URL (with ?key=); the response must not echo it."""
    import httpx
    from app.config import settings
    from app.models.event import EventCluster
    from app.services import factcheck

    secret = "SECRET-KEY-123"
    monkeypatch.setattr(settings, "FACTCHECK_API_KEY", secret)

    async def failing_search(query, api_key):
        req = httpx.Request("GET", f"https://factchecktools.googleapis.com/v1alpha1/claims:search?key={api_key}")
        raise httpx.HTTPStatusError("403 Forbidden for url " + str(req.url), request=req, response=httpx.Response(403, request=req))

    monkeypatch.setattr(factcheck, "search_fact_checks", failing_search)
    db_session.add(EventCluster(id="evt_leak", headline="Strait of Hormuz blockade threat"))
    await db_session.commit()

    res = await client.get("/api/radar/clusters/evt_leak/factchecks")
    assert res.status_code == 502
    assert secret not in res.text
    assert "HTTP 403" in res.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["feed_url", "homepage_url"])
async def test_create_source_rejects_non_http_urls(client: AsyncClient, field):
    payload = {"id": "bad", "name": "Bad", "feed_url": "https://ok.example/rss", field: "file:///etc/passwd"}
    res = await client.post("/api/radar/sources", json=payload)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_source_duplicate_feed_url_is_409(client: AsyncClient):
    base = {"name": "A", "feed_url": "https://dup.example/rss"}
    assert (await client.post("/api/radar/sources", json={**base, "id": "a"})).status_code == 201
    res = await client.post("/api/radar/sources", json={**base, "id": "b"})
    assert res.status_code == 409
    assert "already registered" in res.json()["detail"]


@pytest.mark.asyncio
async def test_scan_rejected_while_another_runs(client: AsyncClient):
    from app.routers import radar
    async with radar._scan_lock:
        res = await client.post("/api/radar/scan")
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_delete_source_updates_or_removes_clusters(client: AsyncClient, db_session):
    from datetime import datetime, timezone
    from sqlalchemy import text
    from app.models.source import Source, Article
    from app.models.event import EventCluster

    assert (await db_session.execute(text("PRAGMA foreign_keys"))).scalar() == 1

    now = datetime.now(timezone.utc)
    db_session.add_all([
        Source(id="s1", name="S1", feed_url="https://s1.example/rss"),
        Source(id="s2", name="S2", feed_url="https://s2.example/rss"),
        EventCluster(id="shared", headline="Shared", article_count=2),
        EventCluster(id="solo", headline="Solo", article_count=1),
    ])
    await db_session.flush()
    for aid, sid, cid in [("a1", "s1", "shared"), ("a2", "s2", "shared"), ("a3", "s1", "solo")]:
        db_session.add(Article(id=aid, source_id=sid, cluster_id=cid, canonical_hash=aid, title=aid, url="https://x.example", published_at=now))
    await db_session.commit()

    assert (await client.delete("/api/radar/sources/s1")).status_code == 204
    assert (await client.get("/api/radar/clusters/solo")).status_code == 404
    shared = (await client.get("/api/radar/clusters/shared")).json()
    assert shared["article_count"] == 1


@pytest.mark.asyncio
async def test_india_focus_pages_after_filtering(client: AsyncClient, db_session):
    """Non-India clusters ranked higher must not eat the page when focus=india."""
    from app.models.event import EventCluster
    for i in range(3):
        db_session.add(EventCluster(id=f"g{i}", headline=f"Brazil election {i}", explainer_score=90 - i))
    for i in range(2):
        db_session.add(EventCluster(id=f"in{i}", headline=f"India border talks {i}", explainer_score=10 - i))
    await db_session.commit()

    res = await client.get("/api/radar/clusters", params={"focus": "india", "limit": 2})
    assert [c["id"] for c in res.json()] == ["in0", "in1"]
    res = await client.get("/api/radar/india", params={"limit": 1, "offset": 1})
    assert [c["id"] for c in res.json()] == ["in1"]


@pytest.mark.asyncio
async def test_update_source_partial_fields(client: AsyncClient):
    await client.post("/api/radar/sources", json={"id": "e", "name": "Old", "feed_url": "https://e.example/rss"})
    await client.post("/api/radar/sources", json={"id": "f", "name": "F", "feed_url": "https://f.example/rss"})

    res = await client.patch("/api/radar/sources/e", json={"name": "New", "bias_category": "domestic_mainstream", "reliability_score": 0.7})
    assert res.status_code == 200
    body = res.json()
    assert (body["name"], body["bias_category"], body["reliability_score"], body["is_active"]) == ("New", "domestic_mainstream", 0.7, True)

    assert (await client.patch("/api/radar/sources/e", json={"is_active": False})).json()["name"] == "New"
    assert (await client.patch("/api/radar/sources/e", json={"feed_url": "https://f.example/rss"})).status_code == 409
    assert (await client.patch("/api/radar/sources/e", json={"feed_url": "ftp://x"})).status_code == 422
    assert (await client.patch("/api/radar/sources/e", json={"reliability_score": 3})).status_code == 422


@pytest.mark.asyncio
async def test_scheduled_scan_loop_runs_and_survives_errors(monkeypatch):
    import asyncio
    from app.routers import radar

    calls = []

    async def fake_scan(db):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return radar.ScanSummary(sources_scanned=0, new_articles_ingested=0, duplicate_articles_skipped=0, clusters_created_or_updated=0)

    monkeypatch.setattr(radar, "run_full_scan", fake_scan)
    task = asyncio.create_task(radar.scheduled_scans(0.001))  # 60ms interval
    await asyncio.sleep(0.25)
    task.cancel()
    assert len(calls) >= 2  # kept going after the first failure
