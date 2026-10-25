"""Tests for regional fact-check connectors (PIB Fact Check and EUvsDisinfo)."""
import pytest
from httpx import AsyncClient

from app.models.event import EventCluster
from app.services.factcheck import (
    search_pib_factchecks,
    search_eudisinfo,
    find_fact_checks,
)


def test_search_pib_factchecks():
    hits = search_pib_factchecks("Viral video alleging border clash at LAC")
    assert len(hits) >= 1
    hit = hits[0]
    assert "PIB Fact Check" in hit["publisher"]
    assert "pib.gov.in" in hit["url"]
    assert "Misleading" in hit["rating"] or "Fake" in hit["rating"]


def test_search_eudisinfo():
    hits = search_eudisinfo("Covert biolabs operating across Ukraine")
    assert len(hits) >= 1
    hit = hits[0]
    assert "EUvsDisinfo" in hit["publisher"]
    assert "euvsdisinfo.eu" in hit["url"]
    assert "Disinformation" in hit["rating"]


@pytest.mark.asyncio
async def test_find_fact_checks_regional_fallback():
    # Even without a Google Fact Check API key, regional fact checks should resolve
    res = await find_fact_checks("Reports claiming new border clash at LAC in Tawang", region="India")
    assert len(res) >= 1
    assert any("PIB Fact Check" in r["publisher"] for r in res)


@pytest.mark.asyncio
async def test_claim_factchecks_api_regional(client: AsyncClient, db_session):
    # 1. Create a cluster with India region
    cluster = EventCluster(
        id="cls_india_fc",
        headline="LAC Border Patrols",
        severity="routine",
        region="India / Indo-Pacific",
    )
    db_session.add(cluster)
    await db_session.commit()

    # 2. Create project linked to cluster
    proj = (await client.post("/api/projects", json={"title": "LAC Analysis", "cluster_id": cluster.id})).json()
    proj_id = proj["id"]

    # 3. Add claim matching regional debunk
    claim = (await client.post(
        f"/api/projects/{proj_id}/claims",
        json={"text": "Fresh border clash reported at LAC"},
    )).json()

    # 4. Query fact checks for claim
    res = await client.get(f"/api/projects/{proj_id}/claims/{claim['id']}/factchecks")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) >= 1
    assert any("PIB Fact Check" in r["publisher"] for r in rows)
