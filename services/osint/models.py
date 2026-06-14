"""
OSINT Fusion — Pydantic Models
Data structures for threat indicators, feeds, alerts, and early warnings.
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

class IndicatorType(str, Enum):
    IP = "ip"
    DOMAIN = "domain"
    HASH = "hash"
    CREDENTIAL = "credential"
    CARD_BIN = "card_bin"


class IndicatorSource(str, Enum):
    DARKWEB = "darkweb"
    TELEGRAM = "telegram"
    GITHUB = "github"
    STIX = "stix"


class ScanTarget(str, Enum):
    DARKWEB = "darkweb"
    TELEGRAM = "telegram"
    GITHUB = "github"
    ALL = "all"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

class ThreatIndicator(BaseModel):
    """A single indicator of compromise (IOC)."""
    indicator_id: str = Field(default_factory=lambda: f"IOC-{uuid.uuid4().hex[:10].upper()}")
    indicator_type: IndicatorType
    value: str
    source: IndicatorSource
    severity: int = Field(ge=1, le=5, description="1=informational, 5=critical")
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_context: str = ""
    geo_info: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)
    matched_accounts: list[str] = Field(default_factory=list)


class ThreatFeed(BaseModel):
    """Paginated collection of threat indicators."""
    indicators: list[ThreatIndicator]
    total: int
    page: int = 1
    page_size: int = 50
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EarlyWarning(BaseModel):
    """Proactive early-warning alert derived from IOC clustering."""
    warning_id: str = Field(default_factory=lambda: f"EW-{uuid.uuid4().hex[:8].upper()}")
    threat_type: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    estimated_hours_until_attack: float = Field(ge=0.0)
    matching_indicators: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True


# ---------------------------------------------------------------------------
# Alert subtypes
# ---------------------------------------------------------------------------

class DarkWebAlert(BaseModel):
    """Alert from dark web monitoring."""
    alert_id: str = Field(default_factory=lambda: f"DWA-{uuid.uuid4().hex[:8].upper()}")
    marketplace: str
    listing_title: str
    price_usd: float | None = None
    seller_reputation: str = ""
    raw_snippet: str = ""
    indicators: list[ThreatIndicator] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelegramAlert(BaseModel):
    """Alert from Telegram channel scanning."""
    alert_id: str = Field(default_factory=lambda: f"TGA-{uuid.uuid4().hex[:8].upper()}")
    channel_name: str
    message_text: str
    sender_username: str = ""
    indicators: list[ThreatIndicator] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GitHubSecretAlert(BaseModel):
    """Alert from GitHub secret/credential scanning."""
    alert_id: str = Field(default_factory=lambda: f"GHA-{uuid.uuid4().hex[:8].upper()}")
    repository: str
    file_path: str
    secret_type: str
    commit_sha: str = ""
    author: str = ""
    indicators: list[ThreatIndicator] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Request/Response helpers
# ---------------------------------------------------------------------------

class ScanTriggerRequest(BaseModel):
    """Request to trigger a manual scan."""
    target: ScanTarget
    keywords: list[str] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)


class ScanTriggerResponse(BaseModel):
    """Response after triggering a scan."""
    scan_id: str = Field(default_factory=lambda: f"SCAN-{uuid.uuid4().hex[:8].upper()}")
    target: ScanTarget
    status: str = "initiated"
    estimated_duration_seconds: int = 30
    message: str = ""


class HealthResponse(BaseModel):
    """Standard health-check response."""
    service: str
    status: str = "healthy"
    version: str
    total_indicators: int = 0
    active_warnings: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
