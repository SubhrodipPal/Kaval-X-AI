"""
APK Threat Classifier — Multi-Stage Model
==========================================
Three-stage Android malware detection pipeline with meta-learner fusion.

Stage 1 — StaticAnalyzer
    TF-IDF byte 4-grams over DEX bytecode + permission-graph features,
    fed to a lightweight gradient-boosted classifier.

Stage 2 — DynamicAnalyzer
    LSTM over API-call sequences captured during sandboxed execution.
    Learns temporal patterns that distinguish malicious call chains
    (e.g. getDeviceId → openConnection → write → exfiltrate).

Stage 3 — GenAIAnalyzer
    Wraps Mistral-7B to deobfuscate suspicious code snippets and
    assign an intent score ∈ [0, 1] across threat categories.

Meta — MetaClassifier
    XGBoost over the 4-d feature vector:
        [static_prob, dynamic_prob, gai_intent_score, permission_risk]
    Produces the final malware verdict with SHAP explanations.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ── Optional imports ────────────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False

from .config import APKConfig

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
#  Stage 1: Static Analyzer
# ════════════════════════════════════════════════════════════════════

class StaticAnalyzer:
    """
    Analyses raw APK bytes and manifest to produce a static malware
    probability.

    Features
    --------
    1. **Byte 4-gram TF-IDF** (200K features) — captures recurring
       byte patterns in DEX bytecode that are characteristic of
       malware families (obfuscated strings, crypto constants, etc.).

    2. **Permission graph features** — one-hot encoding of declared
       Android permissions, weighted by risk level.
    """

    # Android permissions ranked by risk (0 = normal, 1 = dangerous)
    DANGEROUS_PERMISSIONS = {
        "android.permission.READ_SMS": 1.0,
        "android.permission.SEND_SMS": 1.0,
        "android.permission.READ_CONTACTS": 0.9,
        "android.permission.READ_CALL_LOG": 0.9,
        "android.permission.CAMERA": 0.8,
        "android.permission.RECORD_AUDIO": 0.9,
        "android.permission.ACCESS_FINE_LOCATION": 0.8,
        "android.permission.READ_PHONE_STATE": 0.7,
        "android.permission.WRITE_EXTERNAL_STORAGE": 0.6,
        "android.permission.READ_EXTERNAL_STORAGE": 0.5,
        "android.permission.INTERNET": 0.3,
        "android.permission.ACCESS_NETWORK_STATE": 0.2,
        "android.permission.RECEIVE_BOOT_COMPLETED": 0.6,
        "android.permission.SYSTEM_ALERT_WINDOW": 0.8,
        "android.permission.BIND_ACCESSIBILITY_SERVICE": 0.95,
        "android.permission.BIND_DEVICE_ADMIN": 0.95,
        "android.permission.REQUEST_INSTALL_PACKAGES": 0.9,
        "android.permission.WRITE_SETTINGS": 0.7,
        "android.permission.CHANGE_WIFI_STATE": 0.5,
        "android.permission.BLUETOOTH": 0.4,
    }

    def __init__(self, config: APKConfig):
        self.config = config
        self.vectorizer = None
        self.classifier = None
        self._fitted = False

    def _extract_byte_ngrams(self, raw_bytes: bytes) -> str:
        """Convert raw bytes to space-separated hex 4-grams."""
        hex_str = raw_bytes.hex()
        # 4-gram = 8 hex characters
        ngrams = [hex_str[i:i + 8] for i in range(0, len(hex_str) - 7)]
        return " ".join(ngrams)

    def _extract_permission_features(
        self, permissions: List[str]
    ) -> np.ndarray:
        """
        Convert a list of declared permissions to a risk-weighted
        feature vector.
        """
        all_perms = list(self.DANGEROUS_PERMISSIONS.keys())
        features = np.zeros(len(all_perms), dtype=np.float32)
        for i, perm in enumerate(all_perms):
            if perm in permissions:
                features[i] = self.DANGEROUS_PERMISSIONS[perm]
        return features

    def compute_permission_risk(self, permissions: List[str]) -> float:
        """
        Compute an aggregate permission risk score ∈ [0, 1].
        """
        if not permissions:
            return 0.0
        risk_sum = sum(
            self.DANGEROUS_PERMISSIONS.get(p, 0.1) for p in permissions
        )
        return min(risk_sum / 5.0, 1.0)  # normalise

    def fit(
        self,
        byte_data: List[bytes],
        permissions_list: List[List[str]],
        labels: np.ndarray,
    ):
        """
        Fit the static analyzer on training data.

        Parameters
        ----------
        byte_data : list of bytes
            Raw APK/DEX bytes for each sample.
        permissions_list : list of list of str
            Declared permissions for each sample.
        labels : (N,) array
            0 = benign, 1 = malware.
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn required. pip install scikit-learn")

        # TF-IDF on byte n-grams
        corpus = [self._extract_byte_ngrams(b) for b in byte_data]
        self.vectorizer = TfidfVectorizer(
            max_features=self.config.static_max_features,
            ngram_range=self.config.static_ngram_range,
            sublinear_tf=self.config.static_sublinear_tf,
            max_df=self.config.static_max_df,
            min_df=self.config.static_min_df,
            analyzer="word",
        )
        X_tfidf = self.vectorizer.fit_transform(corpus)

        # Permission features
        X_perm = np.stack([
            self._extract_permission_features(p) for p in permissions_list
        ])

        # Combine (sparse + dense)
        from scipy.sparse import hstack as sparse_hstack
        X = sparse_hstack([X_tfidf, X_perm])

        self.classifier = LogisticRegression(
            C=1.0, max_iter=1000, solver="saga", n_jobs=-1
        )
        self.classifier.fit(X, labels)
        self._fitted = True
        logger.info("StaticAnalyzer fitted on %d samples", len(labels))

    def predict_proba(
        self, raw_bytes: bytes, permissions: List[str]
    ) -> float:
        """Return P(malware) for a single APK."""
        if not self._fitted:
            # Return prior based on permission risk alone
            return self.compute_permission_risk(permissions)

        corpus = [self._extract_byte_ngrams(raw_bytes)]
        X_tfidf = self.vectorizer.transform(corpus)
        X_perm = self._extract_permission_features(permissions).reshape(1, -1)
        from scipy.sparse import hstack as sparse_hstack
        X = sparse_hstack([X_tfidf, X_perm])
        return float(self.classifier.predict_proba(X)[0, 1])


