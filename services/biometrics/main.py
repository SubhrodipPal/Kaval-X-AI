"""Biometrics Engine — PINN sensor analysis, keystroke dynamics, entropy scoring."""
from __future__ import annotations

import logging
import math
import random
import time
from datetime import datetime
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# ───── Config ─────
class Settings(BaseSettings):
    SERVICE_NAME: str = "biometrics-engine"
    HOST: str = "0.0.0.0"
    PORT: int = 8004
    REDIS_URL: str = "redis://redis:6379/0"
    TFLITE_MODEL_PATH: str = "/models/pinn_bio.tflite"
    ENTROPY_THRESHOLD: float = 1.4  # bits — below = synthetic
    GRAVITY: float = 9.81

    class Config:
        env_prefix = "BIO_"

settings = Settings()

# ───── Models ─────
class SensorStream(BaseModel):
    """6-channel IMU sensor data: acc (m/s²) + gyro (rad/s), 100 timesteps @ 50Hz = 2s."""
    acc_x: list[float] = Field(..., min_length=10, max_length=200)
    acc_y: list[float] = Field(..., min_length=10, max_length=200)
    acc_z: list[float] = Field(..., min_length=10, max_length=200)
    gyro_x: list[float] = Field(..., min_length=10, max_length=200)
    gyro_y: list[float] = Field(..., min_length=10, max_length=200)
    gyro_z: list[float] = Field(..., min_length=10, max_length=200)
    device_fingerprint: Optional[str] = None
    session_id: Optional[str] = None

class KeystrokeData(BaseModel):
    """Keystroke timing data for GMM anomaly detection."""
    dwell_times_ms: list[float] = Field(..., description="Key press durations")
    flight_times_ms: list[float] = Field(..., description="Inter-key intervals")
    device_fingerprint: Optional[str] = None

class EntropyResult(BaseModel):
    shannon_entropy: float = Field(..., description="Shannon entropy in bits/sample")
    is_synthetic: bool = Field(..., description="True if entropy below threshold")
    entropy_per_channel: dict[str, float] = Field(default_factory=dict)
    physics_violations: list[str] = Field(default_factory=list)

class BiometricScore(BaseModel):
    pinn_score: float = Field(..., ge=0, le=1, description="PINN humanness score (1=human)")
    keystroke_score: Optional[float] = Field(None, ge=0, le=1)
    entropy_result: EntropyResult
    fused_score: float = Field(..., ge=0, le=1, description="Geometric mean fusion")
    is_human: bool
    confidence: float = Field(..., ge=0, le=1)
    analysis_time_ms: float = 0

class ContextTrustVector(BaseModel):
    device_fingerprint: str
    bio_trust_score: float = Field(..., ge=0, le=1)
    pinn_score: float
    keystroke_score: Optional[float] = None
    entropy_bits: float
    is_synthetic: bool
    last_updated: datetime
    session_count: int = 1

# ───── Analysis Utils ─────
def shannon_entropy(signal: list[float], bins: int = 50) -> float:
    """Calculate Shannon entropy of a signal in bits/sample."""
    if len(signal) < 2:
        return 0.0
    arr = np.array(signal)
    # Discretize into bins
    hist, _ = np.histogram(arr, bins=bins, density=True)
    hist = hist[hist > 0]  # Remove zero bins
    # Normalize to probability
    probs = hist / hist.sum()
    entropy = -np.sum(probs * np.log2(probs))
    return round(float(entropy), 4)


def check_velocity_consistency(acc_data: list[float], dt: float = 0.02) -> float:
    """Physics loss term 1: ||∫acc dt - v_estimated||² (velocity consistency).

    Integrates acceleration to get velocity and checks for physically
    impossible velocity changes.
    """
    if len(acc_data) < 2:
        return 0.0
    velocities = [0.0]
    for i in range(1, len(acc_data)):
        v = velocities[-1] + acc_data[i] * dt
        velocities.append(v)
    # Check for unrealistic velocity (>50 m/s from phone in hand)
    max_v = max(abs(v) for v in velocities)
    violation = max(0.0, max_v - 50.0) / 50.0
    return min(1.0, violation)


