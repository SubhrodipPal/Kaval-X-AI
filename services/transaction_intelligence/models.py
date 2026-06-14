"""
Kavalx Transaction Intelligence Service - Pydantic Models
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime
import uuid


class RailType(str, Enum):
    UPI = "UPI"
    IMPS = "IMPS"
    NEFT = "NEFT"
    RTGS = "RTGS"


class RawUPIEvent(BaseModel):
    """Raw transaction event from the payment rail."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    src_account: str = Field(..., description="Source account identifier")
    dst_account: str = Field(..., description="Destination account identifier")
    amount_paise: int = Field(..., gt=0, description="Amount in paise")
    rail: RailType = RailType.UPI
    device_fingerprint: str = Field("", description="Device fingerprint hash")
    ip_hash: str = Field("", description="Hashed IP address")
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FeatureVector(BaseModel):
    """Extracted feature vector for a single transaction."""
    event_id: str
    src_account: str
    amount_log: float = Field(0.0, description="Log10 of amount in INR")
    time_delta: float = Field(0.0, description="Seconds since last txn by src_account")
    velocity_1h: int = Field(0, ge=0, description="Txn count in past 1 hour")
    velocity_24h: int = Field(0, ge=0, description="Txn count in past 24 hours")
    unique_receivers_1h: int = Field(0, ge=0, description="Unique receivers in past 1 hour")
    avg_amount_7d: float = Field(0.0, description="Average txn amount in past 7 days (INR)")
    stddev_amount_7d: float = Field(0.0, description="Std deviation of txn amounts in past 7 days")
    is_new_receiver: bool = Field(False, description="First time sending to this receiver")
    device_age_days: int = Field(0, ge=0, description="Days since first txn from this device")
    geo_distance_km: float = Field(0.0, ge=0.0, description="Haversine distance from last txn location")
    risk_score: float = Field(0.0, ge=0.0, le=1.0, description="Computed risk score")


class TransactionHistory(BaseModel):
    """Transaction history record for a single account."""
    txn_id: str
    src_account: str
    dst_account: str
    amount_paise: int
    rail: str
    timestamp: datetime
    risk_score: float = 0.0


class TransactionHistoryResponse(BaseModel):
    """Response for account transaction history."""
    account_id: str
    transactions: list[TransactionHistory] = []
    total_count: int = 0
    window_days: int = 30


class BatchFeatureMatrix(BaseModel):
    """Batch feature extraction request."""
    events: list[RawUPIEvent] = Field(..., max_length=1000)


class BatchFeatureResponse(BaseModel):
    """Batch feature extraction response."""
    features: list[FeatureVector]
    processed_count: int
    failed_count: int = 0


class IngestResponse(BaseModel):
    """Response after ingesting and scoring a single transaction."""
    event_id: str
    risk_score: float
    feature_vector: FeatureVector
    kafka_published: bool = False
    pg_stored: bool = False
    cached: bool = False
