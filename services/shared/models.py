"""
Kavalx Shared Pydantic Models
===============================

Canonical data models shared across all microservices.  Every model is
immutable (frozen) where appropriate and uses strict validation to catch
data-quality issues at the boundary.

Usage:
    from services.shared.models import TransactionEvent, VerdictOutput
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


# ── Enums ──────────────────────────────────────────────────


class AccountType(str, Enum):
    """Mirror of PostgreSQL account_type_enum."""
    SAVINGS = "savings"
    CURRENT = "current"
    WALLET = "wallet"


class Rail(str, Enum):
    """Mirror of PostgreSQL rail_enum."""
    UPI = "UPI"
    IMPS = "IMPS"
    NEFT = "NEFT"
    RTGS = "RTGS"


class Verdict(str, Enum):
    """Mirror of PostgreSQL verdict_enum."""
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"
    FREEZE = "freeze"


class APKVerdict(str, Enum):
    """Mirror of PostgreSQL apk_verdict_enum."""
    BENIGN = "benign"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


# ── Transaction Models ─────────────────────────────────────


class TransactionEvent(BaseModel):
    """Raw transaction ingested from payment rails (Kafka: kaval.txn.raw)."""

    txn_id: UUID = Field(default_factory=uuid4, description="Unique transaction ID.")
    src_account: UUID = Field(..., description="Source account UUID.")
    dst_account: UUID = Field(..., description="Destination account UUID.")
    amount_paise: int = Field(..., gt=0, description="Amount in paise (positive).")
    rail: Rail = Field(..., description="Payment rail used.")
    initiated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the txn was initiated.",
    )
    device_fingerprint: Optional[str] = Field(
        default=None, max_length=64, description="SHA-256 device fingerprint."
    )
    ip_hash: Optional[str] = Field(
        default=None, max_length=64, description="SHA-256 of originating IP."
    )
    lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    lon: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary key-value metadata."
    )

    @field_validator("amount_paise")
    @classmethod
    def amount_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount_paise must be a positive integer")
        return v


class ScoredTransaction(BaseModel):
    """Transaction enriched with ML risk scores (Kafka: kaval.txn.scored)."""

    txn_id: UUID
    src_account: UUID
    dst_account: UUID
    amount_paise: int = Field(..., gt=0)
    rail: Rail
    initiated_at: datetime

    # ML scores
    tgn_risk_score: float = Field(
        ..., ge=0.0, le=1.0, description="Temporal Graph Network risk score."
    )
    bio_trust_score: float = Field(
        ..., ge=0.0, le=1.0, description="Biometric trust score."
    )
    ensemble_score: float = Field(
        ..., ge=0.0, le=1.0, description="Fused risk score from all models."
    )

    # Feature context
    feature_vector: Optional[List[float]] = Field(
        default=None, description="Feature vector used for scoring."
    )
    device_fingerprint: Optional[str] = None
    ip_hash: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class AccountRiskProfile(BaseModel):
    """Aggregated risk profile for a single account."""

    account_id: UUID
    bank_code: str = Field(..., min_length=4, max_length=4)
    upi_id: Optional[str] = None
    account_type: Optional[AccountType] = None
    kyc_tier: int = Field(default=1, ge=1, le=4)
    risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_updated_at: Optional[datetime] = None
    is_frozen: bool = False
    total_txn_count_24h: int = Field(default=0, ge=0)
    total_amount_24h_paise: int = Field(default=0, ge=0)
    unique_counterparties_24h: int = Field(default=0, ge=0)
    graph_cluster_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── APK Analysis Models ────────────────────────────────────


class APKUpload(BaseModel):
    """APK binary submission for analysis (Kafka: kaval.apk.submitted)."""

    apk_id: UUID = Field(default_factory=uuid4)
    sha256: str = Field(
        ..., min_length=64, max_length=64,
        description="SHA-256 hex digest of the APK binary.",
    )
    package_name: Optional[str] = Field(
        default=None, max_length=200, description="Android package name."
    )
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    file_size_bytes: Optional[int] = Field(default=None, ge=0)
    submitter_id: Optional[str] = Field(
        default=None, description="ID of the user or system that submitted the APK."
    )

    @field_validator("sha256")
    @classmethod
    def sha256_must_be_hex(cls, v: str) -> str:
        v_lower = v.lower()
        if not all(c in "0123456789abcdef" for c in v_lower):
            raise ValueError("sha256 must be a valid hex string")
        return v_lower


class APKThreatReport(BaseModel):
    """Complete APK analysis results persisted to apk_threats table."""

    apk_id: UUID
    sha256: str = Field(..., min_length=64, max_length=64)
    package_name: Optional[str] = None
    submitted_at: datetime

    # Scores
    static_score: float = Field(..., ge=0.0, le=1.0)
    dynamic_score: float = Field(..., ge=0.0, le=1.0)
    meta_score: float = Field(..., ge=0.0, le=1.0)

    # GenAI analysis
    genai_intent: Optional[str] = Field(
        default=None,
        description="LLM-generated summary of decompiled APK intent.",
    )

    # Verdict
    verdict: APKVerdict
    shap_features: Dict[str, float] = Field(
        default_factory=dict,
        description="SHAP feature-importance values explaining the verdict.",
    )
    sandbox_log_path: Optional[str] = None


# ── Verdict / AMADP Models ─────────────────────────────────


class AMADPAgentResult(BaseModel):
    """Result from a single AMADP tribunal agent (prosecutor/defender/judge)."""

    role: str = Field(
        ..., description="Agent role: 'prosecution', 'defense', or 'judge'."
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., description="Natural-language reasoning chain.")
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="List of evidence identifiers cited.",
    )


class VerdictOutput(BaseModel):
    """Final AMADP tribunal verdict (Kafka: kaval.verdict.final)."""

    verdict_id: UUID = Field(default_factory=uuid4)
    txn_id: UUID
    amadp_transcript: Dict[str, Any] = Field(
        ..., description="Full AMADP debate transcript as JSON."
    )
    reasoning_dag_id: Optional[str] = Field(
        default=None, max_length=64,
        description="DAG identifier for the reasoning trace.",
    )

    # Confidence scores
    prosecution_conf: float = Field(..., ge=0.0, le=1.0)
    defense_conf: float = Field(..., ge=0.0, le=1.0)
    judge_conf: float = Field(..., ge=0.0, le=1.0)

    # Final decision
    final_action: str = Field(
        ..., max_length=20,
        description="Final action: allow, review, block, freeze.",
    )

    # Cryptographic anchoring
    pqc_signature: Optional[bytes] = Field(
        default=None,
        description="Dilithium PQC signature over the verdict payload.",
    )
    ledger_tx_id: Optional[str] = Field(
        default=None, max_length=128,
        description="Hyperledger Fabric transaction hash.",
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    analyst_override: bool = Field(
        default=False,
        description="Whether a human analyst overrode the automated verdict.",
    )

    # Helper: per-agent breakdown
    agent_results: Optional[List[AMADPAgentResult]] = Field(
        default=None,
        description="Individual agent result breakdowns.",
    )


# ── OSINT Models ───────────────────────────────────────────


class OSINTAlert(BaseModel):
    """OSINT alert from dark-web / Telegram monitoring (Kafka: kaval.alert.osint)."""

    alert_id: UUID = Field(default_factory=uuid4)
    source: str = Field(
        ..., description="Source channel: 'telegram', 'darkweb', 'misp', 'manual'."
    )
    severity: int = Field(
        ..., ge=0, le=4,
        description="0=info, 1=low, 2=medium, 3=high, 4=critical.",
    )
    title: str = Field(..., max_length=300)
    body: str = Field(..., description="Alert body / extracted text.")
    indicators: List[str] = Field(
        default_factory=list,
        description="IOCs: UPI IDs, phone numbers, IPs, hashes, etc.",
    )
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    raw_url: Optional[str] = None


# ── Federated Learning Models ──────────────────────────────


class FLGradientPayload(BaseModel):
    """Gradient exchange for federated learning (Kafka: kaval.fl.gradients)."""

    round_id: int = Field(..., ge=0, description="Current FL training round.")
    participant_id: str = Field(..., description="Bank / node identifier.")
    model_version: str = Field(..., description="Model version being trained.")
    gradient_checksum: str = Field(
        ..., description="SHA-256 of the serialized gradient tensor."
    )
    gradient_path: str = Field(
        ..., description="Object-store path to the gradient file."
    )
    num_samples: int = Field(..., ge=1, description="Samples used in this round.")
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
