"""
Compliance Engine — Configuration
RBI/CERT-In report generation, IndicTrans2 translation, PQC signing settings.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Compliance Engine"
    app_version: str = "1.0.0"
    debug: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/2"

    # PDF output directory
    pdf_output_dir: str = "reports"

    # AMADP endpoint (for fetching verdict data)
    amadp_base_url: str = "http://localhost:8005"

    # IndicTrans2 endpoint (for Hindi translation)
    indictrans_endpoint: str = "http://localhost:9000/translate"

    # Ledger (blockchain anchoring) endpoint
    ledger_endpoint: str = "http://localhost:8545"

    # PQC signing keys
    pqc_private_key_path: str = "keys/dilithium_private.pem"
    pqc_public_key_path: str = "keys/dilithium_public.pem"

    class Config:
        env_prefix = "COMPLIANCE_"
        env_file = ".env"


settings = Settings()
