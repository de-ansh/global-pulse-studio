"""Tests for AI evidence checks; the essential guarantee is that unverifiable quotes never yield a verdict."""
import pytest

from app.services import verifier

SOURCES = [
    {"id": "S1", "kind": "article", "outlet": "BBC", "title": "Tanker traffic slows near Hormuz",
     "text": "Shipping traffic through the Strait of Hormuz fell by a third on Monday, port officials said.\nTwo tankers were halted."},
    {"id": "S2", "kind": "article", "outlet": "Al Jazeera", "title": "Iran denies mining",
     "text": "Iran’s navy denied laying any mines in the strait."},
]
STATEMENTS = [
    {"id": "L1", "text": "Traffic through Hormuz fell by a third.", "source_ids": ["S1"]},
    {"id": "L2", "text": "Iran admitted laying mines.", "source_ids": ["S2"]},
    {"id": "L3", "text": "Insurance rates tripled.", "source_ids": ["S1"]},
    {"id": "L4", "text": "Two tankers were halted.", "source_ids": ["S1"]},
    {"id": "L5", "text": "Something skipped.", "source_ids": ["S1"]},
]


def test_build_support_prompt_lists_only_needed_sources_and_scope():
    prompt = verifier.build_support_prompt(STATEMENTS[:1], SOURCES)
    assert "[S1] BBC: Tanker traffic slows near Hormuz" in prompt and "[S2]" not in prompt
    assert "L1 (check against S1): Traffic through Hormuz fell by a third." in prompt


def test_verify_quotes_keeps_real_quotes_and_discards_fabricated_ones():
    results = [
        # real quote, different whitespace/case -> kept
        {"statement_id": "L1", "verdict": "supported", "explanation": "matches",
         "quotes": [{"source_id": "S1", "quote": "shipping traffic through the Strait of   Hormuz fell by a third"}]},
        # curly vs straight apostrophe still matches
        {"statement_id": "L2", "verdict": "contradicted", "explanation": "denied",
         "quotes": [{"source_id": "S2", "quote": "Iran's navy denied laying any mines"}]},
        # fabricated quote -> verdict discarded
        {"statement_id": "L3", "verdict": "supported", "explanation": "says so",
         "quotes": [{"source_id": "S1", "quote": "insurance premiums tripled overnight"}]},
        # real text but from a source this line doesn't cite -> rejected
        {"statement_id": "L4", "verdict": "supported", "explanation": "x",
         "quotes": [{"source_id": "S2", "quote": "Two tankers were halted"}]},
        # L5 missing entirely
    ]
    checked = verifier.verify_quotes(results, STATEMENTS, SOURCES)
    assert checked["L1"]["verdict"] == "supported" and checked["L1"]["rejected_quotes"] == 0
    assert checked["L2"]["verdict"] == "contradicted"
    assert checked["L3"]["verdict"] == "unverifiable" and checked["L3"]["rejected_quotes"] == 1
    assert "could not be found" in checked["L3"]["explanation"]
    assert checked["L4"]["verdict"] == "unverifiable"
    assert checked["L5"]["verdict"] == "not_checked"
    assert verifier.summarize(checked) == {
        "supported": 1, "partly_supported": 0, "contradicted": 1, "not_addressed": 0, "unverifiable": 2, "not_checked": 1,
    }


def test_not_addressed_needs_no_quote_and_tiny_quotes_are_rejected():
    results = [
        {"statement_id": "L3", "verdict": "not_addressed", "explanation": "no mention", "quotes": []},
        {"statement_id": "L1", "verdict": "supported", "explanation": "x", "quotes": [{"source_id": "S1", "quote": "a third"}]},
    ]
    checked = verifier.verify_quotes(results, STATEMENTS[:3], SOURCES)
    assert checked["L3"]["verdict"] == "not_addressed"
    assert checked["L1"]["verdict"] == "unverifiable"  # a 7-char fragment proves nothing


@pytest.mark.asyncio
async def test_check_statements_calls_gemini_once_then_verifies(monkeypatch):
    calls = []

    async def fake_generate(system, prompt, schema, **kw):
        calls.append(prompt)
        return {"results": [{"statement_id": "L1", "verdict": "supported", "explanation": "ok",
                             "quotes": [{"source_id": "S1", "quote": "fell by a third on Monday"}]}]}, "gemini-test"

    monkeypatch.setattr(verifier.gemini, "generate_json", fake_generate)
    checked = await verifier.check_statements(STATEMENTS[:1], SOURCES)
    assert len(calls) == 1 and checked["L1"]["verdict"] == "supported"
    assert await verifier.check_statements([], SOURCES) == {}


