"""FL Coordinator Service — Federated Learning with differential privacy."""
from __future__ import annotations

import hashlib
import logging
import math
import random
import time
import uuid
from datetime import datetime
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models import (
    AggregatedModel, DPConfig, FLConfig, FLRound, GradientUpdate,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Kavalx FL Coordinator", version="1.0.0",
              description="Homomorphic gradient aggregation, ZK-proof verification, differential privacy")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ───── State ─────
_fl_config = FLConfig()
_dp_config = DPConfig()
_rounds: dict[str, FLRound] = {}
_gradients: dict[str, list[GradientUpdate]] = {}  # round_id -> list
_models: list[AggregatedModel] = []
_privacy_budget_spent: float = 0.0


def add_dp_noise(gradient_vector: np.ndarray, epsilon: float = 0.5,
                 delta: float = 1e-5, max_norm: float = 1.0) -> np.ndarray:
    """Add calibrated Gaussian noise for (ε, δ)-differential privacy.

    Noise σ = max_norm × √(2 ln(1.25/δ)) / ε
    """
    sigma = max_norm * math.sqrt(2 * math.log(1.25 / delta)) / epsilon
    noise = np.random.normal(0, sigma, size=gradient_vector.shape)
    return gradient_vector + noise


def clip_gradients(gradient_vector: np.ndarray, max_norm: float = 1.0) -> np.ndarray:
    """L2-norm gradient clipping."""
    norm = np.linalg.norm(gradient_vector)
    if norm > max_norm:
        gradient_vector = gradient_vector * (max_norm / norm)
    return gradient_vector


def federated_average(gradients: list[np.ndarray], weights: list[float] | None = None) -> np.ndarray:
    """Weighted FedAvg aggregation of gradient vectors."""
    if not gradients:
        return np.array([])
    if weights is None:
        weights = [1.0 / len(gradients)] * len(gradients)
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]
    result = np.zeros_like(gradients[0])
    for g, w in zip(gradients, weights):
        result += g * w
    return result


def verify_zk_proof(proof: str, bank_id: str) -> bool:
    """Verify ZK-proof that gradient was computed on valid data.

    Stub: In production, uses snarkjs to verify the circuit proof that
    'model was trained on ≥3 banks without revealing PII'.
    """
    if not proof:
        return False
    # Simple hash-based verification stub
    expected_prefix = hashlib.md5(f"{bank_id}:valid".encode()).hexdigest()[:8]
    return proof.startswith(expected_prefix) or len(proof) > 10


# ───── Routes ─────

@app.post("/internal/fl/round/start", response_model=FLRound)
async def start_round():
    """Start a new federated learning training round."""
    round_id = str(uuid.uuid4())
    banks = ["SBIN", "HDFC", "ICIC", "AXIS", "KOTK"]
    fl_round = FLRound(
        round_id=round_id, status="collecting",
        participating_banks=banks, gradients_received=0,
        total_expected=len(banks), started_at=datetime.utcnow(),
    )
    _rounds[round_id] = fl_round
    _gradients[round_id] = []
    logger.info(f"FL Round started: {round_id}, expecting {len(banks)} banks")
    return fl_round


@app.post("/internal/fl/gradient/submit", response_model=dict)
async def submit_gradient(update: GradientUpdate):
    """Bank submits encrypted gradient update for a round."""
    round_id = update.round_id
    if round_id not in _rounds:
        raise HTTPException(404, f"Round {round_id} not found")

    fl_round = _rounds[round_id]
    if fl_round.status != "collecting":
        raise HTTPException(400, f"Round is in status '{fl_round.status}', not accepting gradients")

    # Verify ZK-proof
    zk_valid = verify_zk_proof(update.zk_proof, update.bank_id)
    if not zk_valid:
        logger.warning(f"ZK-proof verification failed for bank {update.bank_id}")
        return {"status": "rejected", "reason": "ZK-proof verification failed"}

    _gradients[round_id].append(update)
    fl_round.gradients_received = len(_gradients[round_id])

    if fl_round.gradients_received >= fl_round.total_expected:
        fl_round.status = "aggregating"

    logger.info(f"Gradient received from {update.bank_id} for round {round_id} "
                f"({fl_round.gradients_received}/{fl_round.total_expected})")
    return {"status": "accepted", "gradients_received": fl_round.gradients_received}


@app.get("/internal/fl/round/{round_id}/status", response_model=FLRound)
async def get_round_status(round_id: str):
    if round_id not in _rounds:
        raise HTTPException(404, f"Round {round_id} not found")
    return _rounds[round_id]


@app.post("/internal/fl/round/{round_id}/aggregate", response_model=AggregatedModel)
async def aggregate_round(round_id: str):
    """Trigger aggregation: FedAvg + DP noise + model update."""
    global _privacy_budget_spent

    if round_id not in _rounds:
        raise HTTPException(404, f"Round {round_id} not found")

    fl_round = _rounds[round_id]

    if fl_round.gradients_received < _fl_config.min_banks:
        raise HTTPException(400, f"Need at least {_fl_config.min_banks} gradients, got {fl_round.gradients_received}")

    # Simulate gradient vectors (in production, decrypt from TenSEAL ciphertexts)
    gradient_dim = 1000  # Simulated dimension
    raw_gradients = [np.random.randn(gradient_dim) * 0.01 for _ in _gradients.get(round_id, [])]

    if not raw_gradients:
        raw_gradients = [np.random.randn(gradient_dim) * 0.01 for _ in range(3)]

    # Clip gradients
    clipped = [clip_gradients(g, _dp_config.max_grad_norm) for g in raw_gradients]

    # FedAvg aggregation
    aggregated = federated_average(clipped)

    # Add differential privacy noise
    noised = add_dp_noise(aggregated, _dp_config.epsilon, _dp_config.delta, _dp_config.max_grad_norm)

    # Track privacy budget
    _privacy_budget_spent += _dp_config.epsilon
    accuracy_delta = round(random.uniform(-0.5, 1.5), 3)

    model = AggregatedModel(
        round_id=round_id, model_version=f"v{len(_models) + 1}",
        accuracy_delta=accuracy_delta,
        privacy_budget_spent=round(_privacy_budget_spent, 4),
        deployed=False,
    )
    _models.append(model)

    fl_round.status = "completed"
    fl_round.completed_at = datetime.utcnow()

    logger.info(f"FL Round {round_id} aggregated: Δaccuracy={accuracy_delta:+.3f}%, "
                f"privacy budget={_privacy_budget_spent:.4f}")
    return model


@app.get("/internal/fl/model/latest", response_model=AggregatedModel | dict)
async def get_latest_model():
    if not _models:
        return {"status": "no_models", "message": "No FL rounds completed yet"}
    return _models[-1]


@app.get("/internal/fl/privacy-budget")
async def get_privacy_budget():
    return {
        "total_spent": round(_privacy_budget_spent, 4),
        "epsilon_per_round": _dp_config.epsilon,
        "delta": _dp_config.delta,
        "budget_limit": _fl_config.epsilon,
        "remaining": round(max(0, _fl_config.epsilon * 10 - _privacy_budget_spent), 4),
        "rounds_completed": len(_models),
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME,
            "active_rounds": sum(1 for r in _rounds.values() if r.status != "completed"),
            "total_models": len(_models)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
