"""AI evidence checks: does a source actually say what a statement claims?

The model never decides what is true; it compares statements to the given source texts and must quote
the sentence it relied on. verify_quotes() then checks every quote really appears in that source and
downgrades any verdict whose quotes can't be found, so a fabricated quote can't produce a "supported".
"""
import re
from typing import Any, Dict, List

from app.services import gemini

VERDICTS = ["supported", "partly_supported", "contradicted", "not_addressed"]
QUOTED_VERDICTS = {"supported", "partly_supported", "contradicted"}  # these need evidence to stand

SUPPORT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "results": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "statement_id": {"type": "STRING"},
                    "verdict": {"type": "STRING", "enum": VERDICTS},
                    "quotes": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {"source_id": {"type": "STRING"}, "quote": {"type": "STRING"}},
                            "required": ["source_id", "quote"],
                        },
                    },
                    "explanation": {"type": "STRING"},
                },
                "required": ["statement_id", "verdict", "quotes", "explanation"],
            },
        }
    },
    "required": ["results"],
}

SUPPORT_SYSTEM = """You are a meticulous fact-checker. For each STATEMENT, judge it ONLY against the SOURCES listed for it.
Never use outside knowledge, even if you believe the statement is true or false.

Verdicts:
- supported: the sources state it (or something that clearly entails it), including the specific names, numbers and dates.
- partly_supported: the sources back part of it, but some detail (a number, date, attribution, or degree) is missing or different.
- contradicted: a source states something incompatible with it.
- not_addressed: the sources do not speak to it.

For every verdict except not_addressed, give 1-3 quotes. Each quote must be copied character-for-character from the
source text (one or two sentences, under 300 characters), with the source's ID. In "explanation", say in one or two
plain sentences what matches and what doesn't. Return one result per statement, using its statement_id.
"""


