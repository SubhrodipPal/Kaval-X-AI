"""
OSINT Fusion — Utility Functions
Simulated threat indicator generation, STIX/TAXII parsing, IOC matching,
and indicator deduplication logic.
"""

from __future__ import annotations

import hashlib
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from models import (
    DarkWebAlert,
    EarlyWarning,
    GitHubSecretAlert,
    IndicatorSource,
    IndicatorType,
    TelegramAlert,
    ThreatIndicator,
)

logger = logging.getLogger("osint.utils")

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_indicators: dict[str, ThreatIndicator] = {}
_early_warnings: list[EarlyWarning] = []
_darkweb_alerts: list[DarkWebAlert] = []
_telegram_alerts: list[TelegramAlert] = []
_github_alerts: list[GitHubSecretAlert] = []


def get_all_indicators() -> dict[str, ThreatIndicator]:
    """Return the global indicator store."""
    return _indicators


def get_early_warnings() -> list[EarlyWarning]:
    """Return active early warnings."""
    return [w for w in _early_warnings if w.active]


# ---------------------------------------------------------------------------
# Simulated Threat Data Generators
# ---------------------------------------------------------------------------

_DARKWEB_MARKETPLACES = [
    "BreachForums", "RussianMarket", "DarkFox", "InTheBox", "BidenCash",
    "Exploit.in", "XSS.is", "BHF.io",
]

_TELEGRAM_CHANNELS = [
    "CARD_BINS_INDIA", "UPI_FRAUD_TOOLS", "BANK_LEAKS_2026",
    "MALWARE_AS_SERVICE", "CREDIT_DUMP_SHOP",
]

_GITHUB_REPOS = [
    "quick-upi-sdk/main", "payment-gateway-test/src", "bank-api-wrapper/config",
    "fintech-demo-app/env", "mobile-wallet-poc/secrets",
]

_INDIAN_CARD_BINS = [
    "411111", "431940", "524367", "545210", "402360",
    "436541", "521234", "414720", "450875", "524233",
]

_SUSPICIOUS_IPS = [
    "185.220.101.42", "91.219.236.136", "198.98.51.189",
    "45.33.32.156", "103.152.220.44", "194.26.135.89",
    "23.129.64.210", "171.25.193.78", "62.102.148.68",
    "185.56.80.65",
]

_MALWARE_HASHES = [
    "e99a18c428cb38d5f260853678922e03",
    "d41d8cd98f00b204e9800998ecf8427e",
    "5d41402abc4b2a76b9719d911017c592",
    "098f6bcd4621d373cade4e832627b4f6",
    "7c6a180b36896a6ba87e50c971c4862e",
]

_LEAKED_DOMAINS = [
    "icicibank.com", "hdfcbank.com", "sbi.co.in", "axisbank.com",
    "kotak.com", "yesbank.in", "paytm.com", "phonepe.com",
]


def _generate_indicator_hash(indicator_type: str, value: str) -> str:
    """Create a deterministic hash for deduplication."""
    return hashlib.sha256(f"{indicator_type}:{value}".encode()).hexdigest()[:16].upper()


