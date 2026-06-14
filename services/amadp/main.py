"""
AMADP Orchestrator — Application Entry-point
Adversarial Multi-Agent Debate Protocol microservice.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routes import router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("amadp")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Adversarial Multi-Agent Debate Protocol (AMADP) Orchestrator. "
        "Coordinates prosecution, defense, and judge agents to produce "
        "confidence-calibrated fraud verdicts with RBI-compliant reasoning DAGs."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup() -> None:
    logger.info(
        "%s v%s starting on port 8005",
        settings.app_name,
        settings.app_version,
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("%s shutting down", settings.app_name)
