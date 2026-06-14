"""
PINN Biometrics Configuration
===============================
Hyperparameters for the Physics-Informed Neural Network that
distinguishes genuine human device-interaction sessions from
Remote Access Trojan (RAT) automated sessions using IMU sensor
data (accelerometer + gyroscope).

Physics constraints
-------------------
λ₁  Velocity consistency : ‖∫ acc dt − v̂‖²
λ₂  Gravity alignment    : ‖acc_z − g·cos(θ)‖²
λ₃  Entropy constraint   : max(0, H_min − H(signal))

The combined loss is:
    L = L_BCE + λ₁·L_vel + λ₂·L_grav + λ₃·L_ent
"""

from dataclasses import dataclass


@dataclass
class PINNBioConfig:
    """Physics-Informed Biometric Classifier hyper-parameters."""

    # ── Input specification ─────────────────────────────────────────
    input_channels: int = 6          # acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z
    sampling_rate: int = 50          # Hz
    window_size: int = 100           # timesteps  →  2 seconds @ 50 Hz
    stride: int = 25                 # 75 % overlap between windows

    # ── BiLSTM backbone ─────────────────────────────────────────────
    lstm_hidden: int = 128
    lstm_layers: int = 2
    lstm_dropout: float = 0.2
    bidirectional: bool = True       # output dim = 2 × lstm_hidden = 256

    # ── Attention ───────────────────────────────────────────────────
    attention_dim: int = 64

    # ── Classifier head ─────────────────────────────────────────────
    fc_hidden: int = 32
    num_classes: int = 1             # binary: human vs RAT

    # ── Physics loss weights ────────────────────────────────────────
    lambda_physics1: float = 0.3     # velocity consistency
    lambda_physics2: float = 0.2     # gravity alignment (g = 9.81 m/s²)
    lambda_physics3: float = 0.5     # entropy constraint

    # ── Physics constants ───────────────────────────────────────────
    gravity: float = 9.81            # m/s²
    entropy_min: float = 2.1         # bits — minimum for genuine signal
    entropy_threshold: float = 1.4   # bits — below = synthetic / RAT

    # ── Training ────────────────────────────────────────────────────
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 128
    epochs: int = 80
    patience: int = 10

    # ── Scheduler ───────────────────────────────────────────────────
    scheduler: str = "cosine"
    scheduler_T_max: int = 80
    scheduler_eta_min: float = 1e-6

    # ── GMM (Keystroke dynamics) ────────────────────────────────────
    gmm_components: int = 3          # K = 3 Gaussian components

    # ── Confidence fusion ───────────────────────────────────────────
    fusion_method: str = "geometric_mean"  # geometric mean of PINN × GMM

    # ── Synthetic data ──────────────────────────────────────────────
    num_human_sessions: int = 10_000
    num_rat_sessions: int = 10_000

    # ── Checkpointing ───────────────────────────────────────────────
    checkpoint_dir: str = "checkpoints/pinn_bio"
    log_dir: str = "logs/pinn_bio"

    # ── Device ──────────────────────────────────────────────────────
    device: str = "cuda"
