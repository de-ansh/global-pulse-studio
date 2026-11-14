"""Tests for Phase 4: Watchable Draft Animatic (Pillow cards, ffmpeg MP4 assembly, API endpoints)."""
import io
import shutil
import tempfile
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from PIL import Image

from app.models.project import Script
from app.services import render
from app.services.production import build_production_package
from app.services.scriptwriter import NEEDS_SOURCE


def _dummy_wav(duration_seconds: float = 1.0, sample_rate: int = 24000) -> bytes:
    """Generate minimal valid mono PCM WAV bytes for audio muxing tests."""
    buf = io.BytesIO()
    num_frames = int(duration_seconds * sample_rate)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_frames)
    return buf.getvalue()


def _sample_script(project_id: str = "proj_animatic"):
    """Script with one normal beat, one blocked [NEEDS SOURCE] beat, and one analysis beat with citations."""
    return SimpleNamespace(
        project_id=project_id,
        content={
            "title": "Strait of Hormuz Crisis",
            "logline": "A strategic maritime chokepoint on the brink.",
            "acts": [
                {
                    "title": "Cold Open",
                    "timecode": "00:00–01:00",
                    "beats": [
                        {
                            "kind": "fact",
                            "narration": "A commercial tanker was intercepted inside the strait on Thursday morning.",
                            "citations": ["S1"],
                            "broll": "Satellite imagery of the strait entrance",
                        },
                        {
                            "kind": "fact",
                            "narration": f"{NEEDS_SOURCE} Patrol boats fired warning flares across the bow.",
                            "citations": ["S2"],
                            "broll": None,
                        },
                    ],
                },
                {
                    "title": "Escalation",
                    "timecode": "01:00–02:00",
                    "beats": [
                        {
                            "kind": "analysis",
                            "narration": "Roughly twenty percent of global petroleum flows through this narrow maritime corridor.",
                            "citations": ["S1", "S3"],
                            "broll": "3D bathymetric chart of shipping channels",
                        },
                    ],
                },
            ],
            "open_questions": [],
        },
        sources=[
            {"id": "S1", "kind": "article", "outlet": "Reuters", "title": "Tanker intercepted in Hormuz", "governance_type": "commercial_wire"},
            {"id": "S2", "kind": "article", "outlet": "IRNA", "title": "Patrol operation statement", "governance_type": "state_controlled"},
        ],
    )


def test_toolchain_status():
    status = render.toolchain_status()
    assert isinstance(status["available"], bool)
    assert "ffmpeg" in status
    assert "pillow" in status
    assert isinstance(status["missing"], list)

    with patch("shutil.which", return_value=None):
        mock_status = render.toolchain_status()
        assert not mock_status["available"]
        assert "ffmpeg" in mock_status["missing"]


def test_renderable_shots_filtering():
    script = _sample_script()
    pkg = build_production_package(script)
    shots = render.renderable_shots(pkg)
    # The blocked NEEDS SOURCE beat must be excluded from renderable shots
    assert len(shots) == 2
    assert all(s["included_in_timeline"] for s in shots)
    assert all(s["duration_seconds"] > 0 for s in shots)
    assert all(NEEDS_SOURCE not in s["narration"] for s in shots)


def test_text_helpers_and_broll_detection():
    assert render._clean_text(f"  {NEEDS_SOURCE}  Hello   world  ") == "Hello world"
    assert render.shoot_has_broll({"broll": "Satellite footage"}) is True
    assert render.shoot_has_broll({"broll": None}) is False
    assert render.shoot_has_broll({"broll": ""}) is False
    assert render.shot_has_broll({"broll": "Map"}) is True

    # Unknown citation
    assert render._citation_label({"id": "X99", "found": False}) == "X99 (unknown)"
    # State-controlled citation gets asterisk
    assert "*" in render._citation_label({"id": "S2", "found": True, "outlet": "IRNA", "governance_type": "state_controlled"})


def test_build_cards_generates_valid_pngs():
    script = _sample_script()
    pkg = build_production_package(script)

    with tempfile.TemporaryDirectory(prefix="gps-test-cards-") as tmp:
        cards = render.build_cards(pkg, Path(tmp))
        assert len(cards) == 2
        for card in cards:
            assert card["path"].exists()
            assert card["duration_seconds"] > 0
            with Image.open(card["path"]) as img:
                assert img.size == (1920, 1080)
                assert img.format == "PNG"


def test_build_cards_empty_or_blocked_raises():
    pkg = {
        "shots": [
            {"included_in_timeline": False, "duration_seconds": None},
        ]
    }
    with pytest.raises(render.NothingToRender):
        with tempfile.TemporaryDirectory() as tmp:
            render.build_cards(pkg, Path(tmp))


