"""Timeline export service for professional Non-Linear Editors (NLEs).

Generates frame-accurate edit interchange files from a video production package:
- FCPXML 1.9+ (Apple Final Cut Pro & Blackmagic DaVinci Resolve)
- Premiere Pro XML / FCP 7 xmeml (Adobe Premiere Pro & DaVinci Resolve)
- CMX 3600 EDL (DaVinci Resolve, Avid Media Composer & general NLEs)

Each export places timed shot beats onto the timeline with markers for B-roll cues,
source citations, and governance risk warnings. Blocked [NEEDS SOURCE] beats never
enter the timeline, matching the behavior of Phase 3 and Phase 4.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Any, Dict, List, Optional, Tuple

from app.services.scriptwriter import NEEDS_SOURCE

SUPPORTED_FORMATS = {"fcpxml", "premiere", "xmeml", "edl"}
SUPPORTED_FPS = {24, 25, 30, 60}


class NLEExportError(Exception):
    """Base error for NLE timeline generation failures."""


class NothingToExport(NLEExportError):
    """Raised when every beat is blocked on missing sources or the script has no beats."""


def seconds_to_frames(seconds: float, fps: int = 30) -> int:
    """Convert float seconds to an integer frame count at a given framerate."""
    return max(0, int(round(float(seconds) * fps)))


def frames_to_smpte(frames: int, fps: int = 30) -> str:
    """Format an integer frame count as a non-drop-frame SMPTE timecode (HH:MM:SS:FF)."""
    frames = max(0, int(frames))
    ff = frames % fps
    total_seconds = frames // fps
    ss = total_seconds % 60
    mm = (total_seconds // 60) % 60
    hh = total_seconds // 3600
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def seconds_to_smpte(seconds: float, fps: int = 30) -> str:
    """Convert decimal seconds directly to a non-drop-frame SMPTE timecode."""
    return frames_to_smpte(seconds_to_frames(seconds, fps), fps)


def _clean(text: Optional[str]) -> str:
    """Strip extraneous whitespace and NEEDS SOURCE tags."""
    cleaned = (text or "").replace(NEEDS_SOURCE, " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def _citation_label(c: Dict[str, Any]) -> str:
    """Format citation outlet and governance risk note."""
    cid = c.get("id") or "?"
    if not c.get("found", True):
        return f"{cid} (unknown)"
    outlet = c.get("outlet")
    label = f"{cid} ({outlet})" if outlet else cid
    if c.get("governance_type") == "state_controlled":
        label += " *"
    return label


def _renderable_shots(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract valid timeline beats with positive durations."""
    return [
        shot for shot in package.get("shots") or []
        if shot.get("included_in_timeline") and (shot.get("duration_seconds") or 0) > 0
    ]


def _pretty_xml(elem: ET.Element) -> str:
    """Pretty-print an ElementTree node into clean XML string with standard declaration."""
    rough = ET.tostring(elem, encoding="utf-8")
    reparsed = minidom.parseString(rough)
    return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def export_fcpxml(package: Dict[str, Any], fps: int = 30) -> str:
    """Export the production timeline as Apple Final Cut Pro XML (FCPXML 1.9)."""
    shots = _renderable_shots(package)
    if not shots:
        raise NothingToExport("No valid timed shots to export to FCPXML.")

    title = _clean(package.get("title") or "Global Pulse Studio Documentary")
    total_seconds = sum(float(s.get("duration_seconds") or 0) for s in shots)
    total_frames = seconds_to_frames(total_seconds, fps)

    root = ET.Element("fcpxml", {"version": "1.9"})

    # Resources header
    resources = ET.SubElement(root, "resources")
    ET.SubElement(
        resources,
        "format",
        {
            "id": "r1",
            "name": f"FFVideoFormat1080p{fps}",
            "frameDuration": f"1/{fps}s",
            "width": "1920",
            "height": "1080",
        },
    )

    # Library / Event / Project structure
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", {"name": "Global Pulse Studio"})
    project = ET.SubElement(event, "project", {"name": title})
    sequence = ET.SubElement(
        project,
        "sequence",
        {
            "format": "r1",
            "duration": f"{total_frames}/{fps}s",
            "tcStart": "0s",
            "tcFormat": "NDF",
        },
    )
    spine = ET.SubElement(sequence, "spine")

    cursor_frame = 0
    for shot in shots:
        dur_frames = seconds_to_frames(shot.get("duration_seconds") or 0, fps)
        shot_num = int(shot.get("shot_number") or 0)
        act = _clean(shot.get("act_title") or "Act")
        kind = _clean(shot.get("kind") or "fact")
        shot_label = f"SHOT {shot_num:02d}: {act} ({kind})"

        gap = ET.SubElement(
            spine,
            "gap",
            {
                "name": shot_label,
                "offset": f"{cursor_frame}/{fps}s",
                "duration": f"{dur_frames}/{fps}s",
                "start": "0s",
            },
        )

        # B-roll cue marker
        broll = _clean(shot.get("broll"))
        if broll:
            ET.SubElement(
                gap,
                "marker",
                {
                    "start": "0s",
                    "duration": f"1/{fps}s",
                    "value": f"B-ROLL: {broll}",
                    "note": f"Visual B-roll prompt for Shot {shot_num:02d}",
                },
            )

        # Citations marker
        citations = shot.get("citations") or []
        if citations:
            cit_str = ", ".join(_citation_label(c) for c in citations)
            narration_snippet = _clean(shot.get("narration") or "")[:120]
            ET.SubElement(
                gap,
                "marker",
                {
                    "start": "0s",
                    "duration": f"1/{fps}s",
                    "value": f"SOURCES: {cit_str}",
                    "note": f"Narration: {narration_snippet}",
                },
            )

        cursor_frame += dur_frames

    return _pretty_xml(root)


