"""Tests for audit readiness scoring, documentary source sheet export, and numerical verification."""
import pytest
from httpx import AsyncClient

from app.services.verifier import (
    extract_numerical_metrics,
    check_numerical_consistency,
    generate_archive_url,
)


def test_generate_archive_url():
    # Regular URL gets wayback prefix
    url = "https://reuters.com/world/middle-east/tanker-incident-123"
    assert generate_archive_url(url) == f"https://web.archive.org/web/*/{url}"

    # Already archived URLs remain unchanged
    wayback = "https://web.archive.org/web/20241020/https://example.com"
    assert generate_archive_url(wayback) == wayback

    archive_today = "https://archive.today/2024.10.20/example"
    assert generate_archive_url(archive_today) == archive_today

    assert generate_archive_url("") == ""


def test_extract_numerical_metrics():
    text = (
        "In 2024, the coalition intercepted 12 missiles and deployed 1,500 troops "
        "costing $2.5 billion, representing a 25% budget increase."
    )
    metrics = extract_numerical_metrics(text)
    kinds = {m["kind"] for m in metrics}
    raws = {m["raw"] for m in metrics}

    assert "currency" in kinds
    assert "$2.5 billion" in raws

    assert "percentage" in kinds
    assert "25%" in raws

    assert "quantity" in kinds
    assert "12 missiles" in raws or "1,500 troops" in raws

    # 2024 is a year and should not be extracted as standalone cardinal
    assert "2024" not in raws


def test_check_numerical_consistency_matched():
    statement = "The defense ministry allocated $4.5 billion for 50 warships."
    source_texts = ["Official release: $4.5 billion allocated towards procuring 50 warships for the navy."]
    res = check_numerical_consistency(statement, source_texts)
    assert res["checked"] is True
    assert res["is_consistent"] is True
    assert len(res["unverified_metrics"]) == 0
    assert res["warning"] is None


def test_check_numerical_consistency_discrepancy():
    statement = "The clash resulted in 45 fatalities and 200 detained soldiers."
    source_texts = ["Spokesperson confirmed 4 fatalities occurred during the skirmish, while 20 soldiers were detained."]
    res = check_numerical_consistency(statement, source_texts)
    assert res["checked"] is True
    assert res["is_consistent"] is False
    assert len(res["unverified_metrics"]) > 0
    assert "not corroborated" in res["warning"]


@pytest.mark.asyncio
async def test_readiness_flags_confirmed_claim_without_two_origins(client: AsyncClient, db_session):
    from datetime import datetime, timezone

    from app.models.event import EventCluster
    from app.models.source import Article, Source

    src_a = Source(id="outlet_a", name="Outlet A", feed_url="https://a.example/rss")
    src_b = Source(id="outlet_b", name="Outlet B", feed_url="https://b.example/rss")
    cluster = EventCluster(
        id="cls_origin_readiness",
        headline="Aden shipping incident",
        severity="crisis",
        region="Middle East",
        status="active",
        summary="Missile strike near Aden",
    )
    db_session.add_all([src_a, src_b, cluster])
    await db_session.flush()

    wire_copy = (
        "ADEN (Reuters) - A bulk carrier was damaged by a missile strike near Aden, "
        "maritime authorities said on Tuesday."
    )
    published = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)
    db_session.add_all([
        Article(
            id="rd_art_1",
            cluster_id=cluster.id,
            source_id="outlet_a",
            canonical_hash="rd_hash_1",
            title="Bulk carrier damaged by missile near Aden",
            url="https://a.example/aden-strike",
            summary=wire_copy,
            published_at=published,
        ),
        Article(
            id="rd_art_2",
            cluster_id=cluster.id,
            source_id="outlet_b",
            canonical_hash="rd_hash_2",
            title="Bulk carrier damaged by missile near Aden",
            url="https://b.example/aden-strike",
            summary=wire_copy,
            published_at=published,
        ),
    ])
    await db_session.commit()

    proj_id = (await client.post(
        "/api/projects", json={"title": "Aden readiness", "cluster_id": cluster.id}
    )).json()["id"]
    claim = (await client.post(
        f"/api/projects/{proj_id}/claims",
        json={"text": "Bulk carrier damaged by missile near Aden"},
    )).json()
    await client.patch(f"/api/projects/{proj_id}/claims/{claim['id']}", json={"status": "confirmed"})

    readiness = (await client.get(f"/api/projects/{proj_id}/readiness")).json()
    origins_check = next(i for i in readiness["checklist"] if i["id"] == "claim_origins")
    assert origins_check["passed"] is False
    assert any("fewer than 2 independent origins" in w for w in readiness["warnings"])


@pytest.mark.asyncio
async def test_project_readiness_and_source_sheet_lifecycle(client: AsyncClient, db_session):
    # 1. Create a project
    res = await client.post("/api/projects", json={"title": "Bab-el-Mandeb Maritime Security"})
    assert res.status_code == 201
    proj_id = res.json()["id"]

    # 2. Check initial readiness
    res_ready = await client.get(f"/api/projects/{proj_id}/readiness")
    assert res_ready.status_code == 200
    ready_data = res_ready.json()
    assert ready_data["score"] == 0
    assert ready_data["status"] == "unverified"
    assert ready_data["total_claims"] == 0

    # 3. Add claims (one unverified, one confirmed)
    c1 = (await client.post(
        f"/api/projects/{proj_id}/claims",
        json={
            "text": "Commercial vessel struck by drone off Yemen coast",
            "evidence": [{"url": "https://reuters.com/article/yemen-tanker", "label": "Reuters Wire"}],
        },
    )).json()
    assert c1["evidence"][0]["archive_url"] is not None
    assert "web.archive.org" in c1["evidence"][0]["archive_url"]

    c2 = (await client.post(
        f"/api/projects/{proj_id}/claims",
        json={"text": "Destroyer USS Laboon intercepted 3 drones in vicinity"},
    )).json()

    # Mark c2 confirmed
    await client.patch(f"/api/projects/{proj_id}/claims/{c2['id']}", json={"status": "confirmed"})

    # 4. Check updated readiness
    res_ready2 = await client.get(f"/api/projects/{proj_id}/readiness")
    assert res_ready2.status_code == 200
    ready2_data = res_ready2.json()
    assert ready2_data["total_claims"] == 2
    assert ready2_data["confirmed_claims"] == 1
    assert ready2_data["unverified_claims"] == 1
    assert any("still unverified" in w for w in ready2_data["warnings"])

    # 5. Export Source Sheet
    res_sheet = await client.get(f"/api/projects/{proj_id}/source-sheet")
    assert res_sheet.status_code == 200
    sheet = res_sheet.json()
    assert sheet["project_id"] == proj_id
    assert len(sheet["citations"]) == 2
    assert "# Fact-Check & Citation Source Sheet" in sheet["markdown"]
    assert "Commercial vessel struck" in sheet["markdown"]
    assert "web.archive.org" in sheet["markdown"]
