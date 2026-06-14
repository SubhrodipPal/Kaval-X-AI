"""
Compliance Engine — Pydantic Models
Data structures for compliance reports, ledger entries, and queues.
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

class ReportType(str, Enum):
    RBI_INCIDENT = "rbi_incident"
    CERT_IN_ADVISORY = "cert_in_advisory"


class ReportStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    SIGNED = "signed"
    FAILED = "failed"


class ReportLanguage(str, Enum):
    EN = "en"
    HI = "hi"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

class ComplianceReport(BaseModel):
    """A generated compliance report (RBI incident or CERT-In advisory)."""
    report_id: str = Field(default_factory=lambda: f"RPT-{uuid.uuid4().hex[:10].upper()}")
    txn_id: str = ""
    verdict_id: str = ""
    report_type: ReportType
    status: ReportStatus = ReportStatus.PENDING
    generated_at: datetime | None = None
    signed_at: datetime | None = None
    pdf_path: str = ""
    pqc_signature_hex: str = ""
    ledger_tx_id: str = ""
    language: ReportLanguage = ReportLanguage.EN
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReportRequest(BaseModel):
    """Request to generate a compliance report."""
    verdict_id: str
    report_type: ReportType = ReportType.RBI_INCIDENT
    language: ReportLanguage = ReportLanguage.EN
    include_reasoning_dag: bool = True
    txn_id: str = ""
    txn_data: dict[str, Any] = Field(default_factory=dict)
    verdict_data: dict[str, Any] = Field(default_factory=dict)


class ReportQueue(BaseModel):
    """Summary of the report generation queue."""
    reports: list[ComplianceReport]
    total_pending: int
    total_completed: int
    total_signed: int


class LedgerEntry(BaseModel):
    """Blockchain ledger anchoring record."""
    entry_id: str = Field(default_factory=lambda: f"LED-{uuid.uuid4().hex[:10].upper()}")
    report_id: str
    tx_hash: str = ""
    block_number: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    verification_status: VerificationStatus = VerificationStatus.PENDING


class ReportSignRequest(BaseModel):
    """Request to PQC-sign a report."""
    signer_id: str = "compliance-officer"
    reason: str = "routine-signing"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Standard health-check response."""
    service: str
    status: str = "healthy"
    version: str
    pending_reports: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
