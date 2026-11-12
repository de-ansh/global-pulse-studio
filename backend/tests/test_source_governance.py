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


def _cluster_with_sources(db_session, cluster_id, project_sources, articles):
    from app.models.event import EventCluster
    from app.models.source import Article, Source

    sources = [
        Source(
            id=sid,
            name=name,
            feed_url=f"https://{sid}.example/rss",
            governance_type=governance,
        )
        for sid, name, governance in project_sources
    ]
    cluster = EventCluster(
        id=cluster_id,
        headline="Regional naval exercise",
        severity="crisis",
        region="Indo-Pacific",
        status="active",
        summary="Naval activity in the region",
    )
    return sources, cluster


@pytest.mark.asyncio
async def test_readiness_penalizes_state_controlled_corroboration(client: AsyncClient, db_session):
    from datetime import datetime, timezone

    from app.models.source import Article

    sources, cluster = _cluster_with_sources(
        db_session,
        "cls_gov_high",
        [
            ("gov_tass", "TASS", "state_controlled"),
            ("gov_xinhua", "Xinhua", "state_controlled"),
        ],
        None,
    )
    db_session.add_all([*sources, cluster])
    await db_session.flush()
    published = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)
    db_session.add_all([
        Article(
            id="gov_art_1",
            cluster_id=cluster.id,
            source_id="gov_tass",
            canonical_hash="gov_hash_1",
            title="Pacific fleet begins exercise",
            url="https://gov_tass.example/exercise",
            summary="The Pacific fleet began a large naval exercise on Wednesday.",
            published_at=published,
        ),
        Article(
            id="gov_art_2",
            cluster_id=cluster.id,
            source_id="gov_xinhua",
            canonical_hash="gov_hash_2",
            title="Navy drill starts across regional waters",
            url="https://gov_xinhua.example/drill",
            summary="The navy launched a multi-day drill spanning several regional waters.",
            published_at=published,
        ),
    ])
    await db_session.commit()

    proj_id = (await client.post(
        "/api/projects", json={"title": "Governance high", "cluster_id": cluster.id}
    )).json()["id"]

    readiness = (await client.get(f"/api/projects/{proj_id}/readiness")).json()
    assert readiness["governance_risk"] == "high"
    assert readiness["governance_penalty"] == 25
    assert readiness["state_controlled_sources"] == 2
    gov_check = next(i for i in readiness["checklist"] if i["id"] == "source_governance")
    assert gov_check["passed"] is False
    assert any("state-controlled" in w for w in readiness["warnings"])
    assert readiness["status"] != "ready"

    sheet = (await client.get(f"/api/projects/{proj_id}/source-sheet")).json()
    assert sheet["governance_risk"] == "high"
    assert sheet["state_controlled_sources"] == 2
    assert "Source Governance" in sheet["markdown"]
    assert "HIGH" in sheet["markdown"]


@pytest.mark.asyncio
async def test_readiness_high_governance_caps_ready_verdict(client: AsyncClient, db_session):
    from datetime import datetime, timezone

    from app.models.project import Script
    from app.models.source import Article

    sources, cluster = _cluster_with_sources(
        db_session,
        "cls_gov_cap",
        [
            ("gov_rt", "RT", "state_controlled"),
            ("gov_cgtn", "CGTN", "state_controlled"),
            ("gov_tass3", "TASS", "state_controlled"),
        ],
        None,
    )
    db_session.add_all([*sources, cluster])
    await db_session.flush()
    published = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)
    db_session.add_all([
        Article(
            id="cap_art_1",
            cluster_id=cluster.id,
            source_id="gov_rt",
            canonical_hash="cap_hash_1",
            title="Destroyer enters contested strait",
            url="https://gov_rt.example/strait",
            summary="A destroyer entered the contested strait on Thursday, officials said.",
            published_at=published,
        ),
        Article(
            id="cap_art_2",
            cluster_id=cluster.id,
            source_id="gov_cgtn",
            canonical_hash="cap_hash_2",
            title="Warship crosses waterway amid tensions",
            url="https://gov_cgtn.example/waterway",
            summary="A warship crossed the strategic waterway amid rising regional tensions.",
            published_at=published,
        ),
        Article(
            id="cap_art_3",
            cluster_id=cluster.id,
            source_id="gov_tass3",
            canonical_hash="cap_hash_3",
            title="Navy sends ship into strategic passage",
            url="https://gov_tass3.example/passage",
            summary="The navy sent a ship into the strategic passage on Thursday.",
            published_at=published,
        ),
    ])
    await db_session.commit()

    proj_id = (await client.post(
        "/api/projects", json={"title": "Governance cap", "cluster_id": cluster.id}
    )).json()["id"]
    claim = (await client.post(
        f"/api/projects/{proj_id}/claims",
        json={"text": "A destroyer entered the contested strait"},
    )).json()
    await client.patch(f"/api/projects/{proj_id}/claims/{claim['id']}", json={"status": "confirmed"})
    db_session.add(Script(
        id="scr_gov_cap",
        project_id=proj_id,
        content={},
        sources=[],
        stats={"support": {"contradicted": 0, "supported": 4, "unsupported": 0}},
        model="test",
    ))
    await db_session.commit()

    readiness = (await client.get(f"/api/projects/{proj_id}/readiness")).json()
    assert readiness["governance_risk"] == "high"
    assert readiness["governance_penalty"] == 25
    # Base scoring would be 100 here; the state-media penalty and cap keep it out of "ready".
    assert readiness["score"] == 75
    assert readiness["status"] == "needs_review"


@pytest.mark.asyncio
async def test_readiness_mixed_governance_discounts_score(client: AsyncClient, db_session):
    from datetime import datetime, timezone

    from app.models.source import Article

    sources, cluster = _cluster_with_sources(
        db_session,
        "cls_gov_mixed",
        [
            ("gov_mix_wire", "Reuters", "commercial_wire"),
            ("gov_mix_state", "IRNA", "state_controlled"),
        ],
        None,
    )
    db_session.add_all([*sources, cluster])
    await db_session.flush()
    published = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)
    db_session.add_all([
        Article(
            id="mix_art_1",
            cluster_id=cluster.id,
            source_id="gov_mix_wire",
            canonical_hash="mix_hash_1",
            title="Tanker rerouted after warning",
            url="https://wire.example/tanker",
            summary="A commercial tanker rerouted after a maritime warning was issued.",
            published_at=published,
        ),
        Article(
            id="mix_art_2",
            cluster_id=cluster.id,
            source_id="gov_mix_state",
            canonical_hash="mix_hash_2",
            title="Shipping company changes course",
            url="https://state.example/shipping",
            summary="A shipping company changed course following a navigation advisory.",
            published_at=published,
        ),
    ])
    await db_session.commit()

    proj_id = (await client.post(
        "/api/projects", json={"title": "Governance mixed", "cluster_id": cluster.id}
    )).json()["id"]

    readiness = (await client.get(f"/api/projects/{proj_id}/readiness")).json()
    assert readiness["governance_risk"] == "mixed"
    assert readiness["governance_penalty"] == 8
    assert readiness["state_controlled_sources"] == 1
    # 25 (multi-source baseline) + 15 (2 independent origins) - 8 governance penalty
    assert readiness["score"] == 32
    gov_check = next(i for i in readiness["checklist"] if i["id"] == "source_governance")
    assert gov_check["passed"] is False

