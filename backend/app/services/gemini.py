"""Thin Gemini generateContent client shared by the script writer and the AI fact checks.

The API key is sent in a header (never the URL) so it can't leak through error messages,
and every failure becomes an HTTPException with an actionable message.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def bad_gateway(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


async def request(
    system: str,
    prompt: str,
    *,
    schema: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.2,
    max_tokens: int = 32768,
) -> Tuple[Dict[str, Any], str]:
    """POST one generateContent request. Returns (raw response payload, model id)."""
    if not settings.GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI features are not configured. Set GPS_GEMINI_API_KEY (Google AI Studio key) in backend/.env and restart.",
        )
    model = settings.GEMINI_MODEL
    config: Dict[str, Any] = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if schema:
        config.update(responseMimeType="application/json", responseSchema=schema)
    body: Dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": config,
    }
    if tools:
        body["tools"] = tools
    try:
        async with httpx.AsyncClient(timeout=settings.GEMINI_TIMEOUT_SECONDS) as client:
            res = await client.post(GEMINI_URL.format(model=model), json=body, headers={"x-goog-api-key": settings.GEMINI_API_KEY})
    except httpx.HTTPError as exc:
        logger.warning("Gemini request failed: %s", type(exc).__name__)
        raise bad_gateway("Could not reach Gemini. Check your connection and try again.")
    if res.status_code != 200:
        try:
            message = res.json().get("error", {}).get("message", "")
        except ValueError:
            message = ""
        hint = f" Check GPS_GEMINI_MODEL ('{model}')." if res.status_code == 404 else ""
        raise bad_gateway(f"Gemini error (HTTP {res.status_code}): {message[:300]}{hint}")
    return res.json(), model


def response_text(payload: Dict[str, Any], cut_off_hint: str = "") -> str:
    """The answer text of a response (thought parts excluded); ValueError on block, empty or truncated output."""
    block = (payload.get("promptFeedback") or {}).get("blockReason")
    if block:
        raise ValueError(f"Gemini blocked the request ({block}).")
    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini returned no answer.")
    if candidates[0].get("finishReason") == "MAX_TOKENS":
        raise ValueError(f"Gemini's answer was cut off by the output limit. {cut_off_hint}".strip())
    return "".join(p.get("text", "") for p in (candidates[0].get("content") or {}).get("parts", []) if not p.get("thought"))


def parse_json_response(payload: Dict[str, Any], cut_off_hint: str = "") -> Dict[str, Any]:
    text = response_text(payload, cut_off_hint)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini returned malformed JSON (finish reason {payload['candidates'][0].get('finishReason')}).") from exc
    if not isinstance(data, dict):
        raise ValueError("Gemini's answer was not a JSON object.")
    return data


async def generate_json(system: str, prompt: str, schema: Dict[str, Any], *, cut_off_hint: str = "", **kwargs: Any) -> Tuple[Dict[str, Any], str]:
    """Structured-output call. Returns (parsed JSON object, model id)."""
    payload, model = await request(system, prompt, schema=schema, **kwargs)
    try:
        return parse_json_response(payload, cut_off_hint), model
    except ValueError as exc:
        raise bad_gateway(str(exc))
