"""Tests for Breaking Story Retraction and Update Tracker."""
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient

from app.models.event import EventCluster
from app.models.source import Article, Source
from app.services.verifier import detect_superseded_claim


def test_detect_superseded_claim_with_revision():
    now = datetime.now(timezone.utc)
    earlier = now - timedelta(hours=4)
    claim_text = "Hospital blast resulted in 500 casualties"

    articles = [
        {
            "id": "a1",
            "title": "Hospital explosion causes 500 casualties",
            "summary": "Local health ministry claims 500 killed",
            "published_at": earlier,
            "outlet": "Wire One",
        },
        {
            "id": "a2",
            "title": "Hospital toll revised down following intelligence review",
            "summary": "Officials revised the earlier reports claiming 500 casualties down to between 100 and 300.",
            "published_at": now,
            "outlet": "Wire One",
        },
    ]

    res = detect_superseded_claim(claim_text, earlier, articles)
    assert res["is_superseded"] is True
    assert res["superseding_article"]["id"] == "a2"
    assert "revised down" in res["superseding_article"]["title"].lower()
    assert "revision or retraction" in res["warning"]


def test_detect_superseded_claim_without_revision():
    now = datetime.now(timezone.utc)
    claim_text = "Destroyer docked at naval facility"
    articles = [
        {
            "id": "a1",
            "title": "Destroyer arrived at naval base",
            "summary": "Routine logistics docking completed",
            "published_at": now,
            "outlet": "Naval Gazette",
        }
    ]
    res = detect_superseded_claim(claim_text, now - timedelta(hours=1), articles)
    assert res["is_superseded"] is False
    assert res["warning"] is None


@pytest.mark.asyncio
async def test_retraction_api_integration(client: AsyncClient, db_session):
    now = datetime.now(timezone.utc)
    earlier = now - timedelta(hours=2)

    src = Source(id="wire_x", name="Wire X", feed_url="https://wirex.example/rss")
    cluster = EventCluster(
        id="cls_retract_test",
        headline="Ammunition Depot Incident",
        severity="crisis",
        region="Eurasia",
    )
    db_session.add_all([src, cluster])
    await db_session.flush()

    art1 = Article(
        id="art_retract_1",
        cluster_id=cluster.id,
        source_id=src.id,
        canonical_hash="hash_ret_1",
        title="Missile strike targeted depot, earlier report claimed",
        summary="Initial claims of enemy missile attack",
        url="https://wirex.example/strike",
        published_at=earlier,
    )
    art2 = Article(
        id="art_retract_2",
        cluster_id=cluster.id,
        source_id=src.id,
        canonical_hash="hash_ret_2",
        title="Depot explosion clarified as internal safety accident, not missile strike",
        summary="Defense ministry clarified that earlier reports of strike were incorrect.",
        url="https://wirex.example/clarification",
        published_at=now,
    )
    db_session.add_all([art1, art2])
    await db_session.commit()

    proj = (await client.post("/api/projects", json={"title": "Depot Investigation", "cluster_id": cluster.id})).json()
    proj_id = proj["id"]

    claim = (await client.post(
        f"/api/projects/{proj_id}/claims",
        json={"text": "Missile strike targeted depot and caused detonation"},
    )).json()

    res = await client.post(f"/api/projects/{proj_id}/claims/{claim['id']}/crosscheck")
    assert res.status_code == 200
    data = res.json()
    assert data["superseded_warning"] is not None
    assert "clarified" in data["superseded_warning"].lower()
