"""
NSE (Neuro-Symbolic Engine) Configuration
==========================================
Configuration for the hybrid LLM + symbolic-reasoning engine that
bridges neural language understanding with formal Datalog rule
evaluation for fraud detection narratives.

Architecture overview
---------------------
1. **Base LLM**: Mistral-7B-Instruct-v0.3 loaded in 4-bit (QLoRA).
2. **LoRA adapter**: rank-16 low-rank updates on attention projections
   and gate projection layers for domain fine-tuning.
3. **Bridge parser**: regex + constrained-grammar extractor that maps
   free-text LLM output to first-order-logic predicates consumable
   by the py-datalog rule engine.
4. **Rule engine**: py-datalog knowledge base with 20+ fraud rules
   derived from RBI Master Direction on Cyber Security (2023).
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class NSEConfig:
    """All Neuro-Symbolic Engine hyper-parameters."""

    # ── Base model ──────────────────────────────────────────────────
    base_model: str = "mistralai/Mistral-7B-Instruct-v0.3"
    tokenizer_name: str = "mistralai/Mistral-7B-Instruct-v0.3"

    # ── LoRA ────────────────────────────────────────────────────────
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: List[str] = field(
        default_factory=lambda: [
            "q_proj", "k_proj", "v_proj", "o_proj", "gate_proj"
        ]
    )

    # ── Quantisation (QLoRA) ────────────────────────────────────────
    load_in_4bit: bool = True
    bnb_4bit_compute_dtype: str = "bfloat16"
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_use_double_quant: bool = True

    # ── Training data ───────────────────────────────────────────────
    training_data_size: int = 12_000
    val_split: float = 0.1
    max_seq_length: int = 4096

    # ── Generation ──────────────────────────────────────────────────
    temperature: float = 0.1
    top_p: float = 0.95
    max_new_tokens: int = 1024
    do_sample: bool = True
    repetition_penalty: float = 1.1

    # ── Training hyper-parameters ───────────────────────────────────
    learning_rate: float = 2e-4
    weight_decay: float = 0.01
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 4
    warmup_ratio: float = 0.03
    lr_scheduler_type: str = "cosine"
    max_grad_norm: float = 0.3
    optim: str = "paged_adamw_32bit"

    # ── Bridge parser ───────────────────────────────────────────────
    predicate_pattern: str = r"(\w+)\(([^)]*)\)"
    confidence_threshold: float = 0.7

    # ── Rule engine ─────────────────────────────────────────────────
    rule_file: str = "models/nse/rules.py"
    max_inference_depth: int = 10

    # ── Checkpointing ───────────────────────────────────────────────
    checkpoint_dir: str = "checkpoints/nse"
    log_dir: str = "logs/nse"
    output_dir: str = "outputs/nse"

    # ── Device ──────────────────────────────────────────────────────
    device: str = "cuda"
