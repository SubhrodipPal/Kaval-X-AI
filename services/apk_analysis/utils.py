"""APK Analysis utilities — static, dynamic, GenAI, and meta-classifier."""
from __future__ import annotations

import hashlib
import logging
import math
import random
import time
from collections import Counter
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Dangerous Android permissions (risk-weighted)
# ──────────────────────────────────────────────
DANGEROUS_PERMISSIONS = {
    "android.permission.SEND_SMS": 0.9,
    "android.permission.READ_SMS": 0.85,
    "android.permission.RECEIVE_SMS": 0.85,
    "android.permission.READ_CONTACTS": 0.6,
    "android.permission.READ_CALL_LOG": 0.7,
    "android.permission.CALL_PHONE": 0.8,
    "android.permission.CAMERA": 0.5,
    "android.permission.RECORD_AUDIO": 0.7,
    "android.permission.ACCESS_FINE_LOCATION": 0.6,
    "android.permission.READ_PHONE_STATE": 0.65,
    "android.permission.WRITE_EXTERNAL_STORAGE": 0.5,
    "android.permission.INSTALL_PACKAGES": 0.95,
    "android.permission.REQUEST_INSTALL_PACKAGES": 0.9,
    "android.permission.SYSTEM_ALERT_WINDOW": 0.85,
    "android.permission.BIND_ACCESSIBILITY_SERVICE": 0.95,
    "android.permission.BIND_DEVICE_ADMIN": 0.9,
    "android.permission.READ_EXTERNAL_STORAGE": 0.4,
    "android.permission.INTERNET": 0.1,
    "android.permission.ACCESS_NETWORK_STATE": 0.1,
    "android.permission.WAKE_LOCK": 0.2,
    "android.permission.RECEIVE_BOOT_COMPLETED": 0.6,
    "android.permission.FOREGROUND_SERVICE": 0.3,
}

SUSPICIOUS_API_CALLS = [
    "Landroid/telephony/SmsManager;->sendTextMessage",
    "Ljava/lang/Runtime;->exec",
    "Ljava/lang/ProcessBuilder;->start",
    "Landroid/app/admin/DevicePolicyManager;->lockNow",
    "Landroid/content/pm/PackageManager;->installPackage",
    "Landroid/os/PowerManager;->reboot",
    "Ldalvik/system/DexClassLoader;-><init>",
    "Ljava/lang/reflect/Method;->invoke",
    "Landroid/provider/Settings$Secure;->putInt",
    "Landroid/accessibilityservice/AccessibilityService;->performGlobalAction",
    "Landroid/media/AudioRecord;->startRecording",
    "Landroid/hardware/Camera;->takePicture",
    "Ljavax/crypto/Cipher;->doFinal",
    "Ljava/net/URL;->openConnection",
]