def generate_darkweb_indicators(count: int = 5) -> list[ThreatIndicator]:
    """Simulate dark web monitoring results."""
    indicators: list[ThreatIndicator] = []
    marketplace = random.choice(_DARKWEB_MARKETPLACES)

    for _ in range(count):
        itype = random.choice([IndicatorType.CARD_BIN, IndicatorType.CREDENTIAL, IndicatorType.IP])

        if itype == IndicatorType.CARD_BIN:
            value = random.choice(_INDIAN_CARD_BINS)
            context = (
                f"[{marketplace}] Listing: 'Fresh India BINs — {value}xxxx — "
                f"Valid rate 85%+ — ₹{random.randint(200, 2000)}/card — "
                f"Batch of {random.randint(50, 5000)} cards — "
                f"Includes CVV, expiry, holder name, and billing ZIP. "
                f"Seller rating: {random.uniform(3.5, 4.9):.1f}/5 "
                f"({random.randint(100, 2000)} transactions)'"
            )
            severity = random.randint(4, 5)
            tags = ["card-dump", "indian-bins", "financial-fraud"]
        elif itype == IndicatorType.CREDENTIAL:
            domain = random.choice(_LEAKED_DOMAINS)
            value = f"leaked@{domain}"
            context = (
                f"[{marketplace}] Credential dump containing {random.randint(1000, 50000)} "
                f"entries for {domain}. Includes email:password pairs, some with "
                f"OTP bypass tokens. Source: database breach dated "
                f"{(datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))).strftime('%Y-%m-%d')}. "
                f"Seller claims 'fresh and untouched, not recycled from previous dumps.'"
            )
            severity = random.randint(3, 5)
            tags = ["credential-dump", "banking-creds", domain.split(".")[0]]
        else:
            value = random.choice(_SUSPICIOUS_IPS)
            context = (
                f"[{marketplace}] C2 infrastructure IP observed in discussion about "
                f"targeting Indian banking apps. Associated with Drinik malware variant. "
                f"Active since {(datetime.now(timezone.utc) - timedelta(days=random.randint(1, 14))).strftime('%Y-%m-%d')}."
            )
            severity = random.randint(3, 4)
            tags = ["c2-infrastructure", "banking-malware", "drinik"]

        indicator = ThreatIndicator(
            indicator_type=itype,
            value=value,
            source=IndicatorSource.DARKWEB,
            severity=severity,
            raw_context=context,
            geo_info={"country": random.choice(["RU", "UA", "CN", "NG", "IN", "US"])},
            tags=tags,
        )
        indicators.append(indicator)

        # Generate alert
        _darkweb_alerts.append(DarkWebAlert(
            marketplace=marketplace,
            listing_title=f"India Banking {itype.value.upper()} — {value[:20]}",
            price_usd=random.uniform(5, 500),
            seller_reputation=f"{random.uniform(3.0, 5.0):.1f}/5",
            raw_snippet=context[:200],
            indicators=[indicator],
        ))

    return indicators


def generate_telegram_indicators(count: int = 4) -> list[ThreatIndicator]:
    """Simulate Telegram channel scanning results."""
    indicators: list[ThreatIndicator] = []

    for _ in range(count):
        channel = random.choice(_TELEGRAM_CHANNELS)
        itype = random.choice([IndicatorType.CARD_BIN, IndicatorType.HASH, IndicatorType.IP])

        if itype == IndicatorType.CARD_BIN:
            value = random.choice(_INDIAN_CARD_BINS)
            message = (
                f"🔥 FRESH BINS 🔥\n"
                f"BIN: {value}xxxxxx\n"
                f"Bank: {random.choice(['ICICI', 'HDFC', 'SBI', 'Axis', 'Kotak'])}\n"
                f"Type: {random.choice(['CREDIT', 'DEBIT'])} - {random.choice(['VISA', 'MASTERCARD'])}\n"
                f"Country: India 🇮🇳\n"
                f"Valid Rate: {random.randint(70, 95)}%\n"
                f"Price: ${random.randint(5, 50)}/card\n"
                f"DM @{''.join(random.choices('abcdefghijk', k=8))} for orders"
            )
            severity = 4
        elif itype == IndicatorType.HASH:
            value = random.choice(_MALWARE_HASHES)
            message = (
                f"📱 New Android Banking Trojan\n"
                f"Hash: {value}\n"
                f"Targets: {', '.join(random.sample(['BHIM', 'PhonePe', 'Google Pay', 'Paytm', 'YONO SBI'], 3))}\n"
                f"Features: Screen overlay, SMS intercept, keylogging\n"
                f"Evades: {random.choice(['Play Protect', 'Samsung Knox', 'both'])}\n"
                f"Builder available: ${random.randint(500, 5000)}"
            )
            severity = 5
        else:
            value = random.choice(_SUSPICIOUS_IPS)
            message = (
                f"🌐 Working C2 for UPI fraud toolkit\n"
                f"IP: {value}\n"
                f"Panel: https://{value}:{random.choice([8080, 443, 8443])}/panel\n"
                f"Status: ✅ Online\n"
                f"Success rate: {random.randint(60, 90)}%"
            )
            severity = 4

        indicator = ThreatIndicator(
            indicator_type=itype,
            value=value,
            source=IndicatorSource.TELEGRAM,
            severity=severity,
            raw_context=message,
            tags=["telegram", channel.lower()],
        )
        indicators.append(indicator)

        _telegram_alerts.append(TelegramAlert(
            channel_name=channel,
            message_text=message,
            sender_username=f"@{''.join(random.choices('abcdefghijk0123456789', k=10))}",
            indicators=[indicator],
        ))

    return indicators


