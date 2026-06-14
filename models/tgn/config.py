"""
TGN (Temporal Graph Neural Network) Configuration
===================================================
Hyperparameters for the Kavalx TGN model used in transaction-graph
fraud detection.  The model learns temporal node embeddings on a
bipartite (account ↔ account) transaction graph and predicts
fraudulent links via a learned link predictor.

Architecture overview
---------------------
1. **Time2Vec** encoder maps continuous timestamps to a learnable
   64-d periodic representation.
2. **MessageFunction** (MLP) compresses source-memory ‖ dest-memory ‖
   edge-features into a 172-d message.
3. **MemoryUpdater** (GRUCell) integrates incoming messages into
   per-node memory vectors.
4. **TemporalGraphAttention** (2 GAT layers × 4 heads) aggregates
   neighbourhood context into node embeddings.
5. **LinkPredictor** (MLP + sigmoid) scores candidate edges.

References
----------
- Rossi et al., "Temporal Graph Networks for Deep Learning on Dynamic
  Graphs", ICML 2020 Workshop on GRL+.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class TGNConfig:
    """All TGN hyper-parameters in a single, serialisable object."""

    # ── Node / Edge dimensions ──────────────────────────────────────
    node_embedding_dim: int = 128
    edge_feature_dim: int = 64
    memory_dim: int = 172

    # ── Message function ────────────────────────────────────────────
    # MLP:  (2 × memory_dim + edge_feature_dim) → memory_dim
    message_function: str = "mlp"
    message_hidden_dim: int = 256  # hidden layer inside the message MLP

    # ── Memory updater ──────────────────────────────────────────────
    # GRUCell(input_size=memory_dim, hidden_size=memory_dim)
    memory_updater: str = "gru"

    # ── Time encoding ───────────────────────────────────────────────
    time_encoder_dim: int = 64  # Time2Vec output dimension

    # ── Temporal Graph Attention ────────────────────────────────────
    gat_layers: int = 2
    gat_heads: int = 4
    gat_dropout: float = 0.1

    # ── Link predictor ──────────────────────────────────────────────
    # MLP:  memory_dim × 2  →  128  →  64  →  1   + sigmoid
    link_predictor: str = "mlp"
    link_hidden_dims: List[int] = field(default_factory=lambda: [128, 64])

    # ── Training ────────────────────────────────────────────────────
    learning_rate: float = 1e-4
    weight_decay: float = 1e-5
    batch_size: int = 512
    epochs: int = 50
    patience: int = 7  # early-stopping patience (epochs)

    # ── Loss ────────────────────────────────────────────────────────
    # BCEWithLogitsLoss with per-sample class weights
    graph_reg_lambda: float = 0.01  # L2 regularisation on embeddings
    pos_weight: float = 49.0        # neg:pos = 49:1

    # ── Scheduler ───────────────────────────────────────────────────
    scheduler: str = "cosine"
    scheduler_T_max: int = 50
    scheduler_eta_min: float = 1e-6

    # ── Negative sampling ───────────────────────────────────────────
    neg_sampling_strategy: str = "temporal"
    neg_sampling_window_minutes: float = 5.0  # ±5 min window

    # ── Synthetic data defaults ─────────────────────────────────────
    num_nodes: int = 500_000
    num_edges: int = 5_000_000
    fraud_ratio: float = 0.02  # 2 % fraud

    # ── Checkpointing ───────────────────────────────────────────────
    checkpoint_dir: str = "checkpoints/tgn"
    log_dir: str = "logs/tgn"

    # ── Device ──────────────────────────────────────────────────────
    device: str = "cuda"  # overridden at runtime if GPU unavailable

    def __post_init__(self):
        """Derived attributes computed once after init."""
        # Message MLP input size = 2×memory + edge features
        self.message_input_dim: int = 2 * self.memory_dim + self.edge_feature_dim
        # GAT per-head dimension (must divide evenly)
        assert self.memory_dim % self.gat_heads == 0, (
            f"memory_dim ({self.memory_dim}) must be divisible by "
            f"gat_heads ({self.gat_heads})"
        )
        self.gat_head_dim: int = self.memory_dim // self.gat_heads
