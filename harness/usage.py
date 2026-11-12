"""Collect model callback evidence without guessing missing usage or prices."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Literal, TypedDict
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, LLMResult


class TokenCounts(TypedDict):
    """Provider-reported token counts for one complete usage record."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class _Observation:
    status: Literal["started", "completed", "failed"]
    tokens: TokenCounts | None = None
    source: str | None = None


def _token_counts(value: object, *, provider_keys: bool = False) -> TokenCounts | None:
    if not isinstance(value, Mapping):
        return None
    keys = ("prompt_tokens", "completion_tokens", "total_tokens") if provider_keys else (
        "input_tokens", "output_tokens", "total_tokens"
    )
    counts = [value.get(key) for key in keys]
    if not all(type(count) is int and count >= 0 for count in counts):
        return None
    if counts[0] + counts[1] != counts[2]:
        return None
    return TokenCounts(input_tokens=counts[0], output_tokens=counts[1], total_tokens=counts[2])


def _response_usage(response: LLMResult) -> _Observation:
    # The runners use one chat prompt and one candidate per invocation.
    if len(response.generations) != 1 or len(response.generations[0]) != 1:
        return _Observation("completed")
    generation = response.generations[0][0]
    if not isinstance(generation, ChatGeneration) or not isinstance(generation.message, AIMessage):
        return _Observation("completed")
    message = generation.message
    tokens = _token_counts(message.usage_metadata)
    if tokens is not None:
        return _Observation("completed", tokens, "usage_metadata")
    tokens = _token_counts(message.response_metadata.get("token_usage"), provider_keys=True)
    return _Observation("completed", tokens, "response_metadata.token_usage" if tokens else None)


class ModelUsageRecorder(BaseCallbackHandler):
    """Observe model invocations, including responses preceding a later failure.

    Counts are LangChain callback invocations, not underlying HTTP attempts.
    Missing usage remains unknown. No token prices are assumed.
    """

    def __init__(self) -> None:
        self._observations: dict[UUID, _Observation] = {}
        self._lock = Lock()

    def on_chat_model_start(
        self,
        serialized: dict[str, object],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        **kwargs: object,
    ) -> None:
        """Record an invocation without retaining prompts or credentials."""
        with self._lock:
            self._observations[run_id] = _Observation("started")

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: object) -> None:
        """Read each successful callback result once, keyed by invocation ID."""
        with self._lock:
            self._observations[run_id] = _response_usage(response)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: object) -> None:
        """Keep failed invocations visible without storing provider error data."""
        with self._lock:
            self._observations[run_id] = _Observation("failed")

    def summary(self) -> dict[str, object]:
        """Return observed token subtotals and their completeness boundary."""
        with self._lock:
            observations = list(self._observations.values())
        covered = [item.tokens for item in observations if item.tokens is not None]
        status = "unavailable"
        if not observations:
            status = "no_calls"
        elif covered:
            status = "complete" if len(covered) == len(observations) else "partial"
        totals = None
        if covered:
            totals = TokenCounts(
                input_tokens=sum(item["input_tokens"] for item in covered),
                output_tokens=sum(item["output_tokens"] for item in covered),
                total_tokens=sum(item["total_tokens"] for item in covered),
            )
        return {
            "schema_version": "model-usage.v1",
            "model_invocations": len(observations),
            "model_responses": sum(item.status == "completed" for item in observations),
            "model_errors": sum(item.status == "failed" for item in observations),
            "unfinished_invocations": sum(item.status == "started" for item in observations),
            "responses_with_usage": len(covered),
            "token_usage_status": status,
            "observed_tokens": totals,
            "usage_sources": sorted({item.source for item in observations if item.source}),
            "provider_http_requests": None,
            "provider_http_requests_status": "not_instrumented",
            "cost": None,
            "cost_status": "pricing_not_configured",
        }
