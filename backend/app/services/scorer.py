"""Explainer scoring algorithm tailored for geopolitical documentary creators."""
import re
from typing import List, Dict, Set, Tuple, Any, Optional

# Strategic choke points and maritime passages critical in geopolitics
CHOKEPOINTS = {
    "malacca strait": "Strait of Malacca",
    "strait of malacca": "Strait of Malacca",
    "hormuz": "Strait of Hormuz",
    "taiwan strait": "Taiwan Strait",
    "bab el-mandeb": "Bab el-Mandeb",
    "suez canal": "Suez Canal",
    "panama canal": "Panama Canal",
    "bosphorus": "Bosphorus / Turkish Straits",
    "dardanelles": "Turkish Straits",
    "suwalki": "Suwalki Gap",
    "suwalki gap": "Suwalki Gap",
    "giuk gap": "GIUK Gap",
    # India, Indian Ocean & Himalayan Flashpoints
    "siliguri": "Siliguri Corridor (Chicken's Neck)",
    "siliguri corridor": "Siliguri Corridor (Chicken's Neck)",
    "chickens neck": "Siliguri Corridor (Chicken's Neck)",
    "andaman": "Andaman & Nicobar Gateway (Malacca Approach)",
    "andaman and nicobar": "Andaman & Nicobar Gateway (Malacca Approach)",
    "ten degree channel": "Ten Degree Channel",
    "six degree channel": "Six Degree Channel (Great Channel)",
    "lac": "Line of Actual Control (LAC)",
    "line of actual control": "Line of Actual Control (LAC)",
    "loc": "Line of Control (LoC)",
    "galwan": "Galwan Valley",
    "pangong": "Pangong Tso",
    "doklam": "Doklam Plateau",
    "chabahar": "Chabahar Port Corridor",
    "indian ocean": "Indian Ocean Region (IOR)",
    "palk strait": "Palk Strait",
    "imec": "India-Middle East-Europe Economic Corridor (IMEC)",
    "instc": "International North-South Transport Corridor (INSTC)",
}

# Critical geopolitical actors, alliances, and pacts
ACTORS = {
    "nato": "NATO",
    "un security council": "UNSC",
    "unsc": "UNSC",
    "european union": "EU",
    "pentagon": "US DoD",
    "kremlin": "Russia",
    "beijing": "China",
    "taiwan": "Taiwan",
    "ukraine": "Ukraine",
    "russia": "Russia",
    "china": "China",
    "iran": "Iran",
    "israel": "Israel",
    "north korea": "North Korea",
    "south korea": "South Korea",
    "india": "India",
    "new delhi": "India",
    "pakistan": "Pakistan",
    "houthis": "Ansar Allah (Houthis)",
    "hezbollah": "Hezbollah",
    "opec": "OPEC+",
    "brics": "BRICS",
    "quad": "Quad (India-US-Japan-Australia)",
    "isro": "ISRO",
    "drdo": "DRDO",
    "raw": "R&AW",
    "sco": "SCO",
    "asean": "ASEAN",
    "mea": "India MEA",
    "pla": "China (PLA)",
}

# High-yield explainer terms (topics that benefit from long-form video explanation)
EXPLAINER_KEYWORDS = {
    # Chokepoints & geography
    "corridor": 1.5,
    "annexation": 2.5,
    "buffer zone": 2.0,
    "sovereignty": 1.5,
    "blockade": 2.5,
    # High-stakes military/defense
    "nuclear": 3.0,
    "deterrence": 2.0,
    "mobilization": 2.0,
    "hypersonic": 2.0,
    "carrier strike group": 2.5,
    "submarine": 1.5,
    "air defense": 1.5,
    "two front war": 3.0,
    "border dispute": 2.5,
    "indigenous defense": 2.0,
    # Geoeconomics & Resources
    "sanctions": 2.0,
    "rare earths": 2.5,
    "semiconductor": 2.5,
    "semiconductor fab": 2.5,
    "pipeline": 2.0,
    "embargo": 2.0,
    "critical minerals": 2.5,
    "lithium": 2.0,
    "strategic autonomy": 2.5,
    "supply chain resilience": 2.0,
    "global south": 2.0,
    "maritime domain awareness": 2.0,
    "de-dollarization": 2.0,
    # Diplomatic & Treaties
    "treaty": 2.0,
    "ceasefire": 2.0,
    "veto": 1.5,
    "ultimatum": 2.5,
    "proxy": 2.0,
}


