"""Tests for automated PDF dossier generation and export endpoint."""
import pytest
from httpx import AsyncClient

from app.services import pdf_generator


def test_generate_source_sheet_pdf_structure():
    """Verify PDF generator produces valid PDF binary structure with citations and sources."""
    citations = [
        {
            "status": "confirmed",
            "text": "Satellite imagery confirms deployment of air defense battery near the port.",
            "evidence_urls": ["https://reuters.com/world/air-defense-123"],
            "archive_urls": ["https://web.archive.org/web/20261020/https://reuters.com/world/air-defense-123"],
            "verbatim_quotes": ["Air defense battery deployed on northern perimeter."],
        },
        {
            "status": "disputed",
            "text": "Ministry claimed 25 UAVs downed in overnight engagement.",
            "evidence_urls": ["https://state-media.example.com/briefing"],
            "archive_urls": [],
            "verbatim_quotes": ["25 enemy UAVs neutralized."],
        },
        {
            "status": "false",
            "text": "Cargo vessel was sunk in international waters.",
            "evidence_urls": ["https://osint.example.com/vessel-tracker"],
            "archive_urls": [],
            "verbatim_quotes": ["Vessel reported afloat under tow."],
        },
        {
            "status": "unverified",
            "text": "Unconfirmed local reports of secondary explosions.",
            "evidence_urls": [],
            "archive_urls": [],
            "verbatim_quotes": [],
        },
    ]

    sources = [
        {
            "id": "S1",
            "title": "Reuters International Wire",
            "url": "https://reuters.com/world/air-defense-123",
            "kind": "wire",
        },
        {
            "id": "S2",
            "title": "State News Agency",
            "url": "https://state-media.example.com/briefing",
            "kind": "state_media",
        },
    ]

    warnings = [
        "2 claims remain unverified or disputed before broadcast.",
        "Single-source dependency on state-controlled media.",
    ]

    pdf_bytes = pdf_generator.generate_source_sheet_pdf(
        title="Red Sea Chokepoint Escalation Brief",
        readiness_score=78,
        citations=citations,
        sources=sources,
        warnings=warnings,
        working_slug="red-sea-escalation",
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1500
    assert pdf_bytes.startswith(b"%PDF-1.")
    assert b"%%EOF" in pdf_bytes[-1024:]


def test_generate_source_sheet_pdf_special_characters():
    """Verify ReportLab handles XML entity escaping safely without parsing exceptions."""
    citations = [
        {
            "status": "confirmed",
            "text": "Claims regarding <ATACMS> & 'Storm Shadow' missiles with 100% accuracy.",
            "evidence_urls": ["https://news.example.com/intel?id=1&ref=2"],
            "archive_urls": ["https://web.archive.org/web/intel?id=1&ref=2"],
            "verbatim_quotes": ["Missiles intercepted at <500m> altitude & sustained minimal damage."],
        }
    ]

    sources = [
        {
            "id": "S1",
            "title": "Defence & Security Review <Daily>",
            "url": "https://news.example.com/intel?id=1&ref=2",
            "kind": "analysis",
        }
    ]

    pdf_bytes = pdf_generator.generate_source_sheet_pdf(
        title="Escalation: AT&T, DoD & Foreign Ministries <Update #1>",
        readiness_score=85,
        citations=citations,
        sources=sources,
        warnings=["Discrepancy in metrics: <10 vs >20 reported."],
        working_slug="special-chars-slug",
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-1.")


def test_generate_source_sheet_pdf_empty_dataset():
    """Verify empty project citations, sources, and warnings generate valid document fallback."""
    pdf_bytes = pdf_generator.generate_source_sheet_pdf(
        title="Empty Project Dossier",
        readiness_score=0,
        citations=[],
        sources=[],
        warnings=None,
        working_slug="empty-proj",
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-1.")
    assert len(pdf_bytes) > 500


@pytest.mark.asyncio
async def test_api_export_source_sheet_pdf_success(client: AsyncClient, db_session):
    """Test full HTTP endpoint export of PDF Fact-Check Source Sheet."""
    # 1. Create a project
    create_res = await client.post("/api/projects", json={"title": "Hormuz Strait Intelligence Review"})
    assert create_res.status_code == 201
    proj_id = create_res.json()["id"]

    # 2. Add a confirmed claim
    claim_res = await client.post(
        f"/api/projects/{proj_id}/claims",
        json={
            "text": "Patrol craft challenged commercial tanker in southern shipping corridor.",
            "evidence": [{"url": "https://reuters.com/tanker-patrol", "label": "Reuters Wire"}],
        },
    )
    assert claim_res.status_code == 201
    claim_id = claim_res.json()["id"]

    await client.patch(f"/api/projects/{proj_id}/claims/{claim_id}", json={"status": "confirmed"})

    # 3. Call PDF export endpoint
    pdf_res = await client.get(f"/api/projects/{proj_id}/source-sheet/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert "attachment" in pdf_res.headers["content-disposition"]
    assert "source-dossier-" in pdf_res.headers["content-disposition"]
    assert pdf_res.content.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_api_export_source_sheet_pdf_not_found(client: AsyncClient, db_session):
    """Test 404 behavior when exporting non-existent project as PDF."""
    res = await client.get("/api/projects/proj_nonexistent_888/source-sheet/pdf")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
