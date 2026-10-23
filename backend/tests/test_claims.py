"""Tests for the per-project claim ledger."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.project import Claim


@pytest.mark.asyncio
async def test_claim_ledger_lifecycle(client: AsyncClient, db_session):
    proj_id = (await client.post("/api/projects", json={"title": "Hormuz tanker seizure"})).json()["id"]
    base = f"/api/projects/{proj_id}/claims"

    res = await client.post(base, json={"text": "Tanker seized on 20 Oct", "evidence": [{"url": "https://example.com/ais", "label": "AIS track"}]})
    assert res.status_code == 201
    claim = res.json()
    assert claim["status"] == "unverified"
    assert claim["status_changed_at"] is None

    await client.post(base, json={"text": "Crew of 23 detained"})

    # Unsafe evidence links and unknown statuses are rejected
    assert (await client.post(base, json={"text": "x", "evidence": [{"url": "javascript:alert(1)"}]})).status_code == 422
    assert (await client.patch(f"{base}/{claim['id']}", json={"status": "probably"})).status_code == 422

    upd = await client.patch(f"{base}/{claim['id']}", json={"status": "confirmed", "note": "Matches AIS and port authority notice"})
    assert upd.status_code == 200
    assert upd.json()["status"] == "confirmed"
    assert upd.json()["status_changed_at"] is not None

    export = (await client.get(f"/api/projects/{proj_id}/export")).text
    assert "WARNING: 1 of 2 claims are not confirmed" in export
    assert "**[CONFIRMED]** Tanker seized on 20 Oct" in export
    assert "**[UNVERIFIED]** Crew of 23 detained" in export
    assert "[AIS track](https://example.com/ais)" in export

    # Claims are scoped to their project
    other = (await client.post("/api/projects", json={"title": "Other"})).json()["id"]
    assert (await client.patch(f"/api/projects/{other}/claims/{claim['id']}", json={"status": "false"})).status_code == 404

    assert (await client.delete(f"{base}/{claim['id']}")).status_code == 204
    assert len((await client.get(base)).json()) == 1

    # Deleting the project removes its claims
    assert (await client.delete(f"/api/projects/{proj_id}")).status_code == 204
    assert (await client.get(base)).status_code == 404
    assert (await db_session.execute(select(Claim).where(Claim.project_id == proj_id))).first() is None


@pytest.mark.asyncio
async def test_claim_fact_check_searches_claim_text(client: AsyncClient, monkeypatch):
    from app.config import settings
    from app.services import factcheck

    seen = {}

    async def fake_search(query, api_key):
        seen["query"] = query
        return [{"claim": "x", "publisher": "AFP", "rating": "False", "url": "https://factcheck.afp.com/x"}]

    monkeypatch.setattr(settings, "FACTCHECK_API_KEY", "k")
    monkeypatch.setattr(factcheck, "search_fact_checks", fake_search)
    pid = (await client.post("/api/projects", json={"title": "T"})).json()["id"]
    cid = (await client.post(f"/api/projects/{pid}/claims", json={"text": "Iran seized two tankers in the Strait of Hormuz on Monday"})).json()["id"]

    res = await client.get(f"/api/projects/{pid}/claims/{cid}/factchecks")
    assert res.status_code == 200
    assert res.json()[0]["publisher"] == "AFP"
    assert seen["query"] == "Iran seized two tankers Strait Hormuz Monday"

    assert (await client.get(f"/api/projects/{pid}/claims/clm_nope/factchecks")).status_code == 404
    monkeypatch.setattr(settings, "FACTCHECK_API_KEY", "")
    assert (await client.get(f"/api/projects/{pid}/claims/{cid}/factchecks")).status_code == 503


def test_parse_fact_checks_drops_non_web_urls():
    from app.services.factcheck import parse_fact_checks
    rows = parse_fact_checks({"claims": [{"text": "c", "claimReview": [
        {"url": "javascript:alert(1)", "textualRating": "False"},
        {"url": "https://ok.example/review", "textualRating": "True"},
    ]}]})
    assert [r["url"] for r in rows] == ["https://ok.example/review"]