def export_premiere_xml(package: Dict[str, Any], fps: int = 30) -> str:
    """Export the timeline as Adobe Premiere Pro / FCP 7 XML (xmeml v5)."""
    shots = _renderable_shots(package)
    if not shots:
        raise NothingToExport("No valid timed shots to export to Premiere XML.")

    title = _clean(package.get("title") or "Global Pulse Studio Documentary")
    total_seconds = sum(float(s.get("duration_seconds") or 0) for s in shots)
    total_frames = seconds_to_frames(total_seconds, fps)

    root = ET.Element("xmeml", {"version": "5"})
    seq = ET.SubElement(root, "sequence", {"id": "sequence-1"})
    ET.SubElement(seq, "name").text = title
    ET.SubElement(seq, "duration").text = str(total_frames)

    rate = ET.SubElement(seq, "rate")
    ET.SubElement(rate, "timebase").text = str(fps)
    ET.SubElement(rate, "ntsc").text = "FALSE"

    timecode = ET.SubElement(seq, "timecode")
    tc_rate = ET.SubElement(timecode, "rate")
    ET.SubElement(tc_rate, "timebase").text = str(fps)
    ET.SubElement(tc_rate, "ntsc").text = "FALSE"
    ET.SubElement(timecode, "string").text = "00:00:00:00"
    ET.SubElement(timecode, "frame").text = "0"
    ET.SubElement(timecode, "displayformat").text = "NDF"

    media = ET.SubElement(seq, "media")
    video = ET.SubElement(media, "video")
    v_format = ET.SubElement(video, "format")
    sample = ET.SubElement(v_format, "samplecharacteristics")
    s_rate = ET.SubElement(sample, "rate")
    ET.SubElement(s_rate, "timebase").text = str(fps)
    ET.SubElement(s_rate, "ntsc").text = "FALSE"
    ET.SubElement(sample, "width").text = "1920"
    ET.SubElement(sample, "height").text = "1080"
    ET.SubElement(sample, "pixelaspectratio").text = "square"

    v_track = ET.SubElement(video, "track")

    cursor_frame = 0
    for idx, shot in enumerate(shots, start=1):
        dur_frames = seconds_to_frames(shot.get("duration_seconds") or 0, fps)
        start_frame = cursor_frame
        end_frame = cursor_frame + dur_frames
        shot_num = int(shot.get("shot_number") or idx)
        act = _clean(shot.get("act_title") or "Act")
        kind = _clean(shot.get("kind") or "fact")

        clip = ET.SubElement(v_track, "clipitem", {"id": f"clipitem-{idx}"})
        ET.SubElement(clip, "name").text = f"SHOT {shot_num:02d}: {act} ({kind})"
        ET.SubElement(clip, "duration").text = str(dur_frames)

        c_rate = ET.SubElement(clip, "rate")
        ET.SubElement(c_rate, "timebase").text = str(fps)
        ET.SubElement(c_rate, "ntsc").text = "FALSE"

        ET.SubElement(clip, "start").text = str(start_frame)
        ET.SubElement(clip, "end").text = str(end_frame)
        ET.SubElement(clip, "in").text = "0"
        ET.SubElement(clip, "out").text = str(dur_frames)

        # B-roll marker
        broll = _clean(shot.get("broll"))
        if broll:
            m = ET.SubElement(clip, "marker")
            ET.SubElement(m, "name").text = f"B-ROLL: {broll[:40]}"
            ET.SubElement(m, "comment").text = broll
            ET.SubElement(m, "in").text = "0"
            ET.SubElement(m, "out").text = "-1"

        # Citations marker
        citations = shot.get("citations") or []
        if citations:
            cit_summary = ", ".join(_citation_label(c) for c in citations)
            narration_snippet = _clean(shot.get("narration") or "")
            m2 = ET.SubElement(clip, "marker")
            ET.SubElement(m2, "name").text = f"SOURCES: {cit_summary[:40]}"
            ET.SubElement(m2, "comment").text = f"{cit_summary} | {narration_snippet}"
            ET.SubElement(m2, "in").text = "0"
            ET.SubElement(m2, "out").text = "-1"

        cursor_frame = end_frame

    return _pretty_xml(root)


