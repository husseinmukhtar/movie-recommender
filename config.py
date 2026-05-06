"""
config.py — Centralised settings loaded from environment variables / .env file.
All modules import from here; never hard-code secrets or URLs elsewhere.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    # ── App ───────────────────────────────────────────────────────────────
    app_name: str = "Movie Recommender API"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./recommender.db"  # swap for postgres in prod
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    model_cache_ttl_seconds: int = 1800       # 30 min recommendation cache
    feature_cache_ttl_seconds: int = 14400    # 4 hr feature cache

    # ── Kafka ─────────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_user_events: str = "user-events"

    # ── Auth ──────────────────────────────────────────────────────────────
    secret_key: str = "CHANGE_ME_IN_PRODUCTION_use_openssl_rand_hex_32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # ── ML ────────────────────────────────────────────────────────────────
    als_factors: int = 128
    als_regularization: float = 0.01
    als_iterations: int = 30
    als_confidence_weight: float = 40.0       # confidence = 1 + weight*(rating/5)

    two_tower_embedding_dim: int = 64
    two_tower_epochs: int = 20
    two_tower_batch_size: int = 1024

    ranker_n_estimators: int = 500
    ranker_learning_rate: float = 0.05

    recommendation_pool_size: int = 500       # candidate pool before re-ranking
    max_recommendations: int = 50             # API hard cap

    # ── MLflow ────────────────────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "movie-recommender"

    # ── External APIs ─────────────────────────────────────────────────────
    tmdb_api_key: str = ""
    tmdb_base_url: str = "https://api.themoviedb.org/3"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings singleton — call this everywhere."""
    return Settings()