def test_render_animatic_silent_offline():
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available on host")

    script = _sample_script()
    pkg = build_production_package(script)

    result = render.render_animatic(pkg)
    assert result["narration_mode"] == "silent"
    assert result["width"] == 1920
    assert result["height"] == 1080
    assert result["fps"] == 30
    assert result["shots"] == 2
    assert result["duration_seconds"] > 0
    assert len(result["video"]) > 1000
    # MP4 file begins with standard ftyp box signature within first 16 bytes
    assert b"ftyp" in result["video"][:32]


def test_render_animatic_with_audio_track():
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available on host")

    script = _sample_script()
    pkg = build_production_package(script)
    audio = _dummy_wav(duration_seconds=2.0)

    result = render.render_animatic(pkg, audio_bytes=audio)
    assert result["narration_mode"] == "tts"
    assert len(result["video"]) > 1000
    assert b"ftyp" in result["video"][:32]


def test_render_animatic_unavailable_raises():
    script = _sample_script()
    pkg = build_production_package(script)
    with patch.object(render, "toolchain_status", return_value={"available": False, "missing": ["ffmpeg"]}):
        with pytest.raises(render.RenderUnavailable) as exc:
            render.render_animatic(pkg)
        assert "ffmpeg" in str(exc.value)


def test_render_animatic_nothing_to_render_zero_duration():
    pkg = {"shots": [{"included_in_timeline": True, "duration_seconds": 0.0}]}
    with patch.object(render, "toolchain_status", return_value={"available": True, "missing": []}):
        with pytest.raises(render.NothingToRender):
            render.render_animatic(pkg)


# ============================================================================
# API Endpoint Integration Tests
# ============================================================================

async def _seed_project(client: AsyncClient, db_session, script_obj, *, project_title="Animatic Test"):
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
async def test_animatic_endpoint_404(client: AsyncClient):
    res = await client.get("/api/projects/proj_nonexistent/production-package/animatic")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_animatic_endpoint_404_no_script(client: AsyncClient):
    project = (await client.post("/api/projects", json={"title": "Scriptless"})).json()
    res = await client.get(f"/api/projects/{project['id']}/production-package/animatic")
    assert res.status_code == 404
    assert "No narration script yet" in res.json()["detail"]


@pytest.mark.asyncio
async def test_production_package_includes_toolchain_info(client: AsyncClient, db_session):
    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    res = await client.get(f"/api/projects/{pid}/production-package")
    assert res.status_code == 200
    data = res.json()
    assert "render_toolchain" in data
    assert "available" in data["render_toolchain"]


@pytest.mark.asyncio
async def test_animatic_endpoint_503_when_toolchain_missing(client: AsyncClient, db_session):
    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    with patch("app.services.render.toolchain_status", return_value={"available": False, "missing": ["ffmpeg", "Pillow"]}):
        res = await client.get(f"/api/projects/{pid}/production-package/animatic")
        assert res.status_code == 503
        assert "Render toolchain missing" in res.json()["detail"]


@pytest.mark.asyncio
async def test_animatic_endpoint_409_when_all_beats_blocked(client: AsyncClient, db_session):
    blocked_script = SimpleNamespace(
        project_id="blocked_all",
        content={
            "title": "Blocked Script",
            "acts": [{
                "title": "Act 1",
                "beats": [
                    {"kind": "fact", "narration": f"{NEEDS_SOURCE} Uncited fact", "citations": []}
                ],
            }],
        },
        sources=[],
    )
    project = await _seed_project(client, db_session, blocked_script, project_title="All Blocked")
    pid = project["id"]

    res = await client.get(f"/api/projects/{pid}/production-package/animatic")
    assert res.status_code == 409
    assert "Nothing to render" in res.json()["detail"]


@pytest.mark.asyncio
async def test_animatic_endpoint_success_silent(client: AsyncClient, db_session):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available on host")

    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    res = await client.get(f"/api/projects/{pid}/production-package/animatic")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("video/mp4")
    assert "inline; filename=" in res.headers["content-disposition"]
    assert len(res.content) > 1000
    assert b"ftyp" in res.content[:32]


@pytest.mark.asyncio
async def test_animatic_endpoint_attachment_download(client: AsyncClient, db_session):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available on host")

    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    res = await client.get(f"/api/projects/{pid}/production-package/animatic?download=true")
    assert res.status_code == 200
    assert "attachment; filename=" in res.headers["content-disposition"]


@pytest.mark.asyncio
async def test_animatic_endpoint_with_tts_audio(client: AsyncClient, db_session):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available on host")

    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]
    fake_wav = _dummy_wav(duration_seconds=2.0)

    with patch("app.services.gemini.request_audio", return_value=fake_wav):
        res = await client.get(f"/api/projects/{pid}/production-package/animatic?with_audio=true")
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("video/mp4")
        assert len(res.content) > 1000
