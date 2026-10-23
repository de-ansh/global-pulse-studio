"""Tests for the grounded narration-script pipeline (no network: Gemini is mocked)."""
import json
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import httpx
import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import gemini, scriptwriter

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


def _article(title, days_ago=0, outlet="Wire"):
    return SimpleNamespace(
        title=title, summary=f"{title} summary", clean_text="", url=f"https://x.example/{days_ago}",
        published_at=NOW - timedelta(days=days_ago), source=SimpleNamespace(name=outlet), source_id="w", entities={},
    )


def _claim(text, status="unverified"):
    return SimpleNamespace(text=text, status=status, note=None, evidence=[])


def test_build_sources_numbers_articles_newest_first_then_claims():
    sources = scriptwriter.build_sources([_article("Old", 3), _article("New", 0)], [_claim("Tanker seized", "confirmed")])
    assert [(s["id"], s.get("title") or s["text"]) for s in sources] == [("S1", "New"), ("S2", "Old"), ("C1", "Tanker seized")]
    assert sources[2]["status"] == "confirmed"


def test_build_prompt_includes_sources_structure_and_budget():
    sources = scriptwriter.build_sources([_article("Iran seizes tanker")], [_claim("Rumour", "false")])
    prompt = scriptwriter.build_prompt("Hormuz", "Deterrence", 10, sources, [{"title": "Act I", "timecode": "00:00", "narrative_focus": "hook"}])
    assert "about 1500 words" in prompt
    assert "- Act I (00:00): hook" in prompt
    assert "[S1] Wire, 2026-10-20: Iran seizes tanker" in prompt
    assert "[C1] CLAIM, status=false: Rumour" in prompt


def _script(*beats):
    return {"title": "T", "logline": "L", "acts": [{"title": "Act I", "timecode": "00:00", "beats": list(beats)}], "open_questions": []}


def test_verify_flags_fake_uncited_needs_source_and_false_claims():
    sources = scriptwriter.build_sources([_article("A")], [_claim("Bad", "false")])
    content = _script(
        {"kind": "fact", "narration": "Good fact.", "citations": ["S1"]},
        {"kind": "fact", "narration": "Invented citation.", "citations": ["S9"]},
        {"kind": "fact", "narration": "No citation.", "citations": []},
        {"kind": "fact", "narration": "Casualties rose. [NEEDS SOURCE]", "citations": []},
        {"kind": "fact", "narration": "Repeats a false claim.", "citations": ["C1"]},
        {"kind": "analysis", "narration": "This matters because stakes.", "citations": []},
    )
    stats = scriptwriter.verify_script(content, sources, 1)
    issues = [b["issues"] for b in content["acts"][0]["beats"]]
    assert issues[0] == [] and issues[5] == []
    assert "Cites sources that don't exist: S9" in issues[1][0]
    assert issues[2] == ["Factual beat with no valid citation"]
    assert "Needs a source" in issues[3]
    assert "false/disputed" in issues[4][0]
    assert stats == {
        "beats": 6, "fact_beats": 5, "fact_beats_verified": 1, "beats_flagged": 4,
        "needs_source": 1, "word_count": sum(len(b["narration"].split()) for b in content["acts"][0]["beats"]),
        "target_words": 150,
    }