MALWARE_FAMILIES = [
    "BankBot", "Cerberus", "Anubis", "FluBot", "TeaBot",
    "SharkBot", "Hydra", "Ermac", "Octo", "Xenomorph",
    "GodFather", "SpyNote", "Hook", "Vultur", "Nexus",
]


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of binary data."""
    return hashlib.sha256(data).hexdigest()


def extract_permissions(apk_bytes: bytes) -> list[str]:
    """Extract Android permissions from APK binary.

    In production, this would parse AndroidManifest.xml from the APK.
    For development, simulates permission extraction.
    """
    random.seed(hashlib.md5(apk_bytes[:1024] if len(apk_bytes) > 1024 else apk_bytes).hexdigest())
    all_perms = list(DANGEROUS_PERMISSIONS.keys())
    n = random.randint(3, 12)
    return sorted(random.sample(all_perms, min(n, len(all_perms))))


def compute_permission_risk(permissions: list[str]) -> float:
    """Compute risk score from declared permissions using risk weights."""
    if not permissions:
        return 0.0
    weights = [DANGEROUS_PERMISSIONS.get(p, 0.1) for p in permissions]
    # Weighted average with penalty for many dangerous permissions
    base = sum(weights) / len(weights)
    count_penalty = min(1.0, len([w for w in weights if w > 0.7]) / 5.0)
    return min(1.0, base * 0.6 + count_penalty * 0.4)


def static_byte_ngram_analysis(apk_bytes: bytes, n: int = 4) -> float:
    """Compute byte n-gram anomaly score using TF-IDF-like approach.

    Counts frequency of 4-byte grams and compares distribution entropy
    against known benign baseline. Higher entropy deviation = more suspicious.
    """
    if len(apk_bytes) < n:
        return 0.5

    # Sample bytes for efficiency (first 50KB + last 50KB)
    sample = apk_bytes[:50000] + apk_bytes[-50000:] if len(apk_bytes) > 100000 else apk_bytes

    # Extract n-grams
    ngrams = [sample[i:i + n] for i in range(len(sample) - n + 1)]
    if not ngrams:
        return 0.5

    counter = Counter(ngrams)
    total = len(ngrams)

    # Shannon entropy of n-gram distribution
    entropy = -sum((c / total) * math.log2(c / total) for c in counter.values() if c > 0)

    # Benign APKs typically have entropy ~12-14 bits for 4-grams
    # Packed/obfuscated malware has lower entropy (~8-11)
    # Very high entropy (>15) also suspicious (encrypted payloads)
    benign_center = 13.0
    deviation = abs(entropy - benign_center) / benign_center
    score = min(1.0, deviation)
    return score


def static_analyze(apk_bytes: bytes) -> dict:
    """Full static analysis: byte n-grams + permission risk."""
    start = time.time()
    permissions = extract_permissions(apk_bytes)
    permission_risk = compute_permission_risk(permissions)
    ngram_score = static_byte_ngram_analysis(apk_bytes)
    # Combined static score (weighted)
    static_score = ngram_score * 0.4 + permission_risk * 0.6
    elapsed = time.time() - start
    logger.info(f"Static analysis completed in {elapsed:.2f}s, score={static_score:.3f}")
    return {
        "byte_ngram_score": round(ngram_score, 4),
        "permission_risk": round(permission_risk, 4),
        "permissions": permissions,
        "static_score": round(static_score, 4),
        "analysis_time_s": round(elapsed, 3),
    }


def simulate_dynamic_analysis(apk_sha256: str) -> dict:
    """Simulate dynamic sandbox analysis.

    In production: submits APK to Cuckoo Sandbox, captures API call traces,
    runs LSTM(256) sequence model on 500-call windows.
    """
    random.seed(apk_sha256)
    start = time.time()
    n_calls = random.randint(50, 500)
    suspicious = random.sample(SUSPICIOUS_API_CALLS, k=random.randint(0, min(5, len(SUSPICIOUS_API_CALLS))))
    # Score based on suspicious API call ratio
    sus_ratio = len(suspicious) / max(1, n_calls) * 20
    noise = random.gauss(0, 0.1)
    dynamic_score = max(0.0, min(1.0, sus_ratio + noise))
    elapsed = time.time() - start
    return {
        "api_calls_captured": n_calls,
        "suspicious_apis": suspicious,
        "dynamic_score": round(dynamic_score, 4),
        "sandbox_duration_s": round(random.uniform(10, 24), 2),
    }


def simulate_genai_deobfuscation(apk_sha256: str, static_score: float) -> dict:
    """Simulate GenAI deobfuscation via Mistral.

    In production: sends obfuscated DEX bytecode to vLLM Mistral,
    reconstructs likely intent (e.g., 'SMS interception', 'overlay attack').
    """
    random.seed(apk_sha256 + "genai")
    intents = [
        "Banking credential overlay attack targeting UPI apps",
        "SMS interception for OTP theft and forwarding to C2 server",
        "Accessibility service abuse for automated fund transfer",
        "Keylogging via InputMethodService with exfiltration over HTTPS",
        "Screen recording during banking sessions with periodic C2 upload",
        "Phishing WebView injection mimicking bank login page",
        "Device admin registration for persistent remote access",
        "Contact harvesting for social engineering campaign",
        "No malicious intent detected — standard utility application",
        "Cryptocurrency miner disguised as system optimization tool",
    ]
    intent_idx = int(static_score * 8) % len(intents)
    intent = intents[intent_idx]
    is_malicious_intent = "No malicious" not in intent
    intent_score = random.uniform(0.6, 0.95) if is_malicious_intent else random.uniform(0.05, 0.3)
    family = random.choice(MALWARE_FAMILIES) if is_malicious_intent else None
    return {
        "deobfuscated_intent": intent,
        "intent_score": round(intent_score, 4),
        "malware_family": family,
    }


def meta_classify(static_score: float, dynamic_score: float,
                  intent_score: float, permission_risk: float) -> tuple[float, str, dict]:
    """XGBoost-style meta-classifier combining all analysis stages.

    Returns (meta_score, verdict, shap_features).
    """
    # Weighted combination simulating XGBoost ensemble
    weights = np.array([0.25, 0.30, 0.25, 0.20])
    features = np.array([static_score, dynamic_score, intent_score, permission_risk])
    meta_score = float(np.dot(weights, features))

    # Apply non-linear boosting for extreme scores
    if max(features) > 0.85:
        meta_score = min(1.0, meta_score * 1.2)
    if min(features) < 0.1 and meta_score > 0.5:
        meta_score *= 0.85

    meta_score = max(0.0, min(1.0, meta_score))

    # Verdict thresholds
    if meta_score >= 0.7:
        verdict = "malicious"
    elif meta_score >= 0.4:
        verdict = "suspicious"
    else:
        verdict = "benign"

    # SHAP-like feature importance (proportional contribution)
    total = sum(w * f for w, f in zip(weights, features))
    if total > 0:
        shap = {
            "static_importance": round(float(weights[0] * features[0] / total), 4),
            "dynamic_importance": round(float(weights[1] * features[1] / total), 4),
            "genai_importance": round(float(weights[2] * features[2] / total), 4),
            "permission_importance": round(float(weights[3] * features[3] / total), 4),
        }
    else:
        shap = {"static_importance": 0.25, "dynamic_importance": 0.25,
                "genai_importance": 0.25, "permission_importance": 0.25}

    return round(meta_score, 4), verdict, shap
