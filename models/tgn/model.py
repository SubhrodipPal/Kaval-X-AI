"""
TGN — Temporal Graph Neural Network Model
==========================================
Full PyTorch implementation of TGN for fraud detection on dynamic
transaction graphs.  The model maintains per-node memory states that
are updated as new edges (transactions) arrive, enabling it to
capture evolving behavioural patterns.

Module hierarchy
----------------
TGN
 ├── Time2Vec           – learnable periodic time encoding
 ├── MessageFunction    – MLP that compresses edge events into messages
 ├── MemoryUpdater      – GRUCell that folds messages into node memory
 ├── TemporalGraphAttention – multi-head attention over temporal neighbours
 └── LinkPredictor      – MLP scoring candidate edges (fraud / legit)
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# torch_geometric is optional — the model can run in standalone mode
# with manual neighbour sampling when pyg is unavailable.
try:
    from torch_geometric.nn import GATConv
    HAS_PYG = True
except ImportError:
    HAS_PYG = False

from .config import TGNConfig


# ════════════════════════════════════════════════════════════════════
#  Time2Vec  –  Learnable Periodic Time Encoding
# ════════════════════════════════════════════════════════════════════

class Time2Vec(nn.Module):
    """
    Maps a scalar timestamp Δt to a *time_dim*-dimensional vector via
    a learnable mix of linear and periodic (sin) components.

        t2v(Δt)[0]   = w₀·Δt + b₀            (linear trend)
        t2v(Δt)[i>0] = sin(wᵢ·Δt + bᵢ)       (periodic components)

    Reference: Kazemi et al., "Time2Vec: Learning Vector Representation
    of Time", 2019.
    """

    def __init__(self, time_dim: int = 64):
        super().__init__()
        self.time_dim = time_dim
        # One linear component + (time_dim - 1) periodic components
        self.w_linear = nn.Linear(1, 1)
        self.w_periodic = nn.Linear(1, time_dim - 1)

    def forward(self, delta_t: torch.Tensor) -> torch.Tensor:
        """
        Parameters
        ----------
        delta_t : Tensor of shape (batch,) or (batch, 1)
            Time deltas (seconds since reference / last event).

        Returns
        -------
        Tensor of shape (batch, time_dim)
        """
        if delta_t.dim() == 1:
            delta_t = delta_t.unsqueeze(-1)  # (B, 1)

        linear_part = self.w_linear(delta_t)                   # (B, 1)
        periodic_part = torch.sin(self.w_periodic(delta_t))    # (B, D-1)
        return torch.cat([linear_part, periodic_part], dim=-1) # (B, D)


# ════════════════════════════════════════════════════════════════════
#  MessageFunction  –  Edge-Event → Message Compression
# ════════════════════════════════════════════════════════════════════

class MessageFunction(nn.Module):
    """
    Compresses an edge event into a fixed-size message vector.

    Input: concat(memory_src, memory_dst, edge_features, time_encoding)
    Output: message of size *memory_dim*.

    Architecture
    ------------
    Linear(input_dim → hidden_dim) → ReLU → Dropout →
    Linear(hidden_dim → memory_dim)
    """

    def __init__(self, config: TGNConfig):
        super().__init__()
        # input = src_memory ‖ dst_memory ‖ edge_features ‖ time_encoding
        input_dim = (2 * config.memory_dim
                     + config.edge_feature_dim
                     + config.time_encoder_dim)
        self.mlp = nn.Sequential(
            nn.Linear(input_dim, config.message_hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(0.1),
            nn.Linear(config.message_hidden_dim, config.memory_dim),
        )

    def forward(
        self,
        src_memory: torch.Tensor,
        dst_memory: torch.Tensor,
        edge_features: torch.Tensor,
        time_encoding: torch.Tensor,
    ) -> torch.Tensor:
        """
        Parameters
        ----------
        src_memory, dst_memory : (B, memory_dim)
        edge_features          : (B, edge_feature_dim)
        time_encoding          : (B, time_encoder_dim)

        Returns
        -------
        messages : (B, memory_dim)
        """
        x = torch.cat([src_memory, dst_memory, edge_features, time_encoding], dim=-1)
        return self.mlp(x)


# ════════════════════════════════════════════════════════════════════
#  MemoryUpdater  –  GRU-based Node Memory Update
# ════════════════════════════════════════════════════════════════════

class MemoryUpdater(nn.Module):
    """
    Recurrently updates node memory with incoming messages using a
    GRUCell.

        memory_new = GRU(message, memory_old)
    """

    def __init__(self, config: TGNConfig):
        super().__init__()
        self.gru = nn.GRUCell(
            input_size=config.memory_dim,
            hidden_size=config.memory_dim,
        )

    def forward(
        self,
        messages: torch.Tensor,
        memory: torch.Tensor,
    ) -> torch.Tensor:
        """
        Parameters
        ----------
        messages : (B, memory_dim)  aggregated messages for each node
        memory   : (B, memory_dim)  current node memory

        Returns
        -------
        updated_memory : (B, memory_dim)
        """
        return self.gru(messages, memory)


# ════════════════════════════════════════════════════════════════════
#  Fallback GAT layer (when torch_geometric is not available)
# ════════════════════════════════════════════════════════════════════

class ManualGATLayer(nn.Module):
    """
    Single-layer multi-head Graph Attention when torch_geometric is
    unavailable.  Operates on dense adjacency or edge-list format.
    """

    def __init__(self, in_dim: int, out_dim: int, heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.heads = heads
        self.head_dim = out_dim // heads
        assert out_dim % heads == 0

        self.W = nn.Linear(in_dim, out_dim, bias=False)
        self.a_src = nn.Parameter(torch.zeros(1, heads, self.head_dim))
        self.a_dst = nn.Parameter(torch.zeros(1, heads, self.head_dim))
        nn.init.xavier_uniform_(self.a_src)
        nn.init.xavier_uniform_(self.a_dst)
        self.leaky_relu = nn.LeakyReLU(0.2)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
    ) -> torch.Tensor:
        """
        Parameters
        ----------
        x          : (N, in_dim) node features
        edge_index : (2, E) source and target indices

        Returns
        -------
        out : (N, out_dim)
        """
        N = x.size(0)
        h = self.W(x).view(N, self.heads, self.head_dim)  # (N, H, D)

        src, dst = edge_index  # (E,), (E,)

        # Attention coefficients
        alpha_src = (h[src] * self.a_src).sum(dim=-1)  # (E, H)
        alpha_dst = (h[dst] * self.a_dst).sum(dim=-1)  # (E, H)
        alpha = self.leaky_relu(alpha_src + alpha_dst)  # (E, H)

        # Softmax per destination node
        alpha_max = torch.zeros(N, self.heads, device=x.device)
        alpha_max.scatter_reduce_(
            0,
            dst.unsqueeze(-1).expand_as(alpha),
            alpha,
            reduce="amax",
            include_self=True,
        )
        alpha = torch.exp(alpha - alpha_max[dst])
        alpha_sum = torch.zeros(N, self.heads, device=x.device)
        alpha_sum.scatter_add_(0, dst.unsqueeze(-1).expand_as(alpha), alpha)
        alpha = alpha / (alpha_sum[dst] + 1e-8)
        alpha = self.dropout(alpha)

        # Weighted aggregation
        msg = h[src] * alpha.unsqueeze(-1)  # (E, H, D)
        out = torch.zeros(N, self.heads, self.head_dim, device=x.device)
        out.scatter_add_(
            0,
            dst.unsqueeze(-1).unsqueeze(-1).expand_as(msg),
            msg,
        )
        return out.reshape(N, -1)  # (N, out_dim)


# ════════════════════════════════════════════════════════════════════
#  TemporalGraphAttention  –  Multi-layer GAT
# ════════════════════════════════════════════════════════════════════

class TemporalGraphAttention(nn.Module):
    """
    Stack of GAT layers that compute contextual node embeddings from
    the temporal neighbourhood.

    If torch_geometric is available, uses the optimised ``GATConv``;
    otherwise falls back to ``ManualGATLayer``.
    """

    def __init__(self, config: TGNConfig):
        super().__init__()
        layers = []
        in_dim = config.memory_dim
        out_dim = config.memory_dim
        for i in range(config.gat_layers):
            if HAS_PYG:
                layers.append(
                    GATConv(
                        in_channels=in_dim,
                        out_channels=out_dim // config.gat_heads,
                        heads=config.gat_heads,
                        dropout=config.gat_dropout,
                        concat=True,
                    )
                )
            else:
                layers.append(
                    ManualGATLayer(
                        in_dim=in_dim,
                        out_dim=out_dim,
                        heads=config.gat_heads,
                        dropout=config.gat_dropout,
                    )
                )
            in_dim = out_dim  # after first layer, in == out
        self.layers = nn.ModuleList(layers)
        self.layer_norms = nn.ModuleList(
            [nn.LayerNorm(out_dim) for _ in range(config.gat_layers)]
        )
        self.dropout = nn.Dropout(config.gat_dropout)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
    ) -> torch.Tensor:
        """
        Parameters
        ----------
        x          : (N, memory_dim) node features (from memory)
        edge_index : (2, E) graph connectivity

        Returns
        -------
        embeddings : (N, memory_dim)
        """
        for gat, ln in zip(self.layers, self.layer_norms):
            residual = x
            x = gat(x, edge_index)
            x = F.elu(x)
            x = self.dropout(x)
            x = ln(x + residual)  # residual connection
        return x


# ════════════════════════════════════════════════════════════════════
#  LinkPredictor  –  Edge Score MLP
# ════════════════════════════════════════════════════════════════════

class LinkPredictor(nn.Module):
    """
    Scores a candidate edge (src, dst) using an MLP over the
    concatenation of the two node embeddings.

    Architecture: (2 × memory_dim) → 128 → 64 → 1
    Sigmoid is applied externally via BCEWithLogitsLoss during training.
    """

    def __init__(self, config: TGNConfig):
        super().__init__()
        in_dim = 2 * config.memory_dim
        layers = []
        for h in config.link_hidden_dims:
            layers.extend([nn.Linear(in_dim, h), nn.ReLU(inplace=True), nn.Dropout(0.1)])
            in_dim = h
        layers.append(nn.Linear(in_dim, 1))
        self.mlp = nn.Sequential(*layers)

    def forward(
        self,
        z_src: torch.Tensor,
        z_dst: torch.Tensor,
    ) -> torch.Tensor:
        """
        Parameters
        ----------
        z_src, z_dst : (B, memory_dim) node embeddings

        Returns
        -------
        logits : (B, 1)
        """
        h = torch.cat([z_src, z_dst], dim=-1)
        return self.mlp(h)


# ════════════════════════════════════════════════════════════════════
#  TGN  –  Main Model
# ════════════════════════════════════════════════════════════════════

class TGN(nn.Module):
    """
    Temporal Graph Network for transaction-level fraud detection.

    The model maintains a *memory bank* (one vector per node) that is
    updated every time a node participates in a transaction.  At
    scoring time, the memory vectors are refined through a temporal
    graph-attention layer and fed to a link predictor.

    Typical usage
    -------------
    >>> cfg = TGNConfig()
    >>> model = TGN(cfg)
    >>> # src_ids, dst_ids: (B,) node indices
    >>> # edge_feats: (B, 64) transaction features
    >>> # timestamps: (B,) float seconds
    >>> logits = model(src_ids, dst_ids, edge_feats, timestamps, edge_index)
    """

    def __init__(self, config: TGNConfig):
        super().__init__()
        self.config = config

        # Sub-modules
        self.time_encoder = Time2Vec(config.time_encoder_dim)
        self.message_fn = MessageFunction(config)
        self.memory_updater = MemoryUpdater(config)
        self.attention = TemporalGraphAttention(config)
        self.link_predictor = LinkPredictor(config)

        # Node memory bank (not a parameter — detached buffer)
        # Initialised to zeros; populated during forward / update steps.
        self.register_buffer(
            "memory",
            torch.zeros(config.num_nodes, config.memory_dim),
        )
        # Track last-update timestamp per node (for time delta computation)
        self.register_buffer(
            "last_update",
            torch.zeros(config.num_nodes),
        )

        # Projection from raw node id to initial embedding (cold start)
        self.node_embedding = nn.Embedding(config.num_nodes, config.memory_dim)
        nn.init.xavier_uniform_(self.node_embedding.weight)

    # ── helpers ─────────────────────────────────────────────────────

    def _get_memory(self, node_ids: torch.Tensor) -> torch.Tensor:
        """Retrieve memory for a batch of nodes, falling back to the
        learned embedding if memory is all-zero (cold start)."""
        mem = self.memory[node_ids]
        cold = (mem.abs().sum(dim=-1) == 0)  # never-updated nodes
        if cold.any():
            mem[cold] = self.node_embedding(node_ids[cold])
        return mem

    def _compute_time_delta(
        self, node_ids: torch.Tensor, timestamps: torch.Tensor
    ) -> torch.Tensor:
        """Time since each node's last event."""
        delta = timestamps - self.last_update[node_ids]
        return delta.clamp(min=0)

    # ── forward ─────────────────────────────────────────────────────

    def forward(
        self,
        src_ids: torch.Tensor,
        dst_ids: torch.Tensor,
        edge_features: torch.Tensor,
        timestamps: torch.Tensor,
        edge_index: torch.Tensor,
        neg_dst_ids: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Full forward pass: compute messages, update memory, compute
        attention embeddings, and score edges.

        Parameters
        ----------
        src_ids       : (B,) long — source node indices
        dst_ids       : (B,) long — destination node indices
        edge_features : (B, edge_feature_dim) — transaction features
        timestamps    : (B,) float — event timestamps
        edge_index    : (2, E) long — graph connectivity for GAT
        neg_dst_ids   : (B,) long, optional — negative destinations

        Returns
        -------
        pos_logits : (B, 1) — scores for positive (real) edges
        neg_logits : (B, 1) — scores for negative (sampled) edges
                     (zeros if neg_dst_ids is None)
        """
        B = src_ids.size(0)

        # 1. Retrieve current memory
        src_mem = self._get_memory(src_ids)
        dst_mem = self._get_memory(dst_ids)

        # 2. Time encoding
        delta_src = self._compute_time_delta(src_ids, timestamps)
        time_enc = self.time_encoder(delta_src)  # (B, time_dim)

        # 3. Compute messages
        messages = self.message_fn(src_mem, dst_mem, edge_features, time_enc)

        # 4. Update memory
        new_src_mem = self.memory_updater(messages, src_mem)
        new_dst_mem = self.memory_updater(messages, dst_mem)

        # 5. Write back to memory bank (detach to stop gradient through bank)
        with torch.no_grad():
            self.memory[src_ids] = new_src_mem.detach()
            self.memory[dst_ids] = new_dst_mem.detach()
            self.last_update[src_ids] = timestamps.detach()
            self.last_update[dst_ids] = timestamps.detach()

        # 6. Collect all unique nodes for GAT
        unique_nodes = torch.unique(torch.cat([src_ids, dst_ids]))
        node_feats = self._get_memory(unique_nodes)

        # 7. Temporal Graph Attention
        z = self.attention(node_feats, edge_index)

        # 8. Map back to batch indices
        node_to_idx = {nid.item(): i for i, nid in enumerate(unique_nodes)}
        src_idx = torch.tensor([node_to_idx[s.item()] for s in src_ids],
                               device=src_ids.device)
        dst_idx = torch.tensor([node_to_idx[d.item()] for d in dst_ids],
                               device=dst_ids.device)
        z_src = z[src_idx]
        z_dst = z[dst_idx]

        # 9. Link prediction — positive edges
        pos_logits = self.link_predictor(z_src, z_dst)  # (B, 1)

        # 10. Negative edges
        neg_logits = torch.zeros(B, 1, device=pos_logits.device)
        if neg_dst_ids is not None:
            # Ensure neg nodes are in the embedding
            for nid in neg_dst_ids:
                nid_item = nid.item()
                if nid_item not in node_to_idx:
                    node_to_idx[nid_item] = len(node_to_idx)
            # Recompute with neg nodes included
            all_nodes = torch.unique(torch.cat([unique_nodes, neg_dst_ids]))
            all_feats = self._get_memory(all_nodes)
            z_all = self.attention(all_feats, edge_index)
            node_to_idx_all = {nid.item(): i for i, nid in enumerate(all_nodes)}
            neg_idx = torch.tensor(
                [node_to_idx_all.get(n.item(), 0) for n in neg_dst_ids],
                device=neg_dst_ids.device,
            )
            z_neg = z_all[neg_idx]
            src_idx_all = torch.tensor(
                [node_to_idx_all[s.item()] for s in src_ids],
                device=src_ids.device,
            )
            z_src_all = z_all[src_idx_all]
            neg_logits = self.link_predictor(z_src_all, z_neg)

        return pos_logits, neg_logits

    def reset_memory(self):
        """Zero-out the memory bank and timestamps (e.g. between epochs)."""
        self.memory.zero_()
        self.last_update.zero_()

    def detach_memory(self):
        """Detach memory from the computation graph (call between batches)."""
        self.memory.detach_()
        self.last_update.detach_()

    @torch.no_grad()
    def get_node_embeddings(
        self,
        node_ids: torch.Tensor,
        edge_index: torch.Tensor,
    ) -> torch.Tensor:
        """
        Return contextual embeddings for a set of nodes without
        updating memory.  Used at inference time.
        """
        self.eval()
        feats = self._get_memory(node_ids)
        z = self.attention(feats, edge_index)
        return z


# ════════════════════════════════════════════════════════════════════
#  Loss helper
# ════════════════════════════════════════════════════════════════════

def tgn_loss(
    pos_logits: torch.Tensor,
    neg_logits: torch.Tensor,
    config: TGNConfig,
    model: TGN,
) -> torch.Tensor:
    """
    Combined TGN loss:
        L = BCE(pos, 1) + BCE(neg, 0) + λ · ‖embeddings‖²

    Uses pos_weight to handle class imbalance (49:1).
    """
    pos_weight = torch.tensor([config.pos_weight], device=pos_logits.device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    pos_labels = torch.ones_like(pos_logits)
    neg_labels = torch.zeros_like(neg_logits)

    loss_pos = criterion(pos_logits, pos_labels)
    loss_neg = F.binary_cross_entropy_with_logits(neg_logits, neg_labels)
    loss = loss_pos + loss_neg

    # Graph regularisation
    if config.graph_reg_lambda > 0:
        reg = sum(p.pow(2).sum() for p in model.parameters())
        loss = loss + config.graph_reg_lambda * reg

    return loss
