"""APK Analysis Service — routes."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from .config import settings
from .models import (
    APKStatusResponse,
    APKSubmitRequest,
    APKThreatReport,
    APKVerdict,
    DynamicAnalysisResult,
    GenAIIntentResult,
    SHAPFeatures,
    StaticAnalysisResult,
)
from .utils import (
    compute_sha256,
    meta_classify,
    simulate_dynamic_analysis,
    simulate_genai_deobfuscation,
    static_analyze,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job store (use Redis in production)
_jobs: dict[str, APKStatusResponse] = {}
_results: dict[str, APKThreatReport] = {}


@router.post("/internal/apk/analyze", response_model=APKThreatReport)
async def analyze_apk(file: UploadFile = File(...)):
    """Full APK analysis pipeline: static → dynamic → GenAI → meta-classifier.

    In production, stages 2-3 run via Celery workers asynchronously.
    For development, runs synchronously with simulated analysis.
    """
    start = time.time()
    apk_bytes = await file.read()
    sha256 = compute_sha256(apk_bytes)
    package_name = file.filename or f"unknown_{sha256[:8]}"

    logger.info(f"Analyzing APK: {package_name} ({sha256[:16]}...), size={len(apk_bytes)} bytes")

    # Check cache
    if sha256 in _results:
        logger.info(f"Cache hit for APK {sha256[:16]}")
        return _results[sha256]

    # Stage 1: Static analysis (byte 4-grams + permission graph)
    static = static_analyze(apk_bytes)
    static_result = StaticAnalysisResult(**{k: v for k, v in static.items() if k != "analysis_time_s"})

    # Stage 2: Dynamic sandbox analysis (Cuckoo)
    dynamic = simulate_dynamic_analysis(sha256)
    dynamic_result = DynamicAnalysisResult(**dynamic)

    # Stage 3: GenAI deobfuscation (Mistral)
    genai = simulate_genai_deobfuscation(sha256, static_result.static_score)
    genai_result = GenAIIntentResult(**genai)

    # Meta-classifier (XGBoost)
    meta_score, verdict_str, shap = meta_classify(
        static_result.static_score,
        dynamic_result.dynamic_score,
        genai_result.intent_score,
        static_result.permission_risk,
    )

    elapsed = time.time() - start
    report = APKThreatReport(
        sha256=sha256,
        package_name=package_name,
        verdict=APKVerdict(verdict_str),
        static_result=static_result,
        dynamic_result=dynamic_result,
        genai_result=genai_result,
        meta_score=meta_score,
        shap_features=SHAPFeatures(**shap),
        analysis_time_s=round(elapsed, 2),
    )

    _results[sha256] = report
    logger.info(f"APK analysis complete: verdict={verdict_str}, meta_score={meta_score}, time={elapsed:.2f}s")
    return report


@router.post("/internal/apk/analyze-hash", response_model=APKThreatReport)
async def analyze_by_hash(request: APKSubmitRequest):
    """Quick analysis by SHA-256 hash (cache lookup or simulated)."""
    sha256 = request.sha256

    if sha256 in _results:
        return _results[sha256]

    # Simulate analysis with hash-derived data
    fake_bytes = sha256.encode() * 100
    static = static_analyze(fake_bytes)
    static_result = StaticAnalysisResult(**{k: v for k, v in static.items() if k != "analysis_time_s"})
    dynamic = simulate_dynamic_analysis(sha256)
    dynamic_result = DynamicAnalysisResult(**dynamic)
    genai = simulate_genai_deobfuscation(sha256, static_result.static_score)
    genai_result = GenAIIntentResult(**genai)
    meta_score, verdict_str, shap = meta_classify(
        static_result.static_score, dynamic_result.dynamic_score,
        genai_result.intent_score, static_result.permission_risk,
    )

    report = APKThreatReport(
        sha256=sha256,
        package_name=request.package_name or f"pkg_{sha256[:8]}",
        verdict=APKVerdict(verdict_str),
        static_result=static_result,
        dynamic_result=dynamic_result,
        genai_result=genai_result,
        meta_score=meta_score,
        shap_features=SHAPFeatures(**shap),
    )
    _results[sha256] = report
    return report


@router.get("/internal/apk/result/{sha256}")
async def get_result(sha256: str):
    """Get analysis result by SHA-256."""
    if sha256 not in _results:
        raise HTTPException(404, f"No analysis found for hash {sha256[:16]}")
    return _results[sha256]


@router.get("/health")
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME, "cached_results": len(_results)}
