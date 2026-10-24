"""Projects router managing video essay workspaces, dossiers, and story outlines."""
import copy
import re
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.project import Project, Dossier, ScriptOutline, Claim, ClaimCheck, Script
from app.models.event import EventCluster
from app.models.source import Article
from app.schemas.project import (
    ClaimCreate,
    ClaimUpdate,
    ClaimResponse,
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectDetailResponse,
    DossierResponse,
    ScriptOutlineResponse,
    ScriptResponse,
    NarrativeAngleOption,
    ProjectReadinessResponse,
    ReadinessChecklistItem,
    ProjectSourceSheetResponse,
    SourceSheetCitation,
)
from app.services import scriptwriter, sourcefinder, verifier
from app.services.clusterer import tokenize_title
from app.services.fulltext import ensure_full_text, fetch_page_text, web_client
from app.schemas.event import FactCheckResponse
from app.services.factcheck import find_fact_checks
from app.services.scorer import extract_entities_and_chokepoints
from app.services.narrative import (
    generate_narrative_angles,
    generate_documentary_outline,
)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


def slugify(text: str) -> str:
    """Generate a clean URL slug from title."""
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", cleaned).strip("-")[:64]


@router.get("", response_model=List[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    """List all creator research projects."""
    stmt = select(Project).order_by(Project.updated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """Create a new video essay project workspace."""
    if payload.cluster_id and not await db.get(EventCluster, payload.cluster_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Event cluster '{payload.cluster_id}' not found.")
    base_slug = slugify(payload.title)
    unique_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
    proj_id = f"proj_{uuid.uuid4().hex[:12]}"

    project = Project(
        id=proj_id,
        title=payload.title,
        working_slug=unique_slug,
        target_duration_mins=payload.target_duration_mins,
        status="concept",
        selected_angle=payload.selected_angle,
        cluster_id=payload.cluster_id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch full project details including linked research dossier and script outline."""
    stmt = (
        select(Project)
        .options(selectinload(Project.dossier), selectinload(Project.script_outline))
        .where(Project.id == project_id)
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    """Update project status, title, angle, or duration."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )

    if payload.title is not None:
        project.title = payload.title
    if payload.target_duration_mins is not None:
        project.target_duration_mins = payload.target_duration_mins
    if payload.status is not None:
        project.status = payload.status
    if payload.selected_angle is not None:
        project.selected_angle = payload.selected_angle

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a video essay project and all associated dossiers."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    # No ORM relationship to Claim, so remove claims explicitly (SQLite does not enforce FK cascades here).
    await db.execute(delete(Claim).where(Claim.project_id == project_id))
    await db.delete(project)
    await db.commit()


async def _get_project_or_404(db: AsyncSession, project_id: str) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


async def _get_claim_or_404(db: AsyncSession, project_id: str, claim_id: str) -> Claim:
    claim = await db.get(Claim, claim_id)
    if not claim or claim.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    return claim


@router.get("/{project_id}/claims", response_model=List[ClaimResponse])
async def list_claims(project_id: str, db: AsyncSession = Depends(get_db)):
    """List the claim ledger for a project."""
    await _get_project_or_404(db, project_id)
    res = await db.execute(select(Claim).where(Claim.project_id == project_id).order_by(Claim.created_at))
    return list(res.scalars().all())


@router.post("/{project_id}/claims", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_claim(project_id: str, payload: ClaimCreate, db: AsyncSession = Depends(get_db)):
    """Add a claim to verify. New claims always start unverified."""
    await _get_project_or_404(db, project_id)
    evidence_data = []
    for e in payload.evidence:
        d = e.model_dump(mode="json")
        if not d.get("archive_url") and d.get("url"):
            d["archive_url"] = verifier.generate_archive_url(str(d["url"]))
        evidence_data.append(d)

    claim = Claim(
        id=f"clm_{uuid.uuid4().hex[:12]}",
        project_id=project_id,
        text=payload.text.strip(),
        status="unverified",
        evidence=evidence_data,
    )
    db.add(claim)
    await db.commit()
    await db.refresh(claim)
    return claim


@router.patch("/{project_id}/claims/{claim_id}", response_model=ClaimResponse)
async def update_claim(project_id: str, claim_id: str, payload: ClaimUpdate, db: AsyncSession = Depends(get_db)):
    """Edit a claim, attach evidence, or record a verdict."""
    claim = await _get_claim_or_404(db, project_id, claim_id)
    if payload.text is not None:
        claim.text = payload.text.strip()
    if payload.note is not None:
        claim.note = payload.note
    if payload.evidence is not None:
        evidence_data = []
        for e in payload.evidence:
            d = e.model_dump(mode="json")
            if not d.get("archive_url") and d.get("url"):
                d["archive_url"] = verifier.generate_archive_url(str(d["url"]))
            evidence_data.append(d)
        claim.evidence = evidence_data
    if payload.status is not None and payload.status != claim.status:
        claim.status = payload.status
        claim.status_changed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(claim)
    return claim


@router.delete("/{project_id}/claims/{claim_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_claim(project_id: str, claim_id: str, db: AsyncSession = Depends(get_db)):
    """Remove a claim from the ledger."""
    claim = await _get_claim_or_404(db, project_id, claim_id)
    await db.delete(claim)
    await db.commit()


@router.get("/{project_id}/claims/{claim_id}/factchecks", response_model=List[FactCheckResponse])
async def get_claim_fact_checks(project_id: str, claim_id: str, db: AsyncSession = Depends(get_db)):
    """Search published fact-checks for this specific claim (more precise than the event headline)."""
    claim = await _get_claim_or_404(db, project_id, claim_id)
    actors, chokepoints, _ = extract_entities_and_chokepoints(claim.text)
    return await find_fact_checks(claim.text, actors + chokepoints)


CLAIM_CHECK_MAX_ARTICLES = 10


@router.post("/{project_id}/claims/extract", response_model=List[ClaimResponse], status_code=status.HTTP_201_CREATED)
async def extract_claims_from_script(project_id: str, db: AsyncSession = Depends(get_db)):
    """Break the script's factual lines into checkable claims and add them to the ledger as unverified.

    Each new claim carries the articles its script line cites as evidence; duplicates of existing claims are skipped.
    """
    await _get_project_or_404(db, project_id)
    script = (await db.execute(select(Script).where(Script.project_id == project_id))).scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Write the script first.")
    by_id = {s["id"]: s for s in script.sources}
    lines, line_articles = [], {}
    for ai, act in enumerate(script.content.get("acts", [])):
        for bi, beat in enumerate(act.get("beats", [])):
            articles = [by_id[c] for c in beat.get("citations") or [] if by_id.get(c, {}).get("kind") == "article"]
            # Lines resting only on ledger claims are already tracked; analysis/transition lines aren't checkable.
            if beat.get("kind") == "fact" and (articles or not beat.get("citations")):
                lid = f"L{ai + 1}.{bi + 1}"
                lines.append({"id": lid, "text": beat["narration"].replace(scriptwriter.NEEDS_SOURCE, "").strip()})
                line_articles[lid] = articles
    existing = list((await db.execute(select(Claim).where(Claim.project_id == project_id))).scalars().all())

    extracted = await verifier.extract_claims(lines, [c.text for c in existing])
    created = []
    for item in extracted:
        claim = Claim(
            id=f"clm_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            text=item["text"],
            status="unverified",
            note=f"Extracted from script line {item['line_id']}.",
            evidence=[{"url": a["url"], "label": f"Cited in script [{a['id']}]: {a['title']}"[:200]} for a in line_articles[item["line_id"]]],
        )
        db.add(claim)
        created.append(claim)
    await db.commit()
    for claim in created:
        await db.refresh(claim)
    return created


async def _cluster_articles(db: AsyncSession, cluster_id: Optional[str]) -> List[Article]:
    """The linked event's articles (with sources loaded), full text fetched; empty when there's no event."""
    if not cluster_id:
        return []
    stmt = (
        select(EventCluster)
        .options(selectinload(EventCluster.articles).selectinload(Article.source))
        .where(EventCluster.id == cluster_id)
    )
    cluster = (await db.execute(stmt)).scalar_one_or_none()
    if not cluster:
        return []
    await ensure_full_text(cluster.articles)
    return cluster.articles


async def _evidence_sources(evidence: List[dict]) -> List[dict]:
    """Fetch the pages a claim cites as evidence (E1..En); pages that can't be read are skipped."""
    sources = []
    async with web_client() as client:
        for i, ev in enumerate(evidence, 1):
            try:
                text = await fetch_page_text(client, ev["url"])
            except Exception:
                continue
            sources.append({"id": f"E{i}", "kind": "evidence", "outlet": "Attached evidence", "title": ev.get("label") or ev["url"],
                            "url": ev["url"], "text": text[:scriptwriter.MAX_SOURCE_CHARS]})
    return sources


@router.post("/{project_id}/claims/{claim_id}/sources/suggest")
async def suggest_primary_sources(project_id: str, claim_id: str, db: AsyncSession = Depends(get_db)):
    """Search the web (Gemini + Google Search) for primary sources on this claim. Suggestions only; nothing is saved."""
    claim = await _get_claim_or_404(db, project_id, claim_id)
    return await sourcefinder.find_primary_sources(claim.text)


@router.post("/{project_id}/claims/{claim_id}/check", response_model=ClaimResponse)
async def check_claim(project_id: str, claim_id: str, db: AsyncSession = Depends(get_db)):
    """AI evidence check: compare the claim to the event's most relevant reports and its attached evidence.

    The result is a suggestion with verbatim, code-verified quotes; the claim's own verdict is never changed.
    """
    claim = await _get_claim_or_404(db, project_id, claim_id)
    project = await _get_project_or_404(db, project_id)
    articles = await _cluster_articles(db, project.cluster_id)

    # Rank reports by word overlap with the claim so the check reads the few that matter.
    claim_tokens = tokenize_title(claim.text)
    ranked = sorted(articles, key=lambda a: len(claim_tokens & tokenize_title(f"{a.title} {a.clean_text or ''}")), reverse=True)
    sources = scriptwriter.build_sources(ranked[:CLAIM_CHECK_MAX_ARTICLES], []) + await _evidence_sources(claim.evidence or [])
    if not sources:
        raise HTTPException(
            status_code=422,
            detail="Nothing to check against. Link the project to a Radar event or attach readable evidence to this claim.",
        )
    await db.commit()  # persist fetched full text even if the AI call fails

    checked = await verifier.check_statements([{"id": "claim", "text": claim.text, "source_ids": [s["id"] for s in sources]}], sources)
    result = checked["claim"]
    if claim.ai_check:
        await db.delete(claim.ai_check)
        await db.flush()
    claim.ai_check = ClaimCheck(
        id=f"chk_{uuid.uuid4().hex[:12]}", claim_id=claim.id, claim_text=claim.text,
        verdict=result["verdict"], explanation=result["explanation"], quotes=result["quotes"],
        sources=[{k: s.get(k) for k in ("id", "title", "outlet", "url")} for s in sources],
        model=settings.GEMINI_MODEL,
    )
    await db.commit()
    await db.refresh(claim)
    return claim


@router.post("/{project_id}/angles", response_model=List[NarrativeAngleOption])
async def get_project_angles(project_id: str, db: AsyncSession = Depends(get_db)):
    """Generate 4 distinct video essay narrative angles for this project."""
    stmt = select(Project).where(Project.id == project_id)
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    actors, chokepoints, keywords = extract_entities_and_chokepoints(project.title)

    # If linked to cluster, inherit cluster entities
    if project.cluster_id:
        c_res = await db.execute(select(EventCluster).where(EventCluster.id == project.cluster_id))
        cluster = c_res.scalar_one_or_none()
        if cluster:
            actors = sorted(list(set(actors + (cluster.key_actors or []))))
            chokepoints = sorted(list(set(chokepoints + (cluster.chokepoints or []))))
            keywords = sorted(list(set(keywords + (cluster.strategic_keywords or []))))

    return generate_narrative_angles(project.title, actors, chokepoints, keywords)


@router.post("/{project_id}/dossier/generate", response_model=DossierResponse)
async def generate_dossier(project_id: str, db: AsyncSession = Depends(get_db)):
    """Synthesize and compile the research dossier backing this project."""
    stmt = (
        select(Project)
        .options(selectinload(Project.dossier))
        .where(Project.id == project_id)
    )
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    actors, chokepoints, keywords = extract_entities_and_chokepoints(project.title)
    citations = []
    timeline = []
    contradictions = []
    articles = []
    region = None

    # If linked to a cluster, extract citations from backing articles
    if project.cluster_id:
        c_stmt = (
            select(EventCluster)
            .options(selectinload(EventCluster.articles).selectinload(Article.source))
            .where(EventCluster.id == project.cluster_id)
        )
        c_res = await db.execute(c_stmt)
        cluster = c_res.scalar_one_or_none()
        if cluster:
            actors = sorted(list(set(actors + (cluster.key_actors or []))))
            chokepoints = sorted(list(set(chokepoints + (cluster.chokepoints or []))))
            articles = sorted(cluster.articles, key=lambda a: a.published_at, reverse=True)
            region = cluster.region
            for art in cluster.articles:
                citations.append({
                    "title": art.title,
                    "url": art.url,
                    "published_at": art.published_at.isoformat(),
                    "source_id": art.source_id,
                })
                timeline.append({
                    "date": art.published_at.strftime("%Y-%m-%d"),
                    "event": art.title,
                    "source": art.source_id,
                    "url": art.url,
                })

            # Pair headlines from different media ecosystems so framing differences are visible.
            by_ecosystem = {}
            for art in cluster.articles:
                if art.source:
                    by_ecosystem.setdefault(art.source.bias_category or art.source.source_type, art)
            framings = list(by_ecosystem.values())
            contradictions = [
                {
                    "issue": f"Framing comparison: {a.source.name} vs {b.source.name} (auto-paired headlines, not verified contradictions)",
                    "side_a": f"{a.source.name}: {a.title}",
                    "side_b": f"{b.source.name}: {b.title}",
                }
                for a, b in zip(framings, framings[1:])
            ][:3]

    # Only state what the coverage shows: how often each actor is named, with a real headline as evidence.
    stakeholders = []
    for a in actors:
        mentions = [art for art in articles if a in ((art.entities or {}).get("actors") or [])]
        stakeholders.append({
            "actor": a,
            "role": f"Named in {len(mentions)} of {len(articles)} report{'' if len(articles) == 1 else 's'}" if articles else "Named in project title",
            "example_headline": mentions[0].title if mentions else None,
        })
    geography = {
        "chokepoints": chokepoints,
        "region": region or "Unspecified",
        "key_corridors": chokepoints,
    }
    now = datetime.now(timezone.utc)
    if project.dossier:
        project.dossier.timeline_events = timeline
        project.dossier.stakeholders = stakeholders
        project.dossier.geography = geography
        project.dossier.contradictions = contradictions
        project.dossier.citations = citations
        project.dossier.updated_at = now
        dossier = project.dossier
    else:
        dossier = Dossier(
            id=f"dos_{uuid.uuid4().hex[:12]}",
            project_id=project.id,
            timeline_events=timeline,
            stakeholders=stakeholders,
            geography=geography,
            contradictions=contradictions,
            citations=citations,
            updated_at=now,
        )
        db.add(dossier)

    project.status = "researching"
    await db.commit()
    await db.refresh(dossier)
    return dossier


@router.post("/{project_id}/dossier/contradictions", response_model=DossierResponse)
async def find_contradictions(project_id: str, db: AsyncSession = Depends(get_db)):
    """Replace auto-paired headlines with AI-found factual disagreements whose quotes are verified in each report."""
    project = (await db.execute(select(Project).options(selectinload(Project.dossier)).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    if not project.dossier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Synthesize the dossier first.")
    articles = await _cluster_articles(db, project.cluster_id)
    if len(articles) < 2:
        raise HTTPException(status_code=422, detail="Needs at least two reports on this event to compare.")
    await db.commit()  # keep fetched full text even if the AI call fails

    found = await verifier.find_disagreements(scriptwriter.build_sources(articles, []))
    # Same shape the War Room already renders (issue / side_a / side_b), plus the verified quotes and links.
    project.dossier.contradictions = [
        {
            "issue": d["issue"],
            "side_a": f"{d['side_a']['outlet']}: \u201c{d['side_a']['quote']}\u201d",
            "side_b": f"{d['side_b']['outlet']}: \u201c{d['side_b']['quote']}\u201d",
            "explanation": d["explanation"],
            "method": "ai_verified",
            "a": d["side_a"],
            "b": d["side_b"],
        }
        for d in found
    ]
    project.dossier.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(project.dossier)
    return project.dossier


@router.post("/{project_id}/outline/generate", response_model=ScriptOutlineResponse)
async def generate_outline(project_id: str, db: AsyncSession = Depends(get_db)):
    """Generate the 5-Act video essay documentary structure with B-roll visual cues."""
    stmt = (
        select(Project)
        .options(selectinload(Project.script_outline))
        .where(Project.id == project_id)
    )
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    actors, chokepoints, _ = extract_entities_and_chokepoints(project.title)
    if project.cluster_id:
        c_res = await db.execute(select(EventCluster).where(EventCluster.id == project.cluster_id))
        cluster = c_res.scalar_one_or_none()
        if cluster:
            actors = sorted(list(set(actors + (cluster.key_actors or []))))
            chokepoints = sorted(list(set(chokepoints + (cluster.chokepoints or []))))

    outline_data = generate_documentary_outline(
        topic=project.title,
        selected_angle=project.selected_angle,
        actors=actors,
        chokepoints=chokepoints,
        target_duration_mins=project.target_duration_mins,
    )

    now = datetime.now(timezone.utc)
    if project.script_outline:
        project.script_outline.acts = outline_data["acts"]
        project.script_outline.hook_variants = outline_data["hook_variants"]
        project.script_outline.visual_prompts = outline_data["visual_prompts"]
        project.script_outline.updated_at = now
        outline = project.script_outline
    else:
        outline = ScriptOutline(
            id=f"out_{uuid.uuid4().hex[:12]}",
            project_id=project.id,
            acts=outline_data["acts"],
            hook_variants=outline_data["hook_variants"],
            visual_prompts=outline_data["visual_prompts"],
            updated_at=now,
        )
        db.add(outline)

    project.status = "scripting"
    await db.commit()
    await db.refresh(outline)
    return outline


@router.get("/{project_id}/script", response_model=ScriptResponse)
async def get_script(project_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch the project's latest narration script."""
    script = (await db.execute(select(Script).where(Script.project_id == project_id))).scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No script yet. Generate one first.")
    return script


@router.post("/{project_id}/script/generate", response_model=ScriptResponse)
async def generate_script(project_id: str, db: AsyncSession = Depends(get_db)):
    """Write a cited narration script from the linked event's reports and the Claim Ledger (one Gemini call)."""
    stmt = (
        select(Project)
        .options(selectinload(Project.script_outline), selectinload(Project.script))
        .where(Project.id == project_id)
    )
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    articles = await _cluster_articles(db, project.cluster_id)
    claims = list((await db.execute(select(Claim).where(Claim.project_id == project_id).order_by(Claim.created_at))).scalars().all())
    if not articles and not claims:
        raise HTTPException(
            status_code=422,
            detail="Nothing to cite yet. Start the project from a Radar event or add claims to the Claim Ledger first.",
        )

    sources = scriptwriter.build_sources(articles, claims)
    prompt = scriptwriter.build_prompt(
        project.title,
        project.selected_angle,
        project.target_duration_mins,
        sources,
        project.script_outline.acts if project.script_outline else [],
    )
    content, model = await scriptwriter.call_gemini(scriptwriter.SYSTEM_INSTRUCTION, prompt)
    stats = scriptwriter.verify_script(content, sources, project.target_duration_mins)

    if project.script:
        script = project.script
        script.content, script.sources, script.stats, script.model = content, sources, stats, model
        script.created_at = datetime.now(timezone.utc)
    else:
        script = Script(
            id=f"scr_{uuid.uuid4().hex[:12]}", project_id=project.id,
            content=content, sources=sources, stats=stats, model=model,
        )
        db.add(script)
    await db.commit()
    await db.refresh(script)
    return script


@router.post("/{project_id}/script/check", response_model=ScriptResponse)
async def check_script(project_id: str, db: AsyncSession = Depends(get_db)):
    """AI citation check: for each factual line, does the cited source actually say it? (one Gemini call)"""
    script = (await db.execute(select(Script).where(Script.project_id == project_id))).scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No script yet. Generate one first.")
    content = copy.deepcopy(script.content)  # new object so the JSON column change is persisted
    known = {s["id"] for s in script.sources}
    statements, beats = [], {}
    for ai, act in enumerate(content.get("acts", [])):
        for bi, beat in enumerate(act.get("beats", [])):
            beat.pop("support", None)
            cites = [c for c in beat.get("citations") or [] if c in known]
            if beat.get("kind") == "fact" and cites:
                sid = f"L{ai + 1}.{bi + 1}"
                statements.append({"id": sid, "text": beat["narration"].replace(scriptwriter.NEEDS_SOURCE, "").strip(), "source_ids": cites})
                beats[sid] = beat
    if not statements:
        raise HTTPException(status_code=422, detail="No cited factual lines to check.")

    checked = await verifier.check_statements(statements, script.sources)
    for sid, beat in beats.items():
        beat["support"] = {k: checked[sid][k] for k in ("verdict", "quotes", "explanation")}
        # Check numerical metrics
        cites = [c for c in beat.get("citations") or [] if c in known]
        source_texts = [verifier.source_text(s) for s in script.sources if s.get("id") in cites]
        num_check = verifier.check_numerical_consistency(beat.get("narration", ""), source_texts)
        if not num_check["is_consistent"] and num_check.get("warning"):
            beat["support"]["numerical_warning"] = num_check["warning"]
            if beat["support"]["verdict"] == "supported":
                beat["support"]["verdict"] = "partly_supported"
    script.content = content
    script.stats = {**(script.stats or {}), "support": verifier.summarize(checked)}
    await db.commit()
    await db.refresh(script)
    return script


@router.get("/{project_id}/readiness", response_model=ProjectReadinessResponse)
async def get_project_readiness(project_id: str, db: AsyncSession = Depends(get_db)):
    """Calculate the audit readiness score and verification checklist for a project."""
    stmt = (
        select(Project)
        .options(selectinload(Project.script))
        .where(Project.id == project_id)
    )
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    claims_res = await db.execute(select(Claim).where(Claim.project_id == project_id))
    claims = list(claims_res.scalars().all())

    cluster_articles = []
    if project.cluster_id:
        articles_res = await db.execute(select(Article).where(Article.cluster_id == project.cluster_id))
        cluster_articles = list(articles_res.scalars().all())

    script_sources = (project.script.sources or []) if project.script else []
    total_sources = max(len(cluster_articles), len(script_sources))

    total_claims = len(claims)
    confirmed_claims = sum(1 for c in claims if c.status == "confirmed")
    unverified_claims = sum(1 for c in claims if c.status == "unverified")
    disputed_claims = sum(1 for c in claims if c.status == "disputed")
    false_claims = sum(1 for c in claims if c.status == "false")

    script_stats = (project.script.stats or {}) if project.script else {}
    script_support = script_stats.get("support") or {}
    script_support_checked = bool(script_support)
    contradicted_statements = script_support.get("contradicted", 0)

    from app.services.scorer import assign_origins
    origins = assign_origins([(a.source_id, a.title or "") for a in cluster_articles]) if cluster_articles else []
    independent_origins = len(set(origins)) if origins else (1 if total_sources > 0 else 0)

    score = 0
    if total_claims > 0:
        claim_ratio = (confirmed_claims * 1.0 + disputed_claims * 0.3 - false_claims * 0.6) / total_claims
        score += int(max(0.0, min(1.0, claim_ratio)) * 50)
    elif total_sources >= 2:
        score += 25

    if independent_origins >= 3:
        score += 25
    elif independent_origins >= 2:
        score += 15
    elif independent_origins == 1:
        score += 5

    if script_support_checked:
        if contradicted_statements == 0:
            score += 25
        else:
            score += 10
    elif project.script:
        score += 10

    score = max(0, min(100, score))
    status_label = "ready" if score >= 80 else ("needs_review" if score >= 50 else "unverified")

    checklist = [
        ReadinessChecklistItem(
            id="multi_source",
            label="Multi-Source Grounding",
            passed=independent_origins >= 2,
            detail=f"{independent_origins} independent origin(s) across {total_sources} source(s)."
            if independent_origins >= 2
            else "Single-source or uncorroborated; ingest secondary reporting before finalizing.",
        ),
        ReadinessChecklistItem(
            id="claims_reviewed",
            label="Claim Ledger Verification",
            passed=total_claims > 0 and unverified_claims == 0,
            detail=f"All {total_claims} claims reviewed ({confirmed_claims} confirmed)."
            if (total_claims > 0 and unverified_claims == 0)
            else f"{unverified_claims} unverified claim(s) remaining in ledger.",
        ),
        ReadinessChecklistItem(
            id="no_contradictions",
            label="Contradiction Freedom",
            passed=false_claims == 0 and contradicted_statements == 0,
            detail="No claims or script lines marked false or contradicted."
            if (false_claims == 0 and contradicted_statements == 0)
            else f"{false_claims} false claim(s), {contradicted_statements} contradicted line(s) detected.",
        ),
        ReadinessChecklistItem(
            id="script_verified",
            label="Script Evidence Check",
            passed=script_support_checked and contradicted_statements == 0,
            detail="Script statements verified character-for-character against sources."
            if script_support_checked
            else "Script not yet checked with AI evidence verifier.",
        ),
    ]

    warnings = []
    if false_claims > 0:
        warnings.append(f"{false_claims} claim(s) marked false in Claim Ledger.")
    if contradicted_statements > 0:
        warnings.append(f"{contradicted_statements} script beat(s) contradicted by sources.")
    if unverified_claims > 0:
        warnings.append(f"{unverified_claims} claim(s) still unverified in ledger.")
    if independent_origins < 2:
        warnings.append("Project relies on fewer than 2 independent news origins.")

    return ProjectReadinessResponse(
        project_id=project_id,
        score=score,
        status=status_label,
        total_claims=total_claims,
        confirmed_claims=confirmed_claims,
        unverified_claims=unverified_claims,
        disputed_claims=disputed_claims,
        false_claims=false_claims,
        total_sources=total_sources,
        independent_origins=independent_origins,
        script_support_checked=script_support_checked,
        script_verdict_summary=script_support,
        checklist=checklist,
        warnings=warnings,
    )


@router.get("/{project_id}/source-sheet", response_model=ProjectSourceSheetResponse)
async def get_project_source_sheet(project_id: str, db: AsyncSession = Depends(get_db)):
    """Generate a broadcast/video essay citation source sheet linking claims, archive URLs, and verified quotes."""
    stmt = (
        select(Project)
        .options(selectinload(Project.script))
        .where(Project.id == project_id)
    )
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    claims_res = await db.execute(select(Claim).where(Claim.project_id == project_id).order_by(Claim.created_at))
    claims = list(claims_res.scalars().all())

    readiness = await get_project_readiness(project_id, db)

    citations = []
    for c in claims:
        evidence_urls = [e.get("url") for e in c.evidence or [] if e.get("url")]
        archive_urls = [e.get("archive_url") or verifier.generate_archive_url(e.get("url")) for e in c.evidence or [] if e.get("url")]
        quotes = [q["quote"] for q in (c.ai_check.quotes if c.ai_check else [])]
        citations.append(SourceSheetCitation(
            type="claim",
            id=c.id,
            text=c.text,
            status=c.status,
            evidence_urls=evidence_urls,
            archive_urls=archive_urls,
            verbatim_quotes=quotes,
            outlet=None,
        ))

    script_sources = (project.script.sources or []) if project.script else []

    md_lines = [
        f"# Fact-Check & Citation Source Sheet: {project.title}",
        f"> Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Audit Readiness Score: **{readiness.score}/100** ({readiness.status.upper()})",
        "",
        "## 1. Verified Claim Ledger",
        "| Status | Claim | Primary Evidence | Archive Permalink | Verified Quote |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    if not citations:
        md_lines.append("| — | *No claims recorded in ledger* | — | — | — |")
    else:
        for cit in citations:
            stat_badge = f"`{cit.status.upper()}`"
            prim_link = f"[{cit.evidence_urls[0]}]({cit.evidence_urls[0]})" if cit.evidence_urls else "*None*"
            arch_link = f"[Wayback]({cit.archive_urls[0]})" if cit.archive_urls else "*None*"
            quote_text = f"\"{cit.verbatim_quotes[0][:120]}...\"" if cit.verbatim_quotes else "*None*"
            clean_text = cit.text.replace("|", "/")
            md_lines.append(f"| {stat_badge} | {clean_text} | {prim_link} | {arch_link} | {quote_text} |")

    md_lines.extend([
        "",
        "## 2. Primary & Secondary Sources",
        "| ID | Title / Outlet | URL | Type |",
        "| :--- | :--- | :--- | :--- |",
    ])

    if not script_sources:
        md_lines.append("| — | *No source references recorded* | — | — |")
    else:
        for s in script_sources:
            sid = s.get("id", "")
            title = (s.get("title") or s.get("outlet") or "Source").replace("|", "/")
            url = s.get("url", "")
            link = f"[{title}]({url})" if url else title
            kind = s.get("kind", "source")
            md_lines.append(f"| `{sid}` | {link} | {url or '—'} | {kind} |")

    md_lines.extend([
        "",
        "## 3. Verification Audit Summary",
        f"- **Total Claims**: {readiness.total_claims} ({readiness.confirmed_claims} confirmed, {readiness.unverified_claims} unverified)",
        f"- **Independent Origins**: {readiness.independent_origins}",
        f"- **Script Verification**: {'Passed (0 contradicted)' if (readiness.script_support_checked and readiness.status != 'unverified') else 'Pending or needs review'}",
    ])
    if readiness.warnings:
        md_lines.append("### Editorial Warnings")
        for w in readiness.warnings:
            md_lines.append(f"- ⚠️ {w}")

    return ProjectSourceSheetResponse(
        project_id=project_id,
        title=project.title,
        generated_at=datetime.now(timezone.utc),
        readiness_score=readiness.score,
        citations=citations,
        sources=script_sources,
        markdown="\n".join(md_lines),
    )



@router.get("/{project_id}/export", response_class=PlainTextResponse)
async def export_project_markdown(project_id: str, db: AsyncSession = Depends(get_db)):
    """Export complete research brief, dossier, and script outline as formatted Markdown."""
    stmt = (
        select(Project)
        .options(selectinload(Project.dossier), selectinload(Project.script_outline), selectinload(Project.script))
        .where(Project.id == project_id)
    )
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    claims_res = await db.execute(select(Claim).where(Claim.project_id == project_id).order_by(Claim.created_at))
    claims = list(claims_res.scalars().all())
    unconfirmed = [c for c in claims if c.status != "confirmed"]

    lines = [
        f"# Video Essay Production Brief: {project.title}",
        f"**Working Slug**: `{project.working_slug}` | **Target Duration**: {project.target_duration_mins} min",
        f"**Selected Angle**: {project.selected_angle or 'General Explainer'}",
        "",
    ]
    if unconfirmed:
        lines.append(f"> **WARNING: {len(unconfirmed)} of {len(claims)} claims are not confirmed.** See the Claim Ledger before recording.")
        lines.append("")
    lines.extend([
        "> *Hooks and acts below are template framings filled with detected actors and chokepoints, not analysis of the coverage.*",
        "",
        "---",
        "## I. Hook Variants for Video Openings",
    ])

    if project.script_outline and project.script_outline.hook_variants:
        for idx, h in enumerate(project.script_outline.hook_variants, 1):
            lines.append(f"### Hook {idx} ({h.get('type')})")
            lines.append(f"> \"{h.get('hook_text')}\"")
            lines.append(f"*Visual Cue*: {h.get('suggested_broll')}\n")

    lines.extend(["---", "## II. 5-Act Documentary Structure"])
    if project.script_outline and project.script_outline.acts:
        for act in project.script_outline.acts:
            lines.append(f"### {act.get('title')} (`{act.get('timecode')}`)")
            lines.append(f"**Focus**: {act.get('narrative_focus')}")
            lines.append("**Key Questions to Address**:")
            for q in act.get("key_questions", []):
                lines.append(f"- {q}")
            lines.append("**B-Roll & Graphic Assets**:")
            for b in act.get("b_roll_and_visual_cues", []):
                lines.append(f"- [Map/Graphic] {b}")
            lines.append("")

    lines.extend(["---", "## III. Research Dossier & Intelligence Base"])
    if project.dossier:
        if project.dossier.stakeholders:
            lines.append("### Stakeholder Analysis")
            for s in project.dossier.stakeholders:
                example = f" — e.g. *{s['example_headline']}*" if s.get("example_headline") else ""
                lines.append(f"- **{s.get('actor')}**: {s.get('role')}{example}")
            lines.append("")

        if project.dossier.contradictions:
            lines.append("### Framing Comparison (auto-paired headlines — verify before scripting)")
            for c in project.dossier.contradictions:
                lines.append(f"**{c.get('issue')}**:")
                lines.append(f"- *Narrative A*: {c.get('side_a')}")
                lines.append(f"- *Narrative B*: {c.get('side_b')}\n")

        if project.dossier.citations:
            lines.append("### Verified Citations & Primary Sources")
            for cite in project.dossier.citations:
                lines.append(f"- [{cite.get('title')}]({cite.get('url')}) ({cite.get('source_id')})")

    if claims:
        lines.extend(["", "---", "## IV. Claim Ledger"])
        for c in claims:
            lines.append(f"- **[{c.status.upper()}]** {c.text}")
            if c.note:
                lines.append(f"  - *Note*: {c.note}")
            for e in c.evidence or []:
                lines.append(f"  - Evidence: [{e.get('label') or e.get('url')}]({e.get('url')})")
            if c.ai_check:
                lines.extend(_ai_check_markdown({"verdict": c.ai_check.verdict, "explanation": c.ai_check.explanation, "quotes": c.ai_check.quotes}, "  - "))

    if project.script:
        lines.extend(_script_markdown(project.script))

    return "\n".join(lines)


def _ai_check_markdown(result: dict, prefix: str) -> List[str]:
    """One 'AI check' line plus its verified quotes, for the export."""
    verdict = result.get("verdict", "").replace("_", " ")
    lines = [f"{prefix}**AI check: {verdict}** (suggestion, not a verdict). {result.get('explanation', '')}".rstrip()]
    lines += [f"{prefix}  \"{q['quote']}\" [{q['source_id']}]" for q in result.get("quotes") or []]
    return lines


def _script_markdown(script: Script) -> List[str]:
    """Narration script with [S#]/[C#] markers and a source list, plus a flag line on any beat that failed verification."""
    content, stats = script.content or {}, script.stats or {}
    lines = [
        "", "---", f"## V. Narration Script: {content.get('title', '')}",
        f"*{content.get('logline', '')}*", "",
        f"> Written by {script.model}. {stats.get('fact_beats_verified', 0)} of {stats.get('fact_beats', 0)} factual beats verified against sources; "
        f"{stats.get('beats_flagged', 0)} beats flagged. ~{stats.get('word_count', 0)} words (target {stats.get('target_words', 0)}).",
        "",
    ]
    for act in content.get("acts", []):
        lines.append(f"### {act.get('title')} (`{act.get('timecode')}`)")
        for beat in act.get("beats", []):
            cites = "".join(f"[{c}]" for c in beat.get("citations") or [])
            lines.append(f"{beat.get('narration')} {cites}".rstrip())
            if beat.get("broll"):
                lines.append(f"*B-roll: {beat['broll']}*")
            for issue in beat.get("issues") or []:
                lines.append(f"> **CHECK:** {issue}")
            if beat.get("support"):
                lines.extend(_ai_check_markdown(beat["support"], "> "))
            lines.append("")
    if content.get("open_questions"):
        lines.append("### Open Questions (need sourcing before recording)")
        lines += [f"- {q}" for q in content["open_questions"]]
        lines.append("")
    lines.append("### Sources")
    for s in script.sources or []:
        if s.get("kind") == "article":
            lines.append(f"- [{s['id']}] [{s['title']}]({s['url']}) ({s['outlet']}, {s['published_at']})")
        else:
            lines.append(f"- [{s['id']}] Claim ({s['status']}): {s['text']}")
    return lines
