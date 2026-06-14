"""
NSE — Neuro-Symbolic Engine Model
===================================
Hybrid LLM + symbolic reasoning model that combines Mistral-7B
(with QLoRA fine-tuning) and py-datalog rule evaluation for
explainable fraud detection reasoning.

The NSE bridges neural language understanding with formal logic:
1. The LLM generates a *reasoning chain* from structured fraud evidence.
2. A *bridge parser* extracts first-order-logic predicates from the
   free-text output.
3. The predicates are evaluated against a py-datalog knowledge base
   containing regulatory rules (RBI Master Direction on Cyber Security).

This architecture ensures that every fraud determination is
traceable to specific rules and evidence, satisfying regulatory
explainability requirements.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ── Optional heavy imports ──────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

try:
    from peft import (
        LoraConfig,
        PeftModel,
        get_peft_model,
        prepare_model_for_kbit_training,
    )
    HAS_PEFT = True
except ImportError:
    HAS_PEFT = False

from .config import NSEConfig


# ════════════════════════════════════════════════════════════════════
#  Predicate — typed container for extracted logical predicates
# ════════════════════════════════════════════════════════════════════

@dataclass
class Predicate:
    """A first-order-logic predicate extracted from LLM output."""
    name: str
    arguments: List[str]
    confidence: float = 1.0
    source_text: str = ""

    def __str__(self):
        args = ", ".join(self.arguments)
        return f"{self.name}({args})"


# ════════════════════════════════════════════════════════════════════
#  BridgeParser — Free-text → Predicates
# ════════════════════════════════════════════════════════════════════

class BridgeParser:
    """
    Parses LLM-generated reasoning text and extracts structured
    predicates that can be fed into the py-datalog rule engine.

    Recognises patterns like:
        - ``suspicious_velocity(ACC_12345)``
        - ``PREDICATE: mule_indicator(ACC_67890)``
        - ``Rule triggered: high_amount(TXN_001, 500000)``

    Also extracts confidence scores when present:
        - ``suspicious_velocity(ACC_12345) [confidence: 0.92]``
    """

    # Patterns for predicate extraction
    PREDICATE_RE = re.compile(
        r"(\w+)\(([^)]*)\)"
    )
    CONFIDENCE_RE = re.compile(
        r"\[confidence:\s*([\d.]+)\]"
    )
    STRUCTURED_BLOCK_RE = re.compile(
        r"```(?:predicates|logic|rules)\s*\n(.*?)```",
        re.DOTALL,
    )

    # Known predicate names for validation
    KNOWN_PREDICATES = {
        "suspicious_velocity", "mule_indicator", "rat_detected",
        "freeze_required", "high_amount", "rapid_in_out",
        "new_account", "device_anomaly", "geo_anomaly",
        "time_anomaly", "cross_border_risk", "layering_detected",
        "smurfing_detected", "structuring_detected", "kyc_mismatch",
        "dormant_activation", "unusual_beneficiary", "round_amount",
        "split_transaction", "velocity_breach", "fraud_confirmed",
        "amount_above_threshold", "entropy_below_threshold",
        "scripted_pattern", "txn_count_1h", "beneficiary_count_24h",
    }

    def __init__(self, config: NSEConfig):
        self.config = config
        self.confidence_threshold = config.confidence_threshold

    def parse(self, text: str) -> List[Predicate]:
        """
        Extract all predicates from LLM-generated text.

        Parameters
        ----------
        text : str
            Raw LLM output containing reasoning and predicates.

        Returns
        -------
        List[Predicate]
            Validated predicates above the confidence threshold.
        """
        predicates = []

        # First, try structured blocks
        structured_matches = self.STRUCTURED_BLOCK_RE.findall(text)
        search_text = text
        if structured_matches:
            search_text = "\n".join(structured_matches) + "\n" + text

        # Find all predicate patterns
        for match in self.PREDICATE_RE.finditer(search_text):
            name = match.group(1).lower()
            args_str = match.group(2).strip()
            arguments = [a.strip().strip("'\"") for a in args_str.split(",") if a.strip()]

            # Look for confidence annotation nearby
            confidence = 1.0
            context_end = min(match.end() + 50, len(search_text))
            context = search_text[match.end():context_end]
            conf_match = self.CONFIDENCE_RE.search(context)
            if conf_match:
                confidence = float(conf_match.group(1))

            # Validate against known predicates
            if name in self.KNOWN_PREDICATES and confidence >= self.confidence_threshold:
                predicates.append(Predicate(
                    name=name,
                    arguments=arguments,
                    confidence=confidence,
                    source_text=match.group(0),
                ))

        # Deduplicate
        seen = set()
        unique = []
        for p in predicates:
            key = str(p)
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    def predicates_to_dict(self, predicates: List[Predicate]) -> Dict[str, List]:
        """Convert predicates to a dictionary grouped by predicate name."""
        result: Dict[str, List] = {}
        for p in predicates:
            if p.name not in result:
                result[p.name] = []
            result[p.name].append({
                "arguments": p.arguments,
                "confidence": p.confidence,
            })
        return result


# ════════════════════════════════════════════════════════════════════
#  NSEModel — Neuro-Symbolic Engine
# ════════════════════════════════════════════════════════════════════

class NSEModel:
    """
    Neuro-Symbolic Engine combining Mistral-7B with LoRA adaptation
    and a bridge parser for predicate extraction.

    Usage
    -----
    >>> config = NSEConfig()
    >>> nse = NSEModel(config)
    >>> nse.load_model()
    >>> result = nse.reason(evidence_dict)
    >>> print(result["predicates"])
    >>> print(result["reasoning_chain"])
    """

    # System prompt template for fraud reasoning
    SYSTEM_PROMPT = """You are Kavalx Fraud Reasoning Engine, a specialised AI that analyses 
