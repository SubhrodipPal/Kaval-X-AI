"""
FL Coordinator — Configuration
Federated Learning coordination, differential privacy, and gradient aggregation settings.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "FL Coordinator"
    app_version: str = "1.0.0"
    debug: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/3"

    # Federated Learning
    min_banks: int = 3
    max_rounds: int = 10
    gradient_vector_size: int = 1000  # dimensions per gradient update

    # Differential Privacy
    dp_epsilon: float = 0.5
    dp_delta: float = 1e-5
    dp_noise_multiplier: float = 1.1
    dp_max_grad_norm: float = 1.0

    # Privacy budget
    total_privacy_budget_epsilon: float = 10.0

    class Config:
        env_prefix = "FL_"
        env_file = ".env"


settings = Settings()