async def _project_with_event(client, db_session, monkeypatch):
    from datetime import datetime, timezone, timedelta
    from app.models.source import Source, Article
    from app.models.event import EventCluster
    from app.routers import projects as projects_router

    async def no_fetch(articles):
        return 0

    monkeypatch.setattr(projects_router, "ensure_full_text", no_fetch)
    db_session.add_all([Source(id="bbc", name="BBC", feed_url="https://bbc.example/rss"), EventCluster(id="evt_v", headline="Hormuz")])
    await db_session.flush()
    db_session.add_all([
        Article(id="v1", source_id="bbc", cluster_id="evt_v", canonical_hash="v1", title="Tanker traffic slows near Hormuz",
                summary=SOURCES[0]["text"], url="https://bbc.example/1", published_at=datetime.now(timezone.utc), entities={}),
        Article(id="v2", source_id="bbc", cluster_id="evt_v", canonical_hash="v2", title="Football results",
                summary="The match ended in a draw on Sunday evening in the capital.", url="https://bbc.example/2",
                published_at=datetime.now(timezone.utc) - timedelta(hours=1), entities={}),
    ])
    await db_session.commit()
    return (await client.post("/api/projects", json={"title": "Hormuz", "cluster_id": "evt_v"})).json()["id"]


@pytest.mark.asyncio
async def test_check_claim_endpoint_stores_suggestion_without_changing_verdict(client, db_session, monkeypatch):
    pid = await _project_with_event(client, db_session, monkeypatch)
    claim = (await client.post(f"/api/projects/{pid}/claims", json={"text": "Traffic through Hormuz fell by a third"})).json()
    seen = {}

    async def fake_generate(system, prompt, schema, **kw):
        seen["prompt"] = prompt
        return {"results": [{"statement_id": "claim", "verdict": "supported", "explanation": "BBC reports it",
                             "quotes": [{"source_id": "S1", "quote": "fell by a third on Monday"}]}]}, "gemini-test"

    monkeypatch.setattr(verifier.gemini, "generate_json", fake_generate)
    from app.routers import projects as projects_router
    monkeypatch.setattr(projects_router, "CLAIM_CHECK_MAX_ARTICLES", 1)
    res = await client.post(f"/api/projects/{pid}/claims/{claim['id']}/check")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "unverified"  # suggestion only
    assert body["ai_check"]["verdict"] == "supported" and body["ai_check"]["quotes"][0]["source_id"] == "S1"
    assert body["ai_check"]["sources"][0] == {"id": "S1", "title": "Tanker traffic slows near Hormuz", "outlet": "BBC", "url": "https://bbc.example/1"}
    # with room for one report, the relevant one is chosen over the newer-but-unrelated one
    assert "Tanker traffic" in seen["prompt"] and "Football" not in seen["prompt"]

    # listed claims carry the check; re-running replaces it; deleting the claim removes it
    assert (await client.get(f"/api/projects/{pid}/claims")).json()[0]["ai_check"]["verdict"] == "supported"
    assert (await client.post(f"/api/projects/{pid}/claims/{claim['id']}/check")).status_code == 200
    from sqlalchemy import select, func
    from app.models.project import ClaimCheck
    assert (await db_session.execute(select(func.count()).select_from(ClaimCheck))).scalar() == 1
    assert (await client.delete(f"/api/projects/{pid}/claims/{claim['id']}")).status_code == 204
    db_session.expire_all()
    assert (await db_session.execute(select(func.count()).select_from(ClaimCheck))).scalar() == 0


@pytest.mark.asyncio
async def test_check_claim_without_sources_is_422(client):
    pid = (await client.post("/api/projects", json={"title": "Empty"})).json()["id"]
    cid = (await client.post(f"/api/projects/{pid}/claims", json={"text": "Something"})).json()["id"]
    assert (await client.post(f"/api/projects/{pid}/claims/{cid}/check")).status_code == 422


