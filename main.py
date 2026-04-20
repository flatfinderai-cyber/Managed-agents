# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — Backend API Entry Point
# Trademarks and Patents Pending (CIPO). Proprietary and Confidential.

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ── Load environment ───────────────────────────────────────────────────────────
load_dotenv(".env.local")
load_dotenv(".env")

# ── Route imports ──────────────────────────────────────────────────────────────
from routes.listings       import router as listings_router
from routes.agents         import router as agents_router
from routes.affordability  import router as affordability_router
from routes.benny          import router as benny_router
from routes.search_blitz   import router as search_router
from routes.vmc            import router as vmc_router
from routes.tenant_verify  import router as tenant_router
from routes.landlord_verify import router as landlord_router
from routes.matching       import router as matching_router
from routes.human_review   import router as review_router
from routes.stack_decisions import router as stack_decisions_router
from routes.orchestrator import router as orchestrator_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("FlatFinder™ API starting — © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin")
    yield
    print("FlatFinder™ API shutting down.")


app = FastAPI(
    title="FlatFinder™ API",
    description=(
        "Anti-gatekeeping rental platform API. "
        "© 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. "
        "Trademarks and Patents Pending (CIPO)."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000"),
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routers ──────────────────────────────────────────────────────────────
app.include_router(listings_router,    prefix="/api/listings",   tags=["Listings"])
app.include_router(agents_router,      prefix="/api/agents",     tags=["Agents"])
app.include_router(affordability_router, prefix="/api/affordability", tags=["Affordability"])
app.include_router(benny_router,       prefix="/api/benny",      tags=["Benny AI"])
app.include_router(search_router,      prefix="/api/search",     tags=["Search"])
app.include_router(vmc_router,         prefix="/api/vmc",        tags=["VMC — FF-CORE-007"])
app.include_router(tenant_router,      prefix="/api/tenant",     tags=["Tenant Verification — FF-CORE-009"])
app.include_router(landlord_router,    prefix="/api/landlord",   tags=["Landlord Verification — FF-CORE-010"])
app.include_router(matching_router,    prefix="/api/match",      tags=["Matching Engine — FF-CORE-011"])
app.include_router(review_router,      prefix="/api/review",     tags=["Human Review — FF-CORE-008"])
app.include_router(stack_decisions_router, prefix="/api/stack-decisions", tags=["Scam Stack Decisions — FF-SCAM-001"])
app.include_router(orchestrator_router, prefix="/api/orchestrator", tags=["Agent Orchestrator — internal"])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "platform": "FlatFinder™",
        "copyright": "© 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin",
    }
