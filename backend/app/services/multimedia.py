"""Multimedia reverse search and verification service for detecting recycled footage and synthetic media."""
import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SIMULATION_KEYWORDS = {
    "arma 3", "arma iii", "arma", "dcs world", "digital combat simulator",
    "war thunder", "cgi", "computer-generated", "blender 3d", "flight simulator",
    "unreal engine", "simulator game", "gameplay", "modded game",
}

YEAR_PATTERN = re.compile(r"/(20[0-2][0-9])(?:[-_/]|\b)")


def extract_years_from_urls_or_titles(texts: List[str]) -> List[int]:
    """Scan historical page URLs and titles for timestamp markers."""
    years = []
    for t in texts:
        matches = YEAR_PATTERN.findall(t)
        for m in matches:
            try:
                y = int(m)
                if 2000 <= y <= 2030:
                    years.append(y)
            except ValueError:
                continue
    return sorted(set(years))


def check_simulation_cues(labels_and_entities: List[str]) -> Optional[str]:
    """Check if web entities contain military video game or CGI signatures."""
    for item in labels_and_entities:
        item_lower = item.lower()
        for kw in SIMULATION_KEYWORDS:
            if kw in item_lower:
                return kw.title()
    return None


async def verify_media_provenance(
    media_url: str,
    claimed_date: Optional[datetime] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Verify an image/video frame URL against reverse web detection to spot recycled footage and simulations."""
    if not media_url or not media_url.startswith(("http://", "https://")):
        return {
            "media_url": media_url or "",
            "verdict": "Inconclusive",
            "risk_level": "medium",
            "is_recycled_footage": False,
            "is_synthetic_or_game": False,
            "earliest_seen_year": None,
            "best_guess_label": None,
            "web_entities": [],
            "matching_domains": [],
            "explanation": "Invalid or missing media URL.",
        }

    target_year = claimed_date.year if claimed_date else datetime.now(timezone.utc).year
    api_key = settings.VISION_API_KEY or settings.FACTCHECK_API_KEY

    # 1. External Google Cloud Vision API Web Detection (if key configured)
    if api_key:
        try:
            should_close = False
            if client is None:
                client = httpx.AsyncClient(timeout=10.0)
                should_close = True

            try:
                vision_url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
                payload = {
                    "requests": [
                        {
                            "image": {"source": {"imageUri": media_url}},
                            "features": [{"type": "WEB_DETECTION", "maxResults": 15}],
                        }
                    ]
                }
                resp = await client.post(vision_url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    annotations = data.get("responses", [{}])[0].get("webDetection", {})
                    return evaluate_web_detection_result(media_url, annotations, target_year)
            finally:
                if should_close and client:
                    await client.aclose()
        except Exception as exc:
            logger.warning("Cloud Vision API call failed: %s, falling back to heuristic evaluation", exc)

    # 2. Local heuristic / pattern analysis fallback
    return evaluate_heuristic_media(media_url, target_year)


def evaluate_web_detection_result(
    media_url: str,
    web_detection: Dict[str, Any],
    target_year: int,
) -> Dict[str, Any]:
    """Parse Google Cloud Vision Web Detection payload into risk verdicts."""
    best_guess_raw = web_detection.get("bestGuessLabels", [])
    best_guess = best_guess_raw[0].get("label") if best_guess_raw else None

    entities_raw = web_detection.get("webEntities", [])
    entities = [e.get("description", "") for e in entities_raw if e.get("description")]

    pages_raw = web_detection.get("pagesWithMatchingImages", [])
    page_urls = [p.get("url", "") for p in pages_raw if p.get("url")]
    page_titles = [p.get("pageTitle", "") for p in pages_raw if p.get("pageTitle")]

    # Check for game or simulation tags
    all_tags = ([best_guess] if best_guess else []) + entities + page_titles
    sim_match = check_simulation_cues(all_tags)
    if sim_match:
        return {
            "media_url": media_url,
            "verdict": "Synthetic / Video Game Footage",
            "risk_level": "high",
            "is_recycled_footage": False,
            "is_synthetic_or_game": True,
            "earliest_seen_year": None,
            "best_guess_label": best_guess,
            "web_entities": entities[:6],
            "matching_domains": list(set([re.sub(r"^https?://([^/]+).*$", r"\1", u) for u in page_urls]))[:5],
            "explanation": f"Web entity detection identified military simulator or CGI signatures ({sim_match}). Often distributed during breaking events as fabricated combat footage.",
        }

    # Check temporal discrepancy
    years_found = extract_years_from_urls_or_titles(page_urls + page_titles)
    if years_found:
        earliest_year = min(years_found)
        if earliest_year < target_year - 1:
            return {
                "media_url": media_url,
                "verdict": "Recycled Footage Warning",
                "risk_level": "high",
                "is_recycled_footage": True,
                "is_synthetic_or_game": False,
                "earliest_seen_year": earliest_year,
                "best_guess_label": best_guess,
                "web_entities": entities[:6],
                "matching_domains": list(set([re.sub(r"^https?://([^/]+).*$", r"\1", u) for u in page_urls]))[:5],
                "explanation": f"Image/footage traces back to {earliest_year} (prior to reported breaking event in {target_year}). High risk of archival footage repackaged as breaking news.",
            }

    # Clean / Low Risk
    domains = list(set([re.sub(r"^https?://([^/]+).*$", r"\1", u) for u in page_urls]))[:5]
    return {
        "media_url": media_url,
        "verdict": "Likely Original / Authentic",
        "risk_level": "low",
        "is_recycled_footage": False,
        "is_synthetic_or_game": False,
        "earliest_seen_year": target_year,
        "best_guess_label": best_guess,
        "web_entities": entities[:6],
        "matching_domains": domains,
        "explanation": "No prior historical publication or synthetic signatures detected across web indexing.",
    }


def evaluate_heuristic_media(media_url: str, target_year: int) -> Dict[str, Any]:
    """Deterministic heuristic inspection for offline or unauthenticated operations."""
    url_lower = media_url.lower()

    # Simulation check in URL or path
    for kw in SIMULATION_KEYWORDS:
        if kw in url_lower:
            return {
                "media_url": media_url,
                "verdict": "Synthetic / Video Game Footage",
                "risk_level": "high",
                "is_recycled_footage": False,
                "is_synthetic_or_game": True,
                "earliest_seen_year": None,
                "best_guess_label": kw.title(),
                "web_entities": [kw.title(), "Military Simulation"],
                "matching_domains": [],
                "explanation": f"URL slug or metadata contains military game simulation indicator '{kw.title()}'.",
            }

    # URL path timestamp check (e.g. /2020/05/footage.mp4)
    years = extract_years_from_urls_or_titles([media_url])
    if years:
        earliest = min(years)
        if earliest < target_year - 1:
            return {
                "media_url": media_url,
                "verdict": "Recycled Footage Warning",
                "risk_level": "high",
                "is_recycled_footage": True,
                "is_synthetic_or_game": False,
                "earliest_seen_year": earliest,
                "best_guess_label": "Archival Media",
                "web_entities": ["Archival Footage"],
                "matching_domains": [],
                "explanation": f"Media URL path indicates file creation in {earliest}, pre-dating the reported event ({target_year}).",
            }

    return {
        "media_url": media_url,
        "verdict": "Likely Original / Authentic",
        "risk_level": "low",
        "is_recycled_footage": False,
        "is_synthetic_or_game": False,
        "earliest_seen_year": target_year,
        "best_guess_label": None,
        "web_entities": [],
        "matching_domains": [],
        "explanation": "Heuristic check passed: No archival timestamp tags or simulation artifacts found in media URL signature.",
    }