financial transaction evidence and produces structured fraud assessments.

For each case, you MUST:
1. Analyse all provided evidence systematically.
2. Identify applicable fraud patterns and regulatory violations.
3. Output your reasoning as a chain of logical steps.
4. Extract formal predicates in the format: predicate_name(argument1, argument2, ...)
5. Wrap all predicates in a ```predicates``` code block.

Available predicates:
- suspicious_velocity(account_id) — txn count exceeds threshold
- mule_indicator(account_id) — rapid in-out pattern on new account
- rat_detected(device_id) — remote access trojan indicators
- freeze_required(account_id) — regulatory freeze needed
- high_amount(txn_id, amount) — amount exceeds reporting threshold
- rapid_in_out(account_id) — funds received and sent within short window
- new_account(account_id) — account opened within 30 days
- device_anomaly(device_id) — device fingerprint mismatch
- geo_anomaly(account_id) — geographic impossibility
- time_anomaly(account_id) — unusual transaction timing
- cross_border_risk(txn_id) — cross-border regulatory concern
- layering_detected(account_id) — money layering pattern
- smurfing_detected(account_id) — transaction structuring below threshold
- structuring_detected(account_id) — deliberate threshold avoidance
- kyc_mismatch(account_id) — KYC data inconsistency
- dormant_activation(account_id) — dormant account suddenly active

Always cite evidence IDs and explain your reasoning step by step."""

    def __init__(self, config: NSEConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.bridge_parser = BridgeParser(config)
        self._loaded = False

    def load_model(self, adapter_path: Optional[str] = None):
        """
        Load the base Mistral model with optional LoRA adapter.

        Parameters
        ----------
        adapter_path : str, optional
            Path to a fine-tuned LoRA adapter. If None, loads the
            base model without adaptation.
        """
        if not HAS_TRANSFORMERS:
            raise ImportError(
                "transformers is required. Install with: "
                "pip install transformers>=4.36.0"
            )
        if not HAS_TORCH:
            raise ImportError("PyTorch is required.")

        # Quantisation config for QLoRA
        bnb_config = None
        if self.config.load_in_4bit:
            try:
                import bitsandbytes  # noqa: F401
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=getattr(
                        torch, self.config.bnb_4bit_compute_dtype
                    ),
                    bnb_4bit_quant_type=self.config.bnb_4bit_quant_type,
                    bnb_4bit_use_double_quant=self.config.bnb_4bit_use_double_quant,
                )
            except ImportError:
                print("WARNING: bitsandbytes not available, loading in fp16")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.tokenizer_name,
            trust_remote_code=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load base model
        load_kwargs = {
            "torch_dtype": torch.float16,
            "device_map": "auto",
            "trust_remote_code": True,
        }
        if bnb_config is not None:
            load_kwargs["quantization_config"] = bnb_config

        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.base_model,
            **load_kwargs,
        )

        # Load LoRA adapter if provided
        if adapter_path and HAS_PEFT:
            self.model = PeftModel.from_pretrained(
                self.model, adapter_path
            )
            print(f"Loaded LoRA adapter from {adapter_path}")

        self.model.eval()
        self._loaded = True

    def _build_prompt(self, evidence: Dict[str, Any]) -> str:
        """
        Build a structured prompt from evidence dictionary.

        Parameters
        ----------
        evidence : dict
            Keys may include: account_id, transactions, device_info,
            risk_scores, alert_details, etc.
        """
        evidence_text = json.dumps(evidence, indent=2, default=str)
        prompt = f"""<s>[INST] {self.SYSTEM_PROMPT}

=== EVIDENCE ===
{evidence_text}