def _normalize(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def source_text(source: Dict[str, Any]) -> str:
    """Everything a quote may legitimately come from: title plus body text."""
    return f"{source.get('title') or ''}\n{source.get('text') or ''}"


def build_support_prompt(statements: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> str:
    """statements: [{id, text, source_ids}]. Only sources referenced by some statement are included."""
    needed = {sid for st in statements for sid in st["source_ids"]}
    lines = ["SOURCES:"]
    for s in sources:
        if s["id"] in needed:
            label = s.get("outlet") or ("Claim ledger" if s.get("kind") == "claim" else "Source")
            lines.append(f"[{s['id']}] {label}: {source_text(s).strip()}")
    lines += ["", "STATEMENTS:"]
    lines += [f"{st['id']} (check against {', '.join(st['source_ids'])}): {st['text']}" for st in statements]
    return "\n".join(lines)


def verify_quotes(results: List[Dict[str, Any]], statements: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Keep only quotes found verbatim (whitespace/quote-style insensitive) in an allowed source.

    Returns {statement_id: {verdict, quotes, explanation, rejected_quotes}}. A quoted verdict left with no
    valid quote becomes "unverifiable"; statements the model skipped become "not_checked".
    """
    texts = {s["id"]: _normalize(source_text(s)) for s in sources}
    allowed = {st["id"]: set(st["source_ids"]) for st in statements}
    by_id = {r.get("statement_id"): r for r in results}
    checked: Dict[str, Dict[str, Any]] = {}
    for st in statements:
        r = by_id.get(st["id"])
        if not r or r.get("verdict") not in VERDICTS:
            checked[st["id"]] = {"verdict": "not_checked", "quotes": [], "explanation": "The AI returned no usable result for this line.", "rejected_quotes": 0}
            continue
        good, rejected = [], 0
        for q in r.get("quotes") or []:
            sid, quote = q.get("source_id"), _normalize(q.get("quote", "").strip(" .\"'…"))
            if sid in allowed[st["id"]] and len(quote) >= 12 and quote in texts.get(sid, ""):
                good.append({"source_id": sid, "quote": q["quote"].strip()})
            else:
                rejected += 1
        verdict, explanation = r["verdict"], r.get("explanation", "")
        if verdict in QUOTED_VERDICTS and not good:
            verdict = "unverifiable"
            explanation = f"The AI said '{r['verdict']}' but its quote could not be found in the source, so the verdict was discarded. {explanation}".strip()
        checked[st["id"]] = {"verdict": verdict, "quotes": good, "explanation": explanation, "rejected_quotes": rejected}
    return checked


async def check_statements(statements: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """One batched Gemini call for all statements, then quote verification."""
    if not statements:
        return {}
    data, _ = await gemini.generate_json(
        SUPPORT_SYSTEM, build_support_prompt(statements, sources), SUPPORT_SCHEMA,
        temperature=0.0, cut_off_hint="Try checking fewer lines at once.",
    )
    return verify_quotes(data.get("results") or [], statements, sources)


def summarize(checked: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    counts = {v: 0 for v in VERDICTS + ["unverifiable", "not_checked"]}
    for c in checked.values():
        counts[c["verdict"]] += 1
    return counts


DISAGREEMENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "disagreements": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "issue": {"type": "STRING"},
                    "side_a": {"type": "OBJECT", "properties": {"source_id": {"type": "STRING"}, "quote": {"type": "STRING"}}, "required": ["source_id", "quote"]},
                    "side_b": {"type": "OBJECT", "properties": {"source_id": {"type": "STRING"}, "quote": {"type": "STRING"}}, "required": ["source_id", "quote"]},
                    "explanation": {"type": "STRING"},
                },
                "required": ["issue", "side_a", "side_b", "explanation"],
            },
        }
    },
    "required": ["disagreements"],
}

DISAGREEMENT_SYSTEM = """You compare news reports about the same event and find where they factually DISAGREE.
Only report genuine incompatibilities in facts: different numbers, dates, places, casualty counts, who did what,
who said what, or one report denying what another asserts. Differences in emphasis, tone or what is left out are
NOT disagreements. If the reports agree, return an empty list; never invent a conflict.

For each disagreement give a short "issue" (e.g. "Number of tankers halted"), one quote from each side copied
character-for-character from that report (one or two sentences, under 300 characters), and a one-sentence
"explanation" of exactly what conflicts. The two sides must come from different reports. Report at most 6.
"""


def _verified_side(side: Dict[str, Any], texts: Dict[str, str]) -> bool:
    quote = _normalize((side or {}).get("quote", "").strip(" .\"'…"))
    return len(quote) >= 12 and quote in texts.get((side or {}).get("source_id"), "")


async def find_disagreements(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One Gemini call over the reports; keep only disagreements whose both quotes are found verbatim."""
    if len(sources) < 2:
        return []
    prompt = "REPORTS:\n" + "\n".join(f"[{s['id']}] {s.get('outlet', '')}: {source_text(s).strip()}" for s in sources)
    data, _ = await gemini.generate_json(DISAGREEMENT_SYSTEM, prompt, DISAGREEMENT_SCHEMA, temperature=0.0)
    texts = {s["id"]: _normalize(source_text(s)) for s in sources}
    by_id = {s["id"]: s for s in sources}
    found = []
    for d in data.get("disagreements") or []:
        a, b = d.get("side_a") or {}, d.get("side_b") or {}
        if a.get("source_id") == b.get("source_id") or not (_verified_side(a, texts) and _verified_side(b, texts)):
            continue
        found.append({
            "issue": d.get("issue", "Disagreement"),
            "explanation": d.get("explanation", ""),
            "side_a": {"source_id": a["source_id"], "quote": a["quote"].strip(), **{k: by_id[a["source_id"]].get(k) for k in ("outlet", "title", "url")}},
            "side_b": {"source_id": b["source_id"], "quote": b["quote"].strip(), **{k: by_id[b["source_id"]].get(k) for k in ("outlet", "title", "url")}},
        })
    return found


EXTRACT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "claims": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"line_id": {"type": "STRING"}, "text": {"type": "STRING"}},
                "required": ["line_id", "text"],
            },
        }
    },
    "required": ["claims"],
}

