"""Provider-neutral LLM client.

This module owns only the transport boundary for calling a configured LLM.
It handles provider configuration, retries, request timeouts, JSON-mode flags,
and raw response return values.

It intentionally does not parse model output, validate business content,
perform AI reasoning, or know anything about the requirement-engine workflow.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from engine.requirement_engine.requirement_normalizer import RequirementNormalizer


logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported provider families.

    ``OPENAI`` and ``AZURE_OPENAI`` use OpenAI-compatible chat-completion
    payloads. ``GEMINI`` and ``LOCAL`` are included as extension points with
    provider-specific payload shaping.
    """

    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    GEMINI = "gemini"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class LLMConfig:
    """Configuration required to call an LLM endpoint.

    Attributes:
        provider: Provider family used to shape payload and headers.
        base_url: Endpoint URL. For OpenAI-compatible providers this should be
            the full chat-completions endpoint.
        model: Model or deployment name.
        api_key: Optional API key. Local models may not require one.
        timeout_seconds: Per-request timeout.
        max_retries: Number of retry attempts after the initial request.
        retry_backoff_seconds: Base delay used for exponential backoff.
        extra_headers: Additional HTTP headers.
        extra_payload: Additional provider-specific payload fields.
    """

    provider: LLMProvider
    base_url: str
    model: str
    api_key: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra_payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create configuration from environment variables.

        Expected variables:
        - ``LLM_PROVIDER``: ``openai``, ``azure_openai``, ``gemini``, or ``local``
        - ``LLM_BASE_URL``: full endpoint URL
        - ``LLM_MODEL``: model or deployment name
        - ``LLM_API_KEY``: optional API key
        - ``LLM_TIMEOUT_SECONDS``: optional timeout
        - ``LLM_MAX_RETRIES``: optional retry count
        - ``LLM_RETRY_BACKOFF_SECONDS``: optional backoff base
        """

        return cls(
            provider=LLMProvider(os.getenv("LLM_PROVIDER", LLMProvider.OPENAI.value)),
            base_url=_required_env("LLM_BASE_URL"),
            model=_required_env("LLM_MODEL"),
            api_key=os.getenv("LLM_API_KEY"),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
            retry_backoff_seconds=float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "1")),
        )


@dataclass(frozen=True, slots=True)
class RawLLMResponse:
    """Raw HTTP response returned from the configured LLM endpoint.

    The body is returned as text and is not parsed or interpreted by this
    client. Downstream parsers are responsible for provider-specific decoding.
    """

    status_code: int
    headers: dict[str, str]
    body: str
    provider: LLMProvider
    elapsed_seconds: float

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "status_code": self.status_code,
            "headers": dict(self.headers),
            "body": self.body,
            "provider": self.provider.value,
            "elapsed_seconds": self.elapsed_seconds,
        }


class LLMClientError(RuntimeError):
    """Raised when the LLM request cannot be completed."""


class OfflineRequirementLLMClient:
    """Offline fallback client that returns a minimal raw analysis response.

    This client exists so the CLI can demonstrate the full Requirement
    Understanding Engine without configured external credentials. It does not
    perform business reasoning; it returns the raw requirement text in the
    expected JSON shape and lets the parser and validator do their work.
    """

    def generate(self, prompt: str) -> str:
        """Return a raw JSON response compatible with RequirementAnalysis."""

        requirement_text = _extract_user_requirement(prompt)
        return json.dumps(RequirementNormalizer().normalize(requirement_text))


class LLMClient:
    """Small provider-neutral client for LLM HTTP calls.

    The public methods return raw endpoint responses only. They do not parse the
    assistant message, enforce schemas, or perform business validation.
    """

    RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}

    def __init__(self, config: LLMConfig) -> None:
        """Create an LLM client with explicit configuration."""

        self.config = config

    @classmethod
    def from_env(cls) -> "LLMClient":
        """Create an LLM client from environment configuration."""

        config = LLMConfig.from_env()
        if config.provider != LLMProvider.LOCAL and not config.api_key:
            raise LLMClientError(
                "Missing required environment variable: LLM_API_KEY"
            )
        return cls(config=config)

    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> RawLLMResponse:
        """Send a prompt to the configured LLM and return the raw response.

        Args:
            prompt: User prompt body.
            system_prompt: Optional system/developer instruction text.
            json_mode: Whether to request JSON-formatted output from providers
                that support a JSON-mode flag.
            temperature: Optional generation temperature.
            max_tokens: Optional output token limit.
        """

        payload = self._build_payload(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self.raw_request(payload)

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> RawLLMResponse:
        """Generate a raw LLM response for a prompt.

        This method is an orchestration-friendly alias for ``complete``. It
        keeps the client compatible with engines that use provider-neutral
        ``generate`` terminology.
        """

        return self.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def raw_request(self, payload: dict[str, Any]) -> RawLLMResponse:
        """Send a raw provider payload and return the raw response."""

        body = json.dumps(payload).encode("utf-8")
        headers = self._build_headers()
        request = Request(
            self._endpoint_url(),
            data=body,
            headers=headers,
            method="POST",
        )

        last_error: Exception | None = None
        attempts = self.config.max_retries + 1

        for attempt in range(attempts):
            start = time.monotonic()
            try:
                with urlopen(
                    request,
                    timeout=self.config.timeout_seconds,
                ) as response:
                    raw_body = response.read().decode("utf-8")
                    logger.debug(
                        "Raw LLM response body: %s",
                        _truncate_for_log(raw_body),
                        extra={
                            "event": "raw_llm_response",
                            "status_code": response.status,
                            "provider": self.config.provider.value,
                        },
                    )
                    return RawLLMResponse(
                        status_code=response.status,
                        headers=dict(response.headers.items()),
                        body=raw_body,
                        provider=self.config.provider,
                        elapsed_seconds=time.monotonic() - start,
                    )
            except HTTPError as exc:
                raw_body = exc.read().decode("utf-8", errors="replace")
                logger.debug(
                    "Raw LLM error response body: %s",
                    _truncate_for_log(raw_body),
                    extra={
                        "event": "raw_llm_error_response",
                        "status_code": exc.code,
                        "provider": self.config.provider.value,
                    },
                )
                if not self._should_retry(exc.code, attempt, attempts):
                    return RawLLMResponse(
                        status_code=exc.code,
                        headers=dict(exc.headers.items()),
                        body=raw_body,
                        provider=self.config.provider,
                        elapsed_seconds=time.monotonic() - start,
                    )
                last_error = exc
            except TimeoutError as exc:
                last_error = exc
                if not self._has_retry_left(attempt, attempts):
                    break
            except URLError as exc:
                last_error = exc
                if not self._has_retry_left(attempt, attempts):
                    break

            self._sleep_before_retry(attempt)

        raise LLMClientError(f"LLM request failed after {attempts} attempts") from last_error

    def _build_headers(self) -> dict[str, str]:
        """Build provider-specific HTTP headers."""

        headers = {
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }

        if self.config.api_key:
            if self.config.provider == LLMProvider.AZURE_OPENAI:
                headers.setdefault("api-key", self.config.api_key)
            elif self.config.provider == LLMProvider.GEMINI:
                headers.setdefault("x-goog-api-key", self.config.api_key)
            else:
                headers.setdefault("Authorization", f"Bearer {self.config.api_key}")

        return headers

    def _endpoint_url(self) -> str:
        """Return the final HTTP endpoint for the configured provider."""

        base_url = self.config.base_url.rstrip("/")
        if (
            self.config.provider == LLMProvider.OPENAI
            and not base_url.endswith("/chat/completions")
        ):
            return f"{base_url}/chat/completions"
        return self.config.base_url

    @property
    def endpoint_url(self) -> str:
        """Final HTTP endpoint URL used for requests."""

        return self._endpoint_url()

    def _build_payload(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        json_mode: bool,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Build a provider-shaped payload."""

        if self.config.provider in {LLMProvider.OPENAI, LLMProvider.AZURE_OPENAI}:
            return self._build_openai_compatible_payload(
                prompt=prompt,
                system_prompt=system_prompt,
                json_mode=json_mode,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        if self.config.provider == LLMProvider.GEMINI:
            return self._build_gemini_payload(
                prompt=prompt,
                system_prompt=system_prompt,
                json_mode=json_mode,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        return self._build_local_payload(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _build_openai_compatible_payload(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        json_mode: bool,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Build a chat-completions payload for OpenAI-compatible endpoints."""

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            **self.config.extra_payload,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return payload

    def _build_gemini_payload(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        json_mode: bool,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Build a Gemini-style payload."""

        text = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": text}]}],
            **self.config.extra_payload,
        }

        generation_config: dict[str, Any] = {}
        if json_mode:
            generation_config["response_mime_type"] = "application/json"
        if temperature is not None:
            generation_config["temperature"] = temperature
        if max_tokens is not None:
            generation_config["max_output_tokens"] = max_tokens
        if generation_config:
            payload["generationConfig"] = generation_config
        return payload

    def _build_local_payload(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        json_mode: bool,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Build a generic local-model payload."""

        payload: dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            **self.config.extra_payload,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if json_mode:
            payload["format"] = "json"
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return payload

    def _should_retry(self, status_code: int, attempt: int, attempts: int) -> bool:
        """Return whether an HTTP status should be retried."""

        return (
            status_code in self.RETRYABLE_STATUS_CODES
            and self._has_retry_left(attempt, attempts)
        )

    @staticmethod
    def _has_retry_left(attempt: int, attempts: int) -> bool:
        """Return whether another retry attempt is available."""

        return attempt < attempts - 1

    def _sleep_before_retry(self, attempt: int) -> None:
        """Sleep using exponential backoff before the next retry."""

        delay = self.config.retry_backoff_seconds * (2**attempt)
        if delay > 0:
            time.sleep(delay)


def _required_env(name: str) -> str:
    """Return a required environment variable or raise a clear error."""

    value = os.getenv(name)
    if not value:
        raise LLMClientError(f"Missing required environment variable: {name}")
    return value


def _truncate_for_log(value: str, limit: int = 4000) -> str:
    """Return bounded diagnostic text for logs."""

    if len(value) <= limit:
        return value
    return f"{value[:limit]}...<truncated>"


def _extract_user_requirement(prompt: str) -> str:
    """Extract the user requirement section from an assembled prompt."""

    marker = "## User Requirement"
    if marker not in prompt:
        return prompt.strip()

    after_marker = prompt.split(marker, 1)[1].strip()
    if after_marker.startswith("---"):
        after_marker = after_marker[3:].strip()
    if "\n\n---\n\n" in after_marker:
        return after_marker.split("\n\n---\n\n", 1)[0].strip()
    return after_marker.strip()

