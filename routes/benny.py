# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™

from __future__ import annotations

import json
import os
from typing import Iterator, List

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
# Online models — good for search-grounded rental guidance (see Perplexity model list in dashboard)
DEFAULT_PERPLEXITY_MODEL = "sonar"


BENNY_SYSTEM_PROMPT = """
You are Benny, an orange tabby cat and FlatFinder™'s AI housing guide.

Your personality:
- Warm, calm, and protective of the person you're helping
- Knowledgeable about renter rights in Canada, UK, and France
- Gently but firmly opposed to housing gatekeeping and discrimination
- You use the economist-backed 33-40% affordability rule. Never the 3x income multiplier.
- You speak clearly and directly. No jargon. You are a cat.

Your cities (Phase 1): Toronto, Vancouver, Paris, Edinburgh

On your first message:
1. Welcome the user warmly
2. Ask which city they're searching in
3. Ask their annual or monthly income — explain this lets you find listings they can truly afford using the 33-40% standard, not the biased 3x rule used by gatekeeping agents
4. Ask bedroom preferences
5. Ask about pets, car, must-haves
6. Summarize their search profile and the honest rent number they should expect

On agent compliance:
- If a user names an agent or company, check if they sound like they use illegal screening
- Clearly explain: any agent demanding 3x monthly rent has no legal or moral basis to do so
- If they mention losing money or being rejected unfairly, validate them. It's not their fault.
- Remind them: FlatFinder flags blacklisted agents so this never happens again

Cities you know:
- Toronto: Ontario Residential Tenancies Act protections, LTB rights, no application fees allowed
- Vancouver: BC Residential Tenancy Act, strict deposit rules
- Paris: Encadrement des loyers (rent control), ALUR law protections
- Edinburgh: Housing (Scotland) Act 2006, Tenant Fees banned, Repairing Standard

Always remember: renters deserve dignity. No one should lose thousands of dollars to a predatory agency.
You are Benny. You are FlatFinder™. Canadian Kind. Scottish Strong.
"""


class Message(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str


class BennyRequest(BaseModel):
    messages: List[Message]


def _perplexity_key() -> str:
    key = (os.environ.get("PERPLEXITY_API_KEY") or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="PERPLEXITY_API_KEY is not set — add it to .env.local (Perplexity API key for Benny).",
        )
    return key


def _perplexity_model() -> str:
    return (os.environ.get("PERPLEXITY_MODEL") or DEFAULT_PERPLEXITY_MODEL).strip() or DEFAULT_PERPLEXITY_MODEL


def _openai_style_messages(request: BennyRequest) -> list[dict]:
    return [
        {"role": "system", "content": BENNY_SYSTEM_PROMPT},
        *[{"role": m.role, "content": m.content} for m in request.messages[-20:]],
    ]


def _complete_content(data: dict) -> str:
    try:
        choices = data.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        return (msg.get("content") or "").strip()
    except (TypeError, KeyError, IndexError):
        return ""


def _iter_stream_text(lines: Iterator[str]) -> Iterator[str]:
    """Parse OpenAI-style SSE from Perplexity and yield text fragments."""
    for line in lines:
        if not line:
            continue
        if line.startswith(":"):
            continue
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            break
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        choices = obj.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        piece = delta.get("content") or ""
        if piece:
            yield piece


@router.post("/chat")
async def chat_with_benny(request: BennyRequest):
    """
    Chat with Benny — streams plain text (compatible with simple clients).
    Uses Perplexity (search-grounded) via Chat Completions API.
    """
    api_key = _perplexity_key()
    payload = {
        "model": _perplexity_model(),
        "messages": _openai_style_messages(request),
        "stream": True,
    }

    def stream_response() -> Iterator[bytes]:
        with httpx.Client(timeout=120.0) as client:
            with client.stream(
                "POST",
                PERPLEXITY_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
                json=payload,
            ) as r:
                try:
                    r.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    err_body = exc.response.text[:500] if exc.response else ""
                    yield f"[Benny error: {exc.response.status_code} {err_body}]".encode("utf-8")
                    return
                for chunk in _iter_stream_text(r.iter_lines()):
                    yield chunk.encode("utf-8")

    return StreamingResponse(stream_response(), media_type="text/plain; charset=utf-8")


@router.post("/chat/complete")
async def chat_complete(request: BennyRequest):
    """Non-streaming — full reply in one JSON body."""
    api_key = _perplexity_key()
    payload = {
        "model": _perplexity_model(),
        "messages": _openai_style_messages(request),
        "stream": False,
    }
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            PERPLEXITY_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=r.text[:1000] or "Perplexity request failed.")
    data = r.json()
    text = _complete_content(data)
    return {"role": "assistant", "content": text}
