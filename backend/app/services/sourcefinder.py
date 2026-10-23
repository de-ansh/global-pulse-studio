"""Primary-source finder: Gemini with Google Search grounding suggests documents that could confirm or refute a claim.

Links come from the response's groundingMetadata (actual search results), never from model-written text,
so they can't be invented. Grounding links are short-lived Google redirects; each is resolved to the real URL.
Nothing is attached automatically: the creator reviews and adds suggestions as evidence.
"""
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx

from app.services import gemini
from app.services.fulltext import web_client

FINDER_SYSTEM = """You help a journalist find PRIMARY sources for a claim: official statements, government, military or
agency documents, court filings, parliamentary records, datasets, and original wire reports, in that order of
preference. Search the web, then in 3-6 short bullet points say what the best sources say about the claim and
whether they confirm it, contradict it, or don't settle it. Do not rely on memory; only use what the search found."""

OFFICIAL_SUFFIXES = (".gov", ".mil", ".int", ".nic.in", "un.org", "europa.eu", "nato.int", "who.int", "worldbank.org", "imf.org")


def is_official(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host.endswith(s) or f"{s}." in f"{host}." for s in OFFICIAL_SUFFIXES) or ".gov." in host


def grounding_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Search results the answer was grounded in, each with the answer text that cites it as a snippet."""
    meta = ((payload.get("candidates") or [{}])[0]).get("groundingMetadata") or {}
    chunks = meta.get("groundingChunks") or []
    snippets: Dict[int, List[str]] = {}
    for support in meta.get("groundingSupports") or []:
        text = (support.get("segment") or {}).get("text", "").strip()
        for idx in support.get("groundingChunkIndices") or []:
            if text and text not in snippets.setdefault(idx, []):
                snippets[idx].append(text)
    results, seen = [], set()
    for i, chunk in enumerate(chunks):
        web = chunk.get("web") or {}
        uri = web.get("uri", "")
        if not uri.startswith(("http://", "https://")) or uri in seen:
            continue
        seen.add(uri)
        results.append({"title": web.get("title") or uri, "redirect_url": uri, "snippet": " ".join(snippets.get(i, []))[:500]})
    return results


async def resolve_redirect(client: httpx.AsyncClient, url: str) -> str:
    """Follow one grounding redirect to the real page URL; returns the input if it can't be resolved."""
    try:
        res = await client.get(url, follow_redirects=False)
        location = res.headers.get("location", "")
        return location if location.startswith(("http://", "https://")) else url
    except httpx.HTTPError:
        return url


async def find_primary_sources(claim_text: str) -> Dict[str, Any]:
    """Returns {summary, sources: [{title, url, domain, snippet, official, resolved}]}, official sources first."""
    payload, model = await gemini.request(
        FINDER_SYSTEM, f"CLAIM: {claim_text}", tools=[{"google_search": {}}], temperature=0.0, max_tokens=4096
    )
    try:
        summary = gemini.response_text(payload)
    except ValueError as exc:
        raise gemini.bad_gateway(str(exc))
    found = grounding_results(payload)
    async with web_client() as client:
        for r in found:
            r["url"] = await resolve_redirect(client, r.pop("redirect_url"))
            r["resolved"] = "grounding-api-redirect" not in r["url"]
            r["domain"] = (urlparse(r["url"]).hostname or r["title"]).removeprefix("www.")
            r["official"] = is_official(r["url"])
    found.sort(key=lambda r: not r["official"])
    return {"summary": summary, "sources": found, "model": model}
