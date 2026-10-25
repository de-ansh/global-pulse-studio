"""Radar router for multi-source intelligence gathering, clustering, and signals."""
import asyncio
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import settings
from app.models.source import Source, Article
from app.models.event import EventCluster
from app.schemas.source import (
    SourceCreate,
    SourceUpdate,
    SourceResponse,
    ArticleResponse,
    ScanSummary,
)
from app.schemas.event import (
    EventClusterResponse,
    EventClusterDetail,
    FactCheckResponse,
)
from app.services.ingester import IngestionEngine
from app.services.clusterer import ClusteringEngine

from app.services.scorer import assign_origins, evaluate_triangulation, verification_label
from app.services.factcheck import find_fact_checks

router = APIRouter(prefix="/api/radar", tags=["Radar"])
logger = logging.getLogger(__name__)
# Overlapping scans race on canonical_hash and one rolls back entirely.
# shortcut: per-process lock, upgrade to a DB/file lock if running multiple uvicorn workers.
_scan_lock = asyncio.Lock()


def enrich_cluster_triangulation(c: EventCluster) -> EventCluster:
    """Calculate multi-source cross-verification and India relevance metrics."""
    sources_seen = {}
    for art in (c.articles or []):
        if getattr(art, "source", None):
            sources_seen[art.source.id] = art.source

    source_count = max(len(sources_seen), 1)
    source_names = [s.name for s in sources_seen.values()]
    source_categories = [s.bias_category or s.source_type for s in sources_seen.values()]

    reports = [
        (art.source_id, f"{art.title} {art.summary or ''} {(art.clean_text or '')[:400]}")
        for art in (c.articles or [])
    ]
    origin_count = max(len(set(assign_origins(reports))), 1)
    reliabilities = [s.reliability_score for s in sources_seen.values()]

    level, confidence, checklist = evaluate_triangulation(
        origin_count, source_categories, reliabilities=reliabilities, outlet_count=source_count
    )

    combined_text = f"{c.headline} {c.summary or ''} {c.region or ''}".lower()
    actors_lower = [a.lower() for a in (c.key_actors or [])]
    chokepoints_lower = [chk.lower() for chk in (c.chokepoints or [])]

    is_india = (
        "india" in combined_text
        or "delhi" in combined_text
        or "himalay" in combined_text
        or any("india" in a for a in actors_lower)
        or any(a in ["isro", "drdo", "raw", "quad", "mea"] for a in actors_lower)
        or any(
            any(k in chk for k in ["siliguri", "andaman", "(lac)", "(loc)", "galwan", "pangong", "doklam", "chabahar", "indian ocean", "palk", "imec", "instc"])
            for chk in chokepoints_lower
        )
        or "india" in (c.region or "").lower()
        or "south asia" in (c.region or "").lower()
        or "indo-pacific" in (c.region or "").lower()
    )

    c.source_count = source_count
    c.source_names = source_names
    c.triangulation_level = level
    c.confidence_score = confidence
    c.independent_origin_count = origin_count
    c.is_india_relevant = is_india
    c.has_domestic_source = any("domestic" in cat or "business_geoecon" in cat for cat in source_categories)
    c.has_international_source = any("western" in cat or "pan_arab" in cat or "policy_establishment" in cat for cat in source_categories)
    c.verification_checklist = checklist
    c.verification_label = verification_label(level, origin_count, c.has_domestic_source and c.has_international_source)

    return c


