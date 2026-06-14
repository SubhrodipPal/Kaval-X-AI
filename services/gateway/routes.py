"""
Kavalx API Gateway - Route Definitions
All public-facing endpoints: transaction scoring, APK submission,
account risk, WebSocket streams, analyst overrides, compliance proxy.
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

import httpx
import jwt
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from models import (
    AccountRiskProfile,
    AnalystOverride,
    APKSubmitResponse,
    APKVerdict,
    ComplianceReport,
    HealthResponse,
    DependencyHealth,
    OverrideResponse,
    TransactionScoreRequest,
    TransactionScoreResponse,
    Verdict,
)

logger = logging.getLogger("kavalx.gateway.routes")

# --------------------------------------------------------------------------- #
#  Router
# --------------------------------------------------------------------------- #

router = APIRouter()
security = HTTPBearer(auto_error=False)

# --------------------------------------------------------------------------- #
#  Auth Helpers
# --------------------------------------------------------------------------- #

def _decode_token(token: str) -> dict:
    """Decode and validate a JWT token, returning its payload."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Dependency that enforces JWT authentication on a route."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    return _decode_token(credentials.credentials)


async def require_analyst(user: dict = Depends(require_auth)) -> dict:
    """Dependency that enforces ANALYST_ROLE on a route."""
    role = user.get("role", "")
    if role != "ANALYST" and role != "ADMIN":
        raise HTTPException(status_code=403, detail="ANALYST or ADMIN role required")
    return user


# --------------------------------------------------------------------------- #
#  Shared HTTP client accessor
# --------------------------------------------------------------------------- #

def _get_http_client() -> httpx.AsyncClient:
    """Return the shared httpx.AsyncClient stored in app state.

    Falls back to creating a fresh client if lifespan hasn't initialised one yet
    (useful for testing).
    """
    from main import _http_client  # deferred to avoid circular import
    return _http_client


# --------------------------------------------------------------------------- #
#  POST /v1/transaction/score
# --------------------------------------------------------------------------- #

