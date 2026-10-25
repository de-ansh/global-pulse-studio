"""Tests for source governance classification and state-controlled media risk evaluation."""
import pytest
from httpx import AsyncClient

from app.services.verifier import evaluate_source_governance_risk


def test_evaluate_source_governance_risk_high():
    sources = [
        {"id": "tass", "outlet": "TASS", "governance_type": "state_controlled"},
        {"id": "rt", "outlet": "RT", "governance_type": "state_controlled"},
    ]
    res = evaluate_source_governance_risk(sources)
    assert res["risk_level"] == "high"
    assert res["state_controlled_count"] == 2
    assert "Solely state-controlled media" in res["warning"]


def test_evaluate_source_governance_risk_mixed():
    sources = [
        {"id": "reuters", "outlet": "Reuters", "governance_type": "commercial_wire"},
        {"id": "irna", "outlet": "IRNA", "governance_type": "state_controlled"},
    ]
    res = evaluate_source_governance_risk(sources)
    assert res["risk_level"] == "mixed"
    assert res["state_controlled_count"] == 1
    assert "Includes 1 state-controlled" in res["warning"]


def test_evaluate_source_governance_risk_low():
    sources = [
        {"id": "reuters", "outlet": "Reuters", "governance_type": "commercial_wire"},
        {"id": "bbc", "outlet": "BBC", "governance_type": "public_broadcaster"},
    ]
    res = evaluate_source_governance_risk(sources)
    assert res["risk_level"] == "low"
    assert res["state_controlled_count"] == 0
    assert res["warning"] is None


@pytest.mark.asyncio
async def test_source_governance_api_lifecycle(client: AsyncClient, db_session):
    # 1. Create a state-controlled source
    res = await client.post(
        "/api/radar/sources",
        json={
            "id": "tass_test",
            "name": "TASS Russian News Agency",
            "feed_url": "https://tass.example/rss.xml",
            "governance_type": "state_controlled",
            "region": "Russia / Eurasia",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["governance_type"] == "state_controlled"

    # 2. Update governance type
    patch_res = await client.patch(
        f"/api/radar/sources/{data['id']}",
        json={"governance_type": "commercial_wire"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["governance_type"] == "commercial_wire"
