"""Turn a verified narration script into a production package: shot list, timings, captions and manifest.

Everything here is deterministic and offline: the shot list, runtime estimates and SRT/VTT captions are
derived from the stored script content and its numbered sources. Only the optional narration audio is
synthesised, by :mod:`app.services.gemini` (TTS), and that is the caller's decision.

Timing is an estimate: Gemini TTS does not return word-level timestamps, so each beat is paced from its
word count at ``WORDS_PER_MINUTE``. Editors should treat the timecodes as a starting point.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.scriptwriter import NEEDS_SOURCE, WORDS_PER_MINUTE

GOVERNANCE_STATE_CONTROLLED = "state_controlled"


def _words(text: str) -> int:
    """Count narration words, ignoring the inline NEEDS SOURCE marker."""
    return len(re.sub(re.escape(NEEDS_SOURCE), " ", text or "").split())


def _seconds_for_words(words: int) -> float:
    """Narration duration for a word count at the configured pace."""
    return round(words / float(WORDS_PER_MINUTE) * 60.0, 3)


def format_clock(seconds: float, *, millis: bool = False, separator: str = ":") -> str:
    """Format seconds as HH:MM:SS (or HH:MM:SS[.,]mmm for captions)."""
    total = max(0.0, float(seconds))
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    secs = total % 60
    if millis:
        whole = int(secs)
        ms = int(round((secs - whole) * 1000))
        if ms == 1000:
            whole += 1
            ms = 0
        return f"{hours:02d}:{minutes:02d}:{whole:02d}{separator}{ms:03d}"
    return f"{hours:02d}:{minutes:02d}:{int(secs):02d}"


def format_runtime(seconds: float) -> str:
    """Human runtime: MM:SS under an hour, else HH:MM:SS."""
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _clean_caption(text: str) -> str:
    """One caption line: marker removed, whitespace collapsed."""
    cleaned = (text or "").replace(NEEDS_SOURCE, " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def _resolve_citations(ids: List[str], by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resolve citation IDs against the script's numbered sources; unknown IDs stay visible as flags."""
    resolved: List[Dict[str, Any]] = []
    for raw in ids or []:
        source = by_id.get(raw)
        if not source:
            resolved.append({"id": raw, "found": False, "kind": "unknown"})
            continue
        resolved.append({
            "id": raw,
            "found": True,
            "kind": source.get("kind"),
            "title": source.get("title"),
            "outlet": source.get("outlet"),
            "url": source.get("url"),
            "published_at": source.get("published_at"),
            "status": source.get("status"),
            "governance_type": source.get("governance_type"),
            "text": source.get("text") if source.get("kind") == "claim" else None,
        })
    return resolved


def _caption_label(citations: List[Dict[str, Any]]) -> str:
    """Compact citation label for Markdown/CSV cells; '*' marks a state-controlled source."""
    parts = []
    for c in citations:
        label = c["id"]
        if c.get("found") and c.get("outlet"):
            label = f"{label} ({c['outlet']})"
        if c.get("governance_type") == GOVERNANCE_STATE_CONTROLLED:
            label += "*"
        parts.append(label)
    return ", ".join(parts)


def _shotlist_markdown(package: Dict[str, Any]) -> str:
    """Editor-facing Markdown shot list with a timeline and a blocked-shots section."""
    lines = [
        f"# Shot List — {package['title']}",
        "",
        package["logline"] or "",
        "",
        f"- Shots: {package['total_shots']} total, {package['included_shots']} in timeline, "
        f"{package['skipped_shots']} blocked",
        f"- Estimated runtime: {package['narration']['estimated_runtime_timecode']} "
        f"({package['narration']['word_count']} words at {package['narration']['words_per_minute']} wpm)",
        f"- Voice: {package['narration'].get('voice') or 'not configured'}",
        f"- Generated: {package['generated_at']}",
    ]
    if package["warnings"]:
        lines.append("")
        lines.append("## Production warnings")
        lines.extend(f"- {w}" for w in package["warnings"])

    lines.extend(["", "## Timeline", "", "| # | Timecode | Act | Kind | Narration | B-roll | Citations |",
                  "|---|---|---|---|---|---|---|"])
    for shot in package["shots"]:
        if not shot["included_in_timeline"]:
            continue
        narration = (shot["narration"] or "").replace("|", "\\|").replace(NEEDS_SOURCE, "").strip()
        broll = (shot["broll"] or "").replace("|", "\\|")
        timecode = f"{shot['start_timecode']}–{shot['end_timecode']}"
        lines.append(
            f"| {shot['shot_number']} | {timecode} | {shot['act_title']} | {shot['kind']} | "
            f"{narration} | {broll} | {_caption_label(shot['citations'])} |"
        )

    blocked = [s for s in package["shots"] if not s["included_in_timeline"]]
    if blocked:
        lines.extend(["", "## Blocked — source needed before recording", ""])
        for shot in blocked:
            lines.append(f"- **Shot {shot['shot_number']}** ({shot['act_title']}): {shot['narration']}")
            if shot["broll"]:
                lines.append(f"  - B-roll: {shot['broll']}")

    if any(c.get("governance_type") == GOVERNANCE_STATE_CONTROLLED for s in package["shots"] for c in s["citations"]):
        lines.extend([
            "",
            "* A citation marked `*` is state-controlled or state-funded: attribute it on screen and in narration.",
        ])
    return "\n".join(lines).strip() + "\n"


