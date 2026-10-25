"""Tests for Cross-Project Claim Memory Cache."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cross_project_claim_memory_lifecycle(client: AsyncClient, db_session):
    # 1. Project 1: User researches and confirms a claim with primary evidence
    p1 = (await client.post("/api/projects", json={"title": "Bab-el-Mandeb Security Incident"})).json()
    p1_id = p1["id"]

    c1 = (await client.post(
        f"/api/projects/{p1_id}/claims",
        json={
            "text": "Bulk carrier MV Gibraltar Eagle struck by anti-ship ballistic missile",
            "evidence": [{"url": "https://reuters.com/gibraltar-eagle", "label": "Reuters Wire"}],
        },
    )).json()
    c1_id = c1["id"]

    # Confirm the claim in Project 1 -> triggers cache write
    patch_res = await client.patch(
        f"/api/projects/{p1_id}/claims/{c1_id}",
        json={"status": "confirmed"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "confirmed"

    # 2. Project 2: Another project a week later encounters the same claim
    p2 = (await client.post("/api/projects", json={"title": "Houthi Anti-Ship Capabilities"})).json()
    p2_id = p2["id"]

    c2 = (await client.post(
        f"/api/projects/{p2_id}/claims",
        json={"text": "Bulk carrier MV Gibraltar Eagle struck by anti-ship ballistic missile"},
    )).json()
    c2_id = c2["id"]
    assert c2["status"] == "unverified"
    assert len(c2["evidence"]) == 0

    # 3. Check for cache match
    match_res = await client.get(f"/api/projects/{p2_id}/claims/{c2_id}/cache-match")
    assert match_res.status_code == 200
    match_data = match_res.json()
    assert match_data["has_match"] is True
    assert match_data["status"] == "confirmed"
    assert match_data["verified_in_project_id"] == p1_id
    assert len(match_data["evidence"]) >= 1

    # 4. Apply cache to Project 2 claim
    apply_res = await client.post(f"/api/projects/{p2_id}/claims/{c2_id}/apply-cache")
    assert apply_res.status_code == 200
    applied_data = apply_res.json()
    assert applied_data["status"] == "confirmed"
    assert len(applied_data["evidence"]) >= 1
    assert applied_data["evidence"][0]["url"] == "https://reuters.com/gibraltar-eagle"