@router.get("/sources", response_model=List[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all configured intelligence sources."""
    stmt = select(Source).order_by(Source.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/sources/seed", response_model=List[SourceResponse], status_code=status.HTTP_201_CREATED)
async def seed_default_sources(db: AsyncSession = Depends(get_db)):
    """Seed the database with high-credibility default international affairs feeds."""
    seeded = []
    for seed in settings.DEFAULT_SEEDS:
        existing = await db.execute(select(Source).where(Source.id == seed["id"]))
        if not existing.scalar_one_or_none():
            src = Source(
                id=seed["id"],
                name=seed["name"],
                feed_url=seed["feed_url"],
                homepage_url=seed.get("homepage_url"),
                source_type=seed.get("source_type", "wire"),
                governance_type=seed.get("governance_type", "commercial_wire"),
                region=seed.get("region", "Global"),
                bias_category=seed.get("bias_category"),
                reliability_score=seed.get("reliability_score", 0.90),
                is_active=True,
            )
            db.add(src)
            seeded.append(src)
    await db.commit()
    # Return all current sources
    stmt = select(Source).order_by(Source.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(payload: SourceCreate, db: AsyncSession = Depends(get_db)):
    """Add a new custom RSS/Atom intelligence source."""
    existing = await db.execute(select(Source).where(Source.id == payload.id))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source with ID '{payload.id}' already exists.",
        )
    dup_feed = (await db.execute(select(Source).where(Source.feed_url == payload.feed_url))).scalar_one_or_none()
    if dup_feed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Feed URL is already registered as '{dup_feed.name}'.",
        )

    src = Source(
        id=payload.id,
        name=payload.name,
        feed_url=payload.feed_url,
        homepage_url=payload.homepage_url,
        source_type=payload.source_type,
        governance_type=payload.governance_type,
        region=payload.region,
        bias_category=payload.bias_category,
        reliability_score=payload.reliability_score,
        is_active=payload.is_active,
    )
    db.add(src)
    await db.commit()
    await db.refresh(src)
    return src


@router.patch("/sources/{source_id}", response_model=SourceResponse)
async def update_source(source_id: str, payload: SourceUpdate, db: AsyncSession = Depends(get_db)):
    """Edit a source's details, or enable/pause it for future scans."""
    src = await db.get(Source, source_id)
    if not src:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("feed_url") and changes["feed_url"] != src.feed_url:
        dup = (await db.execute(select(Source).where(Source.feed_url == changes["feed_url"]))).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Feed URL is already registered as '{dup.name}'.")
    for field, value in changes.items():
        if value is not None or field in ("homepage_url", "bias_category"):
            setattr(src, field, value)
    await db.commit()
    await db.refresh(src)
    return src


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """Remove a source and its ingested articles."""
    # Eager-load articles so the ORM cascade can run without async lazy loading.
    src = await db.get(Source, source_id, options=[selectinload(Source.articles)])
    if not src:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    affected = {a.cluster_id for a in src.articles if a.cluster_id}
    await db.delete(src)
    await db.flush()
    # Keep cluster counts honest; drop clusters whose only coverage came from this source.
    for cid in affected:
        remaining = (await db.execute(select(func.count()).where(Article.cluster_id == cid))).scalar_one()
        cluster = await db.get(EventCluster, cid)
        if remaining == 0:
            await db.delete(cluster)
        else:
            cluster.article_count = remaining
    await db.commit()


@router.post("/scan", response_model=ScanSummary)
async def trigger_scan(db: AsyncSession = Depends(get_db)):
    """Run an on-demand crawl across all active sources and cluster new events."""
    if _scan_lock.locked():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A scan is already running. Try again when it finishes.")
    return await run_full_scan(db)


async def run_full_scan(db: AsyncSession) -> ScanSummary:
    """Ingest all active sources and cluster the new articles (shared by the endpoint and the scheduler)."""
    async with _scan_lock:
        summary = await IngestionEngine(db).run_scan()
        summary.clusters_created_or_updated = await ClusteringEngine(db).cluster_unassigned_articles()
    return summary


async def scheduled_scans(interval_minutes: float) -> None:
    """Background loop started at app startup when GPS_SCAN_INTERVAL_MINUTES > 0."""
    from app.database import AsyncSessionLocal
    while True:
        await asyncio.sleep(interval_minutes * 60)
        if _scan_lock.locked():
            continue
        try:
            async with AsyncSessionLocal() as db:
                summary = await run_full_scan(db)
            logger.info("Scheduled scan: %d new articles, %d errors", summary.new_articles_ingested, len(summary.errors))
        except Exception:
            logger.exception("Scheduled scan failed")


@router.get("/clusters", response_model=List[EventClusterResponse])
async def list_event_clusters(
    region: Optional[str] = None,
    severity: Optional[str] = None,
    min_score: Optional[float] = Query(None, ge=0.0, le=100.0),
    focus: Optional[str] = None,
    include_archived: bool = False,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve scored event clusters with multi-source triangulation."""
    stmt = (
        select(EventCluster)
        .options(selectinload(EventCluster.articles).selectinload(Article.source))
        .order_by(EventCluster.explainer_score.desc(), EventCluster.last_updated.desc())
    )

    if not include_archived:
        stmt = stmt.where(EventCluster.status != "archived")
    if region:
        stmt = stmt.where(EventCluster.region.ilike(f"%{region}%"))
    if severity:
        stmt = stmt.where(EventCluster.severity == severity)
    if min_score is not None:
        stmt = stmt.where(EventCluster.explainer_score >= min_score)

    if focus != "india":
        stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    enriched = [enrich_cluster_triangulation(c) for c in result.scalars().all()]
    if focus == "india":
        # India relevance is computed in Python, so page after filtering or pages come back short.
        enriched = [c for c in enriched if c.is_india_relevant][offset : offset + limit]
    return enriched


@router.get("/india", response_model=List[EventClusterResponse])
async def list_india_desk_clusters(
    severity: Optional[str] = None,
    triangulation: Optional[str] = None,
    include_archived: bool = False,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve India Strategic Desk events with multi-source cross-verification metrics."""
    stmt = (
        select(EventCluster)
        .options(selectinload(EventCluster.articles).selectinload(Article.source))
        .order_by(EventCluster.explainer_score.desc(), EventCluster.last_updated.desc())
    )

    if not include_archived:
        stmt = stmt.where(EventCluster.status != "archived")
    if severity:
        stmt = stmt.where(EventCluster.severity == severity)

    result = await db.execute(stmt)
    all_clusters = list(result.scalars().all())

    india_clusters = []
    for c in all_clusters:
        enriched = enrich_cluster_triangulation(c)
        if not enriched.is_india_relevant:
            continue
        if triangulation and enriched.triangulation_level != triangulation:
            continue
        india_clusters.append(enriched)

    # shortcut: loads every cluster to compute India relevance; persist is_india_relevant at clustering time if this gets slow.
    return india_clusters[offset : offset + limit]


@router.get("/clusters/{cluster_id}", response_model=EventClusterDetail)
async def get_cluster_detail(cluster_id: str, db: AsyncSession = Depends(get_db)):
    """Get full details of an event cluster, including its backing articles and verification."""
    stmt = (
        select(EventCluster)
        .options(selectinload(EventCluster.articles).selectinload(Article.source))
        .where(EventCluster.id == cluster_id)
    )
    result = await db.execute(stmt)
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event cluster '{cluster_id}' not found.",
        )
    return enrich_cluster_triangulation(cluster)


@router.get("/clusters/{cluster_id}/factchecks", response_model=List[FactCheckResponse])
async def get_cluster_fact_checks(cluster_id: str, db: AsyncSession = Depends(get_db)):
    """Find published fact-checks (AFP, Reuters, BOOM, PolitiFact, ...) matching this event."""
    cluster = await db.get(EventCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Event cluster '{cluster_id}' not found.")
    return await find_fact_checks(cluster.headline, (cluster.key_actors or []) + (cluster.chokepoints or []), region=cluster.region)


@router.get("/articles", response_model=List[ArticleResponse])
async def list_articles(
    source_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List raw ingested articles with pagination."""
    stmt = select(Article).order_by(Article.published_at.desc())
    if source_id:
        stmt = stmt.where(Article.source_id == source_id)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())
