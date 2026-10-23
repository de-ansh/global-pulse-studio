"""Lookup of published fact-checks via the Google Fact Check Tools API."""
import logging
import re
from typing import Any, Dict, List

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

FACTCHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
QUERY_STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "over", "after", "amid", "says",
    "said", "will", "have", "has", "are", "was", "were", "this", "that", "new",
}


def build_fact_check_query(headline: str, max_words: int = 6) -> str:
    """Reduce a headline to its leading significant words; long queries match nothing."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", headline) if w.lower() not in QUERY_STOPWORDS]
    return " ".join(words[:max_words])


def parse_fact_checks(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten claims -> claimReview entries into one row per published review."""
    rows = []
    for claim in payload.get("claims", []):
        for review in claim.get("claimReview", []):
            # Review URLs are rendered as links and can be attached as claim evidence; only accept web URLs.
            if not str(review.get("url", "")).lower().startswith(("http://", "https://")):
                continue
            rows.append({
                "claim": claim.get("text", ""),
                "claimant": claim.get("claimant"),
                "claim_date": claim.get("claimDate"),
                "publisher": (review.get("publisher") or {}).get("name") or (review.get("publisher") or {}).get("site", "Unknown"),
                "rating": review.get("textualRating", "Unrated"),
                "title": review.get("title"),
                "url": review.get("url", ""),
                "review_date": review.get("reviewDate"),
            })
    return rows


async def search_fact_checks(query: str, api_key: str) -> List[Dict[str, Any]]:
    """Query published fact-checks matching the given text."""
    async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
        res = await client.get(FACTCHECK_URL, params={"query": query, "key": api_key, "pageSize": 10})
        res.raise_for_status()
    return parse_fact_checks(res.json())


async def fact_checks_or_http_error(query: str) -> List[Dict[str, Any]]:
    """Run a lookup for an API route: 503 when no key is configured, 502 (without the key-bearing URL) on upstream errors."""
    if not settings.FACTCHECK_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fact-check lookup is not configured. Set GPS_FACTCHECK_API_KEY (Google Fact Check Tools API key) and restart.",
        )
    try:
        return await search_fact_checks(query, settings.FACTCHECK_API_KEY)
    except httpx.HTTPError as exc:
        # httpx error text embeds the request URL, which carries the API key; keep it server-side.
        logger.warning("Fact-check lookup failed: %s", type(exc).__name__)
        code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fact-check service error{f' (HTTP {code})' if code else ''}. Check the API key and try again.",
        )
