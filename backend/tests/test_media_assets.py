"""Tests for Phase 6: B-Roll & Media Asset Staging (Uploads, Pillow Compositing, NLE Relinking, Endpoints)."""
import io
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest
from httpx import AsyncClient
from PIL import Image

from app.models.project import Script, MediaAsset
from app.services import production, render, nle_export


@pytest.fixture(autouse=True)
def cleanup_media_uploads():
    yield
    p = Path("media_uploads")
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)


def _dummy_image_bytes(width: int = 640, height: int = 480, color=(30, 80, 160)) -> bytes:
    """Generate PNG bytes of given dimensions."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _sample_script(project_id: str = "proj_asset_test"):
    return SimpleNamespace(
        project_id=project_id,
        content={
            "title": "Taiwan Strait Patrols",
            "logline": "Naval operations in the contested strait.",
            "acts": [
                {
                    "title": "Act 1: Reconnaissance",
                    "timecode": "00:00–01:00",
                    "beats": [
                        {
                            "kind": "fact",
                            "narration": "A maritime patrol plane flew through the median line on Tuesday morning.",
                            "citations": ["S1"],
                            "broll": "Radar flight path of patrol aircraft",
                        },
                        {
                            "kind": "analysis",
                            "narration": "The passage follows heightened surveillance over surrounding air defense zones.",
                            "citations": ["S2"],
                            "broll": "Map of air defense identification zone",
                        },
                    ],
                }
            ],
            "open_questions": [],
        },
        sources=[
            {"id": "S1", "outlet": "CNA", "governance_type": "commercial_wire"},
            {"id": "S2", "outlet": "Reuters", "governance_type": "commercial_wire"},
        ],
    )


async def _seed_project(client: AsyncClient, db_session, script_obj, *, project_title="Asset Test"):
    project = (await client.post("/api/projects", json={"title": project_title})).json()
    db_session.add(Script(
        id=f"scr_{project['id']}",
        project_id=project["id"],
        content=script_obj.content,
        sources=script_obj.sources,
        stats={},
        model="test",
    ))
    await db_session.commit()
    return project


@pytest.mark.asyncio
async def test_upload_media_asset_and_serve_file(client: AsyncClient, db_session):
    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    img_bytes = _dummy_image_bytes(800, 600, (50, 120, 200))
    files = {"file": ("radar_recon.png", img_bytes, "image/png")}
    data = {"shot_number": "1", "caption": "Recon flight path", "source_credit": "FlightRadar24"}

    res = await client.post(f"/api/projects/{pid}/assets", data=data, files=files)
    assert res.status_code == 200
    asset = res.json()
    assert asset["project_id"] == pid
    assert asset["shot_number"] == 1
    assert asset["filename"] == "radar_recon.png"
    assert asset["content_type"] == "image/png"
    assert asset["width"] == 800
    assert asset["height"] == 600
    assert asset["caption"] == "Recon flight path"
    assert asset["source_credit"] == "FlightRadar24"
    assert f"/api/projects/{pid}/assets/{asset['id']}/file" in asset["url"]

    # Verify serving the uploaded file
    file_res = await client.get(f"/api/projects/{pid}/assets/{asset['id']}/file")
    assert file_res.status_code == 200
    assert file_res.headers["content-type"].startswith("image/png")
    assert len(file_res.content) == len(img_bytes)

    # Verify listing project assets
    list_res = await client.get(f"/api/projects/{pid}/assets")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


@pytest.mark.asyncio
async def test_upload_replaces_existing_shot_asset(client: AsyncClient, db_session):
    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    # First upload
    f1 = {"file": ("first.png", _dummy_image_bytes(400, 300), "image/png")}
    res1 = await client.post(f"/api/projects/{pid}/assets", data={"shot_number": "1"}, files=f1)
    assert res1.status_code == 200
    id1 = res1.json()["id"]

    # Second upload for the same shot replaces it
    f2 = {"file": ("second.jpg", _dummy_image_bytes(1000, 800), "image/jpeg")}
    res2 = await client.post(f"/api/projects/{pid}/assets", data={"shot_number": "1"}, files=f2)
    assert res2.status_code == 200
    id2 = res2.json()["id"]
    assert id1 != id2

    # Listing returns 1 asset
    list_res = await client.get(f"/api/projects/{pid}/assets")
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["id"] == id2

    # Old file is gone
    old_file_res = await client.get(f"/api/projects/{pid}/assets/{id1}/file")
    assert old_file_res.status_code == 404


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_type(client: AsyncClient, db_session):
    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    files = {"file": ("malicious.exe", b"MZ...", "application/x-msdownload")}
    res = await client.post(f"/api/projects/{pid}/assets", data={"shot_number": "1"}, files=files)
    assert res.status_code == 400
    assert "Unsupported file type" in res.json()["detail"]


@pytest.mark.asyncio
async def test_delete_media_asset(client: AsyncClient, db_session):
    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    files = {"file": ("to_delete.png", _dummy_image_bytes(200, 200), "image/png")}
    upload_res = await client.post(f"/api/projects/{pid}/assets", data={"shot_number": "2"}, files=files)
    aid = upload_res.json()["id"]

    del_res = await client.delete(f"/api/projects/{pid}/assets/{aid}")
    assert del_res.status_code == 204

    # File and asset are 404 now
    assert (await client.get(f"/api/projects/{pid}/assets/{aid}/file")).status_code == 404


def test_production_package_attaches_media_assets():
    script = _sample_script()
    dummy_asset = SimpleNamespace(
        id="ast_test123",
        project_id="proj_asset_test",
        shot_number=1,
        filename="recon_flight.png",
        content_type="image/png",
        file_size=12345,
        file_path="/tmp/recon_flight.png",
        caption="Satellite recon",
        source_credit="Maxar",
        width=1920,
        height=1080,
        created_at=None,
    )

    pkg = production.build_production_package(script, assets=[dummy_asset])
    shot1 = pkg["shots"][0]
    shot2 = pkg["shots"][1]

    assert shot1["media_asset"] is not None
    assert shot1["media_asset"]["id"] == "ast_test123"
    assert shot1["media_asset"]["filename"] == "recon_flight.png"
    assert shot1["media_asset"]["source_credit"] == "Maxar"

    # Shot 2 has no asset staged
    assert shot2["media_asset"] is None


def test_card_compositor_with_staged_media_asset():
    script = _sample_script()

    with tempfile.TemporaryDirectory(prefix="gps-media-test-") as tmp:
        tmp_dir = Path(tmp)
        # Create a sample staged B-roll image
        img_path = tmp_dir / "sample_broll.png"
        img_path.write_bytes(_dummy_image_bytes(1280, 720, color=(20, 90, 160)))

        dummy_asset = {
            "id": "ast_999",
            "project_id": "proj_asset_test",
            "shot_number": 1,
            "filename": "sample_broll.png",
            "file_path": str(img_path),
            "source_credit": "Commercial Satellite Agency",
        }

        pkg = production.build_production_package(script, assets=[dummy_asset])
        cards = render.build_cards(pkg, tmp_dir)

        assert len(cards) == 2
        card1_path = cards[0]["path"]
        assert card1_path.exists()

        # Verify composite image dimensions
        with Image.open(card1_path) as cimg:
            assert cimg.size == (1920, 1080)
            assert cimg.format == "PNG"


def test_nle_exports_link_staged_media_assets():
    script = _sample_script()
    dummy_asset = {
        "id": "ast_nle1",
        "project_id": "proj_asset_test",
        "shot_number": 1,
        "filename": "sat_recon.png",
        "file_path": "/media/sat_recon.png",
        "source_credit": "Maxar",
    }
    pkg = production.build_production_package(script, assets=[dummy_asset])

    # FCPXML links asset in resources
    fcpxml = nle_export.export_fcpxml(pkg, fps=30)
    assert 'src="file:///media/sat_recon.png"' in fcpxml
    assert 'value="MEDIA: sat_recon.png"' in fcpxml

    # Premiere XML links pathurl in clipitem
    prem = nle_export.export_premiere_xml(pkg, fps=30)
    assert "<pathurl>file:///media/sat_recon.png</pathurl>" in prem

    # EDL lists staged asset remark
    edl = nle_export.export_edl(pkg, fps=30)
    assert "* STAGED ASSET: sat_recon.png" in edl
    assert "* SOURCE CREDIT: Maxar" in edl