def export_edl(package: Dict[str, Any], fps: int = 30) -> str:
    """Export the timeline as a standard CMX 3600 Edit Decision List (EDL)."""
    shots = _renderable_shots(package)
    if not shots:
        raise NothingToExport("No valid timed shots to export to CMX 3600 EDL.")

    title = _clean(package.get("title") or "Global Pulse Studio Documentary").upper()[:40]

    lines: List[str] = [
        f"TITLE: {title}",
        "FCM: NON-DROP FRAME",
        "",
    ]

    cursor_frame = 0
    for idx, shot in enumerate(shots, start=1):
        dur_frames = seconds_to_frames(shot.get("duration_seconds") or 0, fps)
        start_frame = cursor_frame
        end_frame = cursor_frame + dur_frames

        src_in = "00:00:00:00"
        src_out = frames_to_smpte(dur_frames, fps)
        rec_in = frames_to_smpte(start_frame, fps)
        rec_out = frames_to_smpte(end_frame, fps)

        # Standard CMX 3600 Event line:
        # Event#  ReelID  Track  Transition  SrcIn  SrcOut  RecIn  RecOut
        lines.append(f"{idx:03d}  AX       V     C        {src_in} {src_out} {rec_in} {rec_out}")

        shot_num = int(shot.get("shot_number") or idx)
        act = _clean(shot.get("act_title") or "Act").upper()
        kind = _clean(shot.get("kind") or "fact").upper()
        lines.append(f"* FROM CLIP NAME: SHOT {shot_num:02d} - {act} ({kind})")

        broll = _clean(shot.get("broll"))
        if broll:
            lines.append(f"* B-ROLL: {broll}")

        citations = shot.get("citations") or []
        if citations:
            lines.append(f"* CITATIONS: {', '.join(_citation_label(c) for c in citations)}")

        narration = _clean(shot.get("narration"))
        if narration:
            lines.append(f"* NARRATION: {narration[:100]}")

        lines.append("")
        cursor_frame = end_frame

    return "\n".join(lines)


def build_nle_export(
    package: Dict[str, Any],
    format: str = "fcpxml",
    fps: int = 30,
) -> Dict[str, Any]:
    """Central generator dispatcher for timeline export interchange formats."""
    fmt = (format or "fcpxml").lower().strip()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported NLE export format '{format}'. Choose from: {', '.join(sorted(SUPPORTED_FORMATS))}")

    if fps not in SUPPORTED_FPS:
        raise ValueError(f"Unsupported framerate {fps} fps. Choose from: {', '.join(map(str, sorted(SUPPORTED_FPS)))}")

    if fmt == "fcpxml":
        return {
            "content": export_fcpxml(package, fps=fps),
            "media_type": "application/xml",
            "extension": "fcpxml",
        }
    elif fmt in {"premiere", "xmeml"}:
        return {
            "content": export_premiere_xml(package, fps=fps),
            "media_type": "application/xml",
            "extension": "xml",
        }
    elif fmt == "edl":
        return {
            "content": export_edl(package, fps=fps),
            "media_type": "text/plain",
            "extension": "edl",
        }
    raise ValueError(f"Unhandled format '{format}'")
