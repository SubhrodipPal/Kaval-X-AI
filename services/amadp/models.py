"""
AMADP Orchestrator — Pydantic Models
Defines all data structures for the adversarial debate protocol.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentRole(str, Enum):
    PROSECUTION = "prosecution"
    DEFENSE = "defense"
    JUDGE = "judge"


class VerdictAction(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"
    FREEZE = "freeze"


class DebateStatus(str, Enum):
    ONGOING = "ongoing"
    COMPLETED = "completed"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class DeviceInfo(BaseModel):
    """Device fingerprint data."""
    device_id: str = ""
    device_type: str = "mobile"
    os: str = "Android 14"
    ip_address: str = "0.0.0.0"
    geo_lat: float = 0.0
    geo_lon: float = 0.0
    is_rooted: bool = False
    vpn_detected: bool = False
    emulator_detected: bool = False


class TransactionEvidence(BaseModel):
    """Complete evidence bundle for a single transaction under review."""
    txn_id: str = Field(default_factory=lambda: f"TXN-{uuid.uuid4().hex[:12].upper()}")
    txn_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw transaction payload (amount, sender, receiver, etc.)",
    )
    tgn_score: float = Field(0.0, ge=0.0, le=1.0, description="Temporal Graph Network anomaly score")
    bio_trust: float = Field(1.0, ge=0.0, le=1.0, description="Biometric trust score")
    apk_threat: float = Field(0.0, ge=0.0, le=1.0, description="APK threat intelligence score")
    graph_neighbors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="1-hop neighbours from the transaction graph",
    )
    device_info: DeviceInfo = Field(default_factory=DeviceInfo)
    additional_context: str = ""


# ---------------------------------------------------------------------------
# Debate models
# ---------------------------------------------------------------------------

class DebateMessage(BaseModel):
    """A single message emitted during a debate round."""
    agent: AgentRole
    round: int = Field(ge=1)
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DebateTranscript(BaseModel):
    """Full transcript of an adversarial debate."""
    verdict_id: str = Field(default_factory=lambda: f"VRD-{uuid.uuid4().hex[:12].upper()}")
    rounds: list[list[DebateMessage]] = Field(default_factory=list)
    status: DebateStatus = DebateStatus.ONGOING


class DebateConfig(BaseModel):
    """Tunable knobs for the debate engine."""
    max_rounds: int = 3
    judge_threshold: float = 0.82
    disagreement_threshold: float = 0.15


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class VerdictOutput(BaseModel):
    """Final verdict emitted after debate conclusion."""
    verdict_id: str
    txn_id: str
    verdict: VerdictAction
    confidence: float = Field(ge=0.0, le=1.0)
    prosecution_conf: float = Field(ge=0.0, le=1.0)
    defense_conf: float = Field(ge=0.0, le=1.0)
    judge_conf: float = Field(ge=0.0, le=1.0)
    reasoning_dag: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    action: str = ""
    pqc_signature_hex: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VerdictSignRequest(BaseModel):
    """Request to sign a verdict with PQC."""
    signer_id: str = "system"
    reason: str = "automated-signing"


class HealthResponse(BaseModel):
    """Standard health-check response."""
    service: str
    status: str = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
