"""Tests for the Epistemic Stance Classifier (Reported Speech vs Empirical Reality)."""
import pytest
from httpx import AsyncClient

from app.services.verifier import classify_epistemic_stance


def test_classify_official_attribution():
    text1 = "The Russian Defense Ministry claimed 15 Ukrainian drones were shot down over Belgorod."
    res1 = classify_epistemic_stance(text1)
    assert res1["level"] == "official_attribution"
    assert "Defense Ministry" in res1["attributed_to"]

    text2 = "According to the Pentagon, naval escorts began operations in the Red Sea."
    res2 = classify_epistemic_stance(text2)
    assert res2["level"] == "official_attribution"
    assert "Pentagon" in res2["attributed_to"]

    text3 = "Houthi military spokesperson stated commercial vessels must alter heading."
    res3 = classify_epistemic_stance(text3)
    assert res3["level"] == "official_attribution"
    assert "spokesperson" in res3["attributed_to"].lower()


def test_classify_unattributed_rumor():
    text = "Unconfirmed reports suggest multiple explosions occurred near the ammunition depot."
    res = classify_epistemic_stance(text)
    assert res["level"] == "unattributed_rumor"
    assert res["attributed_to"] is None
    assert "corroboration" in res["editorial_guidance"]

    text2 = "Social media clips show plumes of smoke purportedly rising from the airbase."
    res2 = classify_epistemic_stance(text2)
    assert res2["level"] == "unattributed_rumor"


def test_classify_analysis_or_opinion():
    text = "Analysts believe the blockade will likely cause immediate shipping delays."
    res = classify_epistemic_stance(text)
    assert res["level"] == "analysis_or_opinion"
    assert "assessment" in res["editorial_guidance"]


def test_classify_empirical_event():
    text = "Commercial tanker Transworld Navigator docked at Port of Djibouti on 22 October."
    res = classify_epistemic_stance(text)
    assert res["level"] == "empirical_event"
    assert res["attributed_to"] is None


@pytest.mark.asyncio
async def test_claim_epistemic_api_lifecycle(client: AsyncClient, db_session):
    proj_res = await client.post("/api/projects", json={"title": "Red Sea Crisis Analysis"})
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]

    # 1. Post official attribution claim -> auto-classified
    res_claim1 = await client.post(
        f"/api/projects/{proj_id}/claims",
        json={"text": "U.S. Central Command stated two anti-ship missiles were destroyed."},
    )
    assert res_claim1.status_code == 201
    data1 = res_claim1.json()
    assert data1["epistemic_level"] == "official_attribution"
    assert "Central Command" in data1["attributed_to"]

    # 2. Post rumor claim -> auto-classified
    res_claim2 = await client.post(
        f"/api/projects/{proj_id}/claims",
        json={"text": "Unconfirmed reports claim carrier suffered structural damage."},
    )
    assert res_claim2.status_code == 201
    data2 = res_claim2.json()
    assert data2["epistemic_level"] == "unattributed_rumor"

    # 3. Patch claim with manual override
    res_patch = await client.patch(
        f"/api/projects/{proj_id}/claims/{data2['id']}",
        json={"epistemic_level": "empirical_event", "status": "disputed"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["epistemic_level"] == "empirical_event"
    assert res_patch.json()["status"] == "disputed"
