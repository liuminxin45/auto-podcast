"""Thin OpenAI SDK adapter used by Python workflow nodes."""

import json
import os
import time
from collections.abc import Iterator
from typing import Any

DEFAULT_TIMEOUT = 60
DEFAULT_TEMPERATURE = 0.3
BATCH_SIZE = 10
BATCH_DELAY = 0.5
DEBUG_MAX_CHARS = 150
DEBUG_MAX_TOKENS = 200


class LLMError(Exception):
    """Project-level LLM error with a stable code for callers."""

    def __init__(self, message: str, code: str = "UNKNOWN", details: Any = None):
        super().__init__(message)
        self.code = code
        self.details = details


class LLMClient:
    """Small project adapter around the OpenAI SDK."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        temperature: float = DEFAULT_TEMPERATURE,
        debug_mode: bool = False,
    ):
        if not api_base or not api_key:
            raise LLMError("Missing API credentials", "AUTH")

        self.api_base = api_base.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.debug_mode = debug_mode
        self._client = self._create_client(api_key)

    def call(
        self,
        messages: list[dict[str, str]],
        timeout: int = DEFAULT_TIMEOUT,
        max_tokens: int | None = None,
        logs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run one chat completion and return a JSON-serializable dict."""
        messages, max_tokens = self._prepare_request(messages, max_tokens, timeout, logs)

        try:
            response = self._client.with_options(timeout=timeout).chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                **({"max_tokens": max_tokens} if max_tokens else {}),
            )
            return response.model_dump(mode="json")
        except Exception as error:
            raise self._to_llm_error(error) from error

    def stream(
        self,
        messages: list[dict[str, str]],
        timeout: int = DEFAULT_TIMEOUT,
        max_tokens: int | None = None,
        logs: list[str] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Run a streaming chat completion and yield JSON-serializable chunks."""
        messages, max_tokens = self._prepare_request(messages, max_tokens, timeout, logs)

        try:
            stream = self._client.with_options(timeout=timeout).chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                stream=True,
                **({"max_tokens": max_tokens} if max_tokens else {}),
            )
            for chunk in stream:
                yield chunk.model_dump(mode="json")
        except Exception as error:
            raise self._to_llm_error(error) from error

    def fetch_models(self, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """Fetch provider model metadata through the configured SDK client."""
        try:
            response = self._client.with_options(timeout=timeout).models.list()
            return response.model_dump(mode="json")
        except Exception as error:
            raise self._to_llm_error(error) from error

    def extract_content(self, response: dict[str, Any]) -> str:
        """Extract assistant text from an OpenAI chat completion response."""
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError("Invalid response format", "PARSE", details=str(error)) from error

    def parse_json_response(self, content: str) -> Any:
        """Parse JSON from a model response, including fenced code blocks."""
        text = content.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise LLMError(f"JSON parse error: {error}", "PARSE", details=text[:200]) from error

    def batch_analyze(
        self,
        items: list[Any],
        prompt_fn,
        parse_fn,
        logs: list[str] | None = None,
    ) -> list[Any]:
        """Analyze items in batches while preserving per-item fallback results."""
        batch_size = 1 if self.debug_mode else BATCH_SIZE
        total_batches = (len(items) - 1) // batch_size + 1 if items else 0
        results: list[Any] = []

        self._log(logs, f"batch_analyze: {len(items)} items, {total_batches} batches")

        for batch_index, start in enumerate(range(0, len(items), batch_size), start=1):
            batch = items[start : start + batch_size]
            self._log(
                logs,
                f"Processing batch {batch_index}/{total_batches} ({len(batch)} items)",
            )

            try:
                started_at = time.time()
                prompt = prompt_fn(batch)
                response = self.call([{"role": "user", "content": prompt}], logs=logs)
                content = self.extract_content(response)
                parsed = self.parse_json_response(content)
                results.extend(parse_fn(batch, parsed))
                self._log(logs, f"Batch {batch_index} completed in {time.time() - started_at:.2f}s")
            except Exception as error:
                self._log(logs, f"Batch {batch_index} failed: {type(error).__name__}: {error}")
                results.extend(self._error_results(batch, str(error)))

            if batch_index < total_batches:
                time.sleep(BATCH_DELAY)

        self._log(logs, f"batch_analyze completed: {len(results)} results")
        return results

    def _create_client(self, api_key: str):
        try:
            from openai import AzureOpenAI, OpenAI
        except ImportError as error:
            raise LLMError("OpenAI SDK is not installed", "CONFIG") from error

        if "openai.azure.com" in self.api_base:
            return AzureOpenAI(
                api_key=api_key,
                azure_endpoint=self.api_base,
                api_version=os.environ.get("OPENAI_API_VERSION", "2024-02-15-preview"),
            )
        return OpenAI(api_key=api_key, base_url=f"{self.api_base}/")

    def _prepare_request(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None,
        timeout: int,
        logs: list[str] | None,
    ) -> tuple[list[dict[str, str]], int | None]:
        if not self.debug_mode:
            return messages, max_tokens

        original_len = sum(len(message.get("content", "")) for message in messages)
        truncated = [
            {**message, "content": message.get("content", "")[:DEBUG_MAX_CHARS]}
            for message in messages
        ]
        truncated_len = sum(len(message.get("content", "")) for message in truncated)
        max_tokens = min(max_tokens or DEBUG_MAX_TOKENS, DEBUG_MAX_TOKENS)
        self._log(
            logs,
            f"DEBUG CALL: prompt {original_len} chars -> {truncated_len} chars, "
            f"max_tokens={max_tokens}, timeout={timeout}s",
        )
        return truncated, max_tokens

    def _to_llm_error(self, error: Exception) -> LLMError:
        if isinstance(error, LLMError):
            return error

        status_code = getattr(error, "status_code", None)
        code = getattr(error, "code", None) or type(error).__name__

        if status_code in {401, 403}:
            category = "AUTH"
        elif status_code == 429:
            category = "RATE_LIMIT"
        elif "timeout" in type(error).__name__.lower():
            category = "TIMEOUT"
        elif "connection" in type(error).__name__.lower():
            category = "NETWORK"
        else:
            category = "UNKNOWN"

        message = f"{type(error).__name__}: {error}"
        return LLMError(message, category, details={"status_code": status_code, "code": code})

    def _error_results(self, batch: list[Any], error: str) -> list[Any]:
        return [{**item, "_error": error} if isinstance(item, dict) else item for item in batch]

    @staticmethod
    def _log(logs: list[str] | None, message: str) -> None:
        if logs is not None:
            logs.append(f"[LLMClient] {message}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._client.close()
