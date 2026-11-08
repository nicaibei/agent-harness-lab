"""Policy middleware for the Issue-to-PR agent."""

from __future__ import annotations

import fnmatch
import json
import shlex
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any, Literal

from langchain.agents.middleware import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command


DEFAULT_ALLOWED_TOOLS = frozenset(
    {
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "glob",
        "grep",
        "delete",
        "run_command",
        "run_tests",
        "prepare_dependency",
        "write_todos",
    }
)
PATH_TOOLS = frozenset({"ls", "read_file", "write_file", "edit_file", "glob", "grep", "delete"})
MUTATING_TOOLS = frozenset({"write_file", "edit_file", "delete"})
SENSITIVE_NAMES = (".env", ".env.*", "*.pem", "*.key", "id_rsa", "credentials*.json")
COMMAND_TOOLS = frozenset({"run_command"})
PREPARATION_TOOLS = frozenset({"prepare_dependency"})
CommandRisk = Literal["safe", "review", "dangerous"]
_DANGEROUS_COMMANDS = frozenset(
    {"del", "erase", "format", "rm", "rmdir", "shutdown", "taskkill"}
)
_SHELL_OPERATORS = ("&&", "||", ";", "|", ">", "<", "`", "$", "\n")


def classify_command(command: object) -> CommandRisk:
    """Classify a command before any execution tool can receive it."""
    if not isinstance(command, str) or not command.strip():
        return "dangerous"
    if any(operator in command for operator in _SHELL_OPERATORS):
        return "dangerous"
    try:
        parts = shlex.split(command, posix=False)
    except ValueError:
        return "dangerous"
    if not parts:
        return "dangerous"
    executable = PurePosixPath(parts[0].replace("\\", "/")).name.casefold()
    if executable in _DANGEROUS_COMMANDS:
        return "dangerous"
    if executable in {"pytest", "pytest.exe"}:
        return "safe"
    if executable in {"python", "python.exe", "py", "py.exe"} and len(parts) >= 3:
        if parts[1:3] == ["-m", "pytest"]:
            return "safe"
    return "review"