@pytest.mark.asyncio
async def test_check_script_endpoint_annotates_fact_lines(client, db_session, monkeypatch):
    from app.services import scriptwriter
    pid = await _project_with_event(client, db_session, monkeypatch)

    async def fake_write(system, prompt):
        return {"title": "T", "logline": "L", "open_questions": [], "acts": [{"title": "Act I", "timecode": "0", "beats": [
            {"kind": "fact", "narration": "Traffic fell by a third.", "citations": ["S1"]},
            {"kind": "fact", "narration": "Insurance tripled. [NEEDS SOURCE]", "citations": ["S1"]},
            {"kind": "analysis", "narration": "Why it matters.", "citations": []},
            {"kind": "fact", "narration": "Uncited.", "citations": ["S99"]},
        ]}]}, "gemini-test"

    monkeypatch.setattr(scriptwriter, "call_gemini", fake_write)
    assert (await client.post(f"/api/projects/{pid}/script/check")).status_code == 404
    await client.post(f"/api/projects/{pid}/script/generate")
    seen = {}

    async def fake_generate(system, prompt, schema, **kw):
        seen["prompt"] = prompt
        return {"results": [
            {"statement_id": "L1.1", "verdict": "supported", "explanation": "ok", "quotes": [{"source_id": "S1", "quote": "fell by a third on Monday"}]},
            {"statement_id": "L1.2", "verdict": "supported", "explanation": "invented", "quotes": [{"source_id": "S1", "quote": "insurance tripled overnight"}]},
        ]}, "gemini-test"

    monkeypatch.setattr(verifier.gemini, "generate_json", fake_generate)
    body = (await client.post(f"/api/projects/{pid}/script/check")).json()
    beats = body["content"]["acts"][0]["beats"]
    assert beats[0]["support"]["verdict"] == "supported"
    assert beats[1]["support"]["verdict"] == "unverifiable"  # fabricated quote
    assert "support" not in beats[2] and "support" not in beats[3]  # analysis and invalid-citation lines aren't sent
    assert "L1.2 (check against S1): Insurance tripled." in seen["prompt"] and "[NEEDS SOURCE]" not in seen["prompt"]
    assert body["stats"]["support"]["supported"] == 1 and body["stats"]["support"]["unverifiable"] == 1
    assert body["stats"]["fact_beats"] == 3  # original verification stats are kept
    # persisted
    assert (await client.get(f"/api/projects/{pid}/script")).json()["content"]["acts"][0]["beats"][0]["support"]["verdict"] == "supported"
    md = (await client.get(f"/api/projects/{pid}/export")).text
    assert '> **AI check: supported** (suggestion, not a verdict). ok' in md
    assert '>   "fell by a third on Monday" [S1]' in md
    assert "> **AI check: unverifiable**" in md


@pytest.mark.asyncio
async def test_find_disagreements_keeps_only_double_verified_cross_source_conflicts(monkeypatch):
    async def fake_generate(system, prompt, schema, **kw):
        assert "[S1] BBC" in prompt and "[S2] Al Jazeera" in prompt
        return {"disagreements": [
            {"issue": "Who laid mines", "explanation": "denial vs halted",
             "side_a": {"source_id": "S1", "quote": "Two tankers were halted"}, "side_b": {"source_id": "S2", "quote": "Iran's navy denied laying any mines"}},
            {"issue": "Fabricated", "explanation": "x",
             "side_a": {"source_id": "S1", "quote": "Ten tankers were sunk by mines"}, "side_b": {"source_id": "S2", "quote": "Iran's navy denied laying any mines"}},
            {"issue": "Same source", "explanation": "x",
             "side_a": {"source_id": "S1", "quote": "Two tankers were halted"}, "side_b": {"source_id": "S1", "quote": "fell by a third on Monday"}},
        ]}, "gemini-test"

    monkeypatch.setattr(verifier.gemini, "generate_json", fake_generate)
    found = await verifier.find_disagreements(SOURCES)
    assert [d["issue"] for d in found] == ["Who laid mines"]
    assert found[0]["side_b"]["outlet"] == "Al Jazeera"
    assert await verifier.find_disagreements(SOURCES[:1]) == []


