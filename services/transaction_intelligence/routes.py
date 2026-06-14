"""
Kavalx Transaction Intelligence Service - Route Definitions
Handles transaction ingestion, feature extraction, history queries, and batch processing.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from config import settings
from models import (
    BatchFeatureMatrix,
    BatchFeatureResponse,
    FeatureVector,
    IngestResponse,
    RawUPIEvent,
    TransactionHistory,
    TransactionHistoryResponse,
)
from utils import build_feature_vector_from_history

logger = logging.getLogger("kavalx.tis.routes")

router = APIRouter()


# --------------------------------------------------------------------------- #
#  In-memory stores (graceful fallback when PG / Kafka / Redis are offline)
# --------------------------------------------------------------------------- #

_in_memory_store: dict[str, list[dict]] = {}
"""Per-account transaction history stored in memory when PG is unavailable.
Key: src_account, Value: list of dicts with txn data."""

_in_memory_devices: dict[str, datetime] = {}
"""Device fingerprint → first_seen timestamp."""


def _get_account_history(account_id: str) -> tuple[
    list[datetime], list[int], list[str], Optional[float], Optional[float]
]:
    """
    Retrieve historical data for an account from the in-memory store.

    Returns:
        (timestamps, amounts_paise, receivers, last_lat, last_lon)
    """
    records = _in_memory_store.get(account_id, [])
    timestamps = [r["timestamp"] for r in records]
    amounts = [r["amount_paise"] for r in records]
    receivers = [r["dst_account"] for r in records]
    last_lat = records[-1].get("lat") if records else None
    last_lon = records[-1].get("lon") if records else None
    return timestamps, amounts, receivers, last_lat, last_lon


def _store_event(event: RawUPIEvent) -> None:
    """Append an event to the in-memory per-account history."""
    key = event.src_account
    if key not in _in_memory_store:
        _in_memory_store[key] = []
    _in_memory_store[key].append({
        "event_id": event.event_id,
        "src_account": event.src_account,
        "dst_account": event.dst_account,
        "amount_paise": event.amount_paise,
        "rail": event.rail.value,
        "timestamp": event.timestamp,
        "lat": event.lat,
        "lon": event.lon,
    })
    # Keep only last 1000 events per account
    if len(_in_memory_store[key]) > 1000:
        _in_memory_store[key] = _in_memory_store[key][-1000:]

    # Track device first-seen
    fp = event.device_fingerprint
    if fp and fp not in _in_memory_devices:
        _in_memory_devices[fp] = event.timestamp


# --------------------------------------------------------------------------- #
#  POST /internal/txn/ingest
# --------------------------------------------------------------------------- #

@router.post(
    "/internal/txn/ingest",
    response_model=IngestResponse,
    summary="Ingest a raw transaction event and extract features",
    tags=["Transactions"],
)
async def ingest_transaction(event: RawUPIEvent) -> IngestResponse:
    """
    Ingest a single raw UPI/IMPS/NEFT event:
    1. Extract feature vector from event + historical context.
    2. Store event in PostgreSQL (falls back to in-memory).
    3. Publish feature vector to Kafka kaval.txn.features.
    4. Cache risk score in Redis.
    """
    from main import _pg_pool, _redis, _kafka_producer

    current_ts = event.timestamp or datetime.utcnow()

    # --- Retrieve history ---------------------------------------------------
    pg_stored = False
    history_timestamps: list[datetime] = []
    history_amounts: list[int] = []
    history_receivers: list[str] = []
    last_lat: Optional[float] = None
    last_lon: Optional[float] = None
    device_first_seen: Optional[datetime] = None

    if _pg_pool is not None:
        try:
            async with _pg_pool.acquire() as conn:
                # Fetch recent transactions for this account
                rows = await conn.fetch(
                    """
                    SELECT dst_account, amount_paise, timestamp, lat, lon
                    FROM transactions
                    WHERE src_account = $1 AND timestamp > $2
                    ORDER BY timestamp ASC
                    """,
                    event.src_account,
                    current_ts - timedelta(days=settings.HISTORY_DAYS),
                )
                for row in rows:
                    history_timestamps.append(row["timestamp"])
                    history_amounts.append(row["amount_paise"])
                    history_receivers.append(row["dst_account"])
                if rows:
                    last_lat = rows[-1]["lat"]
                    last_lon = rows[-1]["lon"]

                # Fetch device first seen
                dev_row = await conn.fetchrow(
                    "SELECT MIN(timestamp) as first_seen FROM transactions WHERE device_fingerprint = $1",
                    event.device_fingerprint,
                )
                if dev_row and dev_row["first_seen"]:
                    device_first_seen = dev_row["first_seen"]

                # Store current event
                await conn.execute(
                    """
                    INSERT INTO transactions
                        (event_id, src_account, dst_account, amount_paise, rail,
                         device_fingerprint, ip_hash, lat, lon, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    event.event_id, event.src_account, event.dst_account,
                    event.amount_paise, event.rail.value,
                    event.device_fingerprint, event.ip_hash,
                    event.lat, event.lon, current_ts,
                )
                pg_stored = True
        except Exception as exc:
            logger.warning("PG operation failed, using in-memory fallback: %s", exc)
            history_timestamps, history_amounts, history_receivers, last_lat, last_lon = (
                _get_account_history(event.src_account)
            )
            device_first_seen = _in_memory_devices.get(event.device_fingerprint)
    else:
        # In-memory fallback
        history_timestamps, history_amounts, history_receivers, last_lat, last_lon = (
            _get_account_history(event.src_account)
        )
        device_first_seen = _in_memory_devices.get(event.device_fingerprint)

    # --- Feature extraction -------------------------------------------------
    feature_dict = build_feature_vector_from_history(
        event_id=event.event_id,
        src_account=event.src_account,
        amount_paise=event.amount_paise,
        current_ts=current_ts,
        lat=event.lat,
        lon=event.lon,
        device_fingerprint=event.device_fingerprint,
        history_timestamps=history_timestamps,
        history_amounts=history_amounts,
        history_receivers=history_receivers,
        dst_account=event.dst_account,
        last_lat=last_lat,
        last_lon=last_lon,
        device_first_seen=device_first_seen,
    )

    feature_vector = FeatureVector(**feature_dict)

    # --- Store in-memory (always, for local history) ------------------------
    _store_event(event)

    # --- Publish to Kafka ---------------------------------------------------
    kafka_published = False
    if _kafka_producer is not None:
        try:
            payload = json.dumps(feature_dict, default=str).encode("utf-8")
            _kafka_producer.produce(
                topic=settings.KAFKA_TOPIC_FEATURES,
                key=event.src_account.encode("utf-8"),
                value=payload,
            )
            _kafka_producer.poll(0)  # trigger delivery callbacks
            kafka_published = True
        except Exception as exc:
            logger.warning("Kafka publish failed: %s", exc)

    # --- Cache risk score in Redis ------------------------------------------
    cached = False
    if _redis is not None:
        try:
            cache_key = f"kavalx:risk:{event.src_account}"
            await _redis.setex(cache_key, settings.REDIS_RISK_TTL, str(feature_vector.risk_score))
            cached = True
        except Exception as exc:
            logger.warning("Redis cache failed: %s", exc)

    logger.info(
        "Ingested event %s for account %s → risk_score=%.4f (pg=%s, kafka=%s, cache=%s)",
        event.event_id, event.src_account, feature_vector.risk_score,
        pg_stored, kafka_published, cached,
    )

    return IngestResponse(
        event_id=event.event_id,
        risk_score=feature_vector.risk_score,
        feature_vector=feature_vector,
        kafka_published=kafka_published,
        pg_stored=pg_stored,
        cached=cached,
    )


