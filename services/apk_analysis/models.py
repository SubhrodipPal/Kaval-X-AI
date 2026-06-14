"""APK Analysis service Pydantic models."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class APKVerdict(str, Enum):
    BENIGN = "benign"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


class StaticAnalysisResult(BaseModel):
    byte_ngram_score: float = Field(..., ge=0, le=1, description="TF-IDF 4-gram anomaly score")
    permission_risk: float = Field(..., ge=0, le=1, description="Permission graph GCN risk")
    permissions: list[str] = Field(default_factory=list, description="Declared permissions")
    static_score: float = Field(..., ge=0, le=1, description="Combined static score")


class DynamicAnalysisResult(BaseModel):
    api_calls_captured: int = Field(0, description="Number of API calls recorded")
    suspicious_apis: list[str] = Field(default_factory=list)
    dynamic_score: float = Field(..., ge=0, le=1, description="LSTM sequence score")
    sandbox_duration_s: float = Field(0, description="Sandbox execution time")


class GenAIIntentResult(BaseModel):
    deobfuscated_intent: str = Field("", description="Reconstructed intent from bytecode")
    intent_score: float = Field(..., ge=0, le=1, description="Malicious intent confidence")
    malware_family: Optional[str] = None


class SHAPFeatures(BaseModel):
    static_importance: float = 0.0
    dynamic_importance: float = 0.0
    genai_importance: float = 0.0
    permission_importance: float = 0.0


class APKThreatReport(BaseModel):
    apk_id: UUID = Field(default_factory=uuid4)
    sha256: str
    package_name: str = ""
    verdict: APKVerdict
    static_result: StaticAnalysisResult
    dynamic_result: DynamicAnalysisResult
    genai_result: GenAIIntentResult
    meta_score: float = Field(..., ge=0, le=1)
    shap_features: SHAPFeatures
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    analysis_time_s: float = 0.0


class APKSubmitRequest(BaseModel):
    """For JSON-based submission (hash-only quick check)."""
    sha256: str
    package_name: Optional[str] = None


class APKStatusResponse(BaseModel):
    job_id: str
    status: str  # queued, analyzing, completed, failed
    progress: float = 0.0
    result: Optional[APKThreatReport] = None
