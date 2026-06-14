"""OSINT Fusion Service — routes and main app."""
from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timedelta

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models import (
    DarkWebAlert, EarlyWarning, GitHubSecretAlert, TelegramAlert,
    ThreatFeed, ThreatIndicator,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Kavalx OSINT Fusion", version="1.0.0",
              description="Dark web monitoring, Telegram scanning, GitHub secret detection, STIX feed ingestion")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ───── Mock Threat Data ─────
_SOURCES = ["darkweb", "telegram", "github", "stix"]
_TYPES = ["ip", "domain", "hash", "credential", "card_bin"]
_threat_store: list[ThreatIndicator] = []


def _generate_mock_indicators():
    """Generate realistic mock threat indicators."""
    if _threat_store:
        return
    samples = [
        ThreatIndicator(indicator_type="credential", value="user1234@hdfc***", source="darkweb",
                        severity=5, first_seen=datetime.utcnow() - timedelta(hours=2),
                        raw_context="Credential bundle for HDFC net banking found on Exploit.in forum, includes 2FA bypass method",
                        geo_info={"country": "RU", "city": "Moscow"}),
        ThreatIndicator(indicator_type="card_bin", value="4367-26XX-XXXX-XXXX", source="darkweb",
                        severity=4, first_seen=datetime.utcnow() - timedelta(hours=5),
                        raw_context="Batch of 500 SBI debit card numbers listed for sale at $15/card",
                        geo_info={"country": "UA", "city": "Kyiv"}),
        ThreatIndicator(indicator_type="hash", value="a3f2b8c9d1e4f7g8h2i5j3k6l9m1n4o7", source="stix",
                        severity=5, first_seen=datetime.utcnow() - timedelta(hours=1),
                        raw_context="SHA-256 hash of BankBot v4.2 variant targeting Indian UPI apps (CERT-In advisory CIAD-2024-0089)"),
        ThreatIndicator(indicator_type="domain", value="hdfc-secure-login.xyz", source="stix",
                        severity=4, first_seen=datetime.utcnow() - timedelta(hours=8),
                        raw_context="Phishing domain mimicking HDFC Bank login page, SSL cert issued 6h ago"),
        ThreatIndicator(indicator_type="ip", value="185.220.101.42", source="darkweb",
                        severity=3, first_seen=datetime.utcnow() - timedelta(hours=12),
                        raw_context="C2 server for Anubis banking trojan campaign targeting Indian banks",
                        geo_info={"country": "NL", "asn": "AS60729"}),
        ThreatIndicator(indicator_type="credential", value="admin@***.sbi.co.in:P@ss***", source="telegram",
                        severity=5, first_seen=datetime.utcnow() - timedelta(minutes=30),
                        raw_context="SBI internal credentials posted in Telegram channel 'BankLeaks_IN' (180K subscribers)"),
        ThreatIndicator(indicator_type="hash", value="e7d2f1a3b5c8d0e2f4a6b8c1d3e5f7a9", source="github",
                        severity=3, first_seen=datetime.utcnow() - timedelta(hours=3),
                        raw_context="API key for payment gateway found in public GitHub repo (truffleHog detection)"),
        ThreatIndicator(indicator_type="ip", value="103.152.220.18", source="stix",
                        severity=4, first_seen=datetime.utcnow() - timedelta(hours=6),
                        raw_context="SMS phishing campaign origin server targeting Indian mobile numbers",
                        geo_info={"country": "IN", "state": "Delhi"}),
        ThreatIndicator(indicator_type="domain", value="paytm-rewards-claim.com", source="telegram",
                        severity=4, first_seen=datetime.utcnow() - timedelta(hours=4),
                        raw_context="Paytm phishing kit being distributed via WhatsApp groups, found in Telegram fraud channel"),
        ThreatIndicator(indicator_type="credential", value="UPI:victim@oksbi (OTP kit)", source="darkweb",
                        severity=5, first_seen=datetime.utcnow() - timedelta(minutes=45),
                        raw_context="Complete UPI fraud kit with OTP interception tool, priced at ₹5000 on dark web marketplace"),
        ThreatIndicator(indicator_type="card_bin", value="5241-07XX (ICICI Plat)", source="darkweb",
                        severity=4, first_seen=datetime.utcnow() - timedelta(hours=7),
                        raw_context="ICICI Bank platinum card BIN dump, 200 cards, includes CVV and expiry"),
        ThreatIndicator(indicator_type="ip", value="45.153.243.99", source="stix",
                        severity=3, first_seen=datetime.utcnow() - timedelta(hours=18),
                        raw_context="Tor exit node associated with banking fraud reconnaissance",
                        geo_info={"country": "DE", "asn": "AS24940"}),
    ]
    _threat_store.extend(samples)

_generate_mock_indicators()


@app.get("/internal/osint/feed", response_model=ThreatFeed)
async def get_threat_feed(
    source: str | None = Query(None, description="Filter by source"),
    severity_min: int = Query(1, ge=1, le=5),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get current threat indicator feed."""
    filtered = _threat_store
    if source:
        filtered = [t for t in filtered if t.source == source]
    filtered = [t for t in filtered if t.severity >= severity_min]
    filtered.sort(key=lambda x: x.first_seen, reverse=True)
    page = filtered[offset:offset + limit]
    return ThreatFeed(indicators=page, total=len(filtered),
                      last_updated=datetime.utcnow())


@app.get("/internal/osint/indicators/{indicator_hash}")
async def get_indicator(indicator_hash: str):
    """Get specific indicator by hash or value fragment."""
    for ind in _threat_store:
        if indicator_hash in ind.value or indicator_hash in (ind.raw_context or ""):
            return ind
    return {"error": "Indicator not found"}


@app.post("/internal/osint/scan/trigger")
async def trigger_scan(source: str = Query("all")):
    """Trigger manual scan."""
    logger.info(f"Manual scan triggered for source: {source}")
    # Simulate finding a new indicator
    new = ThreatIndicator(
        indicator_type=random.choice(_TYPES), value=f"scan_{int(time.time())}",
        source=source if source != "all" else random.choice(_SOURCES),
        severity=random.randint(2, 5), first_seen=datetime.utcnow(),
        raw_context=f"Indicator discovered during manual {source} scan at {datetime.utcnow().isoformat()}",
    )
    _threat_store.append(new)
    return {"status": "scan_initiated", "source": source, "new_indicator": new}


@app.get("/internal/osint/early-warnings", response_model=list[EarlyWarning])
async def get_early_warnings():
    """Get active early warning alerts."""
    warnings = []
    # Check for credential bundles (high-urgency early warning)
    cred_indicators = [t for t in _threat_store if t.indicator_type == "credential" and t.severity >= 4]
    if cred_indicators:
        hours_since = min((datetime.utcnow() - t.first_seen).total_seconds() / 3600 for t in cred_indicators)
        warnings.append(EarlyWarning(
            threat_type="Credential Bundle Attack",
            confidence=0.87,
            estimated_hours_until_attack=max(0.5, 24 - hours_since * 3),
            matching_indicators=[t.value for t in cred_indicators[:5]],
        ))
    # Check for phishing domains
    phishing = [t for t in _threat_store if t.indicator_type == "domain" and t.severity >= 3]
    if phishing:
        warnings.append(EarlyWarning(
            threat_type="Phishing Campaign",
            confidence=0.72,
            estimated_hours_until_attack=random.uniform(6, 48),
            matching_indicators=[t.value for t in phishing[:5]],
        ))
    return warnings


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME,
            "total_indicators": len(_threat_store)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
