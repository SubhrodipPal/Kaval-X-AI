"""
AMADP Orchestrator — Debate Engine
Core adversarial debate logic: prosecution, defense, and neuro-symbolic judge.

The debate follows this protocol each round:
  1. Prosecution agent analyses evidence and argues fraud.
  2. Defense agent rebuts and argues legitimacy.
  3. Judge agent applies RBI rule ontology and adjudicates.

After max_rounds (or early convergence), the judge emits a final verdict.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import random
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from models import (
    AgentRole,
    DebateConfig,
    DebateMessage,
    DebateStatus,
    DebateTranscript,
    TransactionEvidence,
    VerdictAction,
    VerdictOutput,
)

logger = logging.getLogger("amadp.debate_engine")

# ---------------------------------------------------------------------------
# System prompts (used when calling real LLMs — kept here for reference)
# ---------------------------------------------------------------------------

PROSECUTION_SYSTEM_PROMPT = (
    "You are a fraud prosecution analyst. Given transaction evidence, construct "
    "a detailed argument for why this transaction is fraudulent. Cite specific "
    "evidence IDs, risk scores, and regulatory violations. Be thorough and adversarial."
)

DEFENSE_SYSTEM_PROMPT = (
    "You are a fraud defense analyst. Given the same evidence, construct an "
    "exculpatory argument for why this transaction is legitimate. Identify "
    "alternative explanations, point out weaknesses in the prosecution case, "
    "cite normal behavioral patterns."
)

JUDGE_SYSTEM_PROMPT = (
    "You are a neuro-symbolic adjudicator. Apply RBI regulatory rules and "
    "ontological reasoning to weigh prosecution and defense arguments. Emit a "
    "confidence-calibrated verdict."
)

# ---------------------------------------------------------------------------
# RBI Rule Ontology (Neuro-Symbolic Judge rules)
# ---------------------------------------------------------------------------

# Each rule is a callable that takes evidence + scores and returns
# (rule_name, triggered: bool, weight: float, reasoning: str)

def _rule_high_tgn_anomaly(evidence: TransactionEvidence) -> tuple[str, bool, float, str]:
    """RBI-FR-001: Temporal graph anomaly exceeds safe threshold."""
    triggered = evidence.tgn_score > 0.70
    return (
        "RBI-FR-001-TGN-ANOMALY",
        triggered,
        0.25,
        f"TGN anomaly score {evidence.tgn_score:.3f} {'exceeds' if triggered else 'is within'} "
        f"the 0.70 threshold per RBI circular on digital payment fraud detection.",
    )


def _rule_biometric_mismatch(evidence: TransactionEvidence) -> tuple[str, bool, float, str]:
    """RBI-FR-002: Biometric trust falls below identity assurance minimum."""
    triggered = evidence.bio_trust < 0.60
    return (
        "RBI-FR-002-BIO-MISMATCH",
        triggered,
        0.20,
        f"Biometric trust {evidence.bio_trust:.3f} {'falls below' if triggered else 'meets'} "
        f"the 0.60 minimum identity assurance level (RBI KYC Master Direction 2016, §38).",
    )


def _rule_malicious_apk(evidence: TransactionEvidence) -> tuple[str, bool, float, str]:
    """RBI-FR-003: Device shows signs of malicious application interference."""
    triggered = evidence.apk_threat > 0.50
    return (
        "RBI-FR-003-APK-THREAT",
        triggered,
        0.20,
        f"APK threat score {evidence.apk_threat:.3f} {'indicates' if triggered else 'does not indicate'} "
        f"potential malware/overlay attack (CERT-In Advisory CI-2024-0192).",
    )


def _rule_device_compromise(evidence: TransactionEvidence) -> tuple[str, bool, float, str]:
    """RBI-FR-004: Device is rooted/emulated or tunnelled via VPN."""
    di = evidence.device_info
    triggered = di.is_rooted or di.emulator_detected or di.vpn_detected
    reasons = []
    if di.is_rooted:
        reasons.append("rooted device")
    if di.emulator_detected:
        reasons.append("emulator detected")
    if di.vpn_detected:
        reasons.append("VPN tunnel active")
    return (
        "RBI-FR-004-DEVICE-COMPROMISE",
        triggered,
        0.15,
        f"Device integrity check: {', '.join(reasons) if reasons else 'no issues'}. "
        f"RBI Digital Lending Guidelines §4.2 require device integrity verification.",
    )


def _rule_graph_collusion(evidence: TransactionEvidence) -> tuple[str, bool, float, str]:
    """RBI-FR-005: Suspicious graph neighbourhood pattern."""
    suspicious_neighbors = sum(
        1 for n in evidence.graph_neighbors
        if n.get("risk_score", 0) > 0.6 or n.get("flagged", False)
    )
    triggered = suspicious_neighbors >= 2
    return (
        "RBI-FR-005-GRAPH-COLLUSION",
        triggered,
        0.10,
        f"{suspicious_neighbors} of {len(evidence.graph_neighbors)} graph neighbours "
        f"show elevated risk. {'Potential collusion ring detected' if triggered else 'No collusion pattern'}. "
        f"RBI Master Direction on Fraud §8.12 (network analysis).",
    )


def _rule_amount_anomaly(evidence: TransactionEvidence) -> tuple[str, bool, float, str]:
    """RBI-FR-006: Transaction amount exceeds typical patterns."""
    amount = evidence.txn_data.get("amount", 0)
    avg_amount = evidence.txn_data.get("avg_amount", amount)
    ratio = amount / max(avg_amount, 1)
    triggered = ratio > 5.0
    return (
        "RBI-FR-006-AMOUNT-ANOMALY",
        triggered,
        0.10,
        f"Transaction amount ₹{amount:,.2f} is {ratio:.1f}x the account average ₹{avg_amount:,.2f}. "
        f"{'Exceeds 5x threshold' if triggered else 'Within normal range'} per RBI risk limits.",
    )


RBI_RULES = [
    _rule_high_tgn_anomaly,
    _rule_biometric_mismatch,
    _rule_malicious_apk,
    _rule_device_compromise,
    _rule_graph_collusion,
    _rule_amount_anomaly,
]


# ---------------------------------------------------------------------------
# In-memory stores (replaced by Redis in production)
# ---------------------------------------------------------------------------

_transcripts: dict[str, DebateTranscript] = {}
_verdicts: dict[str, VerdictOutput] = {}
_stream_queues: dict[str, asyncio.Queue] = {}


def get_transcript(verdict_id: str) -> DebateTranscript | None:
    return _transcripts.get(verdict_id)


def get_verdict(verdict_id: str) -> VerdictOutput | None:
    return _verdicts.get(verdict_id)


def get_stream_queue(verdict_id: str) -> asyncio.Queue | None:
    return _stream_queues.get(verdict_id)


# ---------------------------------------------------------------------------
# Simulated LLM Responses
# ---------------------------------------------------------------------------

def _build_prosecution_argument(
    evidence: TransactionEvidence, round_num: int, defense_prev: str | None = None,
) -> tuple[str, float, list[str]]:
    """
    Generate a realistic multi-paragraph prosecution argument.
    In production, this calls Mistral-7B via the LLM endpoint.
    """
    txn = evidence.txn_data
    amount = txn.get("amount", 50000)
    sender = txn.get("sender", "ACC-UNKNOWN")
    receiver = txn.get("receiver", "ACC-UNKNOWN")
    channel = txn.get("channel", "UPI")
    evidence_ids: list[str] = []

    if round_num == 1:
        # Initial prosecution case
        paragraphs = [
            f"PROSECUTION OPENING — Round {round_num}\n"
            f"I present the case that transaction {evidence.txn_id} (₹{amount:,.2f} via {channel} "
            f"from {sender} to {receiver}) constitutes a fraudulent operation based on multiple "
            f"converging risk indicators that collectively paint a clear picture of unauthorised activity.",

            f"EVIDENCE ANALYSIS — Temporal Graph Anomaly:\n"
            f"The Temporal Graph Network has flagged this transaction with an anomaly score of "
            f"{evidence.tgn_score:.4f}. This places the transaction in the top "
            f"{max(1, int((1 - evidence.tgn_score) * 100))}th percentile of suspicious transactions "
            f"processed in the last 24 hours. The TGN model, trained on 47 million historical "
            f"transactions, identifies temporal patterns inconsistent with the sender's established "
            f"behaviour profile. Specifically, the transaction timing, amount, and counterparty "
            f"combination has a probability of < 0.3% given the sender's prior transaction distribution.",

            f"EVIDENCE ANALYSIS — Biometric & Identity Concerns:\n"
            f"The biometric trust score stands at {evidence.bio_trust:.4f}, which "
            f"{'falls critically below' if evidence.bio_trust < 0.6 else 'approaches the lower bound of'} "
            f"the identity assurance threshold mandated by RBI's KYC Master Direction. "
            f"{'This strongly suggests the transaction was not initiated by the legitimate account holder. ' if evidence.bio_trust < 0.6 else ''}"
            f"The device fingerprint analysis reveals {'compromising factors: ' if evidence.device_info.is_rooted or evidence.device_info.vpn_detected else 'some concerning factors. '}"
            f"{'A rooted device was detected, enabling malware to intercept biometric data. ' if evidence.device_info.is_rooted else ''}"
            f"{'VPN tunnelling was active, suggesting IP spoofing to mask true geolocation. ' if evidence.device_info.vpn_detected else ''}",

            f"EVIDENCE ANALYSIS — Application Threat Intelligence:\n"
            f"APK threat analysis yields a score of {evidence.apk_threat:.4f}, indicating "
            f"{'active presence of' if evidence.apk_threat > 0.5 else 'potential'} malicious overlay "
            f"applications or screen-sharing software. CERT-In has documented a 340% increase in "
            f"banking trojan attacks targeting UPI applications in Q1 2026 (Advisory CI-2026-0047). "
            f"The detected threat signature matches patterns associated with known banking malware "
            f"families including Drinik and SOVA variants.",

            f"GRAPH TOPOLOGY — Network Collusion Indicators:\n"
            f"Analysis of {len(evidence.graph_neighbors)} first-hop graph neighbours reveals "
            f"{'a concerning cluster pattern' if len(evidence.graph_neighbors) > 0 else 'limited network data'}. "
            + (
                f"Notably, {sum(1 for n in evidence.graph_neighbors if n.get('flagged', False))} "
                f"of these neighbours have been independently flagged for suspicious activity, "
                f"suggesting a potential mule account network operating under coordinated control. "
                f"The receiver account {receiver} shows burst-mode transaction patterns characteristic "
                f"of fund-layering operations."
                if evidence.graph_neighbors
                else f"The receiver {receiver} is a previously unseen account with no transaction history, "
                     f"a hallmark of disposable mule accounts."
            ),

            f"REGULATORY VIOLATIONS:\n"
            f"Based on the above evidence, I assert violations of: (1) RBI Master Direction on "
            f"Fraud Risk Management §8.3 — failure of real-time fraud monitoring controls, "
            f"(2) RBI Circular on Limiting Liability of Customers in Unauthorised Electronic "
            f"Banking Transactions (2017) — indicators of third-party initiation, (3) CERT-In "
            f"Rules 2013, §12 — reporting obligation for suspected cyber fraud exceeding ₹10,000. "
            f"The prosecution recommends IMMEDIATE BLOCK of this transaction and escalation to "
            f"the bank's fraud response team.",
        ]
        evidence_ids = [
            f"EVD-TGN-{evidence.txn_id[-6:]}",
            f"EVD-BIO-{evidence.txn_id[-6:]}",
            f"EVD-APK-{evidence.txn_id[-6:]}",
            f"EVD-GRAPH-{evidence.txn_id[-6:]}",
            f"EVD-DEVICE-{evidence.txn_id[-6:]}",
        ]
        base_conf = 0.60 + (evidence.tgn_score * 0.20) + ((1 - evidence.bio_trust) * 0.10) + (evidence.apk_threat * 0.10)
    else:
        # Rebuttal rounds
        paragraphs = [
            f"PROSECUTION REBUTTAL — Round {round_num}\n"
            f"The defense's arguments, while superficially plausible, fail to address the "
            f"fundamental statistical improbability of this transaction's characteristics. "
            f"I maintain and strengthen my position with the following counter-arguments:",

            f"COUNTER-ARGUMENT — Statistical Weight:\n"
            f"The defense suggests alternative explanations for the anomalous TGN score of "
            f"{evidence.tgn_score:.4f}. However, the Bayes factor for fraud given this score "
            f"combination (TGN × biometric × APK) is approximately {10 ** (evidence.tgn_score * 3):.1f}:1, "
            f"meaning the evidence is overwhelmingly more likely under the fraud hypothesis. "
            f"The defense's invocation of legitimate high-value transactions ignores the multi-"
            f"dimensional nature of our scoring: amount alone would not trigger this alert. It is "
            f"the CONJUNCTION of anomalous timing, compromised biometrics, and device irregularities "
            f"that makes innocent explanation untenable.",

            f"COUNTER-ARGUMENT — Device Integrity:\n"
            f"Regarding device factors, the defense cannot explain why a legitimate user would "
            f"{'operate from a rooted device with ' if evidence.device_info.is_rooted else 'exhibit '}"
            f"{'VPN tunnelling active during a domestic transaction. ' if evidence.device_info.vpn_detected else 'these device anomalies. '}"
            f"RBI's Digital Payment Security Controls (DPSC) Directions 2024 explicitly classify "
            f"such device states as elevated-risk indicators requiring additional factor authentication, "
            f"which was NOT triggered for this transaction.",

            f"UPDATED RISK ASSESSMENT:\n"
            f"Incorporating the defense's admitted weaknesses (acknowledged inability to explain "
            f"the biometric discrepancy and graph topology), I revise my fraud confidence UPWARD. "
            f"The prosecution rests on the cumulative weight of {len(evidence_ids) + 3} independent "
            f"evidence vectors, each individually concerning and collectively dispositive.",
        ]
        evidence_ids = [
            f"EVD-REBUTTAL-{round_num}-{evidence.txn_id[-6:]}",
            f"EVD-BAYES-{evidence.txn_id[-6:]}",
        ]
        base_conf = min(0.95, 0.70 + (round_num * 0.05) + (evidence.tgn_score * 0.15))

    # Add controlled randomness
    confidence = min(0.99, max(0.30, base_conf + random.uniform(-0.05, 0.05)))
    content = "\n\n".join(paragraphs)
    return content, round(confidence, 4), evidence_ids


def _build_defense_argument(
    evidence: TransactionEvidence,
    round_num: int,
    prosecution_arg: str,
) -> tuple[str, float, list[str]]:
    """
    Generate a realistic multi-paragraph defense argument.
    In production, this calls Mistral-7B via the LLM endpoint.
    """
    txn = evidence.txn_data
    amount = txn.get("amount", 50000)
    sender = txn.get("sender", "ACC-UNKNOWN")
    receiver = txn.get("receiver", "ACC-UNKNOWN")
    channel = txn.get("channel", "UPI")
    evidence_ids: list[str] = []

    if round_num == 1:
        paragraphs = [
            f"DEFENSE OPENING — Round {round_num}\n"
            f"I submit that transaction {evidence.txn_id} (₹{amount:,.2f} via {channel}) "
            f"is a legitimate financial operation, and the prosecution's case relies on "
            f"algorithmic scores that, upon closer examination, do not meet the evidentiary "
            f"threshold required to classify this as fraud. The presumption of legitimacy must "
            f"be upheld until proven otherwise beyond the regulatory confidence threshold.",

            f"EXCULPATORY ANALYSIS — TGN Score Context:\n"
            f"The prosecution places undue emphasis on the TGN anomaly score of {evidence.tgn_score:.4f}. "
            f"However, this score must be interpreted in context. The TGN model's false positive "
            f"rate at this threshold is approximately {max(5, int((1 - evidence.tgn_score) * 40))}%, "
            f"meaning {'one in five' if evidence.tgn_score < 0.8 else 'one in ten'} flagged "
            f"transactions at this level are, in fact, legitimate. The sender {sender} may have "
            f"legitimate reasons for an unusual transaction pattern — salary disbursement, "
            f"investment maturity, property transaction, or emergency medical payment. Without "
            f"examining the sender's stated reason, the TGN score alone is insufficient grounds "
            f"for a fraud determination.",

            f"EXCULPATORY ANALYSIS — Biometric Variance:\n"
            f"The biometric trust score of {evidence.bio_trust:.4f} "
            f"{'is admittedly low' if evidence.bio_trust < 0.6 else 'is within acceptable operating range'}. "
            f"{'However, biometric systems exhibit well-documented failure modes including: ' if evidence.bio_trust < 0.6 else ''}"
            f"Environmental factors (lighting, moisture, screen protectors) routinely cause "
            f"biometric score degradation of 15-25% without any fraudulent intent. Academic "
            f"literature (Jain et al., 2023) documents that fingerprint sensors show a 12% "
            f"degradation rate in tropical climates — directly relevant to Indian geography. "
            f"The RBI's own technical committee acknowledged these limitations in their 2024 "
            f"position paper on biometric authentication reliability.",

            f"EXCULPATORY ANALYSIS — Device State:\n"
            f"{'The prosecution highlights device rooting. ' if evidence.device_info.is_rooted else ''}"
            f"{'However, approximately 18% of Android devices in India run custom ROMs for ' if evidence.device_info.is_rooted else ''}"
            f"{'legitimate purposes including privacy enhancement, ad-blocking, and device ' if evidence.device_info.is_rooted else ''}"
            f"{'longevity extension. Rooting alone is not evidence of fraud. ' if evidence.device_info.is_rooted else ''}"
            f"{'Regarding VPN usage: many users employ VPNs for legitimate privacy, ' if evidence.device_info.vpn_detected else ''}"
            f"{'corporate network access, or to protect against MITM attacks on public Wi-Fi. ' if evidence.device_info.vpn_detected else ''}"
            f"RBI has not prohibited VPN usage during transactions, and penalising users for "
            f"employing security tools creates a perverse incentive against good cyber hygiene.",

            f"GRAPH TOPOLOGY — Alternative Explanations:\n"
            f"The prosecution's network analysis suffers from confirmation bias. Shared graph "
            f"neighbours with elevated scores may simply indicate common membership in the same "
            f"payment ecosystem — e-commerce merchants, utility providers, or peer groups. "
            f"The presence of flagged neighbours is expected in dense transaction graphs and does "
            f"not establish intent or coordination. Correlation in graph topology ≠ causation of fraud.",

            f"CONCLUSION:\n"
            f"The prosecution has presented a constellation of moderate-risk indicators, none of "
            f"which individually crosses the fraud threshold. The principle of 'beyond reasonable '  "
            f"doubt' — while not strictly applicable in automated systems — informs the spirit of "
            f"RBI's customer protection framework. Blocking this transaction risks a Type I error "
            f"that would deny the customer access to their legitimate funds, violating RBI's "
            f"directive on minimising customer inconvenience. The defense recommends ALLOW with "
            f"post-transaction monitoring.",
        ]
        evidence_ids = [
            f"DEF-FPR-{evidence.txn_id[-6:]}",
            f"DEF-BIO-CLIMATE-{evidence.txn_id[-6:]}",
            f"DEF-DEVICE-LEGIT-{evidence.txn_id[-6:]}",
            f"DEF-GRAPH-CORR-{evidence.txn_id[-6:]}",
        ]
        base_conf = 0.60 - (evidence.tgn_score * 0.15) + (evidence.bio_trust * 0.15) - (evidence.apk_threat * 0.10)
    else:
        paragraphs = [
            f"DEFENSE REBUTTAL — Round {round_num}\n"
            f"The prosecution's rebuttal introduces Bayesian reasoning but applies it selectively. "
            f"I address each counter-argument while highlighting critical gaps in the prosecution's "
            f"analytical framework:",

            f"COUNTER-ARGUMENT — Bayesian Priors:\n"
            f"The prosecution's Bayes factor calculation assumes independent evidence streams, but "
            f"the TGN score, biometric trust, and APK threat are correlated through shared device "
            f"state. If the device is in a degraded state (low battery, overheating, background "
            f"processes), ALL three scores degrade simultaneously — this is a confounding variable "
            f"the prosecution has not controlled for. The true Bayes factor, accounting for "
            f"correlation structure, is approximately {10 ** (evidence.tgn_score * 1.5):.1f}:1 — "
            f"substantially lower than claimed and within the range where legitimate explanations "
            f"remain plausible.",

            f"COUNTER-ARGUMENT — Regulatory Proportionality:\n"
            f"The prosecution cites multiple RBI directives but omits the balancing provisions. "
            f"RBI Master Direction on Digital Payment Security Controls (2024), §7.4 explicitly "
            f"states that fraud detection systems must 'balance security with customer convenience' "
            f"and must not 'unduly restrict access to legitimate payment services.' A block action "
            f"on {'the presented evidence' if evidence.tgn_score < 0.85 else 'borderline evidence'} "
            f"may itself constitute a regulatory violation under the customer protection framework.",

            f"DEFENSE POSITION:\n"
            f"I maintain that the evidence supports ALLOW or at most REVIEW disposition. "
            f"{'The TGN score, while elevated, has not crossed the definitive fraud threshold. ' if evidence.tgn_score < 0.9 else ''}"
            f"Post-transaction monitoring and customer confirmation within 24 hours provides "
            f"adequate protection while respecting the customer's right to transact.",
        ]
        evidence_ids = [
            f"DEF-CORR-{round_num}-{evidence.txn_id[-6:]}",
            f"DEF-REG-PROP-{evidence.txn_id[-6:]}",
        ]
        base_conf = max(0.15, 0.50 - (round_num * 0.05) - (evidence.tgn_score * 0.10) + (evidence.bio_trust * 0.10))

    confidence = min(0.95, max(0.10, base_conf + random.uniform(-0.05, 0.05)))
    content = "\n\n".join(paragraphs)
    return content, round(confidence, 4), evidence_ids


# ---------------------------------------------------------------------------
# Neuro-Symbolic Judge
# ---------------------------------------------------------------------------

def judge_adjudicate(
    evidence: TransactionEvidence,
    prosecution_msgs: list[DebateMessage],
    defense_msgs: list[DebateMessage],
    round_num: int,
    config: DebateConfig,
) -> tuple[str, float, list[str], dict[str, Any]]:
    """
    Apply RBI rule ontology to adjudicate between prosecution and defense.

    Returns (content, confidence, evidence_ids, rule_results).
    """
    # Evaluate all rules
    rule_results: list[dict[str, Any]] = []
    weighted_fraud_score = 0.0
    total_weight = 0.0

    for rule_fn in RBI_RULES:
        name, triggered, weight, reasoning = rule_fn(evidence)
        rule_results.append({
            "rule": name,
            "triggered": triggered,
            "weight": weight,
            "reasoning": reasoning,
        })
        weighted_fraud_score += weight * (1.0 if triggered else 0.0)
        total_weight += weight

    # Normalise to [0, 1]
    rule_fraud_score = weighted_fraud_score / total_weight if total_weight > 0 else 0.5

    # Incorporate agent confidence signals
    avg_prosecution_conf = (
        sum(m.confidence for m in prosecution_msgs) / len(prosecution_msgs)
        if prosecution_msgs
        else 0.5
    )
    avg_defense_conf = (
        sum(m.confidence for m in defense_msgs) / len(defense_msgs)
        if defense_msgs
        else 0.5
    )

    # Composite judge score: 60% rules, 20% prosecution strength, 20% inverse-defense
    judge_fraud_score = (
        0.60 * rule_fraud_score
        + 0.20 * avg_prosecution_conf
        + 0.20 * (1 - avg_defense_conf)
    )

    # Determine verdict action
    if judge_fraud_score >= 0.85:
        action_str = "FREEZE"
    elif judge_fraud_score >= config.judge_threshold:
        action_str = "BLOCK"
    elif judge_fraud_score >= 0.55:
        action_str = "REVIEW"
    else:
        action_str = "ALLOW"

    # Count triggered rules
    triggered_rules = [r for r in rule_results if r["triggered"]]

    # Build judge reasoning
    paragraphs = [
        f"JUDGE ADJUDICATION — Round {round_num}\n"
        f"Having considered the prosecution's and defense's arguments across "
        f"{round_num} round{'s' if round_num > 1 else ''} of adversarial debate, "
        f"I render the following analysis under the RBI regulatory framework:",

        f"RULE ENGINE EVALUATION:\n"
        f"Of {len(RBI_RULES)} RBI regulatory rules evaluated, {len(triggered_rules)} "
        f"were triggered:\n" + "\n".join(
            f"  • [{r['rule']}] — {r['reasoning']}"
            for r in rule_results
        ),

        f"WEIGHTED ANALYSIS:\n"
        f"Rule-based fraud score: {rule_fraud_score:.4f}\n"
        f"Prosecution average confidence: {avg_prosecution_conf:.4f}\n"
        f"Defense average confidence: {avg_defense_conf:.4f}\n"
        f"Composite judge fraud score: {judge_fraud_score:.4f}",

        f"CONFIDENCE CALIBRATION:\n"
        f"The disagreement between prosecution ({avg_prosecution_conf:.3f}) and defense "
        f"({avg_defense_conf:.3f}) is {abs(avg_prosecution_conf - avg_defense_conf):.3f}. "
        + (
            f"This exceeds the disagreement threshold of {config.disagreement_threshold}, "
            f"indicating genuine ambiguity in the evidence that warrants careful adjudication."
            if abs(avg_prosecution_conf - avg_defense_conf) > config.disagreement_threshold
            else f"This is within the disagreement threshold, suggesting convergent assessment."
        ),

        f"VERDICT:\n"
        f"Based on composite analysis, the judge renders: **{action_str}** with "
        f"confidence {judge_fraud_score:.4f}.\n"
        f"{'Transaction should be immediately frozen and escalated to the fraud response team.' if action_str == 'FREEZE' else ''}"
        f"{'Transaction should be blocked pending manual review.' if action_str == 'BLOCK' else ''}"
        f"{'Transaction should be flagged for enhanced monitoring and post-transaction review.' if action_str == 'REVIEW' else ''}"
        f"{'Transaction may proceed with standard monitoring.' if action_str == 'ALLOW' else ''}",
    ]

    evidence_ids = [r["rule"] for r in triggered_rules]
    content = "\n\n".join(paragraphs)

    return content, round(judge_fraud_score, 4), evidence_ids, {
        "rules": rule_results,
        "scores": {
            "rule_fraud_score": rule_fraud_score,
            "avg_prosecution_conf": avg_prosecution_conf,
            "avg_defense_conf": avg_defense_conf,
            "composite": judge_fraud_score,
        },
    }


# ---------------------------------------------------------------------------
# Reasoning DAG builder
# ---------------------------------------------------------------------------

def build_reasoning_dag(
    evidence: TransactionEvidence,
    transcript: DebateTranscript,
    rule_results: dict[str, Any],
    verdict: VerdictAction,
) -> dict[str, Any]:
    """Build a JSON-LD reasoning DAG from the debate."""
    return {
        "@context": {
            "kavalx": "https://kavalx.ai/ontology/",
            "rbi": "https://rbi.org.in/fraud-ontology/",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
        },
        "@type": "kavalx:ReasoningDAG",
        "kavalx:verdict_id": transcript.verdict_id,
        "kavalx:txn_id": evidence.txn_id,
        "kavalx:timestamp": datetime.now(timezone.utc).isoformat(),
        "kavalx:evidence_nodes": [
            {
                "@type": "kavalx:EvidenceNode",
                "kavalx:id": "tgn_anomaly",
                "kavalx:score": evidence.tgn_score,
                "kavalx:source": "TemporalGraphNetwork",
            },
            {
                "@type": "kavalx:EvidenceNode",
                "kavalx:id": "biometric_trust",
                "kavalx:score": evidence.bio_trust,
                "kavalx:source": "BiometricEngine",
            },
            {
                "@type": "kavalx:EvidenceNode",
                "kavalx:id": "apk_threat",
                "kavalx:score": evidence.apk_threat,
                "kavalx:source": "APKThreatIntel",
            },
        ],
        "kavalx:rule_evaluations": rule_results.get("rules", []),
        "kavalx:debate_rounds": len(transcript.rounds),
        "kavalx:agent_scores": rule_results.get("scores", {}),
        "kavalx:verdict": verdict.value,
        "kavalx:edges": [
            {"from": "tgn_anomaly", "to": "prosecution_argument", "relation": "supports"},
            {"from": "biometric_trust", "to": "prosecution_argument", "relation": "supports"},
            {"from": "apk_threat", "to": "prosecution_argument", "relation": "supports"},
            {"from": "prosecution_argument", "to": "judge_evaluation", "relation": "input"},
            {"from": "defense_argument", "to": "judge_evaluation", "relation": "input"},
            {"from": "rule_engine", "to": "judge_evaluation", "relation": "constrains"},
            {"from": "judge_evaluation", "to": "verdict", "relation": "produces"},
        ],
    }


# ---------------------------------------------------------------------------
# PQC Signing (CRYSTALS-Dilithium stub using SHA-512)
# ---------------------------------------------------------------------------

def pqc_sign_verdict(verdict: VerdictOutput, signer_id: str = "system") -> str:
    """
    Produce a PQC signature stub for a verdict.

    In production, this uses CRYSTALS-Dilithium (NIST PQC standard).
    For development, we use SHA-512 + HMAC as a placeholder.
    """
    payload = json.dumps(
        {
            "verdict_id": verdict.verdict_id,
            "txn_id": verdict.txn_id,
            "verdict": verdict.verdict.value,
            "confidence": verdict.confidence,
            "timestamp": verdict.timestamp.isoformat(),
            "signer": signer_id,
        },
        sort_keys=True,
    )
    # Simulate Dilithium signature with double-SHA-512
    h1 = hashlib.sha512(payload.encode()).hexdigest()
    h2 = hashlib.sha512((h1 + "dilithium-kavalx-pqc-v1").encode()).hexdigest()
    return h2


# ---------------------------------------------------------------------------
# Main debate orchestrator
# ---------------------------------------------------------------------------

async def run_debate(
    evidence: TransactionEvidence,
    config: DebateConfig | None = None,
) -> VerdictOutput:
    """
    Orchestrate a full adversarial debate between prosecution, defense, and judge.

    Steps per round:
      1. Prosecution presents/rebuts
      2. Defense presents/rebuts
      3. Judge evaluates using RBI rule ontology

    Returns the final VerdictOutput.
    """
    if config is None:
        config = DebateConfig()

    verdict_id = f"VRD-{uuid.uuid4().hex[:12].upper()}"
    transcript = DebateTranscript(verdict_id=verdict_id)
    _transcripts[verdict_id] = transcript

    # Create SSE queue
    queue: asyncio.Queue = asyncio.Queue()
    _stream_queues[verdict_id] = queue

    all_prosecution_msgs: list[DebateMessage] = []
    all_defense_msgs: list[DebateMessage] = []
    last_judge_rule_results: dict[str, Any] = {}
    final_judge_conf = 0.5

    logger.info("Starting debate %s for transaction %s", verdict_id, evidence.txn_id)

    for round_num in range(1, config.max_rounds + 1):
        round_messages: list[DebateMessage] = []

        # --- Prosecution ---
        defense_prev = all_defense_msgs[-1].content if all_defense_msgs else None
        p_content, p_conf, p_evids = _build_prosecution_argument(
            evidence, round_num, defense_prev,
        )
        prosecution_msg = DebateMessage(
            agent=AgentRole.PROSECUTION,
            round=round_num,
            content=p_content,
            confidence=p_conf,
            evidence_ids=p_evids,
        )
        round_messages.append(prosecution_msg)
        all_prosecution_msgs.append(prosecution_msg)

        # Stream prosecution tokens
        await _stream_tokens(queue, AgentRole.PROSECUTION, round_num, p_content)

        # Small delay to simulate LLM inference time
        await asyncio.sleep(0.05)

        # --- Defense ---
        d_content, d_conf, d_evids = _build_defense_argument(
            evidence, round_num, p_content,
        )
        defense_msg = DebateMessage(
            agent=AgentRole.DEFENSE,
            round=round_num,
            content=d_content,
            confidence=d_conf,
            evidence_ids=d_evids,
        )
        round_messages.append(defense_msg)
        all_defense_msgs.append(defense_msg)

        # Stream defense tokens
        await _stream_tokens(queue, AgentRole.DEFENSE, round_num, d_content)
        await asyncio.sleep(0.05)

        # --- Judge ---
        j_content, j_conf, j_evids, rule_results = judge_adjudicate(
            evidence, all_prosecution_msgs, all_defense_msgs, round_num, config,
        )
        judge_msg = DebateMessage(
            agent=AgentRole.JUDGE,
            round=round_num,
            content=j_content,
            confidence=j_conf,
            evidence_ids=j_evids,
        )
        round_messages.append(judge_msg)
        last_judge_rule_results = rule_results
        final_judge_conf = j_conf

        # Stream judge tokens
        await _stream_tokens(queue, AgentRole.JUDGE, round_num, j_content)

        transcript.rounds.append(round_messages)

        logger.info(
            "Round %d complete — P:%.3f  D:%.3f  J:%.3f",
            round_num,
            p_conf,
            d_conf,
            j_conf,
        )

        # Early stop if judge is highly confident
        if j_conf >= 0.90 or j_conf <= 0.15:
            logger.info("Early stop at round %d (judge conf %.3f)", round_num, j_conf)
            break

    # --- Final verdict ---
    if final_judge_conf >= 0.85:
        verdict_action = VerdictAction.FREEZE
        action_text = "Freeze account and escalate to fraud response team. File RBI incident report."
    elif final_judge_conf >= config.judge_threshold:
        verdict_action = VerdictAction.BLOCK
        action_text = "Block transaction and notify customer. Initiate manual review."
    elif final_judge_conf >= 0.55:
        verdict_action = VerdictAction.REVIEW
        action_text = "Flag for enhanced monitoring. Allow with post-transaction review within 24h."
    else:
        verdict_action = VerdictAction.ALLOW
        action_text = "Allow transaction with standard monitoring."

    # Collect all evidence IDs
    all_evidence_ids = list(set(
        eid
        for msgs in [all_prosecution_msgs, all_defense_msgs]
        for m in msgs
        for eid in m.evidence_ids
    ))

    reasoning_dag = build_reasoning_dag(
        evidence, transcript, last_judge_rule_results, verdict_action,
    )

    verdict = VerdictOutput(
        verdict_id=verdict_id,
        txn_id=evidence.txn_id,
        verdict=verdict_action,
        confidence=final_judge_conf,
        prosecution_conf=all_prosecution_msgs[-1].confidence if all_prosecution_msgs else 0,
        defense_conf=all_defense_msgs[-1].confidence if all_defense_msgs else 0,
        judge_conf=final_judge_conf,
        reasoning_dag=reasoning_dag,
        evidence_ids=all_evidence_ids,
        action=action_text,
    )

    _verdicts[verdict_id] = verdict
    transcript.status = DebateStatus.COMPLETED

    # Send final verdict event to stream
    await queue.put({
        "type": "verdict",
        "data": verdict.model_dump(mode="json"),
    })
    await queue.put(None)  # Sentinel to end stream

    logger.info(
        "Debate %s complete — Verdict: %s (%.3f)",
        verdict_id,
        verdict_action.value,
        final_judge_conf,
    )

    return verdict


async def _stream_tokens(
    queue: asyncio.Queue,
    agent: AgentRole,
    round_num: int,
    content: str,
) -> None:
    """
    Simulate token-by-token streaming by chunking content into ~30-char segments.
    In production, each token comes from the LLM's streaming response.
    """
    # Split into word-groups to simulate token streaming
    words = content.split()
    chunk_size = 5  # words per token event
    for i in range(0, len(words), chunk_size):
        token = " ".join(words[i : i + chunk_size])
        await queue.put({
            "type": "token",
            "agent": agent.value,
            "round": round_num,
            "token": token,
        })
        await asyncio.sleep(0.01)  # Small delay to simulate generation


async def stream_debate_events(verdict_id: str) -> AsyncGenerator[dict, None]:
    """
    Async generator that yields debate events from the stream queue.
    Used by the SSE endpoint.
    """
    queue = _stream_queues.get(verdict_id)
    if queue is None:
        yield {"type": "error", "message": f"No active stream for verdict {verdict_id}"}
        return

    while True:
        event = await queue.get()
        if event is None:
            break
        yield event
