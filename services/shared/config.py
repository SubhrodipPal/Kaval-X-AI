"""
Kavalx Shared Configuration
============================

Centralized settings loaded from environment variables using pydantic-settings.
All microservices import ``get_settings()`` to obtain a cached, validated
configuration singleton.

Usage:
    from services.shared.config import get_settings

    settings = get_settings()
    print(settings.pg_dsn)
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Security ───────────────────────────────────────────
    jwt_secret: str = Field(
        ...,
        min_length=32,
        description="HMAC secret for JWT signing (min 32 chars).",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm.")
    jwt_expiry_minutes: int = Field(
        default=60, ge=1, description="JWT token lifetime in minutes."
    )
    api_key_salt: str = Field(
        ...,
        min_length=16,
        description="Salt used for hashing API keys at rest.",
    )

    # ── PostgreSQL ─────────────────────────────────────────
    pg_dsn: str = Field(
        default="postgresql://kavalx:kavalx@postgres:5432/kavalx",
        description="PostgreSQL connection string.",
    )
    pg_pool_min: int = Field(default=2, ge=1)
    pg_pool_max: int = Field(default=20, ge=2)

    # ── Memgraph ───────────────────────────────────────────
    memgraph_url: str = Field(
        default="bolt://memgraph:7687",
        description="Memgraph Bolt connection URL.",
    )

    # ── Redis ──────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://redis:6379/0",
        description="Redis connection URL.",
    )
    redis_max_connections: int = Field(default=50, ge=5)

    # ── Kafka ──────────────────────────────────────────────
    kafka_brokers: str = Field(
        default="kafka:9092",
        description="Comma-separated Kafka bootstrap servers.",
    )

    @property
    def kafka_broker_list(self) -> List[str]:
        """Return broker addresses as a list."""
        return [b.strip() for b in self.kafka_brokers.split(",") if b.strip()]

    # ── Milvus ─────────────────────────────────────────────
    milvus_host: str = Field(default="milvus")
    milvus_port: int = Field(default=19530, ge=1, le=65535)

    # ── ML Serving ─────────────────────────────────────────
    torchserve_url: str = Field(
        default="http://torchserve:8080",
        description="TorchServe inference endpoint.",
    )
    vllm_url: str = Field(
        default="http://vllm:8090",
        description="vLLM inference endpoint.",
    )
    tflite_model_path: str = Field(
        default="/models/pinn_bio.tflite",
        description="Path to the TFLite PINN biometric model.",
    )

    # ── Post-Quantum Cryptography ──────────────────────────
    pqc_key_path: str = Field(
        default="/keys/dilithium_private.key",
        description="Path to the Dilithium private key.",
    )

    # ── Hyperledger Fabric ─────────────────────────────────
    fabric_peer_url: str = Field(
        default="grpc://fabric-peer:7051",
        description="Hyperledger Fabric peer gRPC endpoint.",
    )

    # ── External Services ──────────────────────────────────
    indictrans_url: str = Field(
        default="http://indictrans:8070",
        description="IndicTrans translation service endpoint.",
    )
    tor_proxy: str = Field(
        default="socks5h://tor:9050",
        description="Tor SOCKS5 proxy for dark-web OSINT.",
    )
    telegram_api_id: Optional[str] = Field(
        default=None,
        description="Telegram API ID for channel monitoring.",
    )
    misp_url: str = Field(
        default="https://misp.local",
        description="MISP threat intelligence platform URL.",
    )

    # ── Datalog / Compliance ───────────────────────────────
    datalog_rules_path: str = Field(
        default="/rules/rbi_ontology.dl",
        description="Path to the Soufflé Datalog rules file.",
    )

    # ── Validators ─────────────────────────────────────────
    @field_validator("pg_dsn")
    @classmethod
    def validate_pg_dsn(cls, v: str) -> str:
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("pg_dsn must start with 'postgresql://' or 'postgres://'")
        return v

    @field_validator("memgraph_url")
    @classmethod
    def validate_memgraph_url(cls, v: str) -> str:
        if not v.startswith("bolt://"):
            raise ValueError("memgraph_url must start with 'bolt://'")
        return v

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("redis_url must start with 'redis://' or 'rediss://'")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Uses ``lru_cache`` so the environment is read exactly once per process.
    Call ``get_settings.cache_clear()`` in tests to reload.
    """
    return Settings()  # type: ignore[call-arg]
