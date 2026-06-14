"""
PINN Biometrics — Physics-Informed Neural Network Model
========================================================
Detects Remote Access Trojan (RAT) sessions vs genuine human
device interactions using 6-channel IMU data (accelerometer +
gyroscope).

The model is a BiLSTM with self-attention, regularised by three
physics-informed loss terms that encode fundamental kinematic
constraints.

Physics losses
--------------
1. **Velocity consistency** — the integral of measured acceleration
   should be consistent with estimated velocity:
       L₁ = ‖∫ a(t) dt − v̂(t)‖²

2. **Gravity alignment** — the z-axis accelerometer should approximate
   g·cos(θ) where θ is the device tilt angle:
       L₂ = ‖a_z − g·cos(θ)‖²

3. **Entropy constraint** — genuine human signals have higher
   Shannon entropy than scripted RAT patterns:
       L₃ = max(0, H_min − H(signal))

Combined: L = L_BCE + λ₁·L₁ + λ₂·L₂ + λ₃·L₃
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import PINNBioConfig


# ════════════════════════════════════════════════════════════════════
#  Attention Layer
# ════════════════════════════════════════════════════════════════════

class Attention(nn.Module):
    """
    Additive (Bahdanau-style) attention over LSTM hidden states.

    Given a sequence of hidden states H ∈ ℝ^{T×D}, produces an
    attention-weighted context vector c ∈ ℝ^{D}.
    """

    def __init__(self, hidden_dim: int, attention_dim: int):
        super().__init__()
        self.W = nn.Linear(hidden_dim, attention_dim, bias=False)
        self.v = nn.Linear(attention_dim, 1, bias=False)

    def forward(self, hidden_states: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Parameters
        ----------
        hidden_states : (B, T, D)

        Returns
        -------
        context : (B, D)
        weights : (B, T)
        """
        energy = torch.tanh(self.W(hidden_states))  # (B, T, attn_dim)
        scores = self.v(energy).squeeze(-1)          # (B, T)
        weights = F.softmax(scores, dim=-1)          # (B, T)
        context = torch.bmm(weights.unsqueeze(1), hidden_states).squeeze(1)  # (B, D)
        return context, weights


# ════════════════════════════════════════════════════════════════════
#  PINNBiometricModel
# ════════════════════════════════════════════════════════════════════

