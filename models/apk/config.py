"""
APK Threat Classifier Configuration
=====================================
Hyperparameters for the multi-stage Android malware detection
pipeline that fuses static analysis (byte n-gram TF-IDF),
dynamic analysis (API-call-sequence LSTM), and GenAI-assisted
deobfuscation into a meta-learner (XGBoost).

Pipeline stages
---------------
Stage 1 — Static:  TF-IDF over byte 4-grams + permission-graph
                   features  →  LightGBM / logistic regression
Stage 2 — Dynamic: API call sequence (window=500)  →  LSTM  →  P(mal)
Stage 3 — GenAI:   Mistral deobfuscation of suspicious payloads
                   →  intent score  ∈ [0, 1]
Meta    — XGBoost over [static_prob, dynamic_prob, gai_intent_score,
                        permission_risk]  →  final verdict
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class APKConfig:
    """All APK Threat Classifier hyper-parameters."""

    # ── Static analyser ─────────────────────────────────────────────
    static_max_features: int = 200_000        # TF-IDF vocabulary cap
    static_ngram_range: tuple = (4, 4)        # byte 4-grams
    static_sublinear_tf: bool = True
    static_max_df: float = 0.95
    static_min_df: int = 3
    permission_feature_dim: int = 150         # Android permission one-hot

    # ── Dynamic analyser (LSTM) ─────────────────────────────────────
    dynamic_vocab_size: int = 5_000           # distinct API calls
    dynamic_embedding_dim: int = 128
    dynamic_lstm_hidden: int = 256
    dynamic_lstm_layers: int = 2
    dynamic_lstm_dropout: float = 0.3
    dynamic_window: int = 500                 # API call window length
    dynamic_learning_rate: float = 1e-3
    dynamic_batch_size: int = 64
    dynamic_epochs: int = 30

    # ── GenAI analyser ──────────────────────────────────────────────
    genai_model: str = "mistralai/Mistral-7B-Instruct-v0.3"
    genai_max_tokens: int = 1024
    genai_temperature: float = 0.1
    genai_intent_labels: List[str] = field(
        default_factory=lambda: [
            "data_exfiltration", "credential_theft", "ransomware",
            "cryptomining", "spyware", "adware", "dropper", "benign",
        ]
    )

    # ── Meta classifier (XGBoost) ───────────────────────────────────
    meta_feature_dim: int = 4                 # static, dynamic, gai, perm
    xgboost_params: Dict = field(default_factory=lambda: {
        "n_estimators": 500,
        "max_depth": 6,
        "learning_rate": 0.05,       # eta
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "gamma": 0.1,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "tree_method": "hist",
        "use_label_encoder": False,
    })

    # ── SHAP explainer ──────────────────────────────────────────────
    shap_max_display: int = 20
    shap_background_samples: int = 100

    # ── Synthetic data ──────────────────────────────────────────────
    num_benign_samples: int = 8_000
    num_malware_samples: int = 4_000

    # ── Checkpointing ───────────────────────────────────────────────
    checkpoint_dir: str = "checkpoints/apk"
    log_dir: str = "logs/apk"

    # ── Device ──────────────────────────────────────────────────────
    device: str = "cuda"