@pytest.mark.asyncio
async def test_contradictions_endpoint_updates_dossier(client, db_session, monkeypatch):
    pid = await _project_with_event(client, db_session, monkeypatch)
    assert (await client.post(f"/api/projects/{pid}/dossier/contradictions")).status_code == 404  # no dossier yet
    await client.post(f"/api/projects/{pid}/dossier/generate")

    async def fake_find(sources):
        return [{"issue": "Traffic drop", "explanation": "a third vs half",
                 "side_a": {"source_id": "S1", "quote": "fell by a third", "outlet": "BBC", "title": "t", "url": "https://bbc.example/1"},
                 "side_b": {"source_id": "S2", "quote": "fell by half", "outlet": "BBC", "title": "t2", "url": "https://bbc.example/2"}}]

    monkeypatch.setattr(verifier, "find_disagreements", fake_find)
    dossier = (await client.post(f"/api/projects/{pid}/dossier/contradictions")).json()
    c = dossier["contradictions"][0]
    assert c["method"] == "ai_verified" and c["side_a"] == "BBC: “fell by a third”" and c["b"]["url"] == "https://bbc.example/2"
    assert (await client.get(f"/api/projects/{pid}")).json()["dossier"]["contradictions"][0]["issue"] == "Traffic drop"


@pytest.mark.asyncio
async def test_extract_claims_dedupes_and_validates_line_ids(monkeypatch):
    async def fake_generate(system, prompt, schema, **kw):
        assert "L1.1: Traffic fell by a third on Monday." in prompt
        return {"claims": [
            {"line_id": "L1.1", "text": "Shipping traffic through Hormuz fell by a third on Monday."},
            {"line_id": "L1.1", "text": "shipping traffic through  hormuz fell by a third on monday."},  # dup of previous
            {"line_id": "L1.1", "text": "Two tankers were halted in the strait"},  # dup of existing
            {"line_id": "L9.9", "text": "Line that does not exist claims something."},
            {"line_id": "L1.1", "text": "Port officials gave the figure."},
        ]}, "gemini-test"

    monkeypatch.setattr(verifier.gemini, "generate_json", fake_generate)
    out = await verifier.extract_claims([{"id": "L1.1", "text": "Traffic fell by a third on Monday."}], ["Two tankers were halted in the strait."])
    assert [c["text"] for c in out] == ["Shipping traffic through Hormuz fell by a third on Monday.", "Port officials gave the figure."]


@pytest.mark.asyncio
async def test_extract_endpoint_adds_unverified_claims_with_cited_evidence(client, db_session, monkeypatch):
    from app.services import scriptwriter
    pid = await _project_with_event(client, db_session, monkeypatch)
    assert (await client.post(f"/api/projects/{pid}/claims/extract")).status_code == 404
    await client.post(f"/api/projects/{pid}/claims", json={"text": "Iran's navy denied laying any mines."})

    async def fake_write(system, prompt):
        return {"title": "T", "logline": "L", "open_questions": [], "acts": [{"title": "Act I", "timecode": "0", "beats": [
            {"kind": "fact", "narration": "Traffic fell by a third.", "citations": ["S1"]},
            {"kind": "fact", "narration": "The navy denied it.", "citations": ["C1"]},  # ledger-only: skipped
            {"kind": "analysis", "narration": "A warning sign.", "citations": []},  # not checkable: skipped
        ]}]}, "gemini-test"

    monkeypatch.setattr(scriptwriter, "call_gemini", fake_write)
    await client.post(f"/api/projects/{pid}/script/generate")
    seen = {}

    async def fake_extract(lines, existing):
        seen["lines"], seen["existing"] = lines, existing
        return [{"line_id": "L1.1", "text": "Traffic through Hormuz fell by a third."}]

    monkeypatch.setattr(verifier, "extract_claims", fake_extract)
    res = await client.post(f"/api/projects/{pid}/claims/extract")
    assert res.status_code == 201
    assert [ln["id"] for ln in seen["lines"]] == ["L1.1"] and seen["existing"] == ["Iran's navy denied laying any mines."]
    new = res.json()[0]
    assert new["status"] == "unverified" and new["note"] == "Extracted from script line L1.1."
    assert new["evidence"] == [{"url": "https://bbc.example/1", "label": "Cited in script [S1]: Tanker traffic slows near Hormuz"}]
    assert len((await client.get(f"/api/projects/{pid}/claims")).json()) == 2