# ════════════════════════════════════════════════════════════════════
#  Stage 2: Dynamic Analyzer — API Call Sequence LSTM
# ════════════════════════════════════════════════════════════════════

class DynamicAnalyzerLSTM(nn.Module):
    """
    LSTM over API call sequences captured during sandboxed execution.

    Architecture
    ------------
    Embedding(5000, 128) → LSTM(128→256, 2 layers) → FC(256→1)

    The model learns to distinguish benign API call patterns
    (e.g. normal UI → network → storage) from malicious sequences
    (e.g. getDeviceId → getSubscriberId → openConnection → exfiltrate).
    """

    def __init__(self, config: APKConfig):
        super().__init__()
        self.config = config

        self.embedding = nn.Embedding(
            num_embeddings=config.dynamic_vocab_size,
            embedding_dim=config.dynamic_embedding_dim,
            padding_idx=0,
        )
        self.lstm = nn.LSTM(
            input_size=config.dynamic_embedding_dim,
            hidden_size=config.dynamic_lstm_hidden,
            num_layers=config.dynamic_lstm_layers,
            dropout=config.dynamic_lstm_dropout if config.dynamic_lstm_layers > 1 else 0,
            batch_first=True,
            bidirectional=False,
        )
        self.classifier = nn.Sequential(
            nn.Linear(config.dynamic_lstm_hidden, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(128, 1),
        )

    def forward(self, api_sequence: torch.Tensor) -> torch.Tensor:
        """
        Parameters
        ----------
        api_sequence : (B, window) — integer-encoded API call IDs

        Returns
        -------
        logits : (B, 1)
        """
        embedded = self.embedding(api_sequence)  # (B, W, E)
        lstm_out, (h_n, _) = self.lstm(embedded)
        # Use last hidden state of top layer
        last_hidden = h_n[-1]  # (B, H)
        return self.classifier(last_hidden)


# ════════════════════════════════════════════════════════════════════
#  Stage 3: GenAI Analyzer — Mistral Deobfuscation
# ════════════════════════════════════════════════════════════════════

class GenAIAnalyzer:
    """
    Uses Mistral-7B to deobfuscate suspicious code snippets extracted
    from APKs and assign threat intent scores.

    The model is prompted to:
    1. Identify obfuscation techniques (string encryption, reflection,
       dynamic class loading).
    2. Reconstruct the original intent.
    3. Classify into threat categories.
    4. Assign a malicious intent score ∈ [0, 1].
    """

    DEOBFUSCATION_PROMPT = """You are a mobile malware analyst. Analyse the following 
code snippet extracted from an Android APK.

Tasks:
1. Identify any obfuscation techniques used.
2. Reconstruct what the code actually does.
3. Classify the intent as one of: {categories}
4. Rate malicious intent from 0.0 (benign) to 1.0 (clearly malicious).

Output EXACTLY as JSON:
{{
    "obfuscation_techniques": ["technique1", ...],
    "deobfuscated_intent": "description of actual behaviour",
    "category": "category_name",
    "intent_score": 0.XX
}}

Code snippet:
```
{code}
```"""

    def __init__(self, config: APKConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self._loaded = False

    def load_model(self):
        """Load the GenAI model for deobfuscation."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.genai_model, trust_remote_code=True
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.genai_model,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True,
            )
            self._loaded = True
        except Exception as e:
            logger.warning(f"GenAI model not loaded: {e}")

    def analyse(self, code_snippet: str) -> Dict[str, Any]:
        """
        Analyse a code snippet and return deobfuscation results.

        Parameters
        ----------
        code_snippet : str
            Suspicious code extracted from the APK.

        Returns
        -------
        dict with keys: obfuscation_techniques, deobfuscated_intent,
                       category, intent_score
        """
        if not self._loaded:
            return self._heuristic_fallback(code_snippet)

        categories = ", ".join(self.config.genai_intent_labels)
        prompt = self.DEOBFUSCATION_PROMPT.format(
            categories=categories, code=code_snippet
        )

        inputs = self.tokenizer(
            prompt, return_tensors="pt", truncation=True,
            max_length=2048
        ).to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.config.genai_max_tokens,
                temperature=self.config.genai_temperature,
                do_sample=False,
            )

        text = self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )

        # Parse JSON response
        try:
            # Find JSON block
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            pass

        return self._heuristic_fallback(code_snippet)

    def _heuristic_fallback(self, code_snippet: str) -> Dict[str, Any]:
        """
        Simple heuristic analysis when the LLM is not available.
        Checks for known suspicious API patterns.
        """
        suspicious_apis = {
            "getDeviceId": 0.7,
            "getSubscriberId": 0.8,
            "getSimSerialNumber": 0.7,
            "sendTextMessage": 0.85,
            "openConnection": 0.3,
            "getExternalStorageDirectory": 0.4,
            "exec(": 0.9,
            "Runtime.getRuntime": 0.85,
            "DexClassLoader": 0.9,
            "loadDex": 0.9,
            "Cipher.getInstance": 0.5,
            "KeyGenerator": 0.5,
            "AccessibilityService": 0.8,
            "DeviceAdminReceiver": 0.85,
            "PackageInstaller": 0.7,
            "Base64.decode": 0.4,
            "reflection": 0.6,
            "getInstalledPackages": 0.5,
        }

        techniques = []
        max_score = 0.0
        code_lower = code_snippet.lower()

        for api, score in suspicious_apis.items():
            if api.lower() in code_lower:
                techniques.append(api)
                max_score = max(max_score, score)

        if "base64" in code_lower and ("decode" in code_lower or "encode" in code_lower):
            techniques.append("base64_encoding")
        if "reflect" in code_lower or "getmethod" in code_lower:
            techniques.append("reflection_usage")
        if "dexclassloader" in code_lower or "loaddex" in code_lower:
            techniques.append("dynamic_class_loading")

        category = "benign"
        if max_score > 0.8:
            category = "data_exfiltration"
        elif max_score > 0.6:
            category = "spyware"
        elif max_score > 0.3:
            category = "adware"

        return {
            "obfuscation_techniques": techniques,
            "deobfuscated_intent": f"Detected {len(techniques)} suspicious patterns",
            "category": category,
            "intent_score": max_score,
        }


# ════════════════════════════════════════════════════════════════════
#  Meta Classifier — XGBoost Fusion
# ════════════════════════════════════════════════════════════════════

class MetaClassifier:
    """
    XGBoost meta-learner that fuses predictions from all three stages
    into a final malware verdict.

    Input features (4-d):
        1. static_prob     — P(mal) from StaticAnalyzer
        2. dynamic_prob    — P(mal) from DynamicAnalyzer
        3. gai_intent_score — intent score from GenAIAnalyzer
        4. permission_risk — aggregate permission risk

    Also provides SHAP explanations for each prediction.
    """

    FEATURE_NAMES = [
        "static_prob", "dynamic_prob", "gai_intent_score", "permission_risk"
    ]

    def __init__(self, config: APKConfig):
        self.config = config
        self.model = None
        self._fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray):
        """
        Train the XGBoost meta-classifier.

        Parameters
        ----------
        X : (N, 4) — stage probabilities + permission risk
        y : (N,)   — binary labels
        """
        if not HAS_XGB:
            raise ImportError("xgboost required. pip install xgboost")

        params = dict(self.config.xgboost_params)
        n_estimators = params.pop("n_estimators", 500)

        self.model = xgb.XGBClassifier(
            n_estimators=n_estimators,
            **params,
        )
        self.model.fit(
            X, y,
            eval_set=[(X, y)],
            verbose=False,
        )
        self._fitted = True
        logger.info("MetaClassifier fitted with XGBoost")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return P(malware) for each sample."""
        if not self._fitted:
            # Simple average fallback
            return X.mean(axis=1)
        return self.model.predict_proba(X)[:, 1]

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return binary predictions."""
        if not self._fitted:
            return (X.mean(axis=1) > 0.5).astype(int)
        return self.model.predict(X)

    def explain(self, X: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Generate SHAP explanations for predictions.

        Returns
        -------
        dict with:
            - shap_values: array of SHAP values
            - feature_names: list of feature names
            - base_value: expected value
        """
        if not HAS_SHAP or not self._fitted:
            return None

        explainer = shap.TreeExplainer(self.model)
        shap_values = explainer.shap_values(X)

        return {
            "shap_values": shap_values,
            "feature_names": self.FEATURE_NAMES,
            "base_value": explainer.expected_value,
        }


# ════════════════════════════════════════════════════════════════════
#  APKThreatClassifier — Full Pipeline
# ════════════════════════════════════════════════════════════════════

class APKThreatClassifier:
    """
    End-to-end APK threat classification pipeline combining static
    analysis, dynamic analysis, GenAI deobfuscation, and XGBoost
    meta-learning.

    Usage
    -----
    >>> config = APKConfig()
    >>> clf = APKThreatClassifier(config)
    >>> result = clf.classify(apk_bytes, permissions, api_calls, code_snippet)
    """

    def __init__(self, config: APKConfig):
        self.config = config
        self.static_analyzer = StaticAnalyzer(config)
        self.dynamic_model = DynamicAnalyzerLSTM(config) if HAS_TORCH else None
        self.genai_analyzer = GenAIAnalyzer(config)
        self.meta_classifier = MetaClassifier(config)

    def classify(
        self,
        apk_bytes: Optional[bytes] = None,
        permissions: Optional[List[str]] = None,
        api_sequence: Optional[List[int]] = None,
        code_snippet: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the full classification pipeline on a single APK.

        Returns
        -------
        dict with:
            - verdict: "malware" | "benign"
            - confidence: float
            - static_prob: float
            - dynamic_prob: float
            - genai_intent_score: float
            - permission_risk: float
            - genai_details: dict
            - shap_explanation: dict or None
        """
        permissions = permissions or []
        result: Dict[str, Any] = {}

        # Stage 1: Static analysis
        static_prob = 0.5
        permission_risk = self.static_analyzer.compute_permission_risk(permissions)
        if apk_bytes is not None:
            static_prob = self.static_analyzer.predict_proba(apk_bytes, permissions)
        result["static_prob"] = static_prob
        result["permission_risk"] = permission_risk

        # Stage 2: Dynamic analysis
        dynamic_prob = 0.5
        if api_sequence is not None and self.dynamic_model is not None:
            seq_tensor = torch.tensor(
                api_sequence[:self.config.dynamic_window],
                dtype=torch.long,
            ).unsqueeze(0)
            # Pad if shorter than window
            if seq_tensor.size(1) < self.config.dynamic_window:
                pad_len = self.config.dynamic_window - seq_tensor.size(1)
                seq_tensor = F.pad(seq_tensor, (0, pad_len), value=0)
            with torch.no_grad():
                self.dynamic_model.eval()
                logits = self.dynamic_model(seq_tensor)
                dynamic_prob = float(torch.sigmoid(logits).item())
        result["dynamic_prob"] = dynamic_prob

        # Stage 3: GenAI analysis
        genai_result = {"intent_score": 0.0}
        if code_snippet:
            genai_result = self.genai_analyzer.analyse(code_snippet)
        genai_score = genai_result.get("intent_score", 0.0)
        result["genai_intent_score"] = genai_score
        result["genai_details"] = genai_result

        # Meta classifier
        meta_features = np.array([[
            static_prob, dynamic_prob, genai_score, permission_risk
        ]])

        if self.meta_classifier._fitted:
            final_prob = float(self.meta_classifier.predict_proba(meta_features)[0])
            verdict = "malware" if final_prob > 0.5 else "benign"
            explanation = self.meta_classifier.explain(meta_features)
        else:
            # Weighted average fallback
            final_prob = (
                0.3 * static_prob
                + 0.3 * dynamic_prob
                + 0.2 * genai_score
                + 0.2 * permission_risk
            )
            verdict = "malware" if final_prob > 0.5 else "benign"
            explanation = None

        result["confidence"] = final_prob
        result["verdict"] = verdict
        result["shap_explanation"] = explanation

        return result