# --------------------------------------------------------------------------- #
#  GET /internal/txn/history/{account_id}
# --------------------------------------------------------------------------- #

@router.get(
    "/internal/txn/history/{account_id}",
    response_model=TransactionHistoryResponse,
    summary="Get 30-day transaction history for an account",
    tags=["Transactions"],
)
async def get_transaction_history(account_id: str) -> TransactionHistoryResponse:
    """
    Query PostgreSQL for the 30-day transaction window for the given account.
    Falls back to in-memory store if PG is unavailable.
    """
    from main import _pg_pool

    transactions: list[TransactionHistory] = []
    cutoff = datetime.utcnow() - timedelta(days=settings.HISTORY_DAYS)

    if _pg_pool is not None:
        try:
            async with _pg_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT event_id, src_account, dst_account, amount_paise, rail, timestamp
                    FROM transactions
                    WHERE src_account = $1 AND timestamp > $2
                    ORDER BY timestamp DESC
                    LIMIT 500
                    """,
                    account_id, cutoff,
                )
                for row in rows:
                    transactions.append(TransactionHistory(
                        txn_id=row["event_id"],
                        src_account=row["src_account"],
                        dst_account=row["dst_account"],
                        amount_paise=row["amount_paise"],
                        rail=row["rail"],
                        timestamp=row["timestamp"],
                    ))
        except Exception as exc:
            logger.warning("PG history query failed, using in-memory: %s", exc)
            transactions = _build_history_from_memory(account_id, cutoff)
    else:
        transactions = _build_history_from_memory(account_id, cutoff)

    return TransactionHistoryResponse(
        account_id=account_id,
        transactions=transactions,
        total_count=len(transactions),
        window_days=settings.HISTORY_DAYS,
    )


def _build_history_from_memory(account_id: str, cutoff: datetime) -> list[TransactionHistory]:
    """Build transaction history from in-memory store."""
    records = _in_memory_store.get(account_id, [])
    result = []
    for r in records:
        if r["timestamp"] >= cutoff:
            result.append(TransactionHistory(
                txn_id=r["event_id"],
                src_account=r["src_account"],
                dst_account=r["dst_account"],
                amount_paise=r["amount_paise"],
                rail=r["rail"],
                timestamp=r["timestamp"],
            ))
    return list(reversed(result))  # newest first


# --------------------------------------------------------------------------- #
#  POST /internal/txn/batch-features
# --------------------------------------------------------------------------- #

@router.post(
    "/internal/txn/batch-features",
    response_model=BatchFeatureResponse,
    summary="Batch feature extraction for up to 1000 events",
    tags=["Transactions"],
)
async def batch_features(batch: BatchFeatureMatrix) -> BatchFeatureResponse:
    """
    Extract features for a batch of up to 1000 raw events.
    Does NOT persist or publish — use /ingest for that.
    """
    if len(batch.events) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size exceeds 1000-event limit",
        )

    features: list[FeatureVector] = []
    failed = 0

    for event in batch.events:
        try:
            current_ts = event.timestamp or datetime.utcnow()
            history_timestamps, history_amounts, history_receivers, last_lat, last_lon = (
                _get_account_history(event.src_account)
            )
            device_first_seen = _in_memory_devices.get(event.device_fingerprint)

            feature_dict = build_feature_vector_from_history(
                event_id=event.event_id,
                src_account=event.src_account,
                amount_paise=event.amount_paise,
                current_ts=current_ts,
                lat=event.lat,
                lon=event.lon,
                device_fingerprint=event.device_fingerprint,
                history_timestamps=history_timestamps,
                history_amounts=history_amounts,
                history_receivers=history_receivers,
                dst_account=event.dst_account,
                last_lat=last_lat,
                last_lon=last_lon,
                device_first_seen=device_first_seen,
            )
            features.append(FeatureVector(**feature_dict))
        except Exception as exc:
            logger.warning("Batch feature extraction failed for event %s: %s", event.event_id, exc)
            failed += 1

    return BatchFeatureResponse(
        features=features,
        processed_count=len(features),
        failed_count=failed,
    )


# --------------------------------------------------------------------------- #
#  GET /health
# --------------------------------------------------------------------------- #

@router.get("/health", summary="Health check", tags=["System"])
async def health_check() -> dict:
    """Report health status and dependency connectivity."""
    from main import _pg_pool, _redis, _kafka_producer, _app_start_time

    deps = {}

    # PG check
    if _pg_pool is not None:
        try:
            async with _pg_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            deps["postgresql"] = "healthy"
        except Exception:
            deps["postgresql"] = "unhealthy"
    else:
        deps["postgresql"] = "not_configured"

    # Redis check
    if _redis is not None:
        try:
            await _redis.ping()
            deps["redis"] = "healthy"
        except Exception:
            deps["redis"] = "unhealthy"
    else:
        deps["redis"] = "not_configured"

    # Kafka check
    if _kafka_producer is not None:
        try:
            _kafka_producer.poll(0)
            deps["kafka"] = "healthy"
        except Exception:
            deps["kafka"] = "unhealthy"
    else:
        deps["kafka"] = "not_configured"

    overall = "healthy" if all(v == "healthy" for v in deps.values() if v != "not_configured") else "degraded"

    return {
        "service": "kavalx-transaction-intelligence",
        "status": overall,
        "version": settings.APP_VERSION,
        "uptime_seconds": round(time.time() - _app_start_time, 2),
        "in_memory_accounts": len(_in_memory_store),
        "dependencies": deps,
    }