EXTRACT_SYSTEM = """You turn narration lines into a fact-checking list. For each LINE, write the specific, checkable
factual claims it makes: numbers, dates, places, named people or organisations, who did or said what. One claim per
fact, as a short standalone sentence that keeps the line's exact figures and names (resolve "it"/"they" to the noun).
Skip opinions, framing, rhetorical questions and anything not checkable. Use the line's line_id. At most 25 claims.
"""
MAX_EXTRACTED_CLAIMS = 25


def _similar(a: str, b: str) -> bool:
    from app.services.clusterer import compute_headline_similarity, tokenize_title
    return _normalize(a) == _normalize(b) or compute_headline_similarity(tokenize_title(a), tokenize_title(b)) >= 0.8


async def extract_claims(lines: List[Dict[str, Any]], existing: List[str]) -> List[Dict[str, Any]]:
    """lines: [{id, text}]. Returns [{line_id, text}] for new claims, deduplicated against `existing` and each other."""
    if not lines:
        return []
    prompt = "LINES:\n" + "\n".join(f"{ln['id']}: {ln['text']}" for ln in lines)
    data, _ = await gemini.generate_json(EXTRACT_SYSTEM, prompt, EXTRACT_SCHEMA, temperature=0.0)
    valid_ids = {ln["id"] for ln in lines}
    kept: List[Dict[str, Any]] = []
    for c in data.get("claims") or []:
        text = " ".join((c.get("text") or "").split())[:1000]
        if c.get("line_id") not in valid_ids or len(text) < 8:
            continue
        if any(_similar(text, t) for t in existing) or any(_similar(text, k["text"]) for k in kept):
            continue
        kept.append({"line_id": c["line_id"], "text": text})
        if len(kept) >= MAX_EXTRACTED_CLAIMS:
            break
    return kept


def generate_archive_url(url: str) -> str:
    """Generate permanent web archive URL fallback (Wayback Machine)."""
    cleaned = (url or "").strip()
    if not cleaned:
        return ""
    if cleaned.startswith(("https://web.archive.org/", "http://web.archive.org/", "https://archive.today/", "https://archive.is/")):
        return cleaned
    return f"https://web.archive.org/web/*/{cleaned}"


