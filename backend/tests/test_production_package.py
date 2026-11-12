"""Tests for the video production package: shot list, timings, captions, narration text and endpoints."""
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.models.project import Script
from app.services.production import (
    build_production_package,
    format_clock,
    format_runtime,
    narration_text,
)
from app.services.scriptwriter import NEEDS_SOURCE


def _script(project_id: str = "proj_production"):
    """A stored script with one blocked beat, an unknown citation and a state-controlled source."""
    return SimpleNamespace(
        project_id=project_id,
        content={
            "title": "Strait of Hormuz: The Chokepoint",
            "logline": "A tanker war in the world's most important oil passage.",
            "acts": [
                {
                    "title": "Cold open",
                    "timecode": "00:00–01:00",
                    "beats": [
                        {
                            "kind": "fact",
                            "narration": "A destroyer entered the strait on Thursday.",
                            "citations": ["S1", "S9"],
                            "broll": "Aerial of the strait",
                        },
                        {
                            "kind": "fact",
                            "narration": f"{NEEDS_SOURCE} The navy claimed it fired warning shots.",
                            "citations": ["S2"],
                            "broll": None,
                        },
                    ],
                },
                {
                    "title": "Context",
                    "timecode": "01:00–03:00",
                    "beats": [
                        {
                            "kind": "analysis",
                            "narration": "Analysts say the passage remains vital to global markets.",
                            "citations": ["S2", "C1"],
                            "broll": "Map of tanker routes",
                        },
                    ],
                },
            ],
            "open_questions": [],
        },
        sources=[
            {
                "id": "S1",
                "kind": "article",
                "title": "Destroyer enters strait",
                "outlet": "Reuters",
                "url": "https://reuters.example/a",
                "published_at": "2026-11-11",
                "governance_type": "commercial_wire",
            },
            {
                "id": "S2",
                "kind": "article",
                "title": "Fleet begins exercise",
                "outlet": "TASS",
                "url": "https://tass.example/a",
                "published_at": "2026-11-11",
                "governance_type": "state_controlled",
            },
            {
                "id": "C1",
                "kind": "claim",
                "text": "The strait carries a fifth of global oil.",
                "status": "confirmed",
                "governance_type": None,
            },
        ],
    )


def test_format_clock_and_runtime():
    assert format_clock(0) == "00:00:00"
    assert format_clock(3661.5) == "01:01:01"
    assert format_clock(61.25, millis=True, separator=",") == "00:01:01,250"
    assert format_clock(61.25, millis=True, separator=".") == "00:01:01.250"
    assert format_runtime(42) == "00:42"
    assert format_runtime(3672) == "01:01:12"


def test_package_manifest_shape_and_monotonic_timings():
    package = build_production_package(_script(), voice="Kore")

    assert package["title"] == "Strait of Hormuz: The Chokepoint"
    assert package["total_shots"] == 3
    assert package["included_shots"] == 2
    assert package["skipped_shots"] == 1
    assert package["needs_source_shots"] == 1
    assert [s["shot_number"] for s in package["shots"]] == [1, 2, 3]

    first, blocked, third = package["shots"]
    assert first["included_in_timeline"] is True
    assert first["start_seconds"] == 0.0
    assert first["end_seconds"] > first["start_seconds"]
    assert first["start_timecode"] == "00:00:00"
    assert first["duration_seconds"] == first["end_seconds"]

    # Blocked beats have no timing at all and do not advance the cursor.
    assert blocked["needs_source"] is True
    assert blocked["included_in_timeline"] is False
    assert blocked["start_seconds"] is None
    assert blocked["end_seconds"] is None
    assert blocked["duration_seconds"] is None
    assert blocked["start_timecode"] is None

    # The next included shot starts where the previous included shot ended.
    assert third["start_seconds"] == first["end_seconds"]
    assert third["end_seconds"] >= third["start_seconds"]

    narration = package["narration"]
    assert narration["voice"] == "Kore"
    assert narration["words_per_minute"] == 150
    expected_words = len("A destroyer entered the strait on Thursday.".split()) + len(
        "Analysts say the passage remains vital to global markets.".split()
    )
    assert narration["word_count"] == expected_words
    assert narration["estimated_runtime_seconds"] == third["end_seconds"]
    assert narration["estimated_runtime_timecode"] == format_runtime(third["end_seconds"])


