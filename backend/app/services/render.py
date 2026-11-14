"""Render a watchable draft animatic from a production package.

The production package (:mod:`app.services.production`) is the source of truth: it already knows which
beats made the timeline, how long each one runs and what it cites. This module turns that manifest into
pixels and sound — one 1920x1080 card per included shot, optional narration audio, and an H.264/AAC MP4
assembled by ffmpeg.

Everything is deterministic and offline. Text is drawn into the cards with Pillow rather than ffmpeg
filters, because the ffmpeg builds we can rely on do not ship ``drawtext`` or ``subtitles``. Blocked
``[NEEDS SOURCE]`` beats never enter the render, matching the timeline/captions behaviour of Phase 3.
"""
from __future__ import annotations

import functools
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services.production import format_clock, format_runtime
from app.services.scriptwriter import NEEDS_SOURCE

WIDTH = 1920
HEIGHT = 1080
FPS = 30
MARGIN = 110
CARD_TOP = 290
CARD_BOTTOM = 760

BG = (15, 23, 42)          # slate-900
PANEL = (2, 6, 23)         # slate-950
RULE = (30, 41, 59)        # slate-800
TEXT = (241, 245, 249)     # slate-100
MUTED = (148, 163, 184)    # slate-400
DIM = (100, 116, 139)      # slate-500
ACCENT = (34, 211, 238)    # cyan-400
AMBER = (251, 191, 36)     # amber-400
PURPLE = (192, 132, 252)   # purple-400

KIND_COLORS = {
    "fact": ACCENT,
    "analysis": PURPLE,
    "transition": MUTED,
}

# Prefer the fonts that ship with macOS, then common Linux fallbacks. Pillow's bundled default is the
# last resort so a skeleton render still works on a bare machine.
FONT_CANDIDATES = {
    "regular": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ],
    "bold": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
    "mono": [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ],
}

INSTALL_HINT = (
    "Rendering needs ffmpeg and Pillow. Install ffmpeg (for example `brew install ffmpeg` on macOS) "
    "and Pillow (`pip install 'pillow>=10.0.0'`) in the backend environment, then restart."
)


class RenderError(Exception):
    """Base class for render problems the router turns into HTTP responses."""


class RenderUnavailable(RenderError):
    """ffmpeg or Pillow is missing from this machine."""

    def __init__(self, missing: List[str]):
        self.missing = missing
        super().__init__(f"Missing render dependency: {', '.join(missing)}")


class NothingToRender(RenderError):
    """Every beat is blocked on a missing source, or the script has no timed beats."""


class RenderFailed(RenderError):
    """ffmpeg was available but the encode failed."""

    def __init__(self, log: str):
        self.log = log
        super().__init__("ffmpeg could not assemble the preview.")


def toolchain_status() -> Dict[str, Any]:
    """Report whether the render toolchain is usable, without importing Pillow globally."""
    ffmpeg = shutil.which("ffmpeg")
    try:
        from PIL import Image  # noqa: F401
        pillow = True
    except Exception:  # pragma: no cover - depends on the environment
        pillow = False
    missing = []
    if not ffmpeg:
        missing.append("ffmpeg")
    if not pillow:
        missing.append("Pillow")
    return {"available": not missing, "ffmpeg": ffmpeg, "pillow": pillow, "missing": missing}


