"""APK Analysis Service configuration."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "apk-analysis"
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    REDIS_URL: str = "redis://redis:6379/0"
    PG_DSN: str = "postgresql://kavalx:kavalx@postgres:5432/kavalx"
    VLLM_URL: str = "http://vllm:8090"
    MILVUS_HOST: str = "milvus"
    MILVUS_PORT: int = 19530
    SANDBOX_TIMEOUT: int = 120
    MAX_API_CALLS: int = 500

    class Config:
        env_prefix = "APK_"


settings = Settings()