def extract_numerical_metrics(text: str) -> List[Dict[str, Any]]:
    """Extract checkable numeric metrics: currency, percentages, military/casualty counts, and key quantities."""
    if not text:
        return []
    metrics: List[Dict[str, Any]] = []

    # Currency amounts: $4.5B, €100m, £50,000, Rs 500 crore
    for m in re.finditer(r"[\$€£¥]\s?\d+(?:[.,]\d+)?(?:\s?(?:billion|million|trillion|crore|lakh|[bmk]))?", text, re.IGNORECASE):
        metrics.append({"kind": "currency", "raw": m.group(0).strip()})

    # Percentages: 15%, 3.5 percent
    for m in re.finditer(r"\b\d+(?:[.,]\d+)?\s*(?:%|percent\b)", text, re.IGNORECASE):
        metrics.append({"kind": "percentage", "raw": m.group(0).strip()})

    # Quantity with military / casualty / maritime unit
    units = (
        "troops|soldiers|sailors|warships|tanks|aircraft|vessels|missiles|"
        "dead|killed|fatalities|casualties|wounded|detained|hostages|civilians|km|miles|tons|barrels"
    )
    for m in re.finditer(rf"\b\d+(?:[.,]\d+)?\s*(?:{units})\b", text, re.IGNORECASE):
        metrics.append({"kind": "quantity", "raw": m.group(0).strip()})

    # Standalone cardinal numbers (excluding 4-digit years 1900-2099)
    for m in re.finditer(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b", text):
        raw = m.group(0).strip()
        if re.fullmatch(r"(?:19|20)\d{2}", raw):
            continue
        if not any(raw in m_item["raw"] for m_item in metrics):
            metrics.append({"kind": "number", "raw": raw})

    return metrics


def check_numerical_consistency(statement: str, source_texts: List[str]) -> Dict[str, Any]:
    """Check whether numerical metrics in a statement appear in any supporting source text.
    
    Returns:
      {
        'checked': True,
        'metrics_found': [...],
        'unverified_metrics': [...],
        'is_consistent': bool,
        'warning': Optional[str]
      }
    """
    metrics = extract_numerical_metrics(statement)
    if not metrics:
        return {
            "checked": False,
            "metrics_found": [],
            "unverified_metrics": [],
            "is_consistent": True,
            "warning": None,
        }

    combined_sources = " ".join(source_texts or [])
    norm_source = _normalize(combined_sources)
    unverified: List[Dict[str, Any]] = []

    for item in metrics:
        raw = item["raw"]
        norm_raw = _normalize(raw)
        # Check raw string or plain number representation
        plain_digits = re.sub(r"[^\d.]", "", raw)
        found = (norm_raw in norm_source) or (plain_digits and plain_digits in norm_source)
        if not found:
            unverified.append(item)

    is_consistent = len(unverified) == 0
    warning = None
    if not is_consistent:
        unverified_str = ", ".join(f"'{u['raw']}'" for u in unverified)
        warning = f"Metrics {unverified_str} not corroborated by cited sources."

    return {
        "checked": True,
        "metrics_found": metrics,
        "unverified_metrics": unverified,
        "is_consistent": is_consistent,
        "warning": warning,
    }


EPISTEMIC_LEVELS = [
    "empirical_event",
    "official_attribution",
    "unattributed_rumor",
    "analysis_or_opinion",
]


def classify_epistemic_stance(text: str) -> Dict[str, Any]:
    """Classify the epistemic certainty of a claim (reported speech vs empirical fact vs rumor).
    
    Prevents presenting belligerent or official claims as uncontested physical reality.
    """
    t = (text or "").strip()
    if not t:
        return {
            "level": "empirical_event",
            "attributed_to": None,
            "editorial_guidance": "Empty claim statement.",
        }

    # 1. Check rumors / unverified internet circulating claims
    rumor_patterns = [
        r"\b(?:unconfirmed reports?|reports? circulating|sources? claim|sources? say|rumors? suggest|"
        r"social media (?:clips?|posts?|videos?)|unverified (?:footage|claims?|reports?)|allegedly|purportedly)\b"
    ]
    for pat in rumor_patterns:
        if re.search(pat, t, re.IGNORECASE):
            return {
                "level": "unattributed_rumor",
                "attributed_to": None,
                "editorial_guidance": "Unattributed rumor: independent corroboration or physical evidence required before recording.",
            }

    # 2. Check opinion / speculative analytical projections
    opinion_patterns = [
        r"\b(?:analysts? (?:believe|argue|estimate|predict)|experts? (?:warn|suggest)|"
        r"likely to|could lead to|may indicate|signals? a potential|speculation)\b"
    ]
    for pat in opinion_patterns:
        if re.search(pat, t, re.IGNORECASE):
            return {
                "level": "analysis_or_opinion",
                "attributed_to": None,
                "editorial_guidance": "Analytical projection or opinion: frame as assessment rather than established historical fact.",
            }

    # 3. Check official attribution
    # Pattern A: "According to X, ..." or "As per X, ..."
    m_acc = re.search(r"\b(?:according to|as per)\s+([^,.;]{2,50})", t, re.IGNORECASE)
    if m_acc:
        actor = m_acc.group(1).strip()
        return {
            "level": "official_attribution",
            "attributed_to": actor,
            "editorial_guidance": f"Attributed statement: narrate as claimed by {actor}, not uncontested physical reality.",
        }

    # Pattern B: "[Actor] claimed/stated/asserted..."
    m_state = re.search(
        r"\b([A-Z][A-Za-z0-9\s\.-]{2,40}?)\s+(?:claims?|claimed|states?|stated|alleg(?:es?|ed)|asserts?|asserted|announced|insisted|threatened|denies|denied)\b",
        t,
    )
    if m_state:
        actor = m_state.group(1).strip()
        if actor.lower() not in {"this", "that", "which", "there", "it"}:
            return {
                "level": "official_attribution",
                "attributed_to": actor,
                "editorial_guidance": f"Attributed statement: narrate as claimed by {actor}, not uncontested physical reality.",
            }

    # Pattern C: spokesperson / officials said
    m_spox = re.search(
        r"\b((?:[A-Za-z\s]+)?(?:spokesperson|officials?|ministry|military|command))\s+(?:said|stated|reported)\b",
        t,
        re.IGNORECASE,
    )
    if m_spox:
        actor = m_spox.group(1).strip().title()
        return {
            "level": "official_attribution",
            "attributed_to": actor,
            "editorial_guidance": f"Attributed statement: narrate as claimed by {actor}, not uncontested physical reality.",
        }

    # 4. Default: Empirical event
    return {
        "level": "empirical_event",
        "attributed_to": None,
        "editorial_guidance": "Empirical observation or direct event description.",
    }


def crosscheck_claim_against_articles(claim_text: str, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cross-examine a claim against all articles ingested in a crisis cluster.
    
    Identifies multi-outlet consensus, conflicting reports, denials, or silence.
    """
    from app.services.clusterer import tokenize_title
    c_text = (claim_text or "").strip()
    c_tokens = tokenize_title(c_text)
    claim_metrics = extract_numerical_metrics(c_text)

    supporting = []
    disputing = []
    silent_ids = []

    for art in articles or []:
        art_id = art.get("id") or str(id(art))
        outlet = art.get("outlet") or art.get("source_id") or "Unknown Outlet"
        title = art.get("title") or ""
        summary = art.get("summary") or ""
        full_text = art.get("text") or ""
        combined = f"{title} {summary} {full_text}"
        norm_combined = _normalize(combined)

        if not norm_combined or not c_tokens:
            silent_ids.append(art_id)
            continue

        art_tokens = tokenize_title(f"{title} {summary}")
        # If body text exists, also consider its tokens
        if full_text:
            art_tokens = art_tokens.union(tokenize_title(full_text[:1000]))

        intersection = c_tokens.intersection(art_tokens)
        overlap_ratio = len(intersection) / max(1, len(c_tokens))

        # Check denial/refutation keywords
        has_denial = bool(
            re.search(
                r"\b(?:denies|denied|refutes?|refuted|disputes?|disputed|untrue|false|fabricated|hoax|no evidence)\b",
                norm_combined,
            )
        )

        # Check metric discrepancies
        art_metrics = extract_numerical_metrics(combined)
        metric_conflict = False
        if claim_metrics:
            for cm in claim_metrics:
                if cm["kind"] == "quantity":
                    for am in art_metrics:
                        if am["kind"] == "quantity" and am["raw"] != cm["raw"]:
                            c_unit = re.sub(r"[\d,\.]", "", cm["raw"]).strip()
                            a_unit = re.sub(r"[\d,\.]", "", am["raw"]).strip()
                            if c_unit and c_unit == a_unit:
                                metric_conflict = True

        # Relevant article threshold: at least 2 tokens matched and ratio >= 0.25 (or 1 token if claim is short)
        is_relevant = (len(intersection) >= 2 and overlap_ratio >= 0.25) or (len(c_tokens) <= 2 and len(intersection) >= 1)

        if is_relevant:
            entry = {
                "id": art_id,
                "title": title,
                "outlet": outlet,
                "url": art.get("url"),
                "overlap_ratio": round(overlap_ratio, 2),
                "matched_terms": list(intersection)[:5],
            }
            if has_denial or metric_conflict:
                entry["reason"] = "Denial/refutation reported" if has_denial else "Conflicting metric reported"
                disputing.append(entry)
            else:
                supporting.append(entry)
        else:
            silent_ids.append(art_id)

    # Determine consensus status
    if len(disputing) > 0:
        status = "disputed"
        summary = f"Disputed: {len(disputing)} outlet(s) report denials or conflicting details while {len(supporting)} support."
    elif len(supporting) >= 3:
        status = "broad_consensus"
        summary = f"Broad consensus: corroborated across {len(supporting)} independent articles in cluster."
    elif len(supporting) == 2:
        status = "corroborated"
        summary = f"Corroborated: reported by {len(supporting)} outlets in cluster."
    elif len(supporting) == 1:
        status = "isolated_claim"
        summary = f"Isolated claim: reported by only 1 outlet ({supporting[0]['outlet']}) in cluster."
    else:
        status = "unaddressed"
        summary = "Unaddressed: claim not mentioned in current cluster articles."

    return {
        "status": status,
        "summary": summary,
        "supporting": supporting,
        "disputing": disputing,
        "silent_count": len(silent_ids),
        "total_checked": len(articles or []),
    }


def evaluate_source_governance_risk(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate whether corroborating sources are dominated by state-controlled media."""
    if not sources:
        return {"risk_level": "none", "state_controlled_count": 0, "total_sources": 0, "warning": None}

    total = len(sources)
    state_controlled = [s for s in sources if s.get("governance_type") == "state_controlled"]
    state_count = len(state_controlled)

    if state_count == total and total > 0:
        return {
            "risk_level": "high",
            "state_controlled_count": state_count,
            "total_sources": total,
            "warning": "Solely state-controlled media: all corroborating sources are state-directed. Attribute explicitly in video script.",
        }
    elif state_count > 0:
        return {
            "risk_level": "mixed",
            "state_controlled_count": state_count,
            "total_sources": total,
            "warning": f"Includes {state_count} state-controlled source(s). Verify against commercial wires or independent monitors.",
        }

    return {
        "risk_level": "low",
        "state_controlled_count": 0,
        "total_sources": total,
        "warning": None,
    }


REVISION_PATTERNS = [
    r"\b(?:revised down|revised the|lowered the|retracted|corrected|earlier reports? (?:of|claiming)|initially reported|clarified that|amended)\b",
    r"\b(?:official toll (?:reduced|lowered)|death toll revised)\b",
]


def detect_superseded_claim(
    claim_text: str,
    claim_time: Any,
    articles: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Detect if later reporting in the cluster revised, corrected, or retracted an earlier claim."""
    from app.services.clusterer import tokenize_title
    c_tokens = tokenize_title(claim_text)
    if not c_tokens:
        return {"is_superseded": False, "superseding_article": None, "warning": None}

    for art in articles or []:
        pub = art.get("published_at")
        # If claim has a timestamp and article has a timestamp, ensure article is newer
        if claim_time and pub and hasattr(pub, "__lt__") and hasattr(claim_time, "__lt__"):
            try:
                if pub <= claim_time:
                    continue
            except TypeError:
                pass

        text = f"{art.get('title', '')} {art.get('summary', '')} {art.get('text', '')}"
        norm = _normalize(text)
        art_tokens = tokenize_title(f"{art.get('title', '')} {art.get('summary', '')}")

        # Check topic relevance (at least 2 shared keywords)
        if len(c_tokens.intersection(art_tokens)) < 2:
            continue

        has_revision = any(re.search(pat, norm, re.IGNORECASE) for pat in REVISION_PATTERNS)
        if has_revision:
            outlet = art.get("outlet", "Wire")
            return {
                "is_superseded": True,
                "superseding_article": {
                    "id": art.get("id"),
                    "title": art.get("title"),
                    "outlet": outlet,
                    "url": art.get("url"),
                },
                "warning": f"Later update from [{outlet}] reports a revision or retraction: '{art.get('title')}'",
            }

    return {"is_superseded": False, "superseding_article": None, "warning": None}





