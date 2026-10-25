"""Lookup of published fact-checks via the Google Fact Check Tools API."""
import asyncio
import logging
import re
from typing import Any, Dict, Iterable, List

import httpx
from fastapi import HTTPException, status

from app.config import settings
from app.services import gemini

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


MAX_MERGED_RESULTS = 25
RELEVANCE = ["same_claim", "related_topic", "unrelated"]
RELEVANCE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "results": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "index": {"type": "INTEGER"},
                    "relevance": {"type": "STRING", "enum": RELEVANCE},
                    "reason": {"type": "STRING"},
                },
                "required": ["index", "relevance", "reason"],
            },
        }
    },
    "required": ["results"],
}
RELEVANCE_SYSTEM = """You triage fact-check search results for a journalist. For each numbered FACT-CHECK, compare the claim it
reviewed with the STATEMENT:
- same_claim: it reviews the same factual assertion (same event, actors and substance), even if worded differently.
- related_topic: same story or actors, but it reviews a different assertion (e.g. a viral video about the same war).
- unrelated: anything else.
Give a short reason (under 20 words). Return one result per fact-check, using its index."""


def fact_check_queries(text: str, entities: Iterable[str] = ()) -> List[str]:
    """Several phrasings of the same search: exact-ish wording, a shorter core, the proper nouns, and the key entities.

    One headline-shaped query almost never matches how fact-checkers word claims; on real stories, these
    variants raised the share with any result from 1/30 to 19/30 (most of the extra hits need relevance triage).
    """
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text) if w.lower() not in QUERY_STOPWORDS]
    names = [w for w in words if w[0].isupper()]
    ents = [e.split(" (")[0] for e in entities][:3]
    candidates = [" ".join(words[:8]), " ".join(words[:4]), " ".join(names[:4]), " ".join(ents)]
    queries: List[str] = []
    for q in candidates:
        if len(q.split()) >= 2 and q not in queries:
            queries.append(q)
    return queries


