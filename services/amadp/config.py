"""
AMADP Orchestrator — Configuration
Adversarial Multi-Agent Debate Protocol settings.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    app_name: str = "AMADP Orchestrator"
    app_version: str = "1.0.0"
    debug: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Debate configuration
    max_debate_rounds: int = 3
    judge_threshold: float = 0.82
    disagreement_threshold: float = 0.15

    # LLM endpoints (for future integration)
    prosecution_llm_endpoint: str = "http://localhost:11434/api/generate"
    defense_llm_endpoint: str = "http://localhost:11434/api/generate"
    prosecution_model: str = "mistral:7b"
    defense_model: str = "mistral:7b"

    # Streaming
    sse_retry_timeout_ms: int = 3000

    # PQC Signing
    pqc_private_key_path: str = "keys/dilithium_private.pem"
    pqc_public_key_path: str = "keys/dilithium_public.pem"

    class Config:
        env_prefix = "AMADP_"
        env_file = ".env"


settings = Settings()