def generate_github_indicators(count: int = 3) -> list[ThreatIndicator]:
    """Simulate GitHub secret scanning results."""
    indicators: list[ThreatIndicator] = []

    secret_types = [
        ("API_KEY", "sk_live_", 32),
        ("DATABASE_URL", "postgresql://admin:pass@", 20),
        ("AWS_SECRET", "AKIA", 16),
        ("PRIVATE_KEY", "-----BEGIN RSA PRIVATE KEY-----", 0),
        ("JWT_SECRET", "eyJhbGciOiJ", 24),
    ]

    for _ in range(count):
        repo = random.choice(_GITHUB_REPOS)
        secret_name, prefix, suffix_len = random.choice(secret_types)
        secret_value = prefix + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=suffix_len))

        indicator = ThreatIndicator(
            indicator_type=IndicatorType.CREDENTIAL,
            value=f"{secret_name}:{secret_value[:20]}...",
            source=IndicatorSource.GITHUB,
            severity=random.randint(3, 5),
            raw_context=(
                f"Secret detected in {repo}:\n"
                f"  File: {random.choice(['.env', 'config.yaml', 'settings.py', 'docker-compose.yml'])}\n"
                f"  Type: {secret_name}\n"
                f"  Value: {secret_value[:20]}{'*' * 12}\n"
                f"  Commit: {hashlib.sha1(str(random.random()).encode()).hexdigest()[:7]}\n"
                f"  Author: {random.choice(['dev-intern', 'bot-ci', 'anonymous'])}\n"
                f"  Exposure window: {random.randint(1, 72)} hours"
            ),
            tags=["github-leak", secret_name.lower(), repo.split("/")[0]],
        )
        indicators.append(indicator)

        _github_alerts.append(GitHubSecretAlert(
            repository=repo,
            file_path=random.choice([".env", "config/settings.py", "docker-compose.yml"]),
            secret_type=secret_name,
            commit_sha=hashlib.sha1(str(random.random()).encode()).hexdigest()[:7],
            author=random.choice(["dev-intern", "bot-ci", "anonymous"]),
            indicators=[indicator],
        ))

    return indicators


# ---------------------------------------------------------------------------
# STIX/TAXII Parsing Helpers
# ---------------------------------------------------------------------------

def parse_stix_indicator(stix_object: dict[str, Any]) -> ThreatIndicator | None:
    """
    Parse a STIX 2.1 indicator object into a ThreatIndicator.

    Handles indicator patterns like:
    - [ipv4-addr:value = '1.2.3.4']
    - [domain-name:value = 'evil.com']
    - [file:hashes.MD5 = 'abc123']
    """
    pattern = stix_object.get("pattern", "")
    name = stix_object.get("name", "")
    description = stix_object.get("description", "")

    # Determine indicator type from pattern
    indicator_type: IndicatorType | None = None
    value = ""

    if "ipv4-addr" in pattern or "ipv6-addr" in pattern:
        indicator_type = IndicatorType.IP
        # Extract IP from pattern: [ipv4-addr:value = 'X.X.X.X']
        parts = pattern.split("'")
        value = parts[1] if len(parts) > 1 else pattern
    elif "domain-name" in pattern:
        indicator_type = IndicatorType.DOMAIN
        parts = pattern.split("'")
        value = parts[1] if len(parts) > 1 else pattern
    elif "file:hashes" in pattern:
        indicator_type = IndicatorType.HASH
        parts = pattern.split("'")
        value = parts[1] if len(parts) > 1 else pattern
    else:
        logger.warning("Unsupported STIX pattern: %s", pattern)
        return None

    # Map STIX TLP to severity
    tlp = stix_object.get("object_marking_refs", [""])[0] if stix_object.get("object_marking_refs") else ""
    if "red" in tlp.lower():
        severity = 5
    elif "amber" in tlp.lower():
        severity = 4
    elif "green" in tlp.lower():
        severity = 3
    else:
        severity = 2

    return ThreatIndicator(
        indicator_type=indicator_type,
        value=value,
        source=IndicatorSource.STIX,
        severity=severity,
        raw_context=f"{name}: {description}",
        tags=stix_object.get("labels", []),
    )