Analyse this evidence and produce your fraud assessment with formal predicates. [/INST]"""
        return prompt

    def reason(
        self,
        evidence: Dict[str, Any],
        return_raw: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a reasoning chain from evidence and extract predicates.

        Parameters
        ----------
        evidence : dict
            Structured evidence for a fraud case.
        return_raw : bool
            If True, include the raw LLM output in the result.

        Returns
        -------
        dict with keys:
            - predicates: List[Predicate]
            - predicate_dict: Dict grouped by predicate name
            - reasoning_chain: str (summarised reasoning)
            - confidence: float (average predicate confidence)
            - raw_output: str (only if return_raw=True)
        """
        if not self._loaded:
            # Fallback: rule-based reasoning without LLM
            return self._rule_based_fallback(evidence)

        prompt = self._build_prompt(evidence)

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.config.max_seq_length,
        ).to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                do_sample=self.config.do_sample,
                repetition_penalty=self.config.repetition_penalty,
                pad_token_id=self.tokenizer.pad_token_id,
            )

        raw_output = self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )

        # Parse predicates
        predicates = self.bridge_parser.parse(raw_output)
        predicate_dict = self.bridge_parser.predicates_to_dict(predicates)

        # Calculate average confidence
        avg_confidence = (
            np.mean([p.confidence for p in predicates])
            if predicates else 0.0
        )

        result = {
            "predicates": predicates,
            "predicate_dict": predicate_dict,
            "reasoning_chain": raw_output.strip(),
            "confidence": float(avg_confidence),
        }
        if return_raw:
            result["raw_output"] = raw_output

        return result

    def _rule_based_fallback(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simple rule-based reasoning when the LLM is not loaded.
        Useful for testing and lightweight deployments.
        """
        predicates: List[Predicate] = []
        reasoning_steps: List[str] = []

        account_id = evidence.get("account_id", "UNKNOWN")
        transactions = evidence.get("transactions", [])
        device_info = evidence.get("device_info", {})

        # Velocity check
        if len(transactions) > 10:
            predicates.append(Predicate(
                "suspicious_velocity", [account_id],
                confidence=0.85,
                source_text=f"{len(transactions)} transactions found",
            ))
            reasoning_steps.append(
                f"Step 1: Account {account_id} has {len(transactions)} "
                f"transactions, exceeding velocity threshold of 10."
            )

        # Amount check
        for txn in transactions:
            amount = txn.get("amount", 0)
            txn_id = txn.get("id", "TXN_UNK")
            if amount > 200_000:
                predicates.append(Predicate(
                    "high_amount", [txn_id, str(amount)],
                    confidence=0.95,
                ))
                reasoning_steps.append(
                    f"Step: Transaction {txn_id} amount ₹{amount:,.0f} "
                    f"exceeds ₹2,00,000 reporting threshold."
                )

        # Device anomaly
        if device_info.get("fingerprint_mismatch", False):
            device_id = device_info.get("device_id", "DEV_UNK")
            predicates.append(Predicate(
                "device_anomaly", [device_id],
                confidence=0.9,
            ))
            reasoning_steps.append(
                f"Step: Device {device_id} shows fingerprint mismatch."
            )

        # New account + rapid in/out → mule
        account_age_days = evidence.get("account_age_days", 365)
        has_rapid_in_out = evidence.get("rapid_in_out", False)
        if account_age_days < 30:
            predicates.append(Predicate(
                "new_account", [account_id], confidence=1.0,
            ))
            if has_rapid_in_out:
                predicates.append(Predicate(
                    "rapid_in_out", [account_id], confidence=0.88,
                ))
                predicates.append(Predicate(
                    "mule_indicator", [account_id], confidence=0.85,
                ))
                reasoning_steps.append(
                    f"Step: Account {account_id} opened {account_age_days} days ago "
                    f"with rapid in-out pattern → mule indicator."
                )

        avg_conf = np.mean([p.confidence for p in predicates]) if predicates else 0.0

        return {
            "predicates": predicates,
            "predicate_dict": self.bridge_parser.predicates_to_dict(predicates),
            "reasoning_chain": "\n".join(reasoning_steps),
            "confidence": float(avg_conf),
        }

    def prepare_for_training(self) -> None:
        """
        Prepare the model for QLoRA fine-tuning by adding LoRA adapters.
        """
        if not HAS_PEFT:
            raise ImportError("peft is required for training. pip install peft")
        if not self._loaded:
            raise RuntimeError("Call load_model() first.")

        self.model = prepare_model_for_kbit_training(self.model)

        lora_config = LoraConfig(
            r=self.config.lora_rank,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=self.config.target_modules,
            bias="none",
            task_type="CAUSAL_LM",
        )
        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()


# ════════════════════════════════════════════════════════════════════
#  Convenience: Standalone predicate evaluator (no LLM needed)
# ════════════════════════════════════════════════════════════════════

def evaluate_predicates_standalone(
    evidence: Dict[str, Any],
) -> List[Predicate]:
    """
    Quick predicate evaluation without loading an LLM.
    Uses the rule-based fallback logic from NSEModel.

    >>> preds = evaluate_predicates_standalone({
    ...     "account_id": "ACC_001",
    ...     "transactions": [{"id": "T1", "amount": 500000}],
    ...     "account_age_days": 5,
    ...     "rapid_in_out": True,
    ... })
    >>> [str(p) for p in preds]
    ['high_amount(T1, 500000)', 'new_account(ACC_001)', ...]
    """
    config = NSEConfig()
    model = NSEModel(config)
    result = model._rule_based_fallback(evidence)
    return result["predicates"]