def _shotlist_csv(package: Dict[str, Any]) -> str:
    """Spreadsheet-friendly shot list (one row per beat, blocked beats included)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([
        "shot_number", "act", "act_timecode", "beat", "kind", "included_in_timeline",
        "start_timecode", "end_timecode", "duration_seconds", "narration", "broll",
        "citations", "needs_source",
    ])
    for shot in package["shots"]:
        writer.writerow([
            shot["shot_number"], shot["act_title"], shot["act_timecode"], shot["beat_index"],
            shot["kind"], "yes" if shot["included_in_timeline"] else "no",
            shot["start_timecode"] or "", shot["end_timecode"] or "",
            shot["duration_seconds"] if shot["duration_seconds"] is not None else "",
            _clean_caption(shot["narration"]), shot["broll"] or "",
            _caption_label(shot["citations"]), "yes" if shot["needs_source"] else "no",
        ])
    return buf.getvalue()


def _captions(package: Dict[str, Any], fmt: str) -> str:
    """Render SRT or VTT from the beats included in the timeline."""
    stamp = (lambda s: format_clock(s, millis=True, separator=",")) if fmt == "srt" else (
        lambda s: format_clock(s, millis=True, separator=".")
    )
    blocks: List[str] = []
    index = 1
    for shot in package["shots"]:
        if not shot["included_in_timeline"]:
            continue
        text = _clean_caption(shot["narration"])
        if not text:
            continue
        blocks.append(
            f"{index}\n{stamp(shot['start_seconds'])} --> {stamp(shot['end_seconds'])}\n{text}"
        )
        index += 1
    body = "\n\n".join(blocks)
    if fmt == "vtt":
        return "WEBVTT\n\n" + body + ("\n" if body else "")
    return body + ("\n" if body else "")


def build_production_package(script: Any, *, voice: Optional[str] = None) -> Dict[str, Any]:
    """Build the full production package from a stored ``Script`` row.

    ``script`` only needs ``content`` and ``sources`` attributes, which keeps this testable without a DB.
    """
    content = getattr(script, "content", None) or {}
    sources = getattr(script, "sources", None) or []
    by_id = {s.get("id"): s for s in sources if isinstance(s, dict) and s.get("id")}

    shots: List[Dict[str, Any]] = []
    warnings: List[str] = []
    cursor = 0.0
    word_count = 0
    included = 0
    skipped = 0
    needs_source_count = 0
    shot_number = 0

    for act_index, act in enumerate(content.get("acts", []) or []):
        act_title = act.get("title") or f"Act {act_index + 1}"
        act_timecode = act.get("timecode") or ""
        for beat_index, beat in enumerate(act.get("beats", []) or []):
            shot_number += 1
            narration = beat.get("narration") or ""
            citations = _resolve_citations(beat.get("citations") or [], by_id)
            needs_source = NEEDS_SOURCE in narration
            included_in_timeline = not needs_source

            unknown = [c["id"] for c in citations if not c.get("found")]
            state_controlled = [c["id"] for c in citations if c.get("governance_type") == GOVERNANCE_STATE_CONTROLLED]
            if unknown:
                warnings.append(
                    f"Shot {shot_number} cites unknown source ID(s): {', '.join(unknown)}."
                )
            if state_controlled:
                warnings.append(
                    f"Shot {shot_number} cites state-controlled source(s) {', '.join(state_controlled)}; "
                    "attribute them explicitly in narration and on screen."
                )

            shot: Dict[str, Any] = {
                "shot_number": shot_number,
                "act_index": act_index + 1,
                "act_title": act_title,
                "act_timecode": act_timecode,
                "beat_index": beat_index + 1,
                "kind": beat.get("kind") or "fact",
                "narration": narration,
                "broll": beat.get("broll"),
                "citations": citations,
                "needs_source": needs_source,
                "included_in_timeline": included_in_timeline,
                "start_seconds": None,
                "end_seconds": None,
                "duration_seconds": None,
                "start_timecode": None,
                "end_timecode": None,
            }

            if needs_source:
                skipped += 1
                needs_source_count += 1
                warnings.append(
                    f"Shot {shot_number} is blocked on a missing source; it has no timing, narration audio "
                    "or captions until the fact is sourced."
                )
            else:
                words = _words(narration)
                duration = _seconds_for_words(words)
                shot["duration_seconds"] = duration
                shot["start_seconds"] = round(cursor, 3)
                shot["end_seconds"] = round(cursor + duration, 3)
                shot["start_timecode"] = format_clock(shot["start_seconds"])
                shot["end_timecode"] = format_clock(shot["end_seconds"])
                cursor += duration
                word_count += words
                included += 1

            shots.append(shot)

    if not shots:
        warnings.append("This script has no beats yet. Generate or rewrite the script before production.")

    package: Dict[str, Any] = {
        "project_id": getattr(script, "project_id", None),
        "title": content.get("title") or "Untitled script",
        "logline": content.get("logline") or "",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "narration": {
            "voice": voice,
            "words_per_minute": WORDS_PER_MINUTE,
            "word_count": word_count,
            "estimated_runtime_seconds": round(cursor, 3),
            "estimated_runtime_timecode": format_runtime(cursor),
        },
        "shots": shots,
        "total_shots": len(shots),
        "included_shots": included,
        "skipped_shots": skipped,
        "needs_source_shots": needs_source_count,
        "warnings": warnings,
    }
    package["captions_srt"] = _captions(package, "srt")
    package["captions_vtt"] = _captions(package, "vtt")
    package["shotlist_markdown"] = _shotlist_markdown(package)
    package["shotlist_csv"] = _shotlist_csv(package)
    return package


def narration_text(package: Dict[str, Any]) -> str:
    """The spoken text for TTS: only timeline beats, with the NEEDS SOURCE marker stripped."""
    parts = [
        _clean_caption(shot["narration"])
        for shot in package["shots"]
        if shot["included_in_timeline"]
    ]
    return " ".join(p for p in parts if p)