def generate_simulated_stix_feed(count: int = 5) -> list[dict[str, Any]]:
    """Generate simulated STIX 2.1 indicator objects."""
    stix_objects: list[dict[str, Any]] = []

    for _ in range(count):
        obj_type = random.choice(["ip", "domain", "hash"])

        if obj_type == "ip":
            value = random.choice(_SUSPICIOUS_IPS)
            pattern = f"[ipv4-addr:value = '{value}']"
            name = f"Malicious IP - {value}"
            labels = ["malicious-activity", "c2"]
        elif obj_type == "domain":
            domain = random.choice(_LEAKED_DOMAINS)
            value = f"phishing-{domain}"
            pattern = f"[domain-name:value = '{value}']"
            name = f"Phishing Domain - {value}"
            labels = ["phishing", "banking"]
        else:
            value = random.choice(_MALWARE_HASHES)
            pattern = f"[file:hashes.MD5 = '{value}']"
            name = f"Banking Malware - {value[:12]}"
            labels = ["malware", "banking-trojan"]

        stix_objects.append({
            "type": "indicator",
            "spec_version": "2.1",
            "id": f"indicator--{uuid.uuid4()}",
            "created": datetime.now(timezone.utc).isoformat(),
            "modified": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "description": f"Automated detection from STIX feed. Indicator associated with Indian banking fraud campaigns.",
            "pattern": pattern,
            "pattern_type": "stix",
            "valid_from": datetime.now(timezone.utc).isoformat(),
            "labels": labels,
            "object_marking_refs": [random.choice([
                "marking-definition--tlp-red",
                "marking-definition--tlp-amber",
                "marking-definition--tlp-green",
            ])],
        })

    return stix_objects


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate_indicators(new_indicators: list[ThreatIndicator]) -> list[ThreatIndicator]:
    """
    Deduplicate indicators against the existing store.
    Updates last_seen for existing indicators. Returns only new ones.
    """
    novel: list[ThreatIndicator] = []

    for ind in new_indicators:
        dedup_key = _generate_indicator_hash(ind.indicator_type.value, ind.value)

        if dedup_key in _indicators:
            # Update last_seen on existing indicator
            _indicators[dedup_key].last_seen = datetime.now(timezone.utc)
            if ind.severity > _indicators[dedup_key].severity:
                _indicators[dedup_key].severity = ind.severity
            logger.debug("Duplicate indicator updated: %s", dedup_key)
        else:
            _indicators[dedup_key] = ind
            novel.append(ind)

    logger.info(
        "Deduplication: %d input → %d new, %d updated",
        len(new_indicators),
        len(novel),
        len(new_indicators) - len(novel),
    )
    return novel


# ---------------------------------------------------------------------------
# IOC Matching
# ---------------------------------------------------------------------------

_SIMULATED_ACCOUNT_DATABASE = {
    "411111": ["ACC-001234", "ACC-005678"],
    "431940": ["ACC-009012"],
    "524367": ["ACC-003456", "ACC-007890", "ACC-011234"],
    "545210": ["ACC-004567"],
}


def match_ioc_to_accounts(indicator: ThreatIndicator) -> list[str]:
    """
    Match an indicator of compromise against the simulated account database.
    Returns list of affected account IDs.
    """
    matched: list[str] = []

    if indicator.indicator_type == IndicatorType.CARD_BIN:
        matched = _SIMULATED_ACCOUNT_DATABASE.get(indicator.value, [])
    elif indicator.indicator_type == IndicatorType.CREDENTIAL:
        # Match by domain
        domain = indicator.value.split("@")[-1] if "@" in indicator.value else ""
        if "icici" in domain:
            matched = ["ACC-001234", "ACC-002345"]
        elif "hdfc" in domain:
            matched = ["ACC-003456"]
        elif "sbi" in domain:
            matched = ["ACC-005678", "ACC-006789"]
    elif indicator.indicator_type == IndicatorType.IP:
        # Simulate IP match against recent login IPs
        if random.random() > 0.7:
            matched = [f"ACC-{random.randint(100000, 999999):06d}"]

    indicator.matched_accounts = matched
    return matched


# ---------------------------------------------------------------------------
# Early Warning Generation
# ---------------------------------------------------------------------------

