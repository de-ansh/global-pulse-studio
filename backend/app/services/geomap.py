"""Render a static locator map (1920x1080 PNG) of a story's chokepoints and state actors.

Offline and dependency-free: the basemap is Natural Earth 110m land (public domain), drawn with Pillow in an
equirectangular projection scaled by cos(latitude) so mid-latitude regions do not look stretched.
"""
from __future__ import annotations

import functools
import io
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

from app.services.render import ACCENT, AMBER, HEIGHT, MUTED, TEXT, WIDTH, _font

LAND_PATH = Path(__file__).resolve().parent.parent / "data" / "ne_110m_land.geojson"
CREDIT = "Basemap: Natural Earth (public domain)"

SEA = (8, 13, 30)
LAND = (39, 52, 74)
COAST = (71, 85, 105)       # slate-600
HALO = (2, 6, 23)          # slate-950
TITLE_BAND = 120
FOOTER = 80

# Keyed by the canonical values of scorer.CHOKEPOINTS (lat, lon).
CHOKEPOINT_COORDS: Dict[str, Tuple[float, float]] = {
    "Strait of Malacca": (2.5, 101.5),
    "Strait of Hormuz": (26.6, 56.3),
    "Taiwan Strait": (24.5, 119.5),
    "Bab el-Mandeb": (12.6, 43.3),
    "Suez Canal": (30.6, 32.3),
    "Panama Canal": (9.1, -79.7),
    "Bosphorus / Turkish Straits": (41.1, 29.05),
    "Turkish Straits": (40.2, 26.4),
    "Suwalki Gap": (54.1, 23.0),
    "GIUK Gap": (63.0, -15.0),
    "Siliguri Corridor (Chicken's Neck)": (26.7, 88.4),
    "Andaman & Nicobar Gateway (Malacca Approach)": (11.6, 92.7),
    "Ten Degree Channel": (10.0, 92.5),
    "Six Degree Channel (Great Channel)": (6.0, 94.0),
    "Line of Actual Control (LAC)": (34.0, 78.5),
    "Line of Control (LoC)": (34.3, 74.3),
    "Galwan Valley": (34.75, 78.2),
    "Pangong Tso": (33.75, 78.65),
    "Doklam Plateau": (27.3, 89.0),
    "Chabahar Port Corridor": (25.3, 60.6),
    "Indian Ocean Region (IOR)": (-10.0, 75.0),
    "Palk Strait": (10.0, 79.6),
    "India-Middle East-Europe Economic Corridor (IMEC)": (25.0, 45.0),
    "International North-South Transport Corridor (INSTC)": (37.0, 52.0),
}

# Keyed by the canonical values of scorer.ACTORS -> (map label, lat, lon). State agencies collapse onto their
# country so one country gets one marker. Anchors are capitals except where noted.
ACTOR_PLACES: Dict[str, Tuple[str, float, float]] = {
    "US DoD": ("United States", 38.9, -77.0),
    "Russia": ("Russia", 55.75, 37.6),
    "China": ("China", 39.9, 116.4),
    "China (PLA)": ("China", 39.9, 116.4),
    "Taiwan": ("Taiwan", 25.03, 121.56),
    "Ukraine": ("Ukraine", 50.45, 30.52),
    "Iran": ("Iran", 35.7, 51.4),
    "Israel": ("Israel", 31.5, 34.9),  # country anchor, not a capital
    "North Korea": ("North Korea", 39.03, 125.75),
    "South Korea": ("South Korea", 37.57, 126.98),
    "India": ("India", 28.61, 77.21),
    "ISRO": ("India", 28.61, 77.21),
    "DRDO": ("India", 28.61, 77.21),
    "R&AW": ("India", 28.61, 77.21),
    "India MEA": ("India", 28.61, 77.21),
    "Pakistan": ("Pakistan", 33.68, 73.05),
    "Ansar Allah (Houthis)": ("Yemen (Houthis)", 15.37, 44.19),
    "Hezbollah": ("Lebanon (Hezbollah)", 33.85, 35.86),
}

# Multinational bodies have no single location, so they never get a marker.
ALLIANCES = {"NATO", "UNSC", "EU", "OPEC+", "BRICS", "Quad (India-US-Japan-Australia)", "SCO", "ASEAN"}


def map_places(chokepoints: List[str], actors: List[str]) -> List[Tuple[str, float, float, str]]:
    """(label, lat, lon, kind) for every mappable chokepoint and actor, deduplicated by label."""
    places: Dict[str, Tuple[str, float, float, str]] = {}
    for name in chokepoints:
        if name in CHOKEPOINT_COORDS:
            places[name] = (name, *CHOKEPOINT_COORDS[name], "chokepoint")
    for name in actors:
        if name in ACTOR_PLACES:
            label, lat, lon = ACTOR_PLACES[name]
            places.setdefault(label, (label, lat, lon, "actor"))
    return list(places.values())


