"""LLM transport layer: talks to an OpenAI-compatible chat completions API.

Only this module knows about the provider SDK/HTTP details. It handles
timeouts, retries, rate limits and JSON extraction. The rest of the app only
sees structured data from :class:`AIService`.
"""

import json
import logging
import re
from collections.abc import Callable
from time import sleep

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRYABLE_HTTP = {429, 500, 502, 503, 504}


class AIProviderError(Exception):
    """The LLM provider failed (timeout, network, HTTP error after retries)."""


class AIResponseError(Exception):
    """The LLM returned a response we could not parse into the expected shape."""


class LLMService:
    """Stateless client for an OpenAI-compatible chat completions endpoint."""

    def __init__(self, settings=None, http_client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        # Injectable httpx client makes the transport easy to unit test.
        self._http = http_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def chat(self, messages: list[dict], temperature: float = 0.4) -> str:
        """Send a chat request and return the assistant's message content."""
        return self._with_retries(lambda: self._request(messages, temperature))

    def chat_json(self, messages: list[dict], temperature: float = 0.4) -> dict:
        """Like :meth:`chat` but parses the response as a JSON object."""
        content = self.chat(messages, temperature=temperature)
        return self._parse_json(content)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _request(self, messages: list[dict], temperature: float) -> str:
        settings = self.settings
        if not settings.llm_api_key:
            raise AIProviderError(
                "LLM_API_KEY is not configured. Set LLM_API_KEY, or run with "
                "LLM_PROVIDER=mock for an offline demo."
            )
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        with self._get_client() as client:
            response = client.post(url, json=payload, headers=headers, timeout=settings.llm_timeout_seconds)

        if response.status_code == 401:
            raise AIProviderError("LLM provider rejected the API key (401).")
        if response.status_code >= 500 or response.status_code == 429:
            # Retryable — caller decides whether to retry.
            raise AIProviderError(
                f"LLM provider HTTP {response.status_code}: {response.text[:200]}"
            )
        if response.status_code >= 400:
            raise AIProviderError(
                f"LLM provider HTTP {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise AIResponseError(f"Unexpected LLM response shape: {exc}") from exc

    def _with_retries(self, fn: Callable[[], str]) -> str:
        """Retry transient failures (5xx/429/timeout/network) with backoff."""
        settings = self.settings
        last_error: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                return fn()
            except httpx.TimeoutException as exc:
                last_error = exc
            except httpx.HTTPError as exc:
                last_error = exc
            except AIProviderError as exc:
                last_error = exc
                if exc.args and any(code in exc.args[0] for code in ("500", "502", "503", "504", "429")):
                    pass  # retryable
                else:
                    raise
            if attempt < settings.llm_max_retries:
                sleep(0.5 * (attempt + 1))
                logger.warning("LLM request failed (attempt %s): %s", attempt + 1, last_error)
        raise AIProviderError(f"LLM provider unreachable after retries: {last_error}")

    def _get_client(self) -> httpx.Client:
        return self._http or httpx.Client()

    @staticmethod
    def _parse_json(content: str) -> dict:
        """Parse JSON out of the model output, tolerating stray text.

        Strategy: try full parse -> try extracting the first {...} block ->
        raise AIResponseError if all fail.
        """
        content = content.strip()
        if not content:
            raise AIResponseError("LLM returned an empty response.")

        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        raise AIResponseError(
            f"LLM response is not valid JSON. Content preview: {content[:200]!r}"
        )