def evaluate_early_warnings() -> list[EarlyWarning]:
    """
    Analyse current indicator pool to generate early warning alerts.
    Looks for IOC clusters that suggest imminent attacks.
    """
    new_warnings: list[EarlyWarning] = []

    # Count indicators by type and severity in last 24h
    now = datetime.now(timezone.utc)
    recent = [
        ind for ind in _indicators.values()
        if (now - ind.first_seen).total_seconds() < 86400
    ]

    high_severity = [ind for ind in recent if ind.severity >= 4]
    card_bins = [ind for ind in recent if ind.indicator_type == IndicatorType.CARD_BIN]
    malware_hashes = [ind for ind in recent if ind.indicator_type == IndicatorType.HASH]

    # Pattern 1: Card BIN dump surge
    if len(card_bins) >= 3:
        warning = EarlyWarning(
            threat_type="CARD_BIN_DUMP_SURGE",
            description=(
                f"Detected {len(card_bins)} Indian card BIN indicators in the last 24 hours "
                f"across multiple dark web marketplaces. This pattern historically precedes "
                f"coordinated carding attacks within 12-48 hours. Affected BINs: "
                f"{', '.join(set(ind.value for ind in card_bins[:5]))}"
            ),
            confidence=min(0.95, 0.60 + len(card_bins) * 0.05),
            estimated_hours_until_attack=random.uniform(6, 48),
            matching_indicators=[ind.indicator_id for ind in card_bins],
            recommended_action=(
                "Enable enhanced transaction monitoring for affected BINs. "
                "Reduce velocity limits by 50%. Alert issuing banks."
            ),
        )
        new_warnings.append(warning)

    # Pattern 2: Multi-vector attack preparation
    if len(high_severity) >= 5:
        warning = EarlyWarning(
            threat_type="MULTI_VECTOR_ATTACK_PREP",
            description=(
                f"High concentration of {len(high_severity)} severity-4+ indicators detected "
                f"spanning multiple attack vectors (credentials, malware, C2 infrastructure). "
                f"This pattern is consistent with coordinated attack preparation targeting "
                f"Indian banking infrastructure."
            ),
            confidence=min(0.95, 0.55 + len(high_severity) * 0.04),
            estimated_hours_until_attack=random.uniform(12, 72),
            matching_indicators=[ind.indicator_id for ind in high_severity[:10]],
            recommended_action=(
                "Elevate SOC alert level to AMBER. Brief incident response team. "
                "Pre-position forensic tools. Notify CERT-In per standing protocol."
            ),
        )
        new_warnings.append(warning)

    # Pattern 3: New malware campaign
    if len(malware_hashes) >= 2:
        warning = EarlyWarning(
            threat_type="BANKING_MALWARE_CAMPAIGN",
            description=(
                f"Detected {len(malware_hashes)} new banking malware samples targeting "
                f"Indian UPI/mobile banking applications. Samples feature advanced evasion "
                f"techniques and screen-overlay capabilities."
            ),
            confidence=min(0.90, 0.65 + len(malware_hashes) * 0.08),
            estimated_hours_until_attack=random.uniform(24, 96),
            matching_indicators=[ind.indicator_id for ind in malware_hashes],
            recommended_action=(
                "Update APK threat intelligence signatures. Push detection rules to "
                "mobile banking apps. Notify Google Play Protect team."
            ),
        )
        new_warnings.append(warning)

    # Store new warnings
    _early_warnings.extend(new_warnings)

    return new_warnings


# ---------------------------------------------------------------------------
# Scan orchestration
# ---------------------------------------------------------------------------

async def run_scan(target: str, keywords: list[str] | None = None) -> list[ThreatIndicator]:
    """
    Run a simulated scan against the specified target.
    Returns deduplicated new indicators.
    """
    raw_indicators: list[ThreatIndicator] = []

    if target in ("darkweb", "all"):
        raw_indicators.extend(generate_darkweb_indicators(random.randint(3, 7)))
    if target in ("telegram", "all"):
        raw_indicators.extend(generate_telegram_indicators(random.randint(2, 5)))
    if target in ("github", "all"):
        raw_indicators.extend(generate_github_indicators(random.randint(1, 4)))

    # Ingest STIX feed
    stix_objects = generate_simulated_stix_feed(random.randint(2, 5))
    for obj in stix_objects:
        parsed = parse_stix_indicator(obj)
        if parsed:
            raw_indicators.append(parsed)

    # Deduplicate
    new_indicators = deduplicate_indicators(raw_indicators)

    # Match against accounts
    for ind in new_indicators:
        match_ioc_to_accounts(ind)

    # Evaluate early warnings
    evaluate_early_warnings()

    logger.info(
        "Scan complete (%s): %d raw → %d new indicators",
        target,
        len(raw_indicators),
        len(new_indicators),
    )
    return new_indicators
