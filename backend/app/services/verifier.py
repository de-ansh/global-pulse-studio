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
