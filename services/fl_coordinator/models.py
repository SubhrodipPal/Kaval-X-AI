"""
FL Coordinator — Pydantic Models
Data structures for federated learning rounds, gradient updates,
aggregated models, and differential privacy configuration.
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

class RoundStatus(str, Enum):
    WAITING = "waiting"
    COLLECTING = "collecting"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

class FLRound(BaseModel):
    """A single federated learning training round."""
    round_id: str = Field(default_factory=lambda: f"FLR-{uuid.uuid4().hex[:10].upper()}")
    round_number: int = 1
    status: RoundStatus = RoundStatus.WAITING
    participating_banks: list[str] = Field(default_factory=list)
    gradients_received: int = 0
    total_expected: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    aggregation_method: str = "federated_average"


class GradientUpdate(BaseModel):
    """Encrypted gradient update submitted by a participating bank."""
    submission_id: str = Field(default_factory=lambda: f"GRD-{uuid.uuid4().hex[:10].upper()}")
    bank_id: str
    round_id: str
    encrypted_gradients: str = Field(
        description="Base64-encoded encrypted gradient vector"
    )
    gradient_shape: list[int] = Field(
        default_factory=lambda: [1000],
        description="Shape of the original gradient tensor",
    )
    num_samples: int = Field(
        default=1000,
        description="Number of training samples used by this bank",
    )
    zk_proof: str = Field(
        default="",
        description="Zero-knowledge proof of honest gradient computation",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AggregatedModel(BaseModel):
    """Result of a federated aggregation round."""
    model_id: str = Field(default_factory=lambda: f"MDL-{uuid.uuid4().hex[:10].upper()}")
    round_id: str
    round_number: int = 1
    model_version: str = "1.0.0"
    accuracy_delta: float = 0.0
    loss_delta: float = 0.0
    participating_banks: list[str] = Field(default_factory=list)
    privacy_budget_spent: float = 0.0
    cumulative_privacy_spent: float = 0.0
    dp_epsilon_used: float = 0.0
    dp_delta_used: float = 0.0
    noise_multiplier: float = 0.0
    deployed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FLConfig(BaseModel):
    """Federated learning hyperparameters."""
    min_banks: int = 3
    max_rounds: int = 10
    epsilon: float = 0.5
    delta: float = 1e-5
    gradient_clip_norm: float = 1.0
    noise_multiplier: float = 1.1
    learning_rate: float = 0.01


class DPConfig(BaseModel):
    """Differential privacy configuration."""
    epsilon: float = 0.5
    delta: float = 1e-5
    noise_multiplier: float = 1.1
    max_grad_norm: float = 1.0
    mechanism: str = "gaussian"


class PrivacyBudget(BaseModel):
    """Privacy budget tracking."""
    total_epsilon: float = 10.0
    spent_epsilon: float = 0.0
    remaining_epsilon: float = 10.0
    total_rounds_completed: int = 0
    epsilon_per_round: float = 0.5
    estimated_rounds_remaining: int = 20


class RoundStartRequest(BaseModel):
    """Request to start a new FL round."""
    participating_banks: list[str]
    config: FLConfig | None = None


class AggregateRequest(BaseModel):
    """Request to trigger aggregation for a round."""
    force: bool = False


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Standard health-check response."""
    service: str
    status: str = "healthy"
    version: str
    active_rounds: int = 0
    total_models: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
