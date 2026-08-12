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

    # --- Evaluator / score engine ---
    # Version identifiers recorded on every evaluation for observability and
    # A/B comparison of evaluator improvements.
    evaluator_version: str = "v2"
    prompt_version: str = "v2"

    # Weight of each dimension when computing the final 0-10 score.
    score_weight_relevance: float = 0.25
    score_weight_correctness: float = 0.25
    score_weight_completeness: float = 0.2
    score_weight_understanding: float = 0.2
    score_weight_reasoning: float = 0.1

    # Hard gates: an answer in one of these states can never score above the cap.
    # These make the "score is not the source of truth" rule explicit.
    status_score_caps: str = (
        "on_topic:10,partial:7,incorrect:4.5,irrelevant:2,knowledge_gap:1.5,"
        "contradictory:4,nonsense:1"
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_mock_llm(self) -> bool:
        return self.llm_provider.lower() == "mock"

    @property
    def score_weights(self) -> dict[str, float]:
        return {
            "relevance": self.score_weight_relevance,
            "correctness": self.score_weight_correctness,
            "completeness": self.score_weight_completeness,
            "understanding": self.score_weight_understanding,
            "reasoning": self.score_weight_reasoning,
        }

    @property
    def status_caps(self) -> dict[str, float]:
        caps: dict[str, float] = {}
        for item in self.status_score_caps.split(","):
            key, _, value = item.partition(":")
            try:
                caps[key.strip()] = float(value)
            except ValueError:
                continue
        return caps


@lru_cache
def get_settings() -> Settings:
    return Settings()
