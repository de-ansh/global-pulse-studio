"""Grounded narration-script writer: numbered sources in, cited beats out, citations verified in code.

Pipeline: build_sources -> build_prompt -> call_gemini (one structured-JSON call) -> verify_script.
Only call_gemini touches the network; everything else is deterministic and unit-tested.
"""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from app.services import gemini
WORDS_PER_MINUTE = 150  # typical documentary narration pace
MAX_ARTICLE_SOURCES = 40
MAX_SOURCE_CHARS = 5000  # per article; full text when fetched, else the feed summary
NEEDS_SOURCE = "[NEEDS SOURCE]"

# Gemini responseSchema (OpenAPI subset). "kind" lets hooks/transitions exist without citations
# while every "fact" beat must cite.
SCRIPT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "logline": {"type": "STRING"},
        "acts": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "timecode": {"type": "STRING"},
                    "beats": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "kind": {"type": "STRING", "enum": ["fact", "analysis", "transition"]},
                                "narration": {"type": "STRING"},
                                "citations": {"type": "ARRAY", "items": {"type": "STRING"}},
                                "broll": {"type": "STRING"},
                            },
                            "required": ["kind", "narration", "citations"],
                        },
                    },
                },
                "required": ["title", "timecode", "beats"],
            },
        },
        "open_questions": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["title", "logline", "acts", "open_questions"],
}

SYSTEM_INSTRUCTION = f"""You write narration scripts for long-form geopolitical video essays.
You are given numbered SOURCES: news reports [S#] and the creator's verified-claim ledger [C#].

Hard rules:
1. Use ONLY facts found in the SOURCES. Never add names, numbers, dates, quotes or events from your own knowledge.
2. Every beat of kind "fact" must list the IDs of the sources that support it in "citations". Cite only IDs that exist.
3. If the story needs a fact the sources do not contain, write the sentence and end it with {NEEDS_SOURCE}, with no citation for that fact. Also add it to "open_questions".
4. Claims with status "false" may only be mentioned as false, and "disputed" ones only as disputed, citing the claim.
   Claims with status "unverified" and single-outlet reports must be attributed ("according to ...", "reports say").
5. Beats of kind "analysis" (interpretation, framing, stakes) and "transition" need no citation but must not introduce new facts.
6. When sources disagree, say so and cite both sides.
7. Write for the ear: short sentences, concrete language, no headings inside narration. "broll" describes the visual for the beat.
"""


def build_sources(articles: List[Any], claims: List[Any]) -> List[Dict[str, Any]]:
    """Number the project's evidence: cluster articles as S1..Sn (newest first), ledger claims as C1..Cn."""
    sources: List[Dict[str, Any]] = []
    for i, art in enumerate(sorted(articles, key=lambda a: a.published_at, reverse=True)[:MAX_ARTICLE_SOURCES], 1):
        full = (art.entities or {}).get("fulltext") == "ok"
        text = art.clean_text if full else (art.summary or art.clean_text or "")
        sources.append({
            "id": f"S{i}",
            "kind": "article",
            "title": art.title,
            "outlet": art.source.name if getattr(art, "source", None) else art.source_id,
            "url": art.url,
            "published_at": art.published_at.strftime("%Y-%m-%d"),
            "text": text[:MAX_SOURCE_CHARS],
            "full_text": full,
        })
    for i, claim in enumerate(claims, 1):
        sources.append({
            "id": f"C{i}",
            "kind": "claim",
            "text": claim.text,
            "status": claim.status,
            "note": claim.note or "",
            "evidence": [e.get("url") for e in (claim.evidence or [])],
        })
    return sources


def build_prompt(
    topic: str,
    angle: Optional[str],
    target_minutes: int,
    sources: List[Dict[str, Any]],
    outline_acts: List[Dict[str, Any]],
) -> str:
    """User prompt: the brief, the act structure to follow, and the numbered sources."""
    target_words = target_minutes * WORDS_PER_MINUTE
    lines = [
        f"TOPIC: {topic}",
        f"ANGLE: {angle or 'General explainer'} (a framing lens only; it never overrides the sources)",
        f"LENGTH: about {target_words} words of narration in total (~{target_minutes} minutes at {WORDS_PER_MINUTE} wpm).",
        "",
    ]
    if outline_acts:
        lines.append("ACT STRUCTURE (keep these titles and timecodes):")
        lines += [f"- {a.get('title')} ({a.get('timecode')}): {a.get('narrative_focus', '')}" for a in outline_acts]
    else:
        lines.append("ACT STRUCTURE: five acts (hook, context, escalation, stakes, open ending) with timecodes.")
    lines += ["", "SOURCES:"]
    for s in sources:
        if s["kind"] == "article":
            lines.append(f"[{s['id']}] {s['outlet']}, {s['published_at']}: {s['title']}\n    {s['text']}")
        else:
            note = f" (creator note: {s['note']})" if s["note"] else ""
            lines.append(f"[{s['id']}] CLAIM, status={s['status']}: {s['text']}{note}")
    return "\n".join(lines)


def verify_script(content: Dict[str, Any], sources: List[Dict[str, Any]], target_minutes: int) -> Dict[str, Any]:
    """Check every beat's citations against the real source IDs; annotate beats with issues and return counts.

    The model is told the rules, but this is what enforces them: unknown IDs, uncited facts and
    reliance on false/disputed claims are flagged on the beat itself.
    """
    by_id = {s["id"]: s for s in sources}
    beats = fact_beats = fact_ok = needs_source = flagged = words = 0
    for act in content.get("acts", []):
        for beat in act.get("beats", []):
            beats += 1
            narration = beat.get("narration", "")
            words += len(narration.split())
            cites = beat.get("citations") or []
            issues = []
            unknown = [c for c in cites if c not in by_id]
            if unknown:
                issues.append(f"Cites sources that don't exist: {', '.join(unknown)}")
            if NEEDS_SOURCE in narration:
                needs_source += 1
                issues.append("Needs a source")
            if beat.get("kind") == "fact":
                fact_beats += 1
                if not [c for c in cites if c in by_id]:
                    issues.append("Factual beat with no valid citation")
                shaky = [c for c in cites if by_id.get(c, {}).get("status") in ("false", "disputed")]
                if shaky:
                    issues.append(f"Relies on a false/disputed claim ({', '.join(shaky)}); make sure it's framed as such")
                if not issues:
                    fact_ok += 1
            beat["issues"] = issues
            flagged += bool(issues)
    return {
        "beats": beats,
        "fact_beats": fact_beats,
        "fact_beats_verified": fact_ok,
        "beats_flagged": flagged,
        "needs_source": needs_source,
        "word_count": words,
        "target_words": target_minutes * WORDS_PER_MINUTE,
    }


async def call_gemini(system: str, prompt: str) -> Tuple[Dict[str, Any], str]:
    """One structured-output Gemini call for the script. Returns (script content, model id)."""
    content, model = await gemini.generate_json(
        system, prompt, SCRIPT_SCHEMA, temperature=0.4, cut_off_hint="Try a shorter target duration."
    )
    if not isinstance(content.get("acts"), list):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gemini's response is missing the act structure.")
    return content, model