def test_citations_resolve_unknowns_and_governance():
    package = build_production_package(_script())
    first = package["shots"][0]
    citations = {c["id"]: c for c in first["citations"]}

    assert citations["S1"]["found"] is True
    assert citations["S1"]["kind"] == "article"
    assert citations["S1"]["outlet"] == "Reuters"
    assert citations["S1"]["governance_type"] == "commercial_wire"

    # Unknown IDs stay visible as flags rather than being silently dropped.
    assert citations["S9"]["found"] is False
    assert citations["S9"]["kind"] == "unknown"
    assert any("S9" in w for w in package["warnings"])

    third = package["shots"][2]
    tass = next(c for c in third["citations"] if c["id"] == "S2")
    assert tass["governance_type"] == "state_controlled"
    assert any("state-controlled" in w and "S2" in w for w in package["warnings"])

    claim = next(c for c in third["citations"] if c["id"] == "C1")
    assert claim["kind"] == "claim"
    assert claim["text"] == "The strait carries a fifth of global oil."


def test_blocked_beats_are_excluded_from_captions_and_narration():
    package = build_production_package(_script())

    srt = package["captions_srt"]
    vtt = package["captions_vtt"]
    assert "A destroyer entered the strait on Thursday." in srt
    assert "Analysts say the passage remains vital to global markets." in srt
    assert "warning shots" not in srt
    assert NEEDS_SOURCE not in srt
    assert vtt.startswith("WEBVTT\n\n")
    assert "warning shots" not in vtt
    assert "-->" in srt

    text = narration_text(package)
    assert "A destroyer entered the strait on Thursday." in text
    assert "Analysts say the passage remains vital to global markets." in text
    assert "warning shots" not in text
    assert NEEDS_SOURCE not in text


def test_shotlist_markdown_and_csv_keep_blocked_beats_visible():
    package = build_production_package(_script())

    markdown = package["shotlist_markdown"]
    assert "# Shot List — Strait of Hormuz: The Chokepoint" in markdown
    assert "## Timeline" in markdown
    assert "## Blocked — source needed before recording" in markdown
    assert "S2 (TASS)*" in markdown  # state-controlled citations are flagged
    assert "S9" in markdown  # unknown citations are not hidden

    csv = package["shotlist_csv"]
    assert csv.splitlines()[0].startswith("shot_number,act,act_timecode")
    assert "yes" in csv and "no" in csv
    assert "warning shots" in csv  # blocked rows are retained for the editor
    # CSV marks the URL-free citation label exactly like the Markdown.
    assert "S2 (TASS)*" in csv


def test_empty_script_warns_and_produces_no_timing():
    package = build_production_package(SimpleNamespace(project_id="proj_empty", content={}, sources=[]))
    assert package["total_shots"] == 0
    assert package["included_shots"] == 0
    assert package["narration"]["estimated_runtime_seconds"] == 0.0
    assert package["captions_srt"] == ""
    assert package["captions_vtt"] == "WEBVTT\n\n"
    assert narration_text(package) == ""
    assert any("no beats" in w for w in package["warnings"])


async def _project_with_script(client: AsyncClient, db_session, content, sources, *, script_id="scr_prod"):
    project = (await client.post("/api/projects", json={"title": "Production test"})).json()
    db_session.add(Script(
        id=script_id,
        project_id=project["id"],
        content=content,
        sources=sources,
        stats={},
        model="test",
    ))
    await db_session.commit()
    return project


