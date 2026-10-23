"""Multi-source RSS/Atom feed crawler and sanitizer with deduplication."""
import re
import asyncio
import hashlib
import ipaddress
import socket
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set
import httpx
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.source import Source, Article
from app.schemas.source import ScanSummary
from app.services.scorer import extract_entities_and_chokepoints

logger = logging.getLogger(__name__)


def clean_html_text(raw_html: Optional[str]) -> str:
    """Strip tags, tracking scripts, and excessive whitespace from feed content."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for script_or_style in soup(["script", "style", "nav", "footer", "aside"]):
        script_or_style.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return " ".join(text.split())


def compute_canonical_hash(url: str, title: str) -> str:
    """Generate SHA-256 fingerprint for deduplication across slight title variations."""
    norm_url = url.strip().lower().split("?")[0]
    norm_title = " ".join("".join(c for c in title.lower() if c.isalnum() or c.isspace()).split())
    return hashlib.sha256(f"{norm_url}::{norm_title}".encode("utf-8")).hexdigest()


def parse_published_date(entry: Dict[str, Any]) -> datetime:
    """Parse various timestamp formats from RSS/Atom entries to UTC datetime."""
    for field in ("published", "pubDate", "updated", "created"):
        val = entry.get(field)
        if val:
            try:
                parsed = date_parser.parse(val)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except Exception:
                continue
    return datetime.now(timezone.utc)


async def block_private_hosts(request: httpx.Request) -> None:
    """httpx request hook (runs on every redirect hop): refuse feeds pointing at internal addresses.

    shortcut: resolves DNS separately from httpx, so a DNS-rebinding host could still slip through;
    upgrade to a pinned-IP transport if the API is ever exposed to untrusted users.
    """
    host = request.url.host
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise httpx.ConnectError(f"Cannot resolve host {host}", request=request) from exc
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if not addr.is_global:
            raise httpx.ConnectError(f"Refusing to fetch non-public address for host {host}", request=request)


class IngestionEngine:
    """Asynchronous engine for fetching and sanitizing geopolitical feeds."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def fetch_feed_content(self, client: httpx.AsyncClient, feed_url: str) -> str:
        """Fetch raw XML with timeouts and agent identification."""
        response = await client.get(
            feed_url,
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text

    async def ingest_source(
        self,
        client: httpx.AsyncClient,
        source: Source,
        seen_hashes: Optional[Set[str]] = None,
        prefetched: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Process a single source feed; `prefetched` is its already-downloaded XML (or the fetch exception)."""
        if seen_hashes is None:
            seen_hashes = set()

        result = {"new_count": 0, "duplicate_count": 0, "error": None}
        now = datetime.now(timezone.utc)

        try:
            if isinstance(prefetched, BaseException):
                raise prefetched
            xml_text = prefetched if prefetched is not None else await self.fetch_feed_content(client, source.feed_url)
            parsed = feedparser.parse(xml_text)

            if parsed.bozo and not parsed.entries:
                raise ValueError(f"Malformed feed syntax: {parsed.bozo_exception}")

            source.last_fetched_at = now
            source.last_error = None

            # One query for the whole feed instead of one per entry.
            feed_hashes = [
                compute_canonical_hash(e.get("link", ""), clean_html_text(e.get("title", ""))) for e in parsed.entries
            ]
            existing_hashes = set(
                (await self.db.execute(select(Article.canonical_hash).where(Article.canonical_hash.in_(feed_hashes)))).scalars()
            ) if feed_hashes else set()

            for entry in parsed.entries:
                title = clean_html_text(entry.get("title", ""))
                link = entry.get("link", "")
                # Links are rendered as hrefs; drop javascript:/data: and other non-web schemes.
                if not title or not link.lower().startswith(("http://", "https://")):
                    continue

                raw_summary = entry.get("summary", "") or entry.get("description", "")
                summary = clean_html_text(raw_summary)
                published_at = parse_published_date(entry)

                canonical_hash = compute_canonical_hash(link, title)

                # Deduplication check across batch and database
                if canonical_hash in seen_hashes:
                    result["duplicate_count"] += 1
                    continue

                if canonical_hash in existing_hashes:
                    seen_hashes.add(canonical_hash)
                    result["duplicate_count"] += 1
                    continue

                seen_hashes.add(canonical_hash)

                # Extract entities & topics
                actors, chokepoints, keywords = extract_entities_and_chokepoints(f"{title} {summary}")
                topics = list(set(actors + chokepoints + keywords))

                article = Article(
                    id=f"art_{uuid.uuid4().hex[:12]}",
                    source_id=source.id,
                    canonical_hash=canonical_hash,
                    title=title,
                    url=link,
                    author=entry.get("author"),
                    summary=summary[:1500] if summary else "",
                    clean_text=summary,
                    published_at=published_at,
                    ingested_at=now,
                    entities={"actors": actors, "chokepoints": chokepoints},
                    topics=topics,
                )
                self.db.add(article)
                result["new_count"] += 1

        except Exception as exc:
            source.last_error = str(exc)
            result["error"] = str(exc)
            logger.warning("Failed feed fetch for source %s: %s", source.id, exc)

        return result

    async def run_scan(self) -> ScanSummary:
        """Scan all active sources and persist new articles."""
        # Query active sources
        stmt = select(Source).where(Source.is_active.is_(True))
        result = await self.db.execute(stmt)
        sources = list(result.scalars().all())

        total_new = 0
        total_dup = 0
        errors: List[Dict[str, str]] = []
        seen_hashes: Set[str] = set()

        async with httpx.AsyncClient(event_hooks={"request": [block_private_hosts]}) as client:
            # Download in parallel (network-bound); process sequentially since one AsyncSession can't be shared.
            limit = asyncio.Semaphore(settings.MAX_CONCURRENT_FEEDS)

            async def fetch(src: Source) -> str:
                async with limit:
                    return await self.fetch_feed_content(client, src.feed_url)

            downloads = await asyncio.gather(*(fetch(src) for src in sources), return_exceptions=True)
            for source, prefetched in zip(sources, downloads):
                res = await self.ingest_source(client, source, seen_hashes=seen_hashes, prefetched=prefetched)
                total_new += res["new_count"]
                total_dup += res["duplicate_count"]
                if res["error"]:
                    errors.append({"source_id": source.id, "error": res["error"]})

        await self.db.commit()

        return ScanSummary(
            sources_scanned=len(sources),
            new_articles_ingested=total_new,
            duplicate_articles_skipped=total_dup,
            clusters_created_or_updated=0,
            errors=errors,
        )
