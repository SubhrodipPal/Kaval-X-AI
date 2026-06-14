"""
AMADP Orchestrator — API Routes
Exposes debate orchestration, SSE streaming, transcript retrieval, and PQC signing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from config import settings
from debate_engine import (
    get_transcript,
    get_verdict,
    pqc_sign_verdict,
    run_debate,
    stream_debate_events,
)
from models import (
    DebateConfig,
    DebateStatus,
    HealthResponse,
    TransactionEvidence,
    VerdictOutput,
    VerdictSignRequest,
)

logger = logging.getLogger("amadp.routes")

router = APIRouter()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Service health check."""
    return HealthResponse(
        service=settings.app_name,
        version=settings.app_version,
    )


# ---------------------------------------------------------------------------
# Debate
# ---------------------------------------------------------------------------

@router.post(
    "/internal/amadp/debate",
    response_model=VerdictOutput,
    status_code=status.HTTP_200_OK,
    tags=["Debate"],
    summary="Run adversarial multi-agent debate",
)
async def run_adversarial_debate(
    evidence: TransactionEvidence,
    max_rounds: int = 3,
    judge_threshold: float = 0.82,
    disagreement_threshold: float = 0.15,
) -> VerdictOutput:
    """
    Accept transaction evidence and run a full adversarial debate.

    The debate proceeds through up to `max_rounds` rounds where:
    1. Prosecution Agent argues the transaction IS fraud
    2. Defense Agent argues the transaction is NOT fraud
    3. Judge Agent adjudicates using RBI rule ontology

    Returns the final verdict with confidence scores and reasoning DAG.
    """
    config = DebateConfig(
        max_rounds=max_rounds,
        judge_threshold=judge_threshold,
        disagreement_threshold=disagreement_threshold,
    )
    try:
        verdict = await run_debate(evidence, config)
        logger.info(
            "Debate completed: verdict_id=%s verdict=%s confidence=%.3f",
            verdict.verdict_id,
            verdict.verdict.value,
            verdict.confidence,
        )
        return verdict
    except Exception as exc:
        logger.exception("Debate failed for txn %s", evidence.txn_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Debate engine error: {str(exc)}",
        ) from exc


# ---------------------------------------------------------------------------
# SSE Streaming
# ---------------------------------------------------------------------------

@router.get(
    "/internal/amadp/stream/{verdict_id}",
    tags=["Streaming"],
    summary="Stream debate tokens via SSE",
)
async def stream_debate(verdict_id: str) -> EventSourceResponse:
    """
    Server-Sent Events endpoint that streams debate tokens in real-time.

    Events:
    - ``{type: "token", agent: "prosecution"|"defense"|"judge", round: N, token: "..."}``
    - ``{type: "verdict", data: VerdictOutput}``

    The stream closes after the final verdict event.
    """

    async def _event_generator():
        async for event in stream_debate_events(verdict_id):
            yield {
                "event": event.get("type", "message"),
                "data": json.dumps(event),
                "retry": settings.sse_retry_timeout_ms,
            }

    return EventSourceResponse(
        _event_generator(),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------

@router.get(
    "/internal/amadp/transcript/{verdict_id}",
    tags=["Transcript"],
    summary="Get full debate transcript",
)
async def get_debate_transcript(verdict_id: str) -> dict[str, Any]:
    """
    Retrieve the complete debate transcript for a given verdict ID.

    Returns all rounds with prosecution, defense, and judge messages.
    """
    transcript = get_transcript(verdict_id)
    if transcript is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript not found for verdict {verdict_id}",
        )
    return {
        "verdict_id": transcript.verdict_id,
        "status": transcript.status.value,
        "total_rounds": len(transcript.rounds),
        "rounds": [
            [msg.model_dump(mode="json") for msg in round_msgs]
            for round_msgs in transcript.rounds
        ],
    }


# ---------------------------------------------------------------------------
# PQC Signing
# ---------------------------------------------------------------------------

@router.post(
    "/internal/amadp/verdict/{verdict_id}/sign",
    tags=["Signing"],
    summary="PQC sign a verdict",
)
async def sign_verdict(verdict_id: str, request: VerdictSignRequest) -> dict[str, Any]:
    """
    Apply a CRYSTALS-Dilithium (PQC) signature to a verdict.

    In production, this uses a hardware security module (HSM) with
    post-quantum cryptographic keys. The development stub uses SHA-512.
    """
    verdict = get_verdict(verdict_id)
    if verdict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verdict not found: {verdict_id}",
        )

    if verdict.pqc_signature_hex:
        return {
            "verdict_id": verdict_id,
            "status": "already_signed",
            "pqc_signature_hex": verdict.pqc_signature_hex,
        }

    signature = pqc_sign_verdict(verdict, request.signer_id)
    verdict.pqc_signature_hex = signature

    logger.info("Verdict %s signed by %s", verdict_id, request.signer_id)

    return {
        "verdict_id": verdict_id,
        "status": "signed",
        "signer_id": request.signer_id,
        "algorithm": "CRYSTALS-Dilithium-v3.1-stub",
        "pqc_signature_hex": signature,
    }
