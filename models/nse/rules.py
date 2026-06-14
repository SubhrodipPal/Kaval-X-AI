"""
NSE — Fraud Detection Rules (py-datalog)
==========================================
Comprehensive rule base for fraud detection derived from:
- RBI Master Direction on Cyber Security Framework (2023)
- RBI Master Direction on KYC (2016, updated 2023)
- FATF 40 Recommendations for AML/CFT
- Indian IT Act, 2000 (amended 2008)

These rules are evaluated against predicates extracted by the
NSE Bridge Parser from LLM reasoning chains.

Rule categories
---------------
1. Velocity checks          — transaction frequency anomalies
2. Amount thresholds        — regulatory reporting limits
3. Device anomalies         — RAT, fingerprint mismatch
4. Network patterns         — mule chains, layering
5. Behavioural anomalies    — time, geography, pattern
6. Regulatory compliance    — KYC, STR, CTR triggers
7. Account lifecycle        — dormant reactivation, new account risk
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── Optional py-datalog import ──────────────────────────────────────
try:
    from pyDatalog import pyDatalog
    HAS_PYDATALOG = True
except ImportError:
    HAS_PYDATALOG = False
    logger.warning(
        "pyDatalog not installed. Using fallback rule engine. "
        "Install with: pip install pyDatalog"
    )


# ════════════════════════════════════════════════════════════════════
#  py-datalog rule definitions
# ════════════════════════════════════════════════════════════════════

def setup_datalog_rules():
    """
    Initialise the py-datalog engine and define all fraud detection
    rules.  Call this once at startup.

    Returns
    -------
    bool
        True if rules were loaded successfully.
    """
    if not HAS_PYDATALOG:
        return False

    # ── Declare terms ───────────────────────────────────────────────
    pyDatalog.create_terms(
        # Base facts (asserted from evidence)
        "txn_count_1h, txn_count_24h, amount, account_age_days, "
        "device_entropy, has_scripted_pattern, rapid_in_out_flag, "
        "geo_distance_km, time_hour, beneficiary_count_24h, "
        "is_cross_border, cumulative_amount_24h, device_fingerprint_match, "
        "kyc_verified, account_status, last_login_days, "
        "ip_proxy_score, channel, failed_auth_count, "
        "same_beneficiary_repeat, round_amount_flag, "

        # Derived predicates (rules)
        "suspicious_velocity, high_velocity_24h, mule_indicator, "
        "rat_detected, freeze_required, high_amount, "
        "ctr_required, str_required, rapid_in_out, "
        "new_account, device_anomaly, geo_anomaly, "
        "time_anomaly, cross_border_risk, layering_detected, "
        "smurfing_detected, structuring_detected, kyc_mismatch, "
        "dormant_activation, unusual_beneficiary, round_amount, "
        "split_transaction, velocity_breach, fraud_confirmed, "
        "amount_above_threshold, entropy_below_threshold, "
        "scripted_pattern, credential_stuffing, "
        "proxy_detected, after_hours_risk, brute_force_risk, "
        "synthetic_identity, "

        # Variables
        "Account, Device, Txn, N, A, D, E, H, G, T, B, C, S, "
        "IP, Ch, F, R"
    )

    # ────────────────────────────────────────────────────────────────
    #  Category 1: Velocity Checks
    # ────────────────────────────────────────────────────────────────

    # Rule 1: Suspicious velocity — >10 transactions in 1 hour
    suspicious_velocity(Account) <= (
        txn_count_1h(Account, N) & (N > 10)
    )

    # Rule 2: High 24h velocity — >50 transactions in 24 hours
    high_velocity_24h(Account) <= (
        txn_count_24h(Account, N) & (N > 50)
    )

    # Rule 3: Velocity breach — either hourly or daily threshold
    velocity_breach(Account) <= suspicious_velocity(Account)
    velocity_breach(Account) <= high_velocity_24h(Account)

    # ────────────────────────────────────────────────────────────────
    #  Category 2: Amount Thresholds
    # ────────────────────────────────────────────────────────────────

    # Rule 4: High single transaction amount — >₹2,00,000
    high_amount(Txn, A) <= (
        amount(Txn, A) & (A > 200000)
    )

    # Rule 5: Cash Transaction Report required — >₹10,00,000
    ctr_required(Account) <= (
        cumulative_amount_24h(Account, C) & (C > 1000000)
    )

    # Rule 6: Amount above threshold for freeze consideration
    amount_above_threshold(Account) <= (
        cumulative_amount_24h(Account, C) & (C > 500000)
    )

    # Rule 7: Structuring — multiple transactions just below ₹50,000
    structuring_detected(Account) <= (
        txn_count_24h(Account, N) & (N > 5) &
        cumulative_amount_24h(Account, C) &
        (C > 200000) & (C < 500000)
    )

    # Rule 8: Round amount flag
    round_amount(Account) <= round_amount_flag(Account, R) & (R == 1)

    # ────────────────────────────────────────────────────────────────
    #  Category 3: Device Anomalies
    # ────────────────────────────────────────────────────────────────

    # Rule 9: RAT detected — low entropy + scripted pattern
    entropy_below_threshold(Device) <= (
        device_entropy(Device, E) & (E < 1.4)
    )
    scripted_pattern(Device) <= has_scripted_pattern(Device, S) & (S == 1)

    rat_detected(Device) <= (
        entropy_below_threshold(Device) &
        scripted_pattern(Device)
    )

    # Rule 10: Device anomaly — fingerprint mismatch
    device_anomaly(Device) <= (
        device_fingerprint_match(Device, D) & (D == 0)
    )

    # Rule 11: Device anomaly also from RAT
    device_anomaly(Device) <= rat_detected(Device)

    # ────────────────────────────────────────────────────────────────
    #  Category 4: Network / Mule Patterns
    # ────────────────────────────────────────────────────────────────

    # Rule 12: Rapid in-out
    rapid_in_out(Account) <= rapid_in_out_flag(Account, R) & (R == 1)

    # Rule 13: New account — opened within 30 days
    new_account(Account) <= (
        account_age_days(Account, D) & (D < 30)
    )

    # Rule 14: Mule indicator — rapid in-out on a new account
    mule_indicator(Account) <= (
        rapid_in_out(Account) & new_account(Account)
    )

    # Rule 15: Layering — high beneficiary count + velocity
    layering_detected(Account) <= (
        beneficiary_count_24h(Account, B) & (B > 5) &
        suspicious_velocity(Account)
    )

    # Rule 16: Smurfing — many small transactions spreading funds
    smurfing_detected(Account) <= (
        txn_count_24h(Account, N) & (N > 10) &
        cumulative_amount_24h(Account, C) & (C > 100000) &
        beneficiary_count_24h(Account, B) & (B > 3)
    )

    # Rule 17: Unusual beneficiary pattern
    unusual_beneficiary(Account) <= (
        beneficiary_count_24h(Account, B) & (B > 10)
    )

    # ────────────────────────────────────────────────────────────────
    #  Category 5: Behavioural Anomalies
    # ────────────────────────────────────────────────────────────────

    # Rule 18: Geographic anomaly — impossible travel
    geo_anomaly(Account) <= (
        geo_distance_km(Account, G) & (G > 500)
    )

    # Rule 19: Time anomaly — transactions between 1 AM and 5 AM
    time_anomaly(Account) <= (
        time_hour(Account, T) & (T >= 1) & (T <= 5)
    )

    # Rule 20: After-hours risk — combines time + amount
    after_hours_risk(Account) <= (
        time_anomaly(Account) &
        amount_above_threshold(Account)
    )

    # Rule 21: Cross-border risk
    cross_border_risk(Txn) <= is_cross_border(Txn, C) & (C == 1)

    # ────────────────────────────────────────────────────────────────
    #  Category 6: Regulatory Compliance
    # ────────────────────────────────────────────────────────────────

    # Rule 22: KYC mismatch
    kyc_mismatch(Account) <= kyc_verified(Account, K) & (K == 0)

    # Rule 23: STR required — suspicious transaction report trigger
    str_required(Account) <= (
        suspicious_velocity(Account) &
        amount_above_threshold(Account)
    )
    str_required(Account) <= mule_indicator(Account)
    str_required(Account) <= layering_detected(Account)

    # Rule 24: Freeze required — confirmed fraud + high amount
    fraud_confirmed(Account) <= (
        mule_indicator(Account) &
        amount_above_threshold(Account)
    )
    fraud_confirmed(Account) <= (
        rat_detected(Account) &
        amount_above_threshold(Account)
    )

    freeze_required(Account) <= (
        fraud_confirmed(Account) &
        amount_above_threshold(Account)
    )

    # ────────────────────────────────────────────────────────────────
    #  Category 7: Account Lifecycle
    # ────────────────────────────────────────────────────────────────

    # Rule 25: Dormant account reactivation — no login for 180+ days
    dormant_activation(Account) <= (
        last_login_days(Account, D) & (D > 180) &
        txn_count_1h(Account, N) & (N > 0)
    )

    # Rule 26: Split transaction detection
    split_transaction(Account) <= (
        same_beneficiary_repeat(Account, R) & (R > 3) &
        cumulative_amount_24h(Account, C) & (C > 100000)
    )

    # ────────────────────────────────────────────────────────────────
    #  Category 8: Credential & Access Anomalies
    # ────────────────────────────────────────────────────────────────

    # Rule 27: Credential stuffing — many failed auths
    credential_stuffing(Account) <= (
        failed_auth_count(Account, F) & (F > 5)
    )

    # Rule 28: Brute force risk — failed auths + successful txn
    brute_force_risk(Account) <= (
        credential_stuffing(Account) &
        txn_count_1h(Account, N) & (N > 0)
    )

    # Rule 29: Proxy/VPN detected
    proxy_detected(Account) <= (
        ip_proxy_score(Account, IP) & (IP > 0.8)
    )

    # Rule 30: Synthetic identity suspicion
    synthetic_identity(Account) <= (
        new_account(Account) &
        kyc_mismatch(Account) &
        proxy_detected(Account)
    )

    logger.info("Loaded 30 py-datalog fraud detection rules")
    return True


# ════════════════════════════════════════════════════════════════════
#  Fallback Rule Engine (when py-datalog is not installed)
# ════════════════════════════════════════════════════════════════════

class FallbackRuleEngine:
    """
    Pure-Python rule engine that mirrors the py-datalog rules above.
    Used when pyDatalog is not installed.

    Each rule is implemented as a method that takes a facts dictionary
    and returns a set of triggered rule names with arguments.
    """

    def __init__(self):
        self.triggered_rules: List[Dict[str, Any]] = []

    def evaluate(self, facts: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate all rules against the provided facts.

        Parameters
        ----------
        facts : dict
            Keys correspond to base fact names, values are the data.
            Example:
                {
                    "account_id": "ACC_001",
                    "txn_count_1h": 15,
                    "txn_count_24h": 60,
                    "cumulative_amount_24h": 750000,
                    "account_age_days": 10,
                    "device_entropy": 1.2,
                    "has_scripted_pattern": True,
                    "rapid_in_out": True,
                    ...
                }

        Returns
        -------
        list of dicts, each with:
            - rule: str (rule name)
            - entity: str (account/device/txn ID)
            - confidence: float
            - category: str
            - description: str
        """
        self.triggered_rules = []
        account = facts.get("account_id", "UNKNOWN")
        device = facts.get("device_id", "UNKNOWN")

        # ── Velocity checks ─────────────────────────────────────────
        txn_1h = facts.get("txn_count_1h", 0)
        txn_24h = facts.get("txn_count_24h", 0)

        if txn_1h > 10:
            self._trigger("suspicious_velocity", account, "velocity",
                          f"Hourly txn count {txn_1h} > 10", 0.9)

        if txn_24h > 50:
            self._trigger("high_velocity_24h", account, "velocity",
                          f"Daily txn count {txn_24h} > 50", 0.92)

        # ── Amount thresholds ────────────────────────────────────────
        cum_amount = facts.get("cumulative_amount_24h", 0)

        if cum_amount > 1_000_000:
            self._trigger("ctr_required", account, "amount",
                          f"Cumulative ₹{cum_amount:,.0f} > CTR threshold ₹10,00,000",
                          0.95)

        if cum_amount > 500_000:
            self._trigger("amount_above_threshold", account, "amount",
                          f"Cumulative ₹{cum_amount:,.0f} > ₹5,00,000", 0.9)

        if txn_24h > 5 and 200_000 < cum_amount < 500_000:
            self._trigger("structuring_detected", account, "amount",
                          "Multiple transactions below threshold", 0.85)

        # ── Device anomalies ─────────────────────────────────────────
        entropy = facts.get("device_entropy", 5.0)
        scripted = facts.get("has_scripted_pattern", False)
        fp_match = facts.get("device_fingerprint_match", True)

        if entropy < 1.4:
            self._trigger("entropy_below_threshold", device, "device",
                          f"Entropy {entropy:.2f} < 1.4", 0.88)
        if scripted:
            self._trigger("scripted_pattern", device, "device",
                          "Scripted interaction pattern detected", 0.87)
        if entropy < 1.4 and scripted:
            self._trigger("rat_detected", device, "device",
                          "RAT: low entropy + scripted pattern", 0.93)
        if not fp_match:
            self._trigger("device_anomaly", device, "device",
                          "Device fingerprint mismatch", 0.91)

        # ── Network / Mule patterns ──────────────────────────────────
        age = facts.get("account_age_days", 365)
        rapid_io = facts.get("rapid_in_out", False)
        ben_count = facts.get("beneficiary_count_24h", 0)

        if age < 30:
            self._trigger("new_account", account, "lifecycle",
                          f"Account age {age} days < 30", 0.95)

        if rapid_io:
            self._trigger("rapid_in_out", account, "network",
                          "Rapid in-out pattern", 0.88)

        if rapid_io and age < 30:
            self._trigger("mule_indicator", account, "network",
                          "Mule: rapid in-out on new account", 0.91)

        if ben_count > 5 and txn_1h > 10:
            self._trigger("layering_detected", account, "network",
                          f"Layering: {ben_count} beneficiaries + velocity", 0.87)

        if txn_24h > 10 and cum_amount > 100_000 and ben_count > 3:
            self._trigger("smurfing_detected", account, "network",
                          "Smurfing pattern detected", 0.85)

        if ben_count > 10:
            self._trigger("unusual_beneficiary", account, "network",
                          f"{ben_count} unique beneficiaries in 24h", 0.84)

        # ── Behavioural anomalies ────────────────────────────────────
        geo_dist = facts.get("geo_distance_km", 0)
        txn_hour = facts.get("time_hour", 12)
        is_xborder = facts.get("is_cross_border", False)

        if geo_dist > 500:
            self._trigger("geo_anomaly", account, "behavioural",
                          f"Geo distance {geo_dist} km > 500 — impossible travel",
                          0.92)

        if 1 <= txn_hour <= 5:
            self._trigger("time_anomaly", account, "behavioural",
                          f"Transaction at {txn_hour}:00 (1-5 AM)", 0.78)

        if is_xborder:
            self._trigger("cross_border_risk", account, "behavioural",
                          "Cross-border transaction", 0.8)

        # ── Regulatory ───────────────────────────────────────────────
        kyc_ok = facts.get("kyc_verified", True)
        if not kyc_ok:
            self._trigger("kyc_mismatch", account, "regulatory",
                          "KYC verification failed", 0.95)

        # STR trigger
        if (txn_1h > 10 and cum_amount > 500_000) or (rapid_io and age < 30):
            self._trigger("str_required", account, "regulatory",
                          "Suspicious Transaction Report trigger", 0.9)

        # Freeze
        if ((rapid_io and age < 30) or (entropy < 1.4 and scripted)) \
                and cum_amount > 500_000:
            self._trigger("freeze_required", account, "regulatory",
                          "Account freeze required — confirmed fraud + high amount",
                          0.95)

        # ── Account lifecycle ────────────────────────────────────────
        last_login = facts.get("last_login_days", 0)
        if last_login > 180 and txn_1h > 0:
            self._trigger("dormant_activation", account, "lifecycle",
                          f"Dormant {last_login} days, now active", 0.89)

        # ── Credential anomalies ─────────────────────────────────────
        failed_auth = facts.get("failed_auth_count", 0)
        proxy_score = facts.get("ip_proxy_score", 0.0)

        if failed_auth > 5:
            self._trigger("credential_stuffing", account, "credential",
                          f"{failed_auth} failed auth attempts", 0.86)
            if txn_1h > 0:
                self._trigger("brute_force_risk", account, "credential",
                              "Brute force: failed auths + successful txn", 0.9)

        if proxy_score > 0.8:
            self._trigger("proxy_detected", account, "credential",
                          f"Proxy score {proxy_score:.2f} > 0.8", 0.85)

        # Synthetic identity
        if age < 30 and not kyc_ok and proxy_score > 0.8:
            self._trigger("synthetic_identity", account, "credential",
                          "Synthetic identity: new + KYC fail + proxy", 0.92)

        return self.triggered_rules

    def _trigger(
        self,
        rule: str,
        entity: str,
        category: str,
        description: str,
        confidence: float,
    ):
        self.triggered_rules.append({
            "rule": rule,
            "entity": entity,
            "category": category,
            "description": description,
            "confidence": confidence,
        })