def renderable_shots(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Timeline beats that can actually be drawn: included and longer than zero seconds."""
    return [
        shot for shot in package.get("shots") or []
        if shot.get("included_in_timeline") and (shot.get("duration_seconds") or 0) > 0
    ]


@functools.lru_cache(maxsize=None)
def _font_path(role: str) -> Optional[str]:
    for candidate in FONT_CANDIDATES.get(role, FONT_CANDIDATES["regular"]):
        if Path(candidate).exists():
            return candidate
    return None


@functools.lru_cache(maxsize=None)
def _font(role: str, size: int):
    """Load a font by role, falling back to whatever Pillow can provide."""
    from PIL import ImageFont

    path = _font_path(role)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:  # pragma: no cover - corrupt font file
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 has no size argument
        return ImageFont.load_default()


def _clean_text(text: str) -> str:
    """Collapse whitespace and remove the inline NEEDS SOURCE marker."""
    cleaned = (text or "").replace(NEEDS_SOURCE, " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def _wrap_text(text: str, font, max_width: int) -> List[str]:
    """Greedy word wrap measured with the actual font; never returns an empty list."""
    words = _clean_text(text).split()
    if not words:
        return [""]
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and font.getlength(candidate) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _fit_narration(text: str, max_width: int, max_height: int) -> Tuple[Any, List[str], int]:
    """Pick the largest font size whose wrapped lines fit the body area."""
    for size in (66, 60, 54, 48, 42, 36, 30):
        font = _font("regular", size)
        line_height = int(size * 1.35)
        lines = _wrap_text(text, font, max_width)
        if len(lines) * line_height <= max_height:
            return font, lines, line_height
    font = _font("regular", 30)
    return font, _wrap_text(text, font, max_width), int(30 * 1.35)


def _rounded_rect(draw, box: Tuple[int, int, int, int], radius: int, fill) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _pill(draw, x: int, y: int, label: str, color, *, font) -> int:
    """Draw a rounded kind badge and return the x position after it."""
    pad_x, pad_y = 18, 8
    width = int(font.getlength(label)) + pad_x * 2
    height = 46
    _rounded_rect(draw, (x, y, x + width, y + height), radius=10, fill=color + (28,))
    draw.text((x + pad_x, y + pad_y), label.upper(), font=font, fill=color)
    return x + width


def _citation_label(citation: Dict[str, Any]) -> str:
    """Compact card-side citation label; unknown IDs and state media stay visible."""
    if not citation.get("found"):
        return f"{citation.get('id')} (unknown)"
    label = citation.get("id") or "?"
    if citation.get("outlet"):
        label = f"{label} · {citation['outlet']}"
    if citation.get("governance_type") == "state_controlled":
        label += " *"
    return label


def _draw_shot_card(shot: Dict[str, Any], path: Path, *, total_shots: int, total_seconds: float) -> None:
    """Draw one 16:9 dark-slate card summarising a shot."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image, "RGBA")

    kind_color = KIND_COLORS.get(shot.get("kind") or "fact", ACCENT)
    # Thin coloured rail makes the act kind legible even in a thumbnail strip.
    draw.rectangle((0, 0, 14, HEIGHT), fill=kind_color)

    mono_small = _font("mono", 26)
    mono_tiny = _font("mono", 22)
    bold_act = _font("bold", 30)
    bold_shot = _font("bold", 46)
    bold_pill = _font("bold", 24)
    body_font = _font("regular", 30)

    # Header: act on the left, shot timecode on the right.
    act_label = _clean_text(shot.get("act_title") or "Act").upper()
    act_font = bold_act
    while act_font.getlength(act_label) > 1150 and len(act_label) > 12:
        act_label = act_label[:-2]
        act_font = _font("bold", max(20, int(act_font.size) - 2))
    draw.text((MARGIN, 88), act_label, font=act_font, fill=MUTED)

    timecode = f"{shot.get('start_timecode') or '--:--:--'}  –  {shot.get('end_timecode') or '--:--:--'}"
    timecode_width = mono_small.getlength(timecode)
    draw.text((WIDTH - MARGIN - timecode_width, 92), timecode, font=mono_small, fill=ACCENT)

    draw.line((MARGIN, 150, WIDTH - MARGIN, 150), fill=RULE, width=2)

    # Shot number and kind badge.
    shot_label = f"SHOT {int(shot.get('shot_number') or 0):02d}"
    draw.text((MARGIN, 185), shot_label, font=bold_shot, fill=TEXT)
    shot_width = bold_shot.getlength(shot_label)
    duration = float(shot.get("duration_seconds") or 0)
    meta = f"of {total_shots:02d}  ·  {duration:.1f}s"
    draw.text((MARGIN + shot_width + 24, 202), meta, font=mono_small, fill=DIM)

    pill_label = f"{shot.get('kind') or 'fact'}"
    pill_font = bold_pill
    pill_x = WIDTH - MARGIN - int(pill_font.getlength(pill_label.upper())) - 36
    _pill(draw, pill_x, 188, pill_label, kind_color, font=pill_font)

    # Narration body, vertically centred in its band.
    body_width = WIDTH - MARGIN * 2
    body_font, lines, line_height = _fit_narration(
        shot.get("narration") or "", body_width, CARD_BOTTOM - CARD_TOP
    )
    text_height = len(lines) * line_height
    y = CARD_TOP + max(0, (CARD_BOTTOM - CARD_TOP - text_height) // 2)
    for line in lines:
        draw.text((MARGIN, y), line, font=body_font, fill=TEXT)
        y += line_height

    draw.line((MARGIN, 792, WIDTH - MARGIN, 792), fill=RULE, width=2)

    # B-roll cue.
    draw.text((MARGIN, 820), "B-ROLL", font=_font("bold", 24), fill=AMBER)
    broll = _clean_text(shot.get("broll") or "") or "No B-roll cue"
    broll_lines = _wrap_text(broll, body_font, body_width - 190)
    for i, line in enumerate(broll_lines[:2]):
        draw.text((MARGIN + 160, 816 + i * 36), line, font=body_font, fill=TEXT if shoot_has_broll(shot) else DIM)

    # Sources / claims attached to this beat.
    draw.text((MARGIN, 906), "SOURCES", font=_font("bold", 24), fill=MUTED)
    citations = shot.get("citations") or []
    if citations:
        citation_text = "   ·   ".join(_citation_label(c) for c in citations)
        citation_lines = _wrap_text(citation_text, mono_tiny, body_width - 190)
        for i, line in enumerate(citation_lines[:2]):
            draw.text((MARGIN + 160, 904 + i * 32), line, font=mono_tiny, fill=MUTED)
    else:
        draw.text((MARGIN + 160, 904), "No citations attached", font=mono_tiny, fill=DIM)

    if any(c.get("governance_type") == "state_controlled" for c in citations):
        draw.text(
            (MARGIN, 970),
            "* State-controlled source — attribute explicitly on screen and in narration.",
            font=_font("regular", 24),
            fill=AMBER,
        )

    # Progress rail for a quick sense of place in the draft.
    bar_x, bar_y, bar_w, bar_h = MARGIN, 1022, WIDTH - MARGIN * 2, 8
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=4, fill=RULE)
    ratio = min(1.0, max(0.0, float(shot.get("end_seconds") or 0) / total_seconds)) if total_seconds else 0.0
    if ratio > 0:
        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + max(bar_h, int(bar_w * ratio)), bar_y + bar_h),
            radius=4,
            fill=ACCENT,
        )

    footer = f"GLOBAL PULSE STUDIO · DRAFT ANIMATIC · {format_clock(shot.get('start_seconds') or 0)}"
    draw.text((MARGIN, 1042), footer, font=mono_tiny, fill=DIM)
    runtime = f"runtime {format_runtime(total_seconds)}"
    draw.text((WIDTH - MARGIN - mono_tiny.getlength(runtime), 1042), runtime, font=mono_tiny, fill=DIM)

    image.save(path, format="PNG", optimize=True)


