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
