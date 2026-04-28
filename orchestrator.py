# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved. FlatFinder™
# Agent pipeline API — internal use only (long-running Claude + tools).

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _require_internal_key(x_internal_key: Optional[str]) -> None:
    expected = os.environ.get("INTERNAL_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Internal API key not configured — set INTERNAL_API_KEY in environment.",
        )
    if not x_internal_key or x_internal_key != expected:
        raise HTTPException(status_code=403, detail="Forbidden. Invalid or missing internal API key.")


def _serialize_agent_result(result: Any) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "text": result.text,
        "iterations": result.iterations,
        "tool_calls": result.tool_calls,
    }


class PipelineRequest(BaseModel):
    city: str = "Toronto"
    annual_income: float = Field(72000, ge=0)
    scraper_source: str = "kijiji"
    agents: list[Literal["db", "affordability", "scraper"]] | None = None


def _run_pipeline_sync(body: PipelineRequest) -> dict[str, Any]:
    from agents.orchestrator import FlatFinderOrchestrator

    orch = FlatFinderOrchestrator(verbose=False)
    pr = orch.run_pipeline(
        city=body.city,
        annual_income=body.annual_income,
        scraper_source=body.scraper_source,
        agents=body.agents,
    )
    return {
        "elapsed_seconds": pr.elapsed_seconds,
        "errors": pr.errors,
        "database_architect": _serialize_agent_result(pr.db_result),
        "affordability": _serialize_agent_result(pr.affordability_result),
        "scraper": _serialize_agent_result(pr.scraper_result),
    }


@router.get("/status")
async def orchestrator_status():
    """Lightweight check — does not invoke Claude."""
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_internal = bool(os.environ.get("INTERNAL_API_KEY"))
    return {
        "anthropic_configured": has_anthropic,
        "internal_key_configured": has_internal,
        "repo_root_on_path": str(_REPO_ROOT),
    }


@router.post("/pipeline")
async def run_pipeline_endpoint(
    body: PipelineRequest,
    x_internal_key: Optional[str] = Header(None),
):
    """
    Run the FlatFinder™ agent pipeline (Database Architect → Affordability → Scraper).
    Protected by INTERNAL_API_KEY. Blocks until completion — use only from trusted callers.
    """
    _require_internal_key(x_internal_key)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not set — orchestrator cannot run.",
        )

    try:
        payload = await asyncio.to_thread(_run_pipeline_sync, body)
    except Exception as exc:
        logging.error(f"Pipeline failed: {exc!s}")
        raise HTTPException(status_code=500, detail="Pipeline execution failed.") from exc

    return payload
