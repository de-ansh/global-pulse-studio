"""Locator map generator: coordinate coverage, rendering, and staging onto a shot."""
import io
import shutil
from pathlib import Path

import pytest
from httpx import AsyncClient
from PIL import Image

from app.services import geomap
from app.services.scorer import ACTORS, CHOKEPOINTS


@pytest.fixture(autouse=True)
def cleanup_media_uploads():
    yield
    shutil.rmtree(Path("media_uploads"), ignore_errors=True)


def test_every_detected_chokepoint_has_coordinates():
    assert set(CHOKEPOINTS.values()) - set(geomap.CHOKEPOINT_COORDS) == set()


def test_every_actor_is_placed_or_an_alliance():
    assert set(ACTORS.values()) - set(geomap.ACTOR_PLACES) - geomap.ALLIANCES == set()


def test_map_places_drops_alliances_and_merges_agencies():
    places = geomap.map_places(["Strait of Hormuz"], ["NATO", "India", "ISRO", "Iran"])
    assert sorted(p[0] for p in places) == ["India", "Iran", "Strait of Hormuz"]


def test_render_map_is_1080p_png():
    png = geomap.render_map("Hormuz Tensions", ["Strait of Hormuz", "Bab el-Mandeb"], ["Iran", "Israel"])
    with Image.open(io.BytesIO(png)) as img:
        assert img.format == "PNG"
        assert img.size == (1920, 1080)


def test_render_map_without_places_raises():
    with pytest.raises(ValueError):
        geomap.render_map("Summit communique", [], ["NATO", "BRICS"])


@pytest.mark.asyncio
async def test_generate_map_stages_asset_on_shot(client: AsyncClient):
    pid = (await client.post("/api/projects", json={"title": "Iran and the Strait of Hormuz"})).json()["id"]

    res = await client.post(f"/api/projects/{pid}/maps", json={"shot_number": 2})
    assert res.status_code == 200
    asset = res.json()
    assert asset["shot_number"] == 2
    assert asset["content_type"] == "image/png"
    assert (asset["width"], asset["height"]) == (1920, 1080)
    assert asset["source_credit"] == geomap.CREDIT

    # Regenerating replaces the shot's asset rather than stacking a second one.
    await client.post(f"/api/projects/{pid}/maps", json={"shot_number": 2})
    assets = (await client.get(f"/api/projects/{pid}/assets")).json()
    assert [a["shot_number"] for a in assets] == [2]


@pytest.mark.asyncio
async def test_generate_map_without_places_is_422(client: AsyncClient):
    pid = (await client.post("/api/projects", json={"title": "Budget debate in parliament"})).json()["id"]
    res = await client.post(f"/api/projects/{pid}/maps", json={"shot_number": 1})
    assert res.status_code == 422
