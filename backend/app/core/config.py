from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # --- App ---
    app_name: str = "AI Interviewer API"
    app_env: str = "development"
    debug: bool = False

    # --- Database ---
    # Default is a local PostgreSQL (used by docker-compose). Set to a
    # sqlite:/// URL for quick local development or tests.
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/ai_interviewer"
    )

    # --- Security ---
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24h

    # --- LLM provider ---
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    # When set to "mock", the app uses a deterministic offline LLM service.
    # This lets the full app run without an API key.
    llm_provider: str = "mock"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_mock_llm(self) -> bool:
        return self.llm_provider.lower() == "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