class PolicyMiddleware(AgentMiddleware):
    """Enforce tool, path, sensitive-file, and per-run call policies."""

    def __init__(
        self,
        *,
        max_tool_calls: int = 30,
        allowed_tools: frozenset[str] = DEFAULT_ALLOWED_TOOLS,
        on_decision: Callable[[dict[str, Any]], None] | None = None,
        approval_callback: Callable[[dict[str, Any]], bool] | None = None,
        require_baseline_test: bool = False,
        stop_on_environment_failure: bool = False,
    ) -> None:
        if max_tool_calls < 1:
            raise ValueError("max_tool_calls must be at least 1")
        self.max_tool_calls = max_tool_calls
        self.allowed_tools = allowed_tools
        self.on_decision = on_decision
        self.approval_callback = approval_callback
        self.require_baseline_test = require_baseline_test
        self.stop_on_environment_failure = stop_on_environment_failure
        self.baseline_test_completed = False
        self.environment_failure_detected = False
        self.dependency_conflict_detected = False
        self.environment_preparation_completed = False
        self.call_count = 0

    def _emit(
        self,
        decision: str,
        tool_name: str,
        reason: str,
        call_index: int,
        **details: Any,
    ) -> None:
        if self.on_decision is not None:
            self.on_decision(
                {
                    "decision": decision,
                    "tool": tool_name,
                    "reason": reason,
                    "call_index": call_index,
                    **details,
                }
            )

    @staticmethod
    def _normalize_path(raw_path: object) -> str | None:
        if not isinstance(raw_path, str) or not raw_path.strip():
            return None
        normalized = raw_path.replace("\\", "/")
        path = PurePosixPath(normalized)
        if ".." in path.parts or ":" in path.parts[0] or "\x00" in normalized:
            return None
        return "/" + "/".join(part for part in path.parts if part not in {"/", "."})

    @classmethod
    def _path_reason(cls, tool_name: str, args: dict[str, Any]) -> str | None:
        raw_path = args.get("file_path", args.get("path"))
        normalized = cls._normalize_path(raw_path)
        if raw_path is not None and normalized is None:
            return "path is outside the workspace allowlist or is not a valid virtual path"
        if normalized is None:
            return None
        if any(fnmatch.fnmatch(PurePosixPath(normalized).name, pattern) for pattern in SENSITIVE_NAMES):
            return "sensitive files are not accessible"
        if tool_name == "delete":
            return "delete is disabled by the baseline policy"
        return None

    def _deny(
        self,
        request: ToolCallRequest,
        reason: str,
        call_index: int,
        **details: Any,
    ) -> ToolMessage:
        tool_call = request.tool_call
        tool_name = tool_call["name"]
        self._emit("deny", tool_name, reason, call_index, **details)
        return ToolMessage(
            content=f"Policy denied tool call: {reason}.",
            name=tool_name,
            tool_call_id=tool_call.get("id"),
            status="error",
        )

    @staticmethod
    def _environment_failure_class(result: object) -> str | None:
        """Return the structured environment failure category, when present."""
        if not isinstance(result, ToolMessage) or not isinstance(result.content, str):
            return None
        try:
            payload = json.loads(result.content)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        failure_class = payload.get("failure_class")
        if failure_class in {"environment", "dependency_conflict"}:
            return failure_class
        return None

    @staticmethod
    def _is_environment_prepared(result: object) -> bool:
        """Detect a successful result from the approved preparation tool."""
        if not isinstance(result, ToolMessage) or not isinstance(result.content, str):
            return False
        try:
            payload = json.loads(result.content)
        except json.JSONDecodeError:
            return False
        return isinstance(payload, dict) and payload.get("prepared") is True

    def wrap_tool_call(self, request: ToolCallRequest, handler: Any) -> ToolMessage | Command[Any]:
        """Check a tool call before delegating to the actual tool."""
        tool_call = request.tool_call
        tool_name = tool_call["name"]
        call_index = self.call_count + 1
        if self.call_count >= self.max_tool_calls:
            return self._deny(request, "tool call budget exhausted", call_index)
        self.call_count += 1
        if tool_name not in self.allowed_tools:
            return self._deny(request, f"tool {tool_name!r} is not allowlisted", call_index)
        if (
            tool_name in PREPARATION_TOOLS
            and self.stop_on_environment_failure
            and not self.environment_failure_detected
        ):
            return self._deny(
                request,
                "dependency preparation requires a baseline environment failure",
                call_index,
            )
        if (
            self.stop_on_environment_failure
            and self.environment_failure_detected
            and tool_name in MUTATING_TOOLS
            and not self.environment_preparation_completed
        ):
            return self._deny(
                request,
                "environment failure requires environment preparation before file mutations",
                call_index,
            )
        if (
            self.require_baseline_test
            and tool_name in MUTATING_TOOLS
            and not self.baseline_test_completed
        ):
            return self._deny(request, "baseline test must run before file mutations", call_index)
        if tool_name in COMMAND_TOOLS:
            command = tool_call.get("args", {}).get("command")
            risk = classify_command(command)
            if risk == "dangerous":
                return self._deny(request, "dangerous commands are not allowed", call_index, risk=risk)
            if risk == "review":
                approval_request = {
                    "tool": tool_name,
                    "command": command,
                    "risk": risk,
                    "call_index": call_index,
                }
                if self.approval_callback is None or not self.approval_callback(approval_request):
                    return self._deny(request, "command requires approval", call_index, risk=risk)
                self._emit("allow", tool_name, "command approved", call_index, risk=risk)
                return handler(request)
            self._emit("allow", tool_name, "safe command", call_index, risk=risk)
            return handler(request)
        reason = self._path_reason(tool_name, tool_call.get("args", {})) if tool_name in PATH_TOOLS else None
        if reason is not None:
            return self._deny(request, reason, call_index)
        if tool_name == "run_tests" and self.require_baseline_test:
            result = handler(request)
            self.baseline_test_completed = True
            failure_class = self._environment_failure_class(result)
            if self.stop_on_environment_failure and failure_class is not None:
                self.environment_failure_detected = True
                self.dependency_conflict_detected = failure_class == "dependency_conflict"
                self._emit(
                    "block_environment_recovery",
                    tool_name,
                    f"external dependency failure: {failure_class}",
                    call_index,
                )
            self._emit("allow", tool_name, "baseline test completed", call_index)
            return result
        if tool_name in PREPARATION_TOOLS:
            result = handler(request)
            if self._is_environment_prepared(result):
                self.environment_preparation_completed = True
                self._emit(
                    "environment_prepared",
                    tool_name,
                    "approved dependency prepared",
                    call_index,
                )
            return result
        self._emit("allow", tool_name, "policy checks passed", call_index)
        return handler(request)
