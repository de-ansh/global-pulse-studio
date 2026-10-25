"""Tests for Cluster Cross-Article Consensus Matrix."""
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient

from app.models.event import EventCluster
from app.models.source import Article, Source
from app.services.verifier import crosscheck_claim_against_articles


def test_crosscheck_claim_broad_consensus():
    articles = [
        {"id": "a1", "title": "Missile strikes commercial vessel in Gulf of Aden", "summary": "Coalition confirms missile impact on bulk carrier", "outlet": "Reuters"},
        {"id": "a2", "title": "Bulk carrier damaged by missile attack near Aden", "summary": "Crew safe after missile strike in Gulf of Aden", "outlet": "AP"},
        {"id": "a3", "title": "Aden naval incident: merchant ship struck", "summary": "Maritime trade authorities confirm missile strike off Aden coast", "outlet": "BBC"},
        {"id": "a4", "title": "Tech stocks rally on Wall Street", "summary": "Earnings surge leads to market gains", "outlet": "Bloomberg"},
    ]
    claim = "Merchant vessel struck by missile in Gulf of Aden"
    res = crosscheck_claim_against_articles(claim, articles)

    assert res["status"] == "broad_consensus"
    assert len(res["supporting"]) == 3
    assert len(res["disputing"]) == 0
    assert res["silent_count"] == 1
    assert "Broad consensus" in res["summary"]


def test_crosscheck_claim_disputed_denial():
    articles = [
        {"id": "a1", "title": "Naval forces claim radar station destroyed", "summary": "Strikes successfully targeted coastal radar", "outlet": "State Media"},
        {"id": "a2", "title": "Ministry denies radar station was destroyed", "summary": "Spokesperson refutes claims of damage, calling them fabricated", "outlet": "Independent Wire"},
    ]
    claim = "Radar station destroyed in coastal strike"
    res = crosscheck_claim_against_articles(claim, articles)

    assert res["status"] == "disputed"
    assert len(res["disputing"]) >= 1
    assert "Disputed" in res["summary"]


def test_crosscheck_claim_unaddressed():
    articles = [
        {"id": "a1", "title": "Oil prices steady amid OPEC discussions", "summary": "Output quotas remain unchanged", "outlet": "Reuters"},
    ]
    claim = "Submarine sighted near Bab-el-Mandeb Strait"
    res = crosscheck_claim_against_articles(claim, articles)

    assert res["status"] == "unaddressed"
    assert len(res["supporting"]) == 0
    assert res["silent_count"] == 1


@pytest.mark.asyncio
async def test_cluster_crosscheck_api_endpoint(client: AsyncClient, db_session):
    # 1. Create sources and a cluster with articles
    src1 = Source(id="reuters", name="Reuters", feed_url="https://reuters.example/rss")
    src2 = Source(id="bbc", name="BBC", feed_url="https://bbc.example/rss")
    cluster = EventCluster(
        id="cls_crosscheck_test",
        headline="Hormuz Patrol Operations",
        severity="crisis",
        region="Middle East",
        status="active",
        summary="Naval operations in Hormuz",
    )
    db_session.add_all([src1, src2, cluster])
    await db_session.flush()

    art1 = Article(
        id="art_cc_1",
        cluster_id=cluster.id,
        source_id="reuters",
        canonical_hash="hash_art_1",
        title="Destroyer intercepts three attack drones in Hormuz",
        summary="Naval destroyer successfully intercepted three drones launched towards shipping",
        url="https://reuters.com/hormuz-intercept",
        published_at=datetime.now(timezone.utc),
    )
    art2 = Article(
        id="art_cc_2",
        cluster_id=cluster.id,
        source_id="bbc",
        canonical_hash="hash_art_2",
        title="Three drones intercepted near Hormuz shipping corridor",
        summary="Officials confirm three drones destroyed near shipping lanes",
        url="https://bbc.com/hormuz-intercept",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add_all([art1, art2])
    await db_session.commit()

    # 2. Create project linked to cluster
    proj_res = await client.post("/api/projects", json={"title": "Hormuz Drone Intercepts", "cluster_id": cluster.id})
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]

    # 3. Add claim to project
    claim_res = await client.post(
        f"/api/projects/{proj_id}/claims",
        json={"text": "Destroyer intercepted three attack drones in Hormuz"},
    )
    assert claim_res.status_code == 201
    claim_id = claim_res.json()["id"]

    # 4. Crosscheck claim against cluster articles
    cc_res = await client.post(f"/api/projects/{proj_id}/claims/{claim_id}/crosscheck")
    assert cc_res.status_code == 200
    data = cc_res.json()
    assert data["claim_id"] == claim_id
    assert data["status"] == "corroborated"
    assert len(data["supporting"]) == 2
    assert "Corroborated" in data["summary"]