def _gemini_payload(content, finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": json.dumps(content)}]}}]}


def test_parse_gemini_response_errors():
    assert gemini.parse_json_response(_gemini_payload(_script()))["title"] == "T"
    with pytest.raises(ValueError, match="cut off"):
        gemini.parse_json_response(_gemini_payload(_script(), finish="MAX_TOKENS"))
    with pytest.raises(ValueError, match="blocked"):
        gemini.parse_json_response({"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(ValueError, match="malformed"):
        gemini.parse_json_response({"candidates": [{"content": {"parts": [{"text": "{not json"}]}}]})


def _mock_gemini(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(gemini.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


@pytest.mark.asyncio
async def test_call_gemini_sends_key_in_header_and_schema(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "secret-key")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-test")
    seen = {}

    def handler(request):
        seen["url"], seen["key"], seen["body"] = str(request.url), request.headers.get("x-goog-api-key"), json.loads(request.content)
        return httpx.Response(200, json=_gemini_payload(_script()))

    _mock_gemini(monkeypatch, handler)
    content, model = await scriptwriter.call_gemini("sys", "prompt")
    assert content["title"] == "T" and model == "gemini-test"
    assert seen["url"].endswith("/models/gemini-test:generateContent") and "secret-key" not in seen["url"]
    assert seen["key"] == "secret-key"
    assert seen["body"]["generationConfig"]["responseSchema"] == scriptwriter.SCRIPT_SCHEMA


@pytest.mark.asyncio
async def test_call_gemini_maps_errors(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    with pytest.raises(HTTPException) as e:
        await scriptwriter.call_gemini("s", "p")
    assert e.value.status_code == 503

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "k")
    _mock_gemini(monkeypatch, lambda r: httpx.Response(404, json={"error": {"message": "models/x is not found"}}))
    with pytest.raises(HTTPException) as e:
        await scriptwriter.call_gemini("s", "p")
    assert e.value.status_code == 502 and "not found" in e.value.detail and "GPS_GEMINI_MODEL" in e.value.detail


@pytest.mark.asyncio
async def test_generate_script_endpoint_end_to_end(client: AsyncClient, db_session, monkeypatch):
    from app.models.source import Source, Article
    from app.models.event import EventCluster

    db_session.add_all([
        Source(id="w", name="Wire", feed_url="https://w.example/rss"),
        EventCluster(id="evt_s", headline="Tanker seized"),
    ])
    await db_session.flush()
    db_session.add(Article(id="a1", source_id="w", cluster_id="evt_s", canonical_hash="a1", title="Iran seizes tanker",
                           url="https://w.example/1", published_at=NOW))
    await db_session.commit()

    pid = (await client.post("/api/projects", json={"title": "Hormuz", "cluster_id": "evt_s", "target_duration_mins": 2})).json()["id"]
    assert (await client.get(f"/api/projects/{pid}/script")).status_code == 404

    captured = {}

    async def fake_call(system, prompt):
        captured["prompt"] = prompt
        return _script(
            {"kind": "fact", "narration": "Iran seized a tanker.", "citations": ["S1"], "broll": "Map"},
            {"kind": "fact", "narration": "It was the third this year.", "citations": ["S7"]},
        ), "gemini-test"

    monkeypatch.setattr(scriptwriter, "call_gemini", fake_call)
    fetched = []

    async def fake_full_text(articles):
        fetched.extend(a.id for a in articles)
        return 0

    from app.routers import projects as projects_router
    monkeypatch.setattr(projects_router, "ensure_full_text", fake_full_text)
    res = await client.post(f"/api/projects/{pid}/script/generate")
    assert fetched == ["a1"]  # full text is fetched for the event's articles before writing
    assert res.status_code == 200
    body = res.json()
    assert "[S1] Wire" in captured["prompt"]
    assert body["stats"]["fact_beats_verified"] == 1 and body["stats"]["beats_flagged"] == 1
    assert body["content"]["acts"][0]["beats"][1]["issues"] == ["Cites sources that don't exist: S7", "Factual beat with no valid citation"]

    # regenerating replaces, not duplicates; export carries script + flags + source list
    assert (await client.post(f"/api/projects/{pid}/script/generate")).status_code == 200
    md = (await client.get(f"/api/projects/{pid}/export")).text
    assert "## V. Narration Script" in md and "Iran seized a tanker. [S1]" in md
    assert "**CHECK:** Cites sources that don't exist: S7" in md
    assert "- [S1] [Iran seizes tanker](https://w.example/1) (Wire, 2026-10-20)" in md

    # deleting the project removes its script
    assert (await client.delete(f"/api/projects/{pid}")).status_code == 204
    from sqlalchemy import select, func
    from app.models.project import Script
    assert (await db_session.execute(select(func.count()).select_from(Script))).scalar() == 0


@pytest.mark.asyncio
async def test_generate_script_without_sources_is_422(client: AsyncClient):
    pid = (await client.post("/api/projects", json={"title": "Empty"})).json()["id"]
    res = await client.post(f"/api/projects/{pid}/script/generate")
    assert res.status_code == 422 and "Nothing to cite" in res.json()["detail"]
