"""
Kavalx API Gateway - Pydantic Models
Defines request/response schemas for all gateway-facing endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
import uuid
from datetime import datetime


# --------------------------------------------------------------------------- #
#  Enums
# --------------------------------------------------------------------------- #

class RailType(str, Enum):
    """Payment rail types supported by Kavalx."""
    UPI = "UPI"
    IMPS = "IMPS"
    NEFT = "NEFT"
    RTGS = "RTGS"


class Verdict(str, Enum):
    """Fraud verdict categories."""
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class OverrideAction(str, Enum):
    """Actions an analyst can take on a verdict."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class APKVerdict(str, Enum):
    """APK threat classification."""
    CLEAN = "CLEAN"
    SUSPICIOUS = "SUSPICIOUS"
    MALICIOUS = "MALICIOUS"


# --------------------------------------------------------------------------- #
#  Transaction Scoring
# --------------------------------------------------------------------------- #

class TransactionScoreRequest(BaseModel):
    """Inbound transaction to be scored for fraud risk."""
    src_account: str = Field(..., description="Source account identifier")
    dst_account: str = Field(..., description="Destination account identifier")
    amount_paise: int = Field(..., gt=0, description="Amount in paise (1 INR = 100 paise)")
    rail: RailType = Field(..., description="Payment rail type")
    device_fingerprint: str = Field(..., description="Device fingerprint hash")
    ip_hash: str = Field(..., description="Hashed IP address")
    lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude")
    lon: Optional[float] = Field(None, ge=-180, le=180, description="Longitude")


class TransactionScoreResponse(BaseModel):
    """Scored transaction returned by the gateway."""
    txn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Composite fraud risk 0-1")
    verdict: Verdict
    bio_trust: float = Field(0.5, ge=0.0, le=1.0, description="Biometric trust score")
    tgn_score: float = Field(0.5, ge=0.0, le=1.0, description="Temporal graph network score")
    scored_at: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------- #
#  Account Risk Profile
# --------------------------------------------------------------------------- #

class AccountRiskProfile(BaseModel):
    """Risk profile for a single account from the Graph Intelligence Service."""
    account_id: str
    risk_score: float = Field(0.0, ge=0.0, le=1.0)
    is_frozen: bool = False
    recent_txn_count: int = 0
    mule_cluster_id: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------- #
#  APK Analysis
# --------------------------------------------------------------------------- #

class APKSubmitResponse(BaseModel):
    """Response after submitting an APK for analysis."""
    apk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sha256: str
    verdict: APKVerdict = APKVerdict.CLEAN
    static_score: float = Field(0.0, ge=0.0, le=1.0)
    dynamic_score: float = Field(0.0, ge=0.0, le=1.0)
    meta_score: float = Field(0.0, ge=0.0, le=1.0)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------- #
#  Analyst Override
# --------------------------------------------------------------------------- #

class AnalystOverride(BaseModel):
    """Analyst override on a fraud verdict."""
    override_action: OverrideAction
    reason: str = Field(..., min_length=10, max_length=2000, description="Justification for override")
    analyst_id: str = Field(..., description="Analyst identifier")


class OverrideResponse(BaseModel):
    """Confirmation of an analyst override."""
    verdict_id: str
    override_action: OverrideAction
    analyst_id: str
    accepted: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --------------------------------------------------------------------------- #
#  Health
# --------------------------------------------------------------------------- #

class DependencyHealth(BaseModel):
    """Health of a single dependency."""
    name: str
    status: str  # "healthy" | "degraded" | "unhealthy"
    latency_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """Aggregated gateway health check response."""
    service: str = "kavalx-gateway"
    status: str = "healthy"
    version: str = "1.0.0"
    uptime_seconds: float = 0.0
    dependencies: list[DependencyHealth] = []


# --------------------------------------------------------------------------- #
#  Compliance
# --------------------------------------------------------------------------- #

class ComplianceReport(BaseModel):
    """Compliance report summary."""
    report_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_transactions: int = 0
    flagged_transactions: int = 0
    blocked_transactions: int = 0
    sar_filed: int = 0
    summary: str = ""