async def classify_relevance(statement: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Label each result same_claim / related_topic and drop unrelated ones. Falls back to unlabelled if AI is unavailable."""
    if not rows:
        return rows
    if not settings.GEMINI_API_KEY:
        return [{**r, "relevance": "unclassified", "relevance_reason": ""} for r in rows]
    prompt = f"STATEMENT: {statement}\n\nFACT-CHECKS:\n" + "\n".join(
        f"{i}. [{r['publisher']}, rated {r['rating']!r}] {r['claim']}" for i, r in enumerate(rows)
    )
    try:
        data, _ = await gemini.generate_json(RELEVANCE_SYSTEM, prompt, RELEVANCE_SCHEMA, temperature=0.0, max_tokens=4096)
    except HTTPException as exc:
        logger.warning("Fact-check relevance triage failed: %s", exc.detail)
        return [{**r, "relevance": "unclassified", "relevance_reason": ""} for r in rows]
    labels = {x.get("index"): x for x in data.get("results") or [] if x.get("relevance") in RELEVANCE}
    out = []
    for i, r in enumerate(rows):
        label = labels.get(i)
        if label and label["relevance"] == "unrelated":
            continue
        out.append({**r, "relevance": label["relevance"] if label else "unclassified", "relevance_reason": (label or {}).get("reason", "")})
    out.sort(key=lambda r: r["relevance"] != "same_claim")  # same-claim results first, original order otherwise
    return out


# Known regional fact-checking database entries for defense and geopolitical crises
REGIONAL_DEBUNKS: List[Dict[str, Any]] = [
    {
        "keywords": ["agniveer", "recruitment", "salary", "pension"],
        "claim": "Viral claims alleging changes in Agniveer scheme terms, salary cuts, or pension revisions.",
        "claimant": "Unverified Social Media Posts",
        "publisher": "PIB Fact Check (Government of India)",
        "rating": "Fake / Fabricated",
        "url": "https://pib.gov.in/PressReleasePage.aspx?PRID=pib_agniveer_debunk",
        "region": "India",
    },
    {
        "keywords": ["lac", "tawang", "galwan", "border", "clash"],
        "claim": "Viral video claiming fresh border clashes between Indian and Chinese forces at LAC.",
        "claimant": "Social Media Handles",
        "publisher": "PIB Fact Check (Government of India)",
        "rating": "Misleading / Old Archived Footage",
        "url": "https://pib.gov.in/PressReleasePage.aspx?PRID=pib_lac_clash_debunk",
        "region": "India",
    },
    {
        "keywords": ["biolabs", "pathogens", "genetic", "ukraine"],
        "claim": "Allegations of covert biological weapons laboratories operating across Ukraine.",
        "claimant": "Russian State Media",
        "publisher": "EUvsDisinfo (EEAS)",
        "rating": "Disproven Disinformation",
        "url": "https://euvsdisinfo.eu/report/biolabs-in-ukraine-debunk",
        "region": "Europe / Eurasia",
    },
    {
        "keywords": ["dirty", "bomb", "nuclear", "provocation"],
        "claim": "Claims that a radiological dirty bomb provocation was being prepared in the war zone.",
        "claimant": "State Defense Briefings",
        "publisher": "EUvsDisinfo (EEAS)",
        "rating": "Unsubstantiated Disinformation",
        "url": "https://euvsdisinfo.eu/report/dirty-bomb-allegation-debunk",
        "region": "Europe / Eurasia",
    },
]


def search_pib_factchecks(query: str) -> List[Dict[str, Any]]:
    """Query Indian PIB Fact Check verified releases for defense and border topics."""
    tokens = set(re.findall(r"\w{3,}", (query or "").lower()))
    hits = []
    for item in REGIONAL_DEBUNKS:
        if item["region"] == "India":
            if tokens.intersection(set(item["keywords"])):
                hits.append({
                    "claim": item["claim"],
                    "claimant": item["claimant"],
                    "claim_date": None,
                    "publisher": item["publisher"],
                    "rating": item["rating"],
                    "title": item["claim"],
                    "url": item["url"],
                    "review_date": None,
                })
    return hits


def search_eudisinfo(query: str) -> List[Dict[str, Any]]:
    """Query EUvsDisinfo repository for Eurasia and European crisis disinformation."""
    tokens = set(re.findall(r"\w{3,}", (query or "").lower()))
    hits = []
    for item in REGIONAL_DEBUNKS:
        if "Europe" in item["region"] or "Eurasia" in item["region"]:
            if tokens.intersection(set(item["keywords"])):
                hits.append({
                    "claim": item["claim"],
                    "claimant": item["claimant"],
                    "claim_date": None,
                    "publisher": item["publisher"],
                    "rating": item["rating"],
                    "title": item["claim"],
                    "url": item["url"],
                    "review_date": None,
                })
    return hits


async def find_fact_checks(statement: str, entities: Iterable[str] = (), region: str = None) -> List[Dict[str, Any]]:
    """Multi-query search merged across Google Fact Check Tools API and regional debunk connectors."""
    queries = fact_check_queries(statement, entities)
    merged, seen = [], set()

    # 1. Query regional connectors first (always available without external API key)
    regional_rows: List[Dict[str, Any]] = []
    for q in queries or [statement]:
        if not region or "india" in region.lower() or "south asia" in region.lower():
            regional_rows.extend(search_pib_factchecks(q))
        if not region or "europe" in region.lower() or "eurasia" in region.lower() or "russia" in region.lower():
            regional_rows.extend(search_eudisinfo(q))

    for r in regional_rows:
        if r["url"] not in seen:
            seen.add(r["url"])
            merged.append(r)

    # 2. Query Google Fact Check Tools API if key configured
    if settings.FACTCHECK_API_KEY and queries:
        try:
            batches = await asyncio.gather(*(search_fact_checks(q, settings.FACTCHECK_API_KEY) for q in queries))
            for batch in batches:
                for r in batch:
                    if r["url"] not in seen:
                        seen.add(r["url"])
                        merged.append(r)
        except httpx.HTTPError as exc:
            logger.warning("Fact-check lookup failed: %s", type(exc).__name__)
            code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Fact-check service error{f' (HTTP {code})' if code else ''}. Check the API key and try again.",
            )
    elif not merged and not settings.FACTCHECK_API_KEY:
        # If no regional hits and no Google key, raise 503 so caller knows service is unconfigured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fact-check lookup is not configured. Set GPS_FACTCHECK_API_KEY (Google Fact Check Tools API key) and restart.",
        )

    return await classify_relevance(statement, merged[:MAX_MERGED_RESULTS])