# Short tokens that are ordinary words in lowercase ("raw materials", "lac"); only their acronym form counts.
ACRONYM_PATTERNS = {
    "raw": re.compile(r"\bR&AW\b|\bRAW\b"),
    "quad": re.compile(r"\bQuad\b|\bQUAD\b"),
    "mea": re.compile(r"\bMEA\b"),
    "sco": re.compile(r"\bSCO\b"),
    "pla": re.compile(r"\bPLA\b"),
    "lac": re.compile(r"\bLAC\b"),
    "loc": re.compile(r"\bLoC\b|\bLOC\b"),
}


def _mentions(token: str, text: str, lower_text: str) -> bool:
    pattern = ACRONYM_PATTERNS.get(token)
    if pattern:
        return bool(pattern.search(text))
    return bool(re.search(r"\b" + re.escape(token) + r"\b", lower_text))


def extract_entities_and_chokepoints(text: str) -> Tuple[List[str], List[str], List[str]]:
    """Extract recognized actors, chokepoints, and high-yield strategic terms from text."""
    lower_text = text.lower()

    found_actors = {canonical for token, canonical in ACTORS.items() if _mentions(token, text, lower_text)}
    found_chokepoints = {canonical for token, canonical in CHOKEPOINTS.items() if _mentions(token, text, lower_text)}

    found_keywords: Set[str] = set()
    for keyword in EXPLAINER_KEYWORDS:
        if re.search(r"\b" + re.escape(keyword) + r"(?:s|es)?\b", lower_text):
            found_keywords.add(keyword)

    return sorted(list(found_actors)), sorted(list(found_chokepoints)), sorted(list(found_keywords))


def calculate_explainer_score(
    title: str,
    summary: str,
    article_count: int = 1,
    source_diversity: int = 1,
) -> Tuple[float, str]:
    """
    Calculate 0.0 - 100.0 score of how suitable a topic is for a long-form video essay.
    Returns: (score, severity)
    """
    actors, chokepoints, keywords = extract_entities_and_chokepoints(f"{title} {summary}")

    base_score = 15.0

    # Keyword weights
    for kw in keywords:
        base_score += EXPLAINER_KEYWORDS.get(kw, 1.0) * 4.0

    # Chokepoints bonus (geography videos perform exceptionally well)
    base_score += len(chokepoints) * 12.0

    # Multi-actor friction bonus
    if len(actors) >= 3:
        base_score += 15.0
    elif len(actors) >= 2:
        base_score += 8.0

    # Corroboration & Multi-source consensus bonus
    if source_diversity > 1:
        base_score += min(source_diversity * 5.0, 20.0)

    # Article volume bonus
    if article_count > 3:
        base_score += min(article_count * 2.0, 15.0)

    # Normalize to 0.0 - 100.0
    final_score = min(max(round(base_score, 1), 5.0), 100.0)

    # Classify severity
    if final_score >= 70.0 or any(k in keywords for k in ["nuclear", "blockade", "annexation", "ultimatum"]):
        severity = "crisis"
    elif final_score >= 40.0:
        severity = "escalating"
    else:
        severity = "routine"

    return final_score, severity


# Wire agencies whose copy is syndicated verbatim; outlets carrying it are not independent.
WIRE_AGENCIES = [
    ("Reuters", re.compile(r"\breuters\b", re.I)),
    ("Associated Press", re.compile(r"\(AP\)|\b[Aa]ssociated [Pp]ress\b")),
    ("AFP", re.compile(r"\(AFP\)|\bagence france[- ]presse\b", re.I)),
    ("PTI", re.compile(r"\(PTI\)|\bpress trust of india\b", re.I)),
    ("ANI", re.compile(r"\(ANI\)|\basian news international\b", re.I)),
    ("IANS", re.compile(r"\(IANS\)|\bindo-asian news service\b", re.I)),
    ("Xinhua", re.compile(r"\bxinhua\b", re.I)),
    ("TASS", re.compile(r"\bTASS\b")),
]