@pytest.mark.asyncio
async def test_production_endpoints_404_without_script(client: AsyncClient, db_session):
    project = (await client.post("/api/projects", json={"title": "No script yet"})).json()
    pid = project["id"]

    assert (await client.get(f"/api/projects/{pid}/production-package")).status_code == 404
    assert (await client.get(f"/api/projects/{pid}/production-package/shotlist")).status_code == 404
    assert (await client.get(f"/api/projects/{pid}/production-package/captions")).status_code == 404
    assert (await client.post(f"/api/projects/{pid}/production-package/narration")).status_code == 404
    assert (await client.get("/api/projects/proj_missing/production-package")).status_code == 404


@pytest.mark.asyncio
async def test_production_package_endpoint(client: AsyncClient, db_session):
    script = _script()
    project = await _project_with_script(client, db_session, script.content, script.sources)
    pid = project["id"]

    res = await client.get(f"/api/projects/{pid}/production-package")
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == pid
    assert data["total_shots"] == 3
    assert data["included_shots"] == 2
    assert data["needs_source_shots"] == 1
    assert data["narration"]["voice"]  # defaults to settings.GEMINI_TTS_VOICE
    assert data["shots"][1]["included_in_timeline"] is False
    assert data["shots"][1]["start_seconds"] is None
    assert data["captions_vtt"].startswith("WEBVTT")

    overridden = (await client.get(f"/api/projects/{pid}/production-package?voice=Puck")).json()
    assert overridden["narration"]["voice"] == "Puck"


@pytest.mark.asyncio
async def test_shotlist_and_caption_downloads(client: AsyncClient, db_session):
    script = _script()
    project = await _project_with_script(client, db_session, script.content, script.sources)
    pid = project["id"]

    md = await client.get(f"/api/projects/{pid}/production-package/shotlist")
    assert md.status_code == 200
    assert md.headers["content-type"].startswith("text/markdown")
    assert "attachment; filename=" in md.headers["content-disposition"]
    assert "## Shot List" in md.text or "# Shot List" in md.text

    csv = await client.get(f"/api/projects/{pid}/production-package/shotlist?format=csv")
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert csv.text.startswith("shot_number,")

    srt = await client.get(f"/api/projects/{pid}/production-package/captions")
    assert srt.status_code == 200
    assert srt.headers["content-type"].startswith("text/srt")
    assert "-->" in srt.text

    vtt = await client.get(f"/api/projects/{pid}/production-package/captions?format=vtt")
    assert vtt.status_code == 200
    assert vtt.headers["content-type"].startswith("text/vtt")
    assert vtt.text.startswith("WEBVTT")

    assert (await client.get(f"/api/projects/{pid}/production-package/shotlist?format=pdf")).status_code == 400
    assert (await client.get(f"/api/projects/{pid}/production-package/captions?format=txt")).status_code == 400


@pytest.mark.asyncio
async def test_narration_requires_gemini_key(client: AsyncClient, db_session):
    script = _script()
    project = await _project_with_script(client, db_session, script.content, script.sources)
    pid = project["id"]

    res = await client.post(f"/api/projects/{pid}/production-package/narration")
    assert res.status_code == 503
    assert "GPS_GEMINI_API_KEY" in res.json()["detail"]


@pytest.mark.asyncio
async def test_narration_conflicts_when_every_beat_is_blocked(client: AsyncClient, db_session):
    content = {
        "title": "All blocked",
        "logline": "",
        "acts": [{
            "title": "Act 1",
            "timecode": "00:00–01:00",
            "beats": [
                {"kind": "fact", "narration": f"{NEEDS_SOURCE} Unverified claim.", "citations": []},
            ],
        }],
    }
    project = await _project_with_script(
        client, db_session, content, [], script_id="scr_all_blocked"
    )
    pid = project["id"]

    package = (await client.get(f"/api/projects/{pid}/production-package")).json()
    assert package["included_shots"] == 0
    assert package["captions_srt"] == ""

    res = await client.post(f"/api/projects/{pid}/production-package/narration")
    assert res.status_code == 409
