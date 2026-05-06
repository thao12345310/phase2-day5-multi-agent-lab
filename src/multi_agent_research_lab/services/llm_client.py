"""LLM client abstraction with multi-provider fallback.

Production note: agents should depend on this interface instead of importing an SDK directly.
Supports OpenAI as primary provider with retry + exponential backoff.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.pricing import calculate_cost

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    """Structured response from any LLM provider."""
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    provider: str = "openai"
    model: str = "gpt-4o-mini"


class LLMClient:
    """Provider-agnostic LLM client with retry and fallback.

    Fallback strategy (per lab_plan.md):
    - Retry 3 times with exponential backoff on rate limit / connection errors
    - If all retries fail, raise to let supervisor handle gracefully
    """

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout: float = 30.0,
    ):
        settings = get_settings()
        self.model = model or settings.openai_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        if not settings.openai_api_key:
            log.warning("OPENAI_API_KEY not set — LLM calls will fail")

        self._client = OpenAI(
            api_key=settings.openai_api_key or "dummy-key",
            timeout=timeout,
        )

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _call_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """Make a single OpenAI API call with retry."""
        start = time.perf_counter()

        kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self._client.chat.completions.create(**kwargs)

        latency_ms = (time.perf_counter() - start) * 1000
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        content = response.choices[0].message.content or ""

        cost = calculate_cost(self.model, input_tokens, output_tokens)

        log.debug(
            f"LLM call: model={self.model} in={input_tokens} out={output_tokens} "
            f"cost=${cost.total_cost_usd:.6f} latency={latency_ms:.0f}ms"
        )

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost.total_cost_usd,
            latency_ms=latency_ms,
            provider="openai",
            model=self.model,
        )

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """Return a model completion with retry + fallback.

        Args:
            system_prompt: System instruction for the LLM
            user_prompt: User query/content
            response_format: Optional response format (e.g. {"type": "json_object"})
        """
        try:
            return self._call_openai(system_prompt, user_prompt, response_format)
        except Exception as e:
            log.error(f"LLM call failed after retries: {e}")
            raise

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Complete and parse JSON response.

        Instructs the model to return JSON and parses it.
        Falls back to extracting JSON from markdown code blocks if needed.
        """
        response = self.complete(
            system_prompt=system_prompt + "\n\nRespond ONLY with valid JSON, no markdown.",
            user_prompt=user_prompt,
            response_format={"type": "json_object"},
        )
        text = response.content.strip()

        # Try direct parse
        try:
            parsed = json.loads(text)
            parsed["_llm_response"] = {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
                "latency_ms": response.latency_ms,
                "model": response.model,
            }
            return parsed
        except json.JSONDecodeError:
            pass

        # Try extracting from code block
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            parsed = json.loads(text)
            parsed["_llm_response"] = {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
                "latency_ms": response.latency_ms,
                "model": response.model,
            }
            return parsed
        except json.JSONDecodeError:
            log.error(f"Failed to parse JSON from LLM response: {text[:200]}")
            return {
                "error": "json_parse_failed",
                "raw": text,
                "_llm_response": {
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                    "latency_ms": response.latency_ms,
                    "model": response.model,
                },
            }