def detect_wire_origin(text: str) -> Optional[str]:
    """Return the wire agency credited in an article, if any."""
    for name, pattern in WIRE_AGENCIES:
        if pattern.search(text or ""):
            return name
    return None


def _content_tokens(text: str) -> Set[str]:
    return set(re.findall(r"\b[a-z]{4,}\b", (text or "").lower()))


def assign_origins(reports: List[Tuple[str, str]]) -> List[str]:
    """
    Map each (source_id, text) report to an origin key so that wire copies and
    near-identical rewrites of the same story count once.
    shortcut: an article that merely cites a wire ("Reuters reported...") is merged with it,
    which undercounts independence; upgrade to byline/dateline parsing if that bites.
    """
    origins: List[str] = []
    seen: List[Tuple[str, Set[str]]] = []
    for source_id, text in reports:
        origin = detect_wire_origin(text)
        tokens = _content_tokens(text)
        if not origin:
            for key, other in seen:
                union = tokens | other
                if union and len(tokens & other) / len(union) >= 0.6:
                    origin = key
                    break
        origin = origin or f"source:{source_id}"
        origins.append(origin)
        seen.append((origin, tokens))
    return origins


def evaluate_triangulation(
    source_count: int,
    source_categories: List[str] = None,
    reliabilities: Optional[List[float]] = None,
    outlet_count: Optional[int] = None,
) -> Tuple[str, float, List[Dict[str, Any]]]:
    """
    Evaluates multi-source cross-verification level for geopolitical video essays.
    source_count is the number of independent origins (wire copies already merged).
    Returns: (level, confidence_score, checklist)
    Levels:
      - 'triangulated': >= 3 independent origins with average reliability >= 0.7
      - 'corroborated': 2+ independent origins
      - 'unverified': 1 origin (Single-source warning)
    """
    cats = source_categories or []
    has_domestic = any("domestic" in c or "business_geoecon" in c for c in cats)
    has_international = any("western" in c or "pan_arab" in c or "policy_establishment" in c for c in cats)
    avg_reliability = sum(reliabilities) / len(reliabilities) if reliabilities else 1.0
    outlets = outlet_count if outlet_count is not None else source_count

    checklist = [
        {
            "id": "multi_source",
            "label": "Multi-Source Corroboration",
            "passed": source_count >= 2,
            "detail": f"{outlets} outlet(s), {source_count} independent origin(s) after merging wire copies",
        },
        {
            "id": "perspective_diversity",
            "label": "Cross-Perspective Triangulation",
            "passed": has_domestic and has_international,
            "detail": "Cross-checked across domestic and international reporting lenses"
            if (has_domestic and has_international)
            else "Single media ecosystem (verify external perspective before script lock)",
        },
        {
            "id": "primary_evidence",
            "label": "Primary Documentation / Coordinate Check",
            "passed": source_count >= 3,
            "detail": "High-confidence multi-source corroboration suitable for long-form video essay"
            if source_count >= 3
            else "Secondary reporting only — check official MEA/DoD/OSINT gazettes",
        },
    ]
    if reliabilities:
        checklist.append({
            "id": "source_reliability",
            "label": "Source Reliability",
            "passed": avg_reliability >= 0.7,
            "detail": f"Average editorial reliability rating {round(avg_reliability * 100)}% (set per feed in the registry)",
        })

    if source_count >= 3 and avg_reliability >= 0.7:
        level, base = "triangulated", 0.92
    elif source_count >= 2:
        level, base = "corroborated", 0.75
    else:
        level, base = "unverified", 0.45

    return level, round(base * avg_reliability, 2), checklist


def verification_label(level: str, origin_count: int, cross_ecosystem: bool) -> str:
    """Plain-language claim status shown instead of a bare confidence number."""
    if level == "triangulated":
        where = " across media ecosystems" if cross_ecosystem else ""
        return f"Confirmed by {origin_count} independent origins{where}"
    if level == "corroborated":
        return f"Reported by {origin_count} independent origins — not yet confirmed"
    return "Unconfirmed claim — single origin"
