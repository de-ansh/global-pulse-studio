"""Tests for multimedia reverse search, recycled footage, and synthetic media verification."""
import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.project import Project, Claim
from app.services.multimedia import (
    extract_years_from_urls_or_titles,
    check_simulation_cues,
    evaluate_web_detection_result,
    evaluate_heuristic_media,
    verify_media_provenance,
)


def test_extract_years():
    urls = [
        "https://archive.org/details/syria_airstrike_2018_footage",
        "https://cdn.news.com/uploads/2021/08/explosion.jpg",
        "https://domain.com/article/no-dates-here",
    ]
    years = extract_years_from_urls_or_titles(urls)
    assert 2018 in years
    assert 2021 in years
    assert len(years) == 2


def test_check_simulation_cues():
    tags = ["Aerial combat", "Arma 3 simulation", "Military jet"]
    assert check_simulation_cues(tags) == "Arma 3"

    dcs_tags = ["DCS World dogfight", "F-16 cockpit"]
    assert check_simulation_cues(dcs_tags) == "Dcs World"

    clean_tags = ["Pentagon briefing", "Reuters dispatch", "Press conference"]
    assert check_simulation_cues(clean_tags) is None


def test_evaluate_web_detection_simulation():
    web_detection = {
        "bestGuessLabels": [{"label": "Arma 3 gameplay footage"}],
        "webEntities": [{"description": "Arma 3"}, {"description": "Video game"}],
        "pagesWithMatchingImages": [{"url": "https://youtube.com/watch?v=12345", "pageTitle": "Epic Arma 3 dogfight"}],
    }
    result = evaluate_web_detection_result("https://x.com/viral_clip.mp4", web_detection, target_year=2026)
    assert result["is_synthetic_or_game"] is True
    assert result["verdict"] == "Synthetic / Video Game Footage"
    assert result["risk_level"] == "high"


def test_evaluate_web_detection_recycled_footage():
    web_detection = {
        "bestGuessLabels": [{"label": "Donbas shelling"}],
        "webEntities": [{"description": "Artillery strike"}],
        "pagesWithMatchingImages": [
            {"url": "https://news.com/2015/02/donbas_strike.html", "pageTitle": "2015 artillery barrage in Donetsk"},
        ],
    }
    result = evaluate_web_detection_result("https://x.com/breaking_strike_2026.mp4", web_detection, target_year=2026)
    assert result["is_recycled_footage"] is True
    assert result["earliest_seen_year"] == 2015
    assert result["verdict"] == "Recycled Footage Warning"
    assert result["risk_level"] == "high"


def test_evaluate_heuristic_media_simulation_and_dates():
    sim_res = evaluate_heuristic_media("https://cdn.example.com/videos/arma3_strike_demo.mp4", target_year=2026)
    assert sim_res["is_synthetic_or_game"] is True

    archival_res = evaluate_heuristic_media("https://media.org/uploads/2019/11/protest.jpg", target_year=2026)
    assert archival_res["is_recycled_footage"] is True
    assert archival_res["earliest_seen_year"] == 2019


@pytest.mark.asyncio
async def test_verify_claim_media_api(client: AsyncClient, db_session: AsyncSession):
    # Setup test project and claim
    proj = Project(id="proj_media_test", title="Border Escalation", working_slug="border-escalation")
    db_session.add(proj)
    await db_session.commit()

    claim = Claim(
        id="clm_media_test_1",
        project_id="proj_media_test",
        text="Viral video shows hypersonic missile strike on coastal base.",
        status="unverified",
        evidence=[{"url": "https://archive.com/2020/04/missile_test.mp4", "label": "Social clip"}],
    )
    db_session.add(claim)
    await db_session.commit()

    resp = await client.post(
        f"/api/projects/{proj.id}/claims/{claim.id}/verify-media",
        json={"media_url": "https://archive.com/2020/04/missile_test.mp4"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["media_url"] == "https://archive.com/2020/04/missile_test.mp4"
    assert data["is_recycled_footage"] is True
    assert data["earliest_seen_year"] == 2020
    assert data["risk_level"] == "high"
