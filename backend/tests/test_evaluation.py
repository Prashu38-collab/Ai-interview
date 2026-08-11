"""AI edge cases: malformed output, provider failures and JSON parsing."""

import pytest

from app.services.ai.llm_service import (
    AIProviderError,
    AIResponseError,
    LLMService,
)
from tests.conftest import ControllableAIService


def test_provider_failure_returns_503(client, auth_headers, make_interview, override_ai):
    override_ai(ControllableAIService(fail_with=AIProviderError("LLM is down")))
    interview_id = make_interview()
    res = client.post(f"/interviews/{interview_id}/analyze", headers=auth_headers)
    assert res.status_code == 503
    assert "temporarily unavailable" in res.json()["detail"]
    assert "LLM is down" not in res.json()["detail"]  # no internal detail leak


def test_invalid_ai_response_returns_502(client, auth_headers, make_interview, override_ai):
    override_ai(ControllableAIService(fail_with=AIResponseError("not json")))
    interview_id = make_interview()
    res = client.post(f"/interviews/{interview_id}/analyze", headers=auth_headers)
    assert res.status_code == 502
    assert "invalid response" in res.json()["detail"]


@pytest.mark.parametrize(
    "content, expected",
    [
        ('{"a": 1}', {"a": 1}),
        ('Here is the result: {"a": 1}\n\nHope this helps', {"a": 1}),
        ('{"nested": {"x": [1, 2]}}', {"nested": {"x": [1, 2]}}),
    ],
)
def test_parse_json_extracts_object(content, expected):
    assert LLMService._parse_json(content) == expected


@pytest.mark.parametrize(
    "content", ["", "not json at all", "[1, 2, 3]", "{\"a\": "]
)
def test_parse_json_rejects_garbage(content):
    with pytest.raises(AIResponseError):
        LLMService._parse_json(content)


def test_llm_service_requires_api_key():
    from app.core.config import Settings

    service = LLMService(settings=Settings(llm_api_key="", llm_provider="openai"))
    with pytest.raises(AIProviderError, match="LLM_API_KEY"):
        service.chat_json([{"role": "user", "content": "hi"}])
