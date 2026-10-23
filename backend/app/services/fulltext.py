"""On-demand full-text fetch for articles that AI will write from or check against.

Feeds only carry a short summary, which is too thin to verify anything. Before the script writer or a
fact check runs, the event's articles are downloaded once and their main text stored in Article.clean_text.
The outcome is recorded in Article.entities["fulltext"] ("ok" or "failed: ...") so failures and paywalls
aren't retried on every request.
"""
import asyncio
import logging
from typing import Iterable, List, Optional

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.models.source import Article
from app.services.ingester import block_private_hosts

logger = logging.getLogger(__name__)

MAX_PAGE_BYTES = 3_000_000
MAX_TEXT_CHARS = 20_000
MIN_PARAGRAPH_CHARS = 40
FETCH_TIMEOUT_SECONDS = 10.0
CONCURRENCY = 5
# Short paragraphs containing these are account/paywall chrome (e.g. The Hindu's login prompts), not reporting.
BOILERPLATE_MARKERS = ("subscribe", "subscription", "log in", "login", "logout", "sign in", "sign up", "newsletter",
                       "cookie", "download the app", "follow us", "all rights reserved")
BOILERPLATE_MAX_CHARS = 250


def extract_main_text(html: str) -> str:
    """Pull readable article text out of a page: prefer <article>/<main>, else every substantial <p>.

    shortcut: heuristic extraction, not a full readability algorithm; upgrade (e.g. trafilatura) if
    too many sites come back as navigation boilerplate.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "figure", "button"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = [" ".join(p.get_text(" ", strip=True).split()) for p in root.find_all("p")]
    text = "\n\n".join(p for p in paragraphs if len(p) >= MIN_PARAGRAPH_CHARS and not _is_boilerplate(p))
    return text[:MAX_TEXT_CHARS]


def _is_boilerplate(paragraph: str) -> bool:
    lower = paragraph.lower()
    return len(paragraph) <= BOILERPLATE_MAX_CHARS and any(m in lower for m in BOILERPLATE_MARKERS)


async def fetch_page_text(client: httpx.AsyncClient, url: str) -> str:
    """Download one page (size-capped) and return its main text; raises on HTTP errors or empty extraction."""
    async with client.stream("GET", url) as res:
        res.raise_for_status()
        if "html" not in res.headers.get("content-type", "html"):
            raise ValueError(f"not an HTML page ({res.headers.get('content-type')})")
        chunks, size = [], 0
        async for chunk in res.aiter_bytes():
            size += len(chunk)
            if size > MAX_PAGE_BYTES:
                break
            chunks.append(chunk)
    html = b"".join(chunks).decode(res.encoding or "utf-8", errors="replace")
    text = extract_main_text(html)
    if len(text) < 200:
        raise ValueError("no article text found (paywall or script-rendered page?)")
    return text


def web_client() -> httpx.AsyncClient:
    """HTTP client for fetching third-party pages: same internal-address blocking as feed scans."""
    return httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": settings.USER_AGENT},
        event_hooks={"request": [block_private_hosts]},
    )


async def ensure_full_text(articles: Iterable[Article]) -> int:
    """Fetch full text for articles not yet attempted. Returns how many succeeded. Caller commits."""
    pending: List[Article] = [a for a in articles if not (a.entities or {}).get("fulltext")]
    if not pending:
        return 0
    limit = asyncio.Semaphore(CONCURRENCY)

    async with web_client() as client:
        async def one(art: Article) -> Optional[str]:
            async with limit:
                try:
                    return await fetch_page_text(client, art.url)
                except Exception as exc:  # any failure just leaves the summary in place
                    return f"failed: {type(exc).__name__}: {str(exc)[:120]}"

        outcomes = await asyncio.gather(*(one(a) for a in pending))

    ok = 0
    for art, outcome in zip(pending, outcomes):
        if outcome.startswith("failed: "):
            status = outcome
        else:
            art.clean_text, status, ok = outcome, "ok", ok + 1
        art.entities = {**(art.entities or {}), "fulltext": status}  # reassign so the JSON change is persisted
    logger.info("Full text fetched for %d of %d articles", ok, len(pending))
    return ok