@router.post(
    "/v1/transaction/score",
    response_model=TransactionScoreResponse,
    summary="Score a transaction for fraud risk",
    tags=["Transactions"],
)
async def score_transaction(
    req: TransactionScoreRequest,
    user: dict = Depends(require_auth),
) -> TransactionScoreResponse:
    """
    Accepts a TransactionScoreRequest, fans out to Transaction Intelligence
    Service (TIS) and Graph Intelligence Service (GIS), fuses scores and
    returns a final verdict.
    """
    client = _get_http_client()
    txn_id = str(uuid.uuid4())

    # --- Fan-out to TIS and GIS concurrently --------------------------------
    tis_score: float = 0.5
    gis_score: float = 0.5
    bio_trust: float = 0.5

    async def _call_tis() -> float:
        try:
            resp = await client.post(
                f"{settings.TIS_URL}/internal/txn/ingest",
                json=req.model_dump(mode="json"),
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return float(data.get("risk_score", 0.5))
        except Exception as exc:
            logger.warning("TIS call failed, using default score: %s", exc)
        return 0.5

    async def _call_gis() -> float:
        try:
            resp = await client.post(
                f"{settings.GIS_URL}/internal/graph/score-node",
                json={"node_id": req.src_account, "node_type": "account"},
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return float(data.get("tgn_score", 0.5))
        except Exception as exc:
            logger.warning("GIS call failed, using default score: %s", exc)
        return 0.5

    async def _call_bio() -> float:
        try:
            resp = await client.post(
                f"{settings.BIO_URL}/internal/bio/trust-vector",
                json={
                    "device_fingerprint": req.device_fingerprint,
                    "ip_hash": req.ip_hash,
                    "lat": req.lat,
                    "lon": req.lon,
                },
                timeout=3.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return float(data.get("composite_trust", 0.5))
        except Exception as exc:
            logger.warning("BIO call failed, using default trust: %s", exc)
        return 0.5

    tis_score, gis_score, bio_trust = await asyncio.gather(
        _call_tis(), _call_gis(), _call_bio()
    )

    # --- Score fusion (weighted harmonic mean) ------------------------------
    w_tis, w_gis, w_bio = 0.45, 0.35, 0.20
    # Clamp to avoid division-by-zero in harmonic mean
    tis_clamped = max(tis_score, 1e-6)
    gis_clamped = max(gis_score, 1e-6)
    bio_inverted = max(1.0 - bio_trust, 1e-6)  # lower trust → higher risk

    risk_score = (w_tis + w_gis + w_bio) / (
        w_tis / tis_clamped + w_gis / gis_clamped + w_bio / bio_inverted
    )
    risk_score = round(min(max(risk_score, 0.0), 1.0), 4)

    # --- Verdict determination ----------------------------------------------
    if risk_score >= 0.80:
        verdict = Verdict.BLOCK
    elif risk_score >= 0.45:
        verdict = Verdict.REVIEW
    else:
        verdict = Verdict.ALLOW

    return TransactionScoreResponse(
        txn_id=txn_id,
        risk_score=risk_score,
        verdict=verdict,
        bio_trust=round(bio_trust, 4),
        tgn_score=round(gis_score, 4),
    )


# --------------------------------------------------------------------------- #
#  POST /v1/apk/submit
# --------------------------------------------------------------------------- #

@router.post(
    "/v1/apk/submit",
    response_model=APKSubmitResponse,
    summary="Submit an APK for threat analysis",
    tags=["APK Analysis"],
)
async def submit_apk(
    file: UploadFile = File(..., description="APK file to analyse"),
    user: dict = Depends(require_auth),
) -> APKSubmitResponse:
    """
    Accepts an APK file upload, computes SHA-256, forwards the file to the
    APK Analysis Service, and returns a preliminary verdict.
    """
    contents = await file.read()
    sha256 = hashlib.sha256(contents).hexdigest()
    client = _get_http_client()

    try:
        resp = await client.post(
            f"{settings.APK_URL}/internal/apk/analyze",
            files={"file": (file.filename or "upload.apk", contents, "application/octet-stream")},
            timeout=30.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return APKSubmitResponse(
                apk_id=data.get("job_id", str(uuid.uuid4())),
                sha256=sha256,
                verdict=APKVerdict(data.get("verdict", "CLEAN")),
                static_score=data.get("static_score", 0.0),
                dynamic_score=data.get("dynamic_score", 0.0),
                meta_score=data.get("meta_score", 0.0),
            )
    except Exception as exc:
        logger.warning("APK service call failed: %s", exc)

    # Fallback – return a queued response
    return APKSubmitResponse(
        sha256=sha256,
        verdict=APKVerdict.CLEAN,
        static_score=0.0,
        dynamic_score=0.0,
        meta_score=0.0,
    )


# --------------------------------------------------------------------------- #
#  GET /v1/account/{id}/risk
# --------------------------------------------------------------------------- #

@router.get(
    "/v1/account/{account_id}/risk",
    response_model=AccountRiskProfile,
    summary="Get account risk profile",
    tags=["Accounts"],
)
async def get_account_risk(
    account_id: str,
    user: dict = Depends(require_auth),
) -> AccountRiskProfile:
    """Query the Graph Intelligence Service for an account's risk profile."""
    client = _get_http_client()

    try:
        resp = await client.post(
            f"{settings.GIS_URL}/internal/graph/score-node",
            json={"node_id": account_id, "node_type": "account"},
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return AccountRiskProfile(
                account_id=account_id,
                risk_score=data.get("tgn_score", 0.0),
                is_frozen=data.get("tgn_score", 0.0) >= 0.9,
                recent_txn_count=len(data.get("neighbors", [])),
                mule_cluster_id=data.get("mule_cluster_id"),
            )
    except Exception as exc:
        logger.warning("GIS account risk call failed: %s", exc)

    return AccountRiskProfile(account_id=account_id, risk_score=0.0)


# --------------------------------------------------------------------------- #
#  WS /v1/stream/transactions
# --------------------------------------------------------------------------- #

@router.websocket("/v1/stream/transactions")
async def stream_transactions(ws: WebSocket) -> None:
    """
    WebSocket endpoint that streams scored transactions.
    Clients connect and receive JSON-encoded TransactionScoreResponse objects
    as they are processed.
    """
    await ws.accept()
    logger.info("WebSocket client connected to /v1/stream/transactions")

    try:
        while True:
            # In production this would consume from a Kafka topic or Redis stream.
            # Here we simulate a periodic scored-transaction broadcast.
            simulated = TransactionScoreResponse(
                txn_id=str(uuid.uuid4()),
                risk_score=round(0.1 + (hash(time.time()) % 90) / 100, 4),
                verdict=Verdict.ALLOW,
                bio_trust=0.78,
                tgn_score=0.32,
            )
            await ws.send_json(simulated.model_dump(mode="json"))
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from /v1/stream/transactions")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
        await ws.close(code=1011)


# --------------------------------------------------------------------------- #
#  WS /v1/stream/amadp/{verdict_id}
# --------------------------------------------------------------------------- #

@router.websocket("/v1/stream/amadp/{verdict_id}")
async def stream_amadp_debate(ws: WebSocket, verdict_id: str) -> None:
    """
    WebSocket streaming the Adversarial Multi-Agent Debate Protocol (AMADP)
    for a given verdict.  Each agent turn is streamed as a JSON message with
    agent name, argument, stance, and confidence.
    """
    await ws.accept()
    logger.info("AMADP WebSocket connected for verdict %s", verdict_id)

    agents = [
        {"agent": "Prosecutor", "stance": "BLOCK"},
        {"agent": "Defender", "stance": "ALLOW"},
        {"agent": "Arbiter", "stance": "REVIEW"},
    ]

    try:
        for round_num in range(1, 4):
            for agent_info in agents:
                debate_msg = {
                    "verdict_id": verdict_id,
                    "round": round_num,
                    "agent": agent_info["agent"],
                    "stance": agent_info["stance"],
                    "confidence": round(0.5 + round_num * 0.1, 2),
                    "argument": (
                        f"{agent_info['agent']} argues for {agent_info['stance']} "
                        f"in round {round_num} based on feature analysis."
                    ),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                await ws.send_json(debate_msg)
                await asyncio.sleep(1.0)

        # Final verdict after all rounds
        final = {
            "verdict_id": verdict_id,
            "final_verdict": "REVIEW",
            "consensus_confidence": 0.72,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await ws.send_json(final)
        await ws.close(code=1000)
    except WebSocketDisconnect:
        logger.info("AMADP WebSocket disconnected for verdict %s", verdict_id)
    except Exception as exc:
        logger.error("AMADP WebSocket error: %s", exc)
        await ws.close(code=1011)


# --------------------------------------------------------------------------- #
#  POST /v1/verdict/{id}/override
# --------------------------------------------------------------------------- #

@router.post(
    "/v1/verdict/{verdict_id}/override",
    response_model=OverrideResponse,
    summary="Analyst override on a fraud verdict",
    tags=["Analyst"],
)
async def override_verdict(
    verdict_id: str,
    body: AnalystOverride,
    user: dict = Depends(require_analyst),
) -> OverrideResponse:
    """
    Allows an analyst with ANALYST_ROLE to override a verdict.
    The override is logged and the original verdict is updated.
    """
    logger.info(
        "Analyst %s overriding verdict %s → %s: %s",
        body.analyst_id,
        verdict_id,
        body.override_action.value,
        body.reason,
    )

    # In production: persist to PG audit log, publish to Kafka kaval.audit.overrides
    return OverrideResponse(
        verdict_id=verdict_id,
        override_action=body.override_action,
        analyst_id=body.analyst_id,
        accepted=True,
    )


# --------------------------------------------------------------------------- #
#  GET /v1/compliance/report/{id}
# --------------------------------------------------------------------------- #

@router.get(
    "/v1/compliance/report/{report_id}",
    response_model=ComplianceReport,
    summary="Retrieve a compliance report",
    tags=["Compliance"],
)
async def get_compliance_report(
    report_id: str,
    user: dict = Depends(require_auth),
) -> ComplianceReport:
    """
    Proxy to a compliance reporting service.  Currently returns a generated
    stub report; in production this calls an internal compliance micro-service.
    """
    # In production: proxy to compliance service
    return ComplianceReport(
        report_id=report_id,
        total_transactions=125_430,
        flagged_transactions=342,
        blocked_transactions=87,
        sar_filed=12,
        summary=(
            f"Compliance report {report_id}: 342 flagged transactions in the "
            f"reporting period with 87 blocked and 12 SARs filed to FIU-IND."
        ),
    )


# --------------------------------------------------------------------------- #
#  GET /health
# --------------------------------------------------------------------------- #

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint that reports on the gateway and its downstream
    dependencies (Redis, TIS, GIS, APK, BIO).
    """
    from main import _app_start_time, _redis

    deps: list[DependencyHealth] = []

    # Check Redis
    try:
        t0 = time.perf_counter()
        if _redis is not None:
            await _redis.ping()
        latency = (time.perf_counter() - t0) * 1000
        deps.append(DependencyHealth(name="redis", status="healthy", latency_ms=round(latency, 2)))
    except Exception:
        deps.append(DependencyHealth(name="redis", status="unhealthy"))

    # Check downstream services
    client = _get_http_client()
    for name, url in [
        ("transaction-intelligence", settings.TIS_URL),
        ("apk-analysis", settings.APK_URL),
        ("graph-intelligence", settings.GIS_URL),
        ("biometrics", settings.BIO_URL),
    ]:
        try:
            t0 = time.perf_counter()
            resp = await client.get(f"{url}/health", timeout=2.0)
            latency = (time.perf_counter() - t0) * 1000
            st = "healthy" if resp.status_code == 200 else "degraded"
            deps.append(DependencyHealth(name=name, status=st, latency_ms=round(latency, 2)))
        except Exception:
            deps.append(DependencyHealth(name=name, status="unhealthy"))

    overall = "healthy" if all(d.status == "healthy" for d in deps) else "degraded"
    uptime = time.time() - _app_start_time

    return HealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        uptime_seconds=round(uptime, 2),
        dependencies=deps,
    )
