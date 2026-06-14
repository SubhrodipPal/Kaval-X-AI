"""TGN Inference — model loading and node scoring."""
from __future__ import annotations

import logging
import random
import numpy as np
from typing import Optional

from .config import TGNConfig

logger = logging.getLogger(__name__)


class TGNInference:
    """TGN model inference wrapper for fraud scoring.

    In production, this loads a trained TGN checkpoint and runs inference
    via TorchServe gRPC. For development, uses simulated scoring.
    """

    def __init__(self, model_path: Optional[str] = None, config: Optional[TGNConfig] = None):
        self.config = config or TGNConfig()
        self.model_path = model_path
        self._loaded = False
        logger.info(f"TGN Inference initialized (model_path={model_path})")

    def load_model(self):
        """Load trained TGN model from checkpoint."""
        if self.model_path:
            logger.info(f"Loading TGN model from {self.model_path}")
            # In production: torch.load(self.model_path)
        self._loaded = True
        logger.info("TGN model loaded (simulation mode)")

    def score_node(self, node_id: str, neighbors: list[dict] | None = None) -> dict:
        """Score a single node for fraud probability.

        Args:
            node_id: Account identifier
            neighbors: List of neighbor dicts with {node_id, amount, timestamp}

        Returns:
            Dict with tgn_score, embedding, risk_label
        """
        random.seed(hash(node_id) % 2**32)

        # Base score from node features
        base_score = random.gauss(0.3, 0.2)

        # Neighborhood influence
        if neighbors:
            neighbor_scores = [n.get("risk_score", 0.3) for n in neighbors]
            avg_neighbor_risk = sum(neighbor_scores) / len(neighbor_scores)
            base_score = base_score * 0.6 + avg_neighbor_risk * 0.4

        tgn_score = max(0.0, min(1.0, base_score))

        # Generate 128-dim embedding
        rng = np.random.RandomState(hash(node_id) % 2**32)
        embedding = rng.randn(self.config.node_embedding_dim).tolist()

        risk_label = (
            "critical" if tgn_score > 0.8 else
            "high" if tgn_score > 0.6 else
            "medium" if tgn_score > 0.3 else "low"
        )

        return {
            "node_id": node_id,
            "tgn_score": round(tgn_score, 4),
            "embedding": [round(x, 4) for x in embedding],
            "risk_label": risk_label,
        }

    def score_batch(self, node_ids: list[str]) -> list[dict]:
        """Score a batch of nodes."""
        return [self.score_node(nid) for nid in node_ids]