@functools.lru_cache(maxsize=1)
def _land_polygons() -> List[List[List[Tuple[float, float]]]]:
    data = json.loads(LAND_PATH.read_text())
    polygons = []
    for feature in data["features"]:
        geom = feature["geometry"]
        parts = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        polygons.extend([[tuple(pt) for pt in ring] for ring in poly] for poly in parts)
    return polygons


def _viewport(places) -> Tuple[float, float, float, float]:
    """Centre lat/lon and pixels-per-degree that fit every place with padding, at 16:9."""
    lats = [p[1] for p in places]
    lons = [p[2] for p in places]
    clat = (min(lats) + max(lats)) / 2
    clon = (min(lons) + max(lons)) / 2
    xfactor = max(math.cos(math.radians(clat)), 0.2)
    # A lone point or tight cluster still shows ~30 degrees of context.
    span_lon = max((max(lons) - min(lons)) * xfactor, 30.0) * 1.35
    map_h = HEIGHT - TITLE_BAND - FOOTER
    span_lat = max(max(lats) - min(lats), 30.0 * map_h / WIDTH) * 1.35
    scale = min(WIDTH / span_lon, map_h / span_lat)
    return clat, clon, scale, xfactor


def render_map(title: str, chokepoints: List[str], actors: List[str]) -> bytes:
    """PNG bytes of the locator map. Raises ValueError when nothing in the story can be placed."""
    from PIL import Image, ImageDraw

    places = map_places(chokepoints, actors)
    if not places:
        raise ValueError("No mappable chokepoints or countries were detected for this project.")

    clat, clon, scale, xfactor = _viewport(places)
    cy = (TITLE_BAND + HEIGHT - FOOTER) / 2  # centre of the area between title band and legend

    def project(lon: float, lat: float) -> Tuple[float, float]:
        return WIDTH / 2 + (lon - clon) * xfactor * scale, cy - (lat - clat) * scale

    img = Image.new("RGB", (WIDTH, HEIGHT), SEA)
    draw = ImageDraw.Draw(img)
    for poly in _land_polygons():
        exterior, *holes = poly
        draw.polygon([project(*pt) for pt in exterior], fill=LAND, outline=COAST)
        for hole in holes:  # inland seas such as the Caspian
            draw.polygon([project(*pt) for pt in hole], fill=SEA, outline=COAST)

    # Markers first, so no marker is ever painted over a label.
    r = 11
    points = [(label, *project(lon, lat), kind) for label, lat, lon, kind in places]
    taken: List[Tuple[float, float, float, float]] = []
    for _, x, y, kind in points:
        color = AMBER if kind == "chokepoint" else ACCENT
        if kind == "chokepoint":
            draw.polygon([(x, y - r - 3), (x + r + 3, y), (x, y + r + 3), (x - r - 3, y)], fill=color, outline=HALO)
        else:
            draw.ellipse([x - r, y - r, x + r, y + r], fill=color, outline=HALO, width=3)
        taken.append((x - r - 3, y - r - 3, x + r + 3, y + r + 3))

    def free(box) -> bool:
        return (
            20 <= box[0] and box[2] <= WIDTH - 20 and TITLE_BAND <= box[1] and box[3] <= HEIGHT - FOOTER
            and not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in taken)
        )

    label_font = _font("bold", 30)
    for label, x, y, _ in points:
        left, top, right, bottom = draw.textbbox((0, 0), label, font=label_font)
        w, h = right - left, bottom - top
        # Try right then left of the marker, stepping further away vertically until a slot is free.
        candidates = [
            (lx, y - h / 2 + dy * (h + 8))
            for dy in (0, 1, -1, 2, -2, 3, -3)
            for lx in (x + r + 10, x - r - 10 - w)
        ]
        lx, ly = next((c for c in candidates if free((c[0], c[1], c[0] + w, c[1] + h))), candidates[0])
        taken.append((lx, ly, lx + w, ly + h))
        draw.text((lx, ly - top), label, font=label_font, fill=TEXT, stroke_width=4, stroke_fill=HALO)

    # Title band and credit.
    draw.rectangle([0, 0, WIDTH, TITLE_BAND], fill=HALO)
    draw.text((60, 34), title[:90], font=_font("bold", 48), fill=TEXT)
    small = _font("regular", 22)
    draw.text((WIDTH - 60, HEIGHT - 30), CREDIT, font=small, fill=MUTED, anchor="rs", stroke_width=3, stroke_fill=HALO)
    legend_y = HEIGHT - 52
    draw.polygon([(60, legend_y - 9), (69, legend_y), (60, legend_y + 9), (51, legend_y)], fill=AMBER)
    draw.text((80, legend_y), "Chokepoint", font=small, fill=TEXT, anchor="lm", stroke_width=3, stroke_fill=HALO)
    draw.ellipse([231, legend_y - 9, 249, legend_y + 9], fill=ACCENT)
    draw.text((260, legend_y), "Country / actor", font=small, fill=TEXT, anchor="lm", stroke_width=3, stroke_fill=HALO)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
