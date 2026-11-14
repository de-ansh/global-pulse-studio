"""Tests for Phase 5: Professional NLE Timeline Export (FCPXML, Premiere XML, CMX 3600 EDL)."""
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.models.project import Script
from app.services import nle_export
from app.services.production import build_production_package
from app.services.scriptwriter import NEEDS_SOURCE


def _sample_script(project_id: str = "proj_nle"):
    """Script with one normal beat, one blocked [NEEDS SOURCE] beat, and one analysis beat with citations."""
    return SimpleNamespace(
        project_id=project_id,
        content={
            "title": "Suez Canal Blockade",
            "logline": "Maritime chokepoint shutdown economics.",
            "acts": [
                {
                    "title": "Act 1: The Grounding",
                    "timecode": "00:00–01:00",
                    "beats": [
                        {
                            "kind": "fact",
                            "narration": "A 400-meter container ship ran aground diagonally across the narrow canal.",
                            "citations": ["S1"],
                            "broll": "Satellite view of the grounded vessel",
                        },
                        {
                            "kind": "fact",
                            "narration": f"{NEEDS_SOURCE} Tugboat operators reported engine loss before impact.",
                            "citations": ["S2"],
                            "broll": None,
                        },
                    ],
                },
                {
                    "title": "Act 2: The Supply Shock",
                    "timecode": "01:00–02:00",
                    "beats": [
                        {
                            "kind": "analysis",
                            "narration": "Roughly ten billion dollars of cargo is stalled every day the waterway remains blocked.",
                            "citations": ["S1", "S3"],
                            "broll": "Anchor queue chart at northern canal entrance",
                        },
                    ],
                },
            ],
            "open_questions": [],
        },
        sources=[
            {"id": "S1", "kind": "article", "outlet": "Reuters", "title": "Ever Given blocks canal", "governance_type": "commercial_wire"},
            {"id": "S2", "kind": "article", "outlet": "State News", "title": "Tug operations", "governance_type": "state_controlled"},
            {"id": "S3", "kind": "article", "outlet": "Lloyd's List", "title": "Daily trade impact"},
        ],
    )


def test_timecode_and_frame_conversions():
    # 30 fps
    assert nle_export.seconds_to_frames(0.0, 30) == 0
    assert nle_export.seconds_to_frames(1.0, 30) == 30
    assert nle_export.seconds_to_frames(1.5, 30) == 45
    assert nle_export.seconds_to_smpte(0.0, 30) == "00:00:00:00"
    assert nle_export.seconds_to_smpte(1.5, 30) == "00:00:01:15"
    assert nle_export.seconds_to_smpte(65.0, 30) == "00:01:05:00"
    assert nle_export.seconds_to_smpte(3661.1, 30) == "01:01:01:03"

    # 24 fps
    assert nle_export.seconds_to_frames(1.0, 24) == 24
    assert nle_export.seconds_to_smpte(1.5, 24) == "00:00:01:12"

    # 60 fps
    assert nle_export.seconds_to_frames(0.5, 60) == 30
    assert nle_export.seconds_to_smpte(0.5, 60) == "00:00:00:30"


def test_fcpxml_export_structure():
    script = _sample_script()
    pkg = build_production_package(script)

    xml_text = nle_export.export_fcpxml(pkg, fps=30)
    root = ET.fromstring(xml_text)

    assert root.tag == "fcpxml"
    assert root.attrib["version"] == "1.9"

    # Format resource verification
    fmt = root.find(".//format")
    assert fmt is not None
    assert fmt.attrib["name"] == "FFVideoFormat1080p30"
    assert fmt.attrib["width"] == "1920"
    assert fmt.attrib["height"] == "1080"

    # Spine gaps
    spine = root.find(".//spine")
    assert spine is not None
    gaps = spine.findall("gap")
    # Only 2 renderable shots (blocked beat Shot 02 must be excluded)
    assert len(gaps) == 2
    assert "SHOT 01" in gaps[0].attrib["name"]
    assert "SHOT 03" in gaps[1].attrib["name"]

    # Markers for B-roll and citations
    markers = gaps[0].findall("marker")
    marker_values = [m.attrib["value"] for m in markers]
    assert any("B-ROLL:" in v for v in marker_values)
    assert any("SOURCES:" in v for v in marker_values)


def test_premiere_xml_export_structure():
    script = _sample_script()
    pkg = build_production_package(script)

    xml_text = nle_export.export_premiere_xml(pkg, fps=30)
    root = ET.fromstring(xml_text)

    assert root.tag == "xmeml"
    assert root.attrib["version"] == "5"

    seq = root.find("sequence")
    assert seq is not None
    assert seq.find("name").text == "Suez Canal Blockade"
    assert int(seq.find("duration").text) > 0

    # Rate verification
    assert seq.find(".//rate/timebase").text == "30"

    # Clipitems
    clipitems = seq.findall(".//clipitem")
    assert len(clipitems) == 2
    assert "SHOT 01" in clipitems[0].find("name").text
    assert "SHOT 03" in clipitems[1].find("name").text

    # Start and end frame continuity
    start0 = int(clipitems[0].find("start").text)
    end0 = int(clipitems[0].find("end").text)
    start1 = int(clipitems[1].find("start").text)
    end1 = int(clipitems[1].find("end").text)
    assert start0 == 0
    assert start1 == end0
    assert end1 > start1

    # Markers
    markers = clipitems[0].findall("marker")
    assert len(markers) >= 1
    m_comments = [m.find("comment").text for m in markers if m.find("comment") is not None]
    assert any("Satellite view" in c for c in m_comments)