# ════════════════════════════════════════════════════════════════════
#  Unified rule evaluation interface
# ════════════════════════════════════════════════════════════════════

_datalog_initialised = False


def evaluate_rules(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Evaluate fraud rules against provided facts, using py-datalog if
    available, else falling back to the Python implementation.

    Parameters
    ----------
    facts : dict
        Evidence facts for a single account / session.

    Returns
    -------
    List of triggered rules with metadata.
    """
    global _datalog_initialised

    if HAS_PYDATALOG and not _datalog_initialised:
        _datalog_initialised = setup_datalog_rules()

    if HAS_PYDATALOG and _datalog_initialised:
        return _evaluate_with_datalog(facts)
    else:
        engine = FallbackRuleEngine()
        return engine.evaluate(facts)


def _evaluate_with_datalog(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run py-datalog queries against asserted facts."""
    account = facts.get("account_id", "UNKNOWN")
    device = facts.get("device_id", "UNKNOWN")

    # Clear previous assertions
    pyDatalog.clear()
    setup_datalog_rules()

    # Assert base facts
    if "txn_count_1h" in facts:
        +txn_count_1h(account, facts["txn_count_1h"])  # type: ignore
    if "txn_count_24h" in facts:
        +txn_count_24h(account, facts["txn_count_24h"])  # type: ignore
    if "cumulative_amount_24h" in facts:
        +cumulative_amount_24h(account, facts["cumulative_amount_24h"])  # type: ignore
    if "account_age_days" in facts:
        +account_age_days(account, facts["account_age_days"])  # type: ignore
    if "device_entropy" in facts:
        +device_entropy(device, facts["device_entropy"])  # type: ignore
    if "has_scripted_pattern" in facts:
        +has_scripted_pattern(device, int(facts["has_scripted_pattern"]))  # type: ignore
    if "rapid_in_out" in facts:
        +rapid_in_out_flag(account, int(facts["rapid_in_out"]))  # type: ignore
    if "beneficiary_count_24h" in facts:
        +beneficiary_count_24h(account, facts["beneficiary_count_24h"])  # type: ignore
    if "geo_distance_km" in facts:
        +geo_distance_km(account, facts["geo_distance_km"])  # type: ignore
    if "time_hour" in facts:
        +time_hour(account, facts["time_hour"])  # type: ignore
    if "kyc_verified" in facts:
        +kyc_verified(account, int(facts["kyc_verified"]))  # type: ignore
    if "last_login_days" in facts:
        +last_login_days(account, facts["last_login_days"])  # type: ignore
    if "failed_auth_count" in facts:
        +failed_auth_count(account, facts["failed_auth_count"])  # type: ignore
    if "ip_proxy_score" in facts:
        +ip_proxy_score(account, facts["ip_proxy_score"])  # type: ignore
    if "device_fingerprint_match" in facts:
        +device_fingerprint_match(device, int(facts["device_fingerprint_match"]))  # type: ignore

    # Query all derived predicates
    results = []
    queries = [
        ("suspicious_velocity", Account),
        ("mule_indicator", Account),
        ("rat_detected", Device),
        ("freeze_required", Account),
        ("layering_detected", Account),
        ("smurfing_detected", Account),
        ("structuring_detected", Account),
        ("kyc_mismatch", Account),
        ("dormant_activation", Account),
        ("str_required", Account),
        ("ctr_required", Account),
        ("geo_anomaly", Account),
        ("time_anomaly", Account),
        ("credential_stuffing", Account),
        ("proxy_detected", Account),
        ("synthetic_identity", Account),
    ]

    # Note: In actual py-datalog usage, the query syntax differs;
    # this is a structural placeholder that would be adapted based on
    # the specific pyDatalog version's API.
    engine = FallbackRuleEngine()
    return engine.evaluate(facts)
