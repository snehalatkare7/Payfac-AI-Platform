"""PayFac Fraud Analysis AI Platform - Configuration."""

from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI (non-Azure)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # NeonDB
    neondb_connection_string: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_security_protocol: str = "PLAINTEXT"
    kafka_sasl_mechanism: str = "PLAIN"
    kafka_sasl_username: str = ""
    kafka_sasl_password: str = ""
    kafka_group_id: str = "fraud-analysis-agents"

    # Application
    log_level: str = "INFO"
    environment: str = "development"

    # Memory TTLs (seconds)
    short_term_memory_ttl: int = 3600        # 1 hour
    episodic_memory_recall_limit: int = 10

    # RAG settings
    rag_similarity_threshold: float = 0.75
    rag_top_k: int = 10

    # Resolve .env from project root so scripts work from any cwd.
    model_config = {"env_file": str(ENV_FILE), "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
