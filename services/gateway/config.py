"""
Kavalx API Gateway - Configuration Module
Manages environment-driven settings for JWT, Redis, and internal service URLs.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Central configuration for the API Gateway."""

    # --- Application ---
    APP_NAME: str = "Kavalx API Gateway"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # --- JWT ---
    JWT_SECRET: str = "kavalx-super-secret-change-in-production-2024"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_MAX_REQUESTS: int = 100

    # --- Internal Service URLs ---
    TIS_URL: str = "http://localhost:8001"
    APK_URL: str = "http://localhost:8002"
    GIS_URL: str = "http://localhost:8003"
    BIO_URL: str = "http://localhost:8004"

    # --- OpenTelemetry ---
    OTEL_SERVICE_NAME: str = "kavalx-gateway"
    OTEL_EXPORTER_ENDPOINT: Optional[str] = None

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {"env_prefix": "KAVALX_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
