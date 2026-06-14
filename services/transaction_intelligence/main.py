"""
Kavalx Transaction Intelligence Service - Application Entry Point
FastAPI app with PostgreSQL, Redis, and Kafka lifecycle management.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from config import settings

# --------------------------------------------------------------------------- #
#  Logging
# --------------------------------------------------------------------------- #

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("kavalx.tis")

# --------------------------------------------------------------------------- #
#  Module-level state
# --------------------------------------------------------------------------- #

_pg_pool = None
_redis = None
_kafka_producer = None
_app_start_time: float = time.time()

# --------------------------------------------------------------------------- #
#  Lifespan
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown of PG pool, Redis, and Kafka producer."""
    global _pg_pool, _redis, _kafka_producer, _app_start_time
    _app_start_time = time.time()

    # --- PostgreSQL ---------------------------------------------------------
    try:
        import asyncpg
        _pg_pool = await asyncpg.create_pool(
            dsn=settings.PG_DSN,
            min_size=settings.PG_MIN_POOL,
            max_size=settings.PG_MAX_POOL,
            command_timeout=10,
        )
        # Ensure transactions table exists
        async with _pg_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    event_id TEXT PRIMARY KEY,
                    src_account TEXT NOT NULL,
                    dst_account TEXT NOT NULL,
                    amount_paise BIGINT NOT NULL,
                    rail TEXT NOT NULL,
                    device_fingerprint TEXT,
                    ip_hash TEXT,
                    lat DOUBLE PRECISION,
                    lon DOUBLE PRECISION,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_txn_src_ts ON transactions (src_account, timestamp);
                CREATE INDEX IF NOT EXISTS idx_txn_device ON transactions (device_fingerprint);
            """)
        logger.info("PostgreSQL pool created (%d-%d connections)", settings.PG_MIN_POOL, settings.PG_MAX_POOL)
    except Exception as exc:
        logger.warning("PostgreSQL unavailable (%s) — using in-memory store", exc)
        _pg_pool = None

    # --- Redis ---------------------------------------------------------------
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=3)
        await _redis.ping()
        logger.info("Connected to Redis at %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — caching disabled", exc)
        _redis = None

    # --- Kafka ---------------------------------------------------------------
    try:
        from confluent_kafka import Producer
        _kafka_producer = Producer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP,
            "client.id": "kavalx-tis",
            "acks": "all",
            "retries": 3,
            "retry.backoff.ms": 200,
        })
        # Quick connectivity check
        _kafka_producer.poll(0)
        logger.info("Kafka producer initialised (bootstrap: %s)", settings.KAFKA_BOOTSTRAP)
    except Exception as exc:
        logger.warning("Kafka unavailable (%s) — publishing disabled", exc)
        _kafka_producer = None

    yield

    # --- Shutdown ------------------------------------------------------------
    if _kafka_producer is not None:
        _kafka_producer.flush(timeout=5)
        logger.info("Kafka producer flushed")
    if _redis is not None:
        await _redis.aclose()
        logger.info("Redis connection closed")
    if _pg_pool is not None:
        await _pg_pool.close()
        logger.info("PostgreSQL pool closed")


# --------------------------------------------------------------------------- #
#  App
# --------------------------------------------------------------------------- #

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Ingests UPI/IMPS/NEFT events, extracts features, publishes to scoring queue.",
    lifespan=lifespan,
)

from routes import router  # noqa: E402
app.include_router(router)

logger.info("Kavalx TIS ready — %s v%s", settings.APP_NAME, settings.APP_VERSION)