def shoot_has_broll(shot: Dict[str, Any]) -> bool:
    """True when the beat carries a real B-roll cue (keeps placeholder styling honest)."""
    return bool(_clean_text(shot.get("broll") or ""))


shot_has_broll = shoot_has_broll


def build_cards(package: Dict[str, Any], out_dir: Path) -> List[Dict[str, Any]]:
    """Draw one PNG per renderable shot and return the card plan."""
    shots = renderable_shots(package)
    if not shots:
        raise NothingToRender(
            "Nothing to render: every beat is blocked on a missing source or the script has no timed beats."
        )
    total_seconds = sum(float(s.get("duration_seconds") or 0) for s in shots)
    total_shots = int(package.get("total_shots") or len(shots))
    cards: List[Dict[str, Any]] = []
    for shot in shots:
        path = Path(out_dir) / f"shot-{int(shot.get('shot_number') or 0):03d}.png"
        _draw_shot_card(shot, path, total_shots=total_shots, total_seconds=total_seconds)
        cards.append({
            "shot_number": shot.get("shot_number"),
            "duration_seconds": float(shot.get("duration_seconds") or 0),
            "path": path,
        })
    return cards


def _concat_quote(path: Path) -> str:
    """Quote an absolute path for the ffmpeg concat demuxer."""
    return "'" + str(path).replace("'", "'\\''") + "'"


def render_animatic(
    package: Dict[str, Any],
    *,
    audio_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Assemble the draft MP4. Returns the encoded bytes plus a small manifest.

    ``audio_bytes`` is an optional WAV from Gemini TTS. Without it the video is rendered against a silent
    stereo track so the visual draft still plays, and the caller can report ``silent`` narration.
    """
    status = toolchain_status()
    if not status["available"]:
        raise RenderUnavailable(status["missing"])

    shots = renderable_shots(package)
    if not shots:
        raise NothingToRender(
            "Nothing to render: every beat is blocked on a missing source or the script has no timed beats."
        )
    total_seconds = round(sum(float(s.get("duration_seconds") or 0) for s in shots), 3)
    if total_seconds <= 0:
        raise NothingToRender("Nothing to render: the timed shots have zero duration.")

    with tempfile.TemporaryDirectory(prefix="gps-render-") as tmp:
        tmp_dir = Path(tmp)
        cards = build_cards(package, tmp_dir)

        concat_path = tmp_dir / "timeline.txt"
        lines: List[str] = []
        for card in cards:
            lines.append(f"file {_concat_quote(card['path'])}")
            lines.append(f"duration {card['duration_seconds']:.3f}")
        # The concat demuxer needs the last file repeated so the final shot holds on screen.
        lines.append(f"file {_concat_quote(cards[-1]['path'])}")
        concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        audio_path: Optional[Path] = None
        if audio_bytes:
            audio_path = tmp_dir / "narration.wav"
            audio_path.write_bytes(audio_bytes)

        out_path = tmp_dir / "preview.mp4"
        cmd = [
            status["ffmpeg"], "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
        ]
        if audio_path:
            cmd += ["-i", str(audio_path)]
        else:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono"]
        cmd += [
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k",
            "-af", "apad",
            "-t", f"{total_seconds:.3f}",
            "-movflags", "+faststart",
            str(out_path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RenderFailed(str(exc)) from exc
        if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            log = (proc.stderr or proc.stdout or "").strip()
            raise RenderFailed(log[-1200:] or f"ffmpeg exited with status {proc.returncode}.")

        video = out_path.read_bytes()

    return {
        "video": video,
        "duration_seconds": total_seconds,
        "duration_timecode": format_runtime(total_seconds),
        "shots": len(cards),
        "narration_mode": "tts" if audio_bytes else "silent",
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
    }