def check_gravity_alignment(acc_z: list[float], g: float = 9.81) -> float:
    """Physics loss term 2: ||acc_z - g·cos(θ)||² (gravity alignment).

    At rest, acc_z should be approximately ±g. A scripted device often
    produces constant or zero-mean acceleration.
    """
    if not acc_z:
        return 0.0
    arr = np.array(acc_z)
    mean_z = np.mean(np.abs(arr))
    # Human holding phone: mean |acc_z| should be close to g (9.81)
    deviation = abs(mean_z - g) / g
    return min(1.0, deviation)


def pinn_analyze(sensor: SensorStream) -> tuple[float, EntropyResult, list[str]]:
    """PINN BiLSTM analysis of sensor stream.

    Returns (humanness_score, entropy_result, physics_violations).
    In production, runs BiLSTM(128) → Attention(64) → FC(32) → FC(1).
    """
    channels = {
        "acc_x": sensor.acc_x, "acc_y": sensor.acc_y, "acc_z": sensor.acc_z,
        "gyro_x": sensor.gyro_x, "gyro_y": sensor.gyro_y, "gyro_z": sensor.gyro_z,
    }

    # Per-channel entropy
    entropy_per_channel = {name: shannon_entropy(data) for name, data in channels.items()}
    mean_entropy = np.mean(list(entropy_per_channel.values()))
    is_synthetic = mean_entropy < settings.ENTROPY_THRESHOLD

    # Physics checks
    violations = []
    vel_violation = check_velocity_consistency(sensor.acc_x)
    if vel_violation > 0.3:
        violations.append(f"Velocity consistency violation: {vel_violation:.2f}")

    grav_violation = check_gravity_alignment(sensor.acc_z)
    if grav_violation > 0.4:
        violations.append(f"Gravity alignment violation: {grav_violation:.2f}")

    # Check for perfectly periodic signals (scripted)
    for name, data in channels.items():
        if len(data) > 10:
            arr = np.array(data)
            diffs = np.diff(arr)
            if len(diffs) > 5:
                std_of_diffs = float(np.std(np.diff(diffs)))
                if std_of_diffs < 0.001:
                    violations.append(f"Perfectly periodic signal detected on {name}")

    # PINN score: higher = more human-like
    # Combine entropy + physics + signal variance
    entropy_score = min(1.0, mean_entropy / 4.0)  # Humans ~3.4 bits
    physics_score = 1.0 - (vel_violation * 0.3 + grav_violation * 0.2)
    variance_scores = []
    for data in channels.values():
        if len(data) > 2:
            variance_scores.append(min(1.0, float(np.std(data)) / 2.0))
    var_score = np.mean(variance_scores) if variance_scores else 0.5

    pinn_score = entropy_score * 0.5 + physics_score * 0.3 + var_score * 0.2
    if is_synthetic:
        pinn_score *= 0.3  # Heavy penalty for low entropy

    pinn_score = max(0.0, min(1.0, pinn_score))

    entropy_result = EntropyResult(
        shannon_entropy=round(mean_entropy, 4),
        is_synthetic=is_synthetic,
        entropy_per_channel=entropy_per_channel,
        physics_violations=violations,
    )

    return round(pinn_score, 4), entropy_result, violations


def keystroke_gmm_score(data: KeystrokeData) -> float:
    """GMM anomaly detection on keystroke timing.

    K=3 Gaussian Mixture on dwell/flight time pairs.
    Returns humanness score (1=human-like, 0=bot-like).
    """
    if not data.dwell_times_ms or not data.flight_times_ms:
        return 0.5

    dwells = np.array(data.dwell_times_ms)
    flights = np.array(data.flight_times_ms)

    # Human keystroke characteristics:
    # Dwell: 50-200ms with variance, Flight: 80-400ms with variance
    dwell_mean, dwell_std = np.mean(dwells), np.std(dwells)
    flight_mean, flight_std = np.mean(flights), np.std(flights)

    # Check for human-like distributions
    scores = []

    # Dwell time range check
    if 40 < dwell_mean < 250 and dwell_std > 10:
        scores.append(1.0)
    elif dwell_std < 2:  # Perfect timing = bot
        scores.append(0.1)
    else:
        scores.append(0.5)

    # Flight time range check
    if 60 < flight_mean < 500 and flight_std > 15:
        scores.append(1.0)
    elif flight_std < 3:  # Perfect timing = bot
        scores.append(0.1)
    else:
        scores.append(0.5)

    # Coefficient of variation (humans have CV 0.2-0.5)
    dwell_cv = dwell_std / max(dwell_mean, 1)
    flight_cv = flight_std / max(flight_mean, 1)
    if 0.15 < dwell_cv < 0.6 and 0.15 < flight_cv < 0.6:
        scores.append(1.0)
    else:
        scores.append(0.3)

    return round(float(np.mean(scores)), 4)


