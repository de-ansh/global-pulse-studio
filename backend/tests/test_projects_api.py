"""Integration tests for project workspaces, dossiers, and narrative generation."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_project_workflow_end_to_end(client: AsyncClient):
    """Verify full creator workflow: project creation -> angles -> dossier -> outline -> export."""
    # 1. Create Project
    proj_payload = {
        "title": "The Suwalki Gap: NATO's Most Dangerous Chokepoint",
        "target_duration_mins": 18,
    }
    create_res = await client.post("/api/projects", json=proj_payload)
    assert create_res.status_code == 201
    proj_data = create_res.json()
    proj_id = proj_data["id"]
    assert proj_data["title"] == proj_payload["title"]
    assert proj_data["status"] == "concept"

    # 2. Generate 4 Narrative Angles
    angles_res = await client.post(f"/api/projects/{proj_id}/angles")
    assert angles_res.status_code == 200
    angles = angles_res.json()
    assert len(angles) == 4
    angle_types = [a["angle_type"] for a in angles]
    assert "resource_economic" in angle_types
    assert "historical_grievance" in angle_types
    assert "deterrence_game_theory" in angle_types

    # 3. Select Angle and Update Project
    update_res = await client.patch(
        f"/api/projects/{proj_id}",
        json={"selected_angle": "deterrence_game_theory"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["selected_angle"] == "deterrence_game_theory"

    # 4. Generate Research Dossier
    dossier_res = await client.post(f"/api/projects/{proj_id}/dossier/generate")
    assert dossier_res.status_code == 200
    dossier = dossier_res.json()
    assert dossier["project_id"] == proj_id
    assert "Suwalki Gap" in dossier["geography"]["chokepoints"]
    assert len(dossier["stakeholders"]) > 0
    # No linked cluster means no coverage to compare, so no invented contradictions.
    assert dossier["contradictions"] == []

    # 5. Generate 5-Act Documentary Outline
    outline_res = await client.post(f"/api/projects/{proj_id}/outline/generate")
    assert outline_res.status_code == 200
    outline = outline_res.json()
    assert len(outline["acts"]) == 5
    assert outline["acts"][0]["title"].startswith("Act I")
    assert len(outline["hook_variants"]) >= 3

    # 6. Fetch Project Detail
    detail_res = await client.get(f"/api/projects/{proj_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["status"] == "scripting"
    assert detail["dossier"] is not None
    assert detail["script_outline"] is not None

    # 7. Export Markdown Production Brief
    export_res = await client.get(f"/api/projects/{proj_id}/export")
    assert export_res.status_code == 200
    md_content = export_res.text
    assert "# Video Essay Production Brief" in md_content
    assert "Suwalki Gap" in md_content
    assert "Act I: The Flashpoint" in md_content
    assert "Hook 1" in md_content

    # 8. Delete Project
    del_res = await client.delete(f"/api/projects/{proj_id}")
    assert del_res.status_code == 204

    # Confirm 404 after deletion
    get_after_del = await client.get(f"/api/projects/{proj_id}")
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"title": "   "},
    {"title": "x" * 513},
    {"title": "ok", "target_duration_mins": 0},
    {"title": "ok", "target_duration_mins": -5},
])
async def test_create_project_rejects_bad_input(client: AsyncClient, payload):
    assert (await client.post("/api/projects", json=payload)).status_code == 422


@pytest.mark.asyncio
async def test_create_project_unknown_cluster_is_404(client: AsyncClient):
    assert (await client.post("/api/projects", json={"title": "ok", "cluster_id": "evt_nope"})).status_code == 404


@pytest.mark.asyncio
async def test_update_project_rejects_unknown_status(client: AsyncClient):
    pid = (await client.post("/api/projects", json={"title": "ok"})).json()["id"]
    assert (await client.patch(f"/api/projects/{pid}", json={"status": "bogus"})).status_code == 422
    assert (await client.patch(f"/api/projects/{pid}", json={"status": "ready"})).status_code == 200


@pytest.mark.asyncio
async def test_generated_angle_title_can_be_selected_for_long_topic(client: AsyncClient):
    """Angle titles embed the topic; selecting one must not trip the length limit."""
    pid = (await client.post("/api/projects", json={"title": "India " + "border " * 60})).json()["id"]
    angles = (await client.post(f"/api/projects/{pid}/angles")).json()
    longest = max((a["title"] for a in angles), key=len)
    assert (await client.patch(f"/api/projects/{pid}", json={"selected_angle": longest})).status_code == 200


@pytest.mark.asyncio
async def test_dossier_stakeholders_are_grounded_in_coverage(client: AsyncClient, db_session):
    from datetime import datetime, timezone, timedelta
    from app.models.source import Source, Article
    from app.models.event import EventCluster

    now = datetime.now(timezone.utc)
    db_session.add_all([
        Source(id="w", name="W", feed_url="https://w.example/rss"),
        EventCluster(id="evt_g", headline="Iran tanker seizure", region="Middle East", key_actors=["Iran", "Israel"]),
    ])
    await db_session.flush()
    db_session.add_all([
        Article(id="g1", source_id="w", cluster_id="evt_g", canonical_hash="g1", title="Iran seizes tanker",
                url="https://w.example/1", published_at=now, entities={"actors": ["Iran"]}),
        Article(id="g2", source_id="w", cluster_id="evt_g", canonical_hash="g2", title="Israel and Iran trade warnings",
                url="https://w.example/2", published_at=now - timedelta(hours=1), entities={"actors": ["Iran", "Israel"]}),
    ])
    await db_session.commit()

    pid = (await client.post("/api/projects", json={"title": "Tanker crisis", "cluster_id": "evt_g"})).json()["id"]
    dossier = (await client.post(f"/api/projects/{pid}/dossier/generate")).json()

    by_actor = {s["actor"]: s for s in dossier["stakeholders"]}
    assert by_actor["Iran"]["role"] == "Named in 2 of 2 reports"
    assert by_actor["Iran"]["example_headline"] == "Iran seizes tanker"
    assert by_actor["Israel"]["role"] == "Named in 1 of 2 reports"
    assert dossier["geography"]["region"] == "Middle East"
    assert "Strategic Zone" not in str(dossier) and "Sovereignty & Deterrence" not in str(dossier)