class PINNBiometricModel(nn.Module):
    """
    Bidirectional LSTM with self-attention for behavioural biometric
    classification, regularised by physics-informed loss terms.

    Architecture
    ------------
    IMU(6ch) → BiLSTM(128, 2-layer) → Attention(256→64)
             → FC(64→32) → ReLU → FC(32→1)
    """

    def __init__(self, config: PINNBioConfig):
        super().__init__()
        self.config = config

        # ── BiLSTM encoder ──────────────────────────────────────────
        self.lstm = nn.LSTM(
            input_size=config.input_channels,
            hidden_size=config.lstm_hidden,
            num_layers=config.lstm_layers,
            dropout=config.lstm_dropout if config.lstm_layers > 1 else 0,
            bidirectional=config.bidirectional,
            batch_first=True,
        )
        lstm_out_dim = config.lstm_hidden * (2 if config.bidirectional else 1)

        # ── Attention ───────────────────────────────────────────────
        self.attention = Attention(lstm_out_dim, config.attention_dim)

        # ── Classifier head ─────────────────────────────────────────
        self.classifier = nn.Sequential(
            nn.Linear(lstm_out_dim, config.fc_hidden),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(config.fc_hidden, 1),
        )

        # ── Batch normalisation on input ────────────────────────────
        self.input_bn = nn.BatchNorm1d(config.input_channels)

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Parameters
        ----------
        x : (B, T, 6) — 6-channel IMU time series

        Returns
        -------
        logits  : (B, 1)
        weights : (B, T) — attention weights (for interpretability)
        """
        B, T, C = x.shape

        # Normalise per-channel across the time axis
        x_perm = x.permute(0, 2, 1)         # (B, C, T)
        x_perm = self.input_bn(x_perm)
        x = x_perm.permute(0, 2, 1)         # (B, T, C)

        # BiLSTM
        lstm_out, _ = self.lstm(x)           # (B, T, 2*H)

        # Attention
        context, weights = self.attention(lstm_out)  # (B, 2*H), (B, T)

        # Classification
        logits = self.classifier(context)    # (B, 1)
        return logits, weights


# ════════════════════════════════════════════════════════════════════
#  Physics Loss Functions
# ════════════════════════════════════════════════════════════════════

def velocity_consistency_loss(
    imu_data: torch.Tensor,
    config: PINNBioConfig,
) -> torch.Tensor:
    """
    L₁ — Velocity consistency.

    Integrates the acceleration channels (first 3 of 6) via the
    trapezoidal rule and penalises deviation from a smooth velocity
    profile estimated by finite differences.

        L₁ = mean ‖ cumsum(acc·dt) − v_estimated ‖²

    Parameters
    ----------
    imu_data : (B, T, 6)  acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z
    """
    dt = 1.0 / config.sampling_rate  # seconds per sample
    acc = imu_data[:, :, :3]         # (B, T, 3) — acceleration

    # Integrated velocity via trapezoidal rule
    v_integrated = torch.cumsum(acc * dt, dim=1)  # (B, T, 3)

    # Estimated velocity from finite differences of integrated position
    pos_estimated = torch.cumsum(v_integrated * dt, dim=1)
    v_estimated = torch.zeros_like(v_integrated)
    v_estimated[:, 1:, :] = (pos_estimated[:, 1:, :] - pos_estimated[:, :-1, :]) / dt

    loss = F.mse_loss(v_integrated, v_estimated)
    return loss


def gravity_alignment_loss(
    imu_data: torch.Tensor,
    config: PINNBioConfig,
) -> torch.Tensor:
    """
    L₂ — Gravity alignment.

    For a stationary or slowly-moving device, the z-axis accelerometer
    should read approximately g·cos(θ).  We estimate θ from the
    gyroscope and penalise deviation.

        L₂ = mean ‖ a_z − g · cos(θ_estimated) ‖²

    Parameters
    ----------
    imu_data : (B, T, 6)
    """
    g = config.gravity
    acc_z = imu_data[:, :, 2]    # (B, T)
    gyro_x = imu_data[:, :, 3]   # pitch rate
    gyro_y = imu_data[:, :, 4]   # roll rate

    dt = 1.0 / config.sampling_rate

    # Integrate pitch angle from gyroscope
    theta = torch.cumsum(gyro_x * dt, dim=1)  # (B, T)

    # Expected z-acceleration under gravity
    acc_z_expected = g * torch.cos(theta)      # (B, T)

    loss = F.mse_loss(acc_z, acc_z_expected)
    return loss


def entropy_loss(
    imu_data: torch.Tensor,
    config: PINNBioConfig,
) -> torch.Tensor:
    """
    L₃ — Entropy constraint.

    Genuine human movement has higher Shannon entropy than scripted
    RAT actions.  We discretise the IMU signal into bins and compute
    per-channel entropy, then penalise if entropy falls below H_min.

        L₃ = mean max(0, H_min − H(signal))

    Parameters
    ----------
    imu_data : (B, T, 6)
    """
    H_min = config.entropy_min
    B, T, C = imu_data.shape
    num_bins = 32

    total_entropy_loss = torch.tensor(0.0, device=imu_data.device)

    for c in range(C):
        channel = imu_data[:, :, c]  # (B, T)

        # Min-max normalise to [0, 1] per sample
        c_min = channel.min(dim=1, keepdim=True).values
        c_max = channel.max(dim=1, keepdim=True).values
        c_range = (c_max - c_min).clamp(min=1e-8)
        normed = (channel - c_min) / c_range  # (B, T)

        # Soft histogram via Gaussian kernel (differentiable)
        bin_centres = torch.linspace(0, 1, num_bins, device=imu_data.device)
        bin_centres = bin_centres.unsqueeze(0).unsqueeze(0)   # (1, 1, num_bins)
        normed_exp = normed.unsqueeze(-1)                     # (B, T, 1)
        sigma = 1.0 / num_bins
        weights = torch.exp(-0.5 * ((normed_exp - bin_centres) / sigma) ** 2)  # (B, T, bins)
        histogram = weights.sum(dim=1)  # (B, bins)
        histogram = histogram / histogram.sum(dim=1, keepdim=True).clamp(min=1e-8)

        # Shannon entropy
        log_hist = torch.log2(histogram.clamp(min=1e-10))
        H = -(histogram * log_hist).sum(dim=1)  # (B,)

        # Hinge loss: penalise if entropy < H_min
        channel_loss = F.relu(H_min - H).mean()
        total_entropy_loss = total_entropy_loss + channel_loss

    return total_entropy_loss / C


def pinn_combined_loss(
    logits: torch.Tensor,
    labels: torch.Tensor,
    imu_data: torch.Tensor,
    config: PINNBioConfig,
) -> Dict[str, torch.Tensor]:
    """
    Combined PINN biometric loss.

        L = L_BCE + λ₁·L_vel + λ₂·L_grav + λ₃·L_ent

    Returns a dict with individual and total loss for logging.
    """
    bce = F.binary_cross_entropy_with_logits(logits.squeeze(-1), labels.float())
    l_vel = velocity_consistency_loss(imu_data, config)
    l_grav = gravity_alignment_loss(imu_data, config)
    l_ent = entropy_loss(imu_data, config)

    total = (
        bce
        + config.lambda_physics1 * l_vel
        + config.lambda_physics2 * l_grav
        + config.lambda_physics3 * l_ent
    )

    return {
        "total": total,
        "bce": bce,
        "velocity": l_vel,
        "gravity": l_grav,
        "entropy": l_ent,
    }
