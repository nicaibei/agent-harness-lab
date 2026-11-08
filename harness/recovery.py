"""Recovery middleware for transient tool failures and repeated calls."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

from langchain.agents.middleware import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command


FailureCategory = Literal[
    "transient",
    "environment",
    "dependency_conflict",
    "policy",
    "budget",
    "tool_error",
    "exception",
]
_TRANSIENT_MARKERS = ("timeout", "timed out", "temporarily", "connection reset", "unavailable")


def classify_failure(value: object) -> FailureCategory | None:
    """Classify a tool exception or error message for recovery decisions."""
    if isinstance(value, str):
        raw_text = value
        text = raw_text[:500].casefold()
        if any(marker in text for marker in _TRANSIENT_MARKERS):
            return "transient"
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and payload.get("failure_class") in {
            "environment",
            "dependency_conflict",
        }:
            return payload["failure_class"]
        if isinstance(payload, dict) and payload.get("success") is False:
            return "tool_error"
        return None
    if isinstance(value, ToolMessage):
        raw_text = value.content if isinstance(value.content, str) else _message_text(value.content)
        text = raw_text[:500].casefold()
        if "policy denied" in text:
            return "policy"
        if "budget exhausted" in text:
            return "budget"
        if any(marker in text for marker in _TRANSIENT_MARKERS):
            return "transient"
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and payload.get("failure_class") in {
            "environment",
            "dependency_conflict",
        }:
            return payload["failure_class"]
        if isinstance(payload, dict) and payload.get("success") is False:
            return "tool_error"
        if value.status != "error":
            return None
        return "tool_error"
    if isinstance(value, BaseException):
        text = str(value).casefold()
        if isinstance(value, (TimeoutError, ConnectionError)) or any(
            marker in text for marker in _TRANSIENT_MARKERS
        ):
            return "transient"
        return "exception"
    return None


def _message_text(content: object) -> str:
    """Convert tool content into bounded text for classification and logs."""
    if isinstance(content, str):
        return content[:500]
    try:
        return json.dumps(content, ensure_ascii=False)[:500]
    except TypeError:
        return str(content)[:500]


class RecoveryMiddleware(AgentMiddleware):
    """Retry transient tool failures and stop repeated identical tool calls."""

    def __init__(
        self,
        *,
        max_retries: int = 1,
        max_repeated_calls: int = 2,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if max_repeated_calls < 1:
            raise ValueError("max_repeated_calls must be at least 1")
        self.max_retries = max_retries
        self.max_repeated_calls = max_repeated_calls
        self.on_event = on_event
        self._call_counts: dict[str, int] = {}

    def _emit(self, event: str, **details: Any) -> None:
        if self.on_event is not None:
            self.on_event({"event": event, **details})

    @staticmethod
    def _signature(request: ToolCallRequest) -> str:
        tool_call = request.tool_call
        return json.dumps(
            {"name": tool_call["name"], "args": tool_call.get("args", {})},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    @staticmethod
    def _error_message(request: ToolCallRequest, content: str) -> ToolMessage:
        return ToolMessage(
            content=content,
            name=request.tool_call["name"],
            tool_call_id=request.tool_call.get("id"),
            status="error",
        )

    def wrap_tool_call(self, request: ToolCallRequest, handler: Any) -> ToolMessage | Command[Any]:
        """Run a tool, retry transient failures, and block repeated calls."""
        tool_name = request.tool_call["name"]
        signature = self._signature(request)
        call_count = self._call_counts.get(signature, 0) + 1
        self._call_counts[signature] = call_count
        if call_count > self.max_repeated_calls:
            self._emit(
                "recovery_loop_blocked",
                tool=tool_name,
                repeated_calls=call_count,
            )
            return self._error_message(request, "Recovery stopped repeated identical tool calls.")

        for attempt in range(self.max_retries + 1):
            try:
                result = handler(request)
            except Exception as error:  # noqa: BLE001 - classify and bound tool failures
                category = classify_failure(error)
                self._emit(
                    "recovery_failure",
                    tool=tool_name,
                    category=category,
                    attempt=attempt + 1,
                    error=str(error)[:500],
                )
                if category == "transient" and attempt < self.max_retries:
                    self._emit("recovery_retry", tool=tool_name, attempt=attempt + 2)
                    continue
                self._emit("recovery_terminal", tool=tool_name, category=category)
                return self._error_message(request, f"Recovery stopped after tool failure: {error}")

            category = classify_failure(result)
            if category is None:
                self._emit("recovery_success", tool=tool_name, attempt=attempt + 1)
                return result
            self._emit(
                "recovery_failure",
                tool=tool_name,
                category=category,
                attempt=attempt + 1,
                error=_message_text(result.content) if isinstance(result, ToolMessage) else "",
            )
            if category == "transient" and attempt < self.max_retries:
                self._emit("recovery_retry", tool=tool_name, attempt=attempt + 2)
                continue
            self._emit("recovery_terminal", tool=tool_name, category=category)
            return result

        return self._error_message(request, "Recovery retry budget exhausted.")