def test_edl_export_structure():
    script = _sample_script()
    pkg = build_production_package(script)

    edl = nle_export.export_edl(pkg, fps=30)
    assert "TITLE: SUEZ CANAL BLOCKADE" in edl
    assert "FCM: NON-DROP FRAME" in edl

    # Event line check
    assert "001  AX       V     C        00:00:00:00" in edl
    assert "* FROM CLIP NAME: SHOT 01 - ACT 1: THE GROUNDING (FACT)" in edl
    assert "* B-ROLL: Satellite view of the grounded vessel" in edl
    assert "* CITATIONS: S1 (Reuters)" in edl

    # Second event
    assert "002  AX       V     C" in edl
    assert "* FROM CLIP NAME: SHOT 03 - ACT 2: THE SUPPLY SHOCK (ANALYSIS)" in edl


def test_empty_or_all_blocked_raises_nothing_to_export():
    pkg = {"shots": [{"included_in_timeline": False, "duration_seconds": None}]}
    with pytest.raises(nle_export.NothingToExport):
        nle_export.export_fcpxml(pkg)
    with pytest.raises(nle_export.NothingToExport):
        nle_export.export_premiere_xml(pkg)
    with pytest.raises(nle_export.NothingToExport):
        nle_export.export_edl(pkg)


def test_build_nle_export_dispatcher():
    script = _sample_script()
    pkg = build_production_package(script)

    fcpxml = nle_export.build_nle_export(pkg, format="fcpxml", fps=30)
    assert fcpxml["media_type"] == "application/xml"
    assert fcpxml["extension"] == "fcpxml"
    assert "<fcpxml" in fcpxml["content"]

    prem = nle_export.build_nle_export(pkg, format="premiere", fps=24)
    assert prem["media_type"] == "application/xml"
    assert prem["extension"] == "xml"
    assert "<xmeml" in prem["content"]

    edl = nle_export.build_nle_export(pkg, format="edl", fps=25)
    assert edl["media_type"] == "text/plain"
    assert edl["extension"] == "edl"
    assert "TITLE:" in edl["content"]

    with pytest.raises(ValueError) as exc1:
        nle_export.build_nle_export(pkg, format="invalid_format")
    assert "Unsupported NLE export format" in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        nle_export.build_nle_export(pkg, format="fcpxml", fps=120)
    assert "Unsupported framerate" in str(exc2.value)


# ============================================================================
# API Endpoint Tests
# ============================================================================

async def _seed_project(client: AsyncClient, db_session, script_obj, *, project_title="NLE Test"):
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
async def test_timeline_export_endpoint_404_no_project(client: AsyncClient):
    res = await client.get("/api/projects/proj_missing/production-package/timeline-export")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_timeline_export_endpoint_404_no_script(client: AsyncClient):
    project = (await client.post("/api/projects", json={"title": "Scriptless"})).json()
    res = await client.get(f"/api/projects/{project['id']}/production-package/timeline-export")
    assert res.status_code == 404
    assert "No narration script yet" in res.json()["detail"]


@pytest.mark.asyncio
async def test_timeline_export_endpoint_400_invalid_params(client: AsyncClient, db_session):
    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    res_fmt = await client.get(f"/api/projects/{pid}/production-package/timeline-export?format=avi")
    assert res_fmt.status_code == 400
    assert "Unsupported format" in res_fmt.json()["detail"]

    res_fps = await client.get(f"/api/projects/{pid}/production-package/timeline-export?fps=999")
    assert res_fps.status_code == 400
    assert "Unsupported framerate" in res_fps.json()["detail"]


@pytest.mark.asyncio
async def test_timeline_export_endpoint_409_all_blocked(client: AsyncClient, db_session):
    blocked_script = SimpleNamespace(
        project_id="all_blocked",
        content={
            "title": "Blocked Script",
            "acts": [{
                "title": "Act 1",
                "beats": [
                    {"kind": "fact", "narration": f"{NEEDS_SOURCE} Unverified", "citations": []}
                ],
            }],
        },
        sources=[],
    )
    project = await _seed_project(client, db_session, blocked_script, project_title="Blocked")
    pid = project["id"]

    res = await client.get(f"/api/projects/{pid}/production-package/timeline-export")
    assert res.status_code == 409
    assert "No valid timed shots" in res.json()["detail"]


@pytest.mark.asyncio
async def test_timeline_export_endpoint_success_fcpxml(client: AsyncClient, db_session):
    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    res = await client.get(f"/api/projects/{pid}/production-package/timeline-export?format=fcpxml&fps=30")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/xml")
    assert 'attachment; filename="timeline-' in res.headers["content-disposition"]
    assert res.headers["content-disposition"].endswith('.fcpxml"')
    assert "<fcpxml" in res.text


@pytest.mark.asyncio
async def test_timeline_export_endpoint_success_premiere(client: AsyncClient, db_session):
    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    res = await client.get(f"/api/projects/{pid}/production-package/timeline-export?format=premiere&fps=24")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/xml")
    assert 'attachment; filename="timeline-' in res.headers["content-disposition"]
    assert res.headers["content-disposition"].endswith('.xml"')
    assert "<xmeml" in res.text


@pytest.mark.asyncio
async def test_timeline_export_endpoint_success_edl(client: AsyncClient, db_session):
    script = _sample_script()
    project = await _seed_project(client, db_session, script)
    pid = project["id"]

    res = await client.get(f"/api/projects/{pid}/production-package/timeline-export?format=edl&fps=25")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert 'attachment; filename="timeline-' in res.headers["content-disposition"]
    assert res.headers["content-disposition"].endswith('.edl"')
    assert "TITLE: SUEZ CANAL BLOCKADE" in res.text
