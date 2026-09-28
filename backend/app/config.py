from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Anthropic Claude — powers every agent and extraction call
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"
    anthropic_model_fast: str = "claude-sonnet-5"
    # Thinking/output depth: low | medium | high | xhigh | max. Blank = API
    # default (high). Lower it to trade quality for latency and cost.
    anthropic_effort: str = ""
    anthropic_max_retries: int = 5
    anthropic_timeout_seconds: float = 600.0

    # OpenAI — ONLY used by the semantic embedding layer (app/utils/semantic.py).
    # Anthropic has no embeddings API. Leave blank to use the lexical fallback.
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"

    # App
    app_name: str = "TopNotchResume"
    debug: bool = False
    downloads_dir: str = "downloads"
    download_ttl_seconds: int = 86400  # 24 hours — files are swept after this
    history_db_path: str = "data/history.db"

    # Abuse protection — the API is public and every AI call spends credits.
    # Per client IP, per hour. 0 disables a limit.
    rate_limit_generations_per_hour: int = 10
    rate_limit_ai_calls_per_hour: int = 60
    max_concurrent_generations: int = 3
    # In-memory job/session retention
    job_ttl_seconds: int = 7200
    session_ttl_seconds: int = 86400

    # CORS
    allowed_origins: list[str] = [
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3010", "http://127.0.0.1:3010",
    ]

    # PostgreSQL (Data Vault 2.0 persistence)
    database_url: str = ""

    # Generation limits
    max_generation_timeout: int = 120
    # How long the SSE stream stays open waiting for a running pipeline.
    # Claude with adaptive thinking on a large profile (many roles + projects)
    # regularly runs 2-4 minutes, so this must be generous. The background job
    # is never cancelled by this — the client falls back to polling the result
    # endpoint if the stream drops first.
    stream_timeout_seconds: int = 900
    max_bullets_per_role: int = 6
    min_bullets_per_role: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
