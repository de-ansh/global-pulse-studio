"""Tests for the grounded primary-source finder (Gemini and redirects mocked)."""
import httpx
import pytest

from app.services import sourcefinder

PAYLOAD = {"candidates": [{
    "finishReason": "STOP",
    "content": {"parts": [{"text": "- The ministry confirmed two tankers were halted."}]},
    "groundingMetadata": {
        "groundingChunks": [
            {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AAA", "title": "reuters.com"}},
            {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/BBB", "title": "mea.gov.in"}},
            {"web": {"uri": "javascript:alert(1)", "title": "evil"}},
            {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AAA", "title": "dup"}},
        ],
        "groundingSupports": [
            {"segment": {"text": "The ministry confirmed two tankers were halted."}, "groundingChunkIndices": [1, 0]},
        ],
    },
}]}


def test_grounding_results_uses_search_chunks_with_snippets():
    out = sourcefinder.grounding_results(PAYLOAD)
    assert [r["title"] for r in out] == ["reuters.com", "mea.gov.in"]  # non-web and duplicate links dropped
    assert out[1]["snippet"] == "The ministry confirmed two tankers were halted."
    assert sourcefinder.grounding_results({"candidates": [{}]}) == []


@pytest.mark.parametrize("url,official", [
    ("https://www.mea.gov.in/press.htm", True), ("https://www.state.gov/x", True), ("https://www.nato.int/x", True),
    ("https://news.un.org/x", True), ("https://www.gov.uk/x", True), ("https://www.reuters.com/x", False),
    ("https://governance-news.com/x", False),
])
def test_is_official(url, official):
    assert sourcefinder.is_official(url) is official


@pytest.mark.asyncio
async def test_find_primary_sources_resolves_redirects_and_ranks_official_first(monkeypatch):
    async def fake_request(system, prompt, **kw):
        assert kw["tools"] == [{"google_search": {}}] and "CLAIM: Two tankers were halted" in prompt
        return PAYLOAD, "gemini-test"

    targets = {"AAA": "https://www.reuters.com/world/tankers", "BBB": "https://www.mea.gov.in/press-releases.htm"}

    def handler(request):
        return httpx.Response(302, headers={"location": targets[request.url.path.rsplit("/", 1)[-1]]})

    real = httpx.AsyncClient
    monkeypatch.setattr(sourcefinder.gemini, "request", fake_request)
    monkeypatch.setattr(sourcefinder, "web_client", lambda: real(transport=httpx.MockTransport(handler)))
    out = await sourcefinder.find_primary_sources("Two tankers were halted")
    assert out["summary"].startswith("- The ministry")
    assert [(s["domain"], s["official"], s["resolved"]) for s in out["sources"]] == [
        ("mea.gov.in", True, True), ("reuters.com", False, True),
    ]
    assert out["sources"][0]["url"] == "https://www.mea.gov.in/press-releases.htm"


@pytest.mark.asyncio
async def test_suggest_endpoint(client, monkeypatch):
    async def fake_find(text):
        return {"summary": "s", "sources": [], "model": "m", "text": text}

    monkeypatch.setattr(sourcefinder, "find_primary_sources", fake_find)
    pid = (await client.post("/api/projects", json={"title": "T"})).json()["id"]
    cid = (await client.post(f"/api/projects/{pid}/claims", json={"text": "Two tankers were halted"})).json()["id"]
    res = await client.post(f"/api/projects/{pid}/claims/{cid}/sources/suggest")
    assert res.status_code == 200 and res.json()["text"] == "Two tankers were halted"
    assert (await client.post(f"/api/projects/{pid}/claims/nope/sources/suggest")).status_code == 404
