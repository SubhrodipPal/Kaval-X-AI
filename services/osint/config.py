"""
OSINT Fusion — Configuration
Dark web monitoring, Telegram scanning, GitHub secret detection settings.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "OSINT Fusion"
    app_version: str = "1.0.0"
    debug: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/1"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_indicators: str = "osint.indicators"
    kafka_consumer_group: str = "osint-fusion"

    # STIX/TAXII endpoints (simulated)
    taxii_server_url: str = "https://taxii.example.com/api/v21"
    taxii_collection_id: str = "collection-001"

    # Scan intervals (seconds)
    darkweb_scan_interval: int = 3600
    telegram_scan_interval: int = 1800
    github_scan_interval: int = 900

    # Alert thresholds
    early_warning_min_confidence: float = 0.70
    high_severity_threshold: int = 4

    class Config:
        env_prefix = "OSINT_"
        env_file = ".env"


settings = Settings()