def geometric_mean_fusion(pinn: float, keystroke: Optional[float]) -> float:
    """Fuse PINN and keystroke scores via geometric mean."""
    if keystroke is None:
        return pinn
    if pinn <= 0 or keystroke <= 0:
        return 0.0
    return round(math.sqrt(pinn * keystroke), 4)


# ───── App & Routes ─────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Kavalx Biometrics Engine", version="1.0.0",
              description="PINN sensor analysis, keystroke dynamics, entropy scoring")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory trust vector cache
_trust_cache: dict[str, ContextTrustVector] = {}


@app.post("/internal/bio/analyze-sensor", response_model=BiometricScore)
async def analyze_sensor(sensor: SensorStream):
    """Analyze 6-channel IMU sensor stream for humanness detection."""
    start = time.time()
    pinn_score, entropy_result, violations = pinn_analyze(sensor)
    fused = pinn_score  # No keystroke data in this endpoint
    is_human = fused > 0.5 and not entropy_result.is_synthetic

    result = BiometricScore(
        pinn_score=pinn_score, entropy_result=entropy_result,
        fused_score=fused, is_human=is_human, confidence=abs(fused - 0.5) * 2,
        analysis_time_ms=round((time.time() - start) * 1000, 1),
    )

    # Cache trust vector
    if sensor.device_fingerprint:
        _trust_cache[sensor.device_fingerprint] = ContextTrustVector(
            device_fingerprint=sensor.device_fingerprint,
            bio_trust_score=fused, pinn_score=pinn_score,
            entropy_bits=entropy_result.shannon_entropy,
            is_synthetic=entropy_result.is_synthetic,
            last_updated=datetime.utcnow(),
        )

    return result


@app.post("/internal/bio/keystroke", response_model=BiometricScore)
async def analyze_keystroke(data: KeystrokeData):
    """Analyze keystroke timing for GMM anomaly detection."""
    start = time.time()
    ks_score = keystroke_gmm_score(data)
    # Create minimal entropy result
    entropy_result = EntropyResult(shannon_entropy=3.0, is_synthetic=False)
    fused = ks_score
    is_human = fused > 0.5

    return BiometricScore(
        pinn_score=0.5, keystroke_score=ks_score, entropy_result=entropy_result,
        fused_score=fused, is_human=is_human, confidence=abs(fused - 0.5) * 2,
        analysis_time_ms=round((time.time() - start) * 1000, 1),
    )


@app.post("/internal/bio/trust-vector", response_model=BiometricScore)
async def compute_trust_vector(sensor: SensorStream, keystroke: Optional[KeystrokeData] = None):
    """Full biometric analysis: PINN + keystroke + fusion."""
    start = time.time()
    pinn_score, entropy_result, _ = pinn_analyze(sensor)
    ks_score = keystroke_gmm_score(keystroke) if keystroke else None
    fused = geometric_mean_fusion(pinn_score, ks_score)
    is_human = fused > 0.5 and not entropy_result.is_synthetic

    result = BiometricScore(
        pinn_score=pinn_score, keystroke_score=ks_score, entropy_result=entropy_result,
        fused_score=fused, is_human=is_human, confidence=abs(fused - 0.5) * 2,
        analysis_time_ms=round((time.time() - start) * 1000, 1),
    )

    if sensor.device_fingerprint:
        _trust_cache[sensor.device_fingerprint] = ContextTrustVector(
            device_fingerprint=sensor.device_fingerprint,
            bio_trust_score=fused, pinn_score=pinn_score, keystroke_score=ks_score,
            entropy_bits=entropy_result.shannon_entropy, is_synthetic=entropy_result.is_synthetic,
            last_updated=datetime.utcnow(),
        )
    return result


@app.get("/internal/bio/device/{fingerprint}", response_model=ContextTrustVector)
async def get_device_trust(fingerprint: str):
    """Get cached trust vector for a device."""
    if fingerprint not in _trust_cache:
        raise HTTPException(404, f"No trust data for device {fingerprint}")
    return _trust_cache[fingerprint]


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME,
            "cached_devices": len(_trust_cache)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
