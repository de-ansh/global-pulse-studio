"""Health and root endpoint verification."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Ensure health check returns 200 and valid status."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Ensure root metadata endpoint returns platform details."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "Global Pulse Studio"
    assert "/docs" in data["docs_url"]


@pytest.mark.asyncio
async def test_root_serves_html(client: AsyncClient):
    """Ensure browser requests receiving Accept: text/html receive the web dashboard."""
    response = await client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Global Pulse Studio" in response.text



@pytest.mark.asyncio
async def test_basic_auth_when_password_set(client: AsyncClient, monkeypatch):
    """With GPS_AUTH_PASSWORD set, the API needs credentials but the health probe stays open."""
    from app.config import settings
    monkeypatch.setattr(settings, "AUTH_PASSWORD", "s3cret")

    assert (await client.get("/api/health")).status_code == 200
    denied = await client.get("/api/projects")
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"].startswith("Basic")
    assert (await client.get("/api/projects", auth=("admin", "wrong"))).status_code == 401
    assert (await client.get("/api/projects", headers={"Authorization": "Basic !!notbase64"})).status_code == 401
    assert (await client.get("/api/projects", auth=("admin", "s3cret"))).status_code == 200


@pytest.mark.asyncio
async def test_frontend_source_tree_not_served(client: AsyncClient):
    assert (await client.get("/static/package.json")).status_code == 404


@pytest.mark.asyncio
async def test_features_reports_flags_only_and_requires_auth(client: AsyncClient, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "secret-gemini")
    monkeypatch.setattr(settings, "FACTCHECK_API_KEY", "")
    res = await client.get("/api/health/features")
    assert res.json() == {"ai": True, "factcheck": False} and "secret" not in res.text
    monkeypatch.setattr(settings, "AUTH_PASSWORD", "pw")
    assert (await client.get("/api/health/features")).status_code == 401
    assert (await client.get("/api/health")).status_code == 200
