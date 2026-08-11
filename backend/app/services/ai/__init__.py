"""AI service factory: picks the implementation from settings.

``LLM_PROVIDER``:
- ``mock``  (default) -> deterministic offline service (great for demo + tests)
- anything else        -> real OpenAI-compatible LLM service
"""

from app.core.config import get_settings
from app.services.ai.ai_service import LLMAIService
from app.services.ai.base import AIService
from app.services.ai.mock_ai_service import MockAIService


def build_ai_service() -> AIService:
    settings = get_settings()
    if settings.is_mock_llm:
        return MockAIService()
    return LLMAIService()
