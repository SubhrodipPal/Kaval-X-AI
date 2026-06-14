"""
Kavalx Transaction Intelligence Service - Configuration
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Configuration for the Transaction Intelligence Service."""

    APP_NAME: str = "Kavalx Transaction Intelligence"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # --- PostgreSQL ---
    PG_DSN: str = "postgresql://kavalx:kavalx@localhost:5432/kavalx_txn"
    PG_MIN_POOL: int = 5
    PG_MAX_POOL: int = 20

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/1"
    REDIS_RISK_TTL: int = 3600  # 1 hour

    # --- Kafka ---
    KAFKA_BOOTSTRAP: str = "localhost:9092"
    KAFKA_TOPIC_FEATURES: str = "kaval.txn.features"
    KAFKA_TOPIC_RAW: str = "kaval.txn.raw"

    # --- Feature Extraction ---
    VELOCITY_WINDOW_1H: int = 3600
    VELOCITY_WINDOW_24H: int = 86400
    HISTORY_DAYS: int = 30

    model_config = {"env_prefix": "KAVALX_TIS_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
