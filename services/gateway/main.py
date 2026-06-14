"""
Kavalx API Gateway - Application Entry Point
FastAPI app with CORS, OpenTelemetry, Redis-based rate limiting, JWT auth.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings

# --------------------------------------------------------------------------- #
#  Logging
# --------------------------------------------------------------------------- #

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("kavalx.gateway")

# --------------------------------------------------------------------------- #
#  Module-level state (populated during lifespan)
# --------------------------------------------------------------------------- #

_redis: Optional[aioredis.Redis] = None
_http_client: Optional[httpx.AsyncClient] = None
_app_start_time: float = time.time()

# --------------------------------------------------------------------------- #
#  Lifespan
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown of shared resources."""
    global _redis, _http_client, _app_start_time
    _app_start_time = time.time()

    # --- Redis ---------------------------------------------------------------
    try:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        await _redis.ping()
        logger.info("Connected to Redis at %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — rate limiting disabled", exc)
        _redis = None

    # --- HTTPX ---------------------------------------------------------------
    _http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
    )
    logger.info("HTTPX async client initialised")

    # --- OpenTelemetry -------------------------------------------------------
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry tracing initialised")
    except Exception as exc:
        logger.warning("OpenTelemetry setup skipped: %s", exc)

    yield

    # --- Shutdown ------------------------------------------------------------
    if _http_client:
        await _http_client.aclose()
        logger.info("HTTPX client closed")
    if _redis:
        await _redis.aclose()
        logger.info("Redis connection closed")


# --------------------------------------------------------------------------- #
#  App
# --------------------------------------------------------------------------- #

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Kavalx fraud-detection API gateway — auth, rate-limiting, routing.",
    lifespan=lifespan,
)

# --- CORS -------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
#  Rate-Limiter Middleware (Redis sliding window)
# --------------------------------------------------------------------------- #

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next) -> Response:
    """
    Sliding-window rate limiter backed by Redis.
    Allows RATE_LIMIT_MAX_REQUESTS per RATE_LIMIT_WINDOW_SECONDS per client IP.
    Degrades gracefully if Redis is unavailable.
    """
    # Skip rate limiting for health endpoint
    if request.url.path == "/health":
        return await call_next(request)

    if _redis is None:
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    key = f"kavalx:ratelimit:{client_ip}"
    window = settings.RATE_LIMIT_WINDOW_SECONDS
    max_requests = settings.RATE_LIMIT_MAX_REQUESTS
    now = time.time()

    try:
        pipe = _redis.pipeline(transaction=True)
        # Remove entries outside the window
        await pipe.zremrangebyscore(key, 0, now - window)
        # Count current entries
        await pipe.zcard(key)
        # Add current request
        await pipe.zadd(key, {f"{now}:{id(request)}": now})
        # Set expiry on the key
        await pipe.expire(key, window + 1)
        results = await pipe.execute()

        current_count = results[1]

        if current_count >= max_requests:
            logger.warning("Rate limit exceeded for IP %s (%d/%d)", client_ip, current_count, max_requests)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after_seconds": window,
                },
                headers={"Retry-After": str(window)},
            )
    except Exception as exc:
        logger.warning("Rate limiter error (degrading gracefully): %s", exc)

    response = await call_next(request)

    # Add rate-limit headers
    response.headers["X-RateLimit-Limit"] = str(max_requests)
    response.headers["X-RateLimit-Window"] = str(window)
    return response


# --------------------------------------------------------------------------- #
#  Request-ID Middleware
# --------------------------------------------------------------------------- #

@app.middleware("http")
async def request_id_middleware(request: Request, call_next) -> Response:
    """Attach a unique request ID to every request/response cycle."""
    import uuid

    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# --------------------------------------------------------------------------- #
#  Mount Routes
# --------------------------------------------------------------------------- #

from routes import router  # noqa: E402

app.include_router(router)

logger.info("Kavalx API Gateway ready — %s v%s", settings.APP_NAME, settings.APP_VERSION)
