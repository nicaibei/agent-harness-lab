"""Run deterministic offline fault-injection cases for Recovery evaluation."""

from __future__ import annotations

import argparse
import difflib
import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, tool

from harness.recovery import RecoveryMiddleware


class BoundFakeChatModel(FakeMessagesListChatModel):
    """Offline model that accepts the tool binding used by create_deep_agent."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> BoundFakeChatModel:
        return self


def _snapshot(root: Path) -> dict[str, str]:
    """Read text files from a temporary fault-injection workspace."""
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file()
    }


def _build_diff(before: dict[str, str], after: dict[str, str]) -> str:
    """Build a small unified diff for the injected workspace."""
    chunks: list[str] = []
    for name in sorted(before.keys() | after.keys()):
        if before.get(name) == after.get(name):
            continue
        chunks.extend(
            difflib.unified_diff(
                before.get(name, "").splitlines(keepends=True),
                after.get(name, "").splitlines(keepends=True),
                fromfile=f"a/{name}" if name in before else "/dev/null",
                tofile=f"b/{name}" if name in after else "/dev/null",
            )
        )
    return "".join(chunks)


def _tool_calls(messages: list[object]) -> list[dict[str, object]]:
    """Extract model tool calls for comparing first and later actions."""
    calls: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for call in message.tool_calls:
            calls.append({"name": call["name"], "args": call.get("args", {})})
    return calls


def _run_agent(
    workspace: Path,
    tools: list[BaseTool],
    responses: list[AIMessage],
    events: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    """Run one deterministic fake-model case and return its final diff."""
    before = _snapshot(workspace)
    agent = create_deep_agent(
        model=BoundFakeChatModel(responses=responses),
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        tools=tools,
        middleware=[RecoveryMiddleware(on_event=events.append)],
    )
    result = agent.invoke({"messages": [("user", "run the fault-injection case")]})
    return result, _build_diff(before, _snapshot(workspace))


def _case_result(
    case_id: str,
    correction_type: str,
    result: dict[str, Any],
    events: list[dict[str, Any]],
    diff: str,
) -> dict[str, object]:
    """Convert one graph result into a comparable case record."""
    messages = result.get("messages", [])
    calls = _tool_calls(messages)
    test_results = [
        json.loads(message.content)
        for message in messages
        if isinstance(message, ToolMessage)
        and message.name == "run_injected_tests"
        and isinstance(message.content, str)
    ]
    changed_action = len({json.dumps(call, sort_keys=True) for call in calls}) > 1
    final_message = messages[-1] if messages else None
    return {
        "case_id": case_id,
        "correction_type": correction_type,
        "first_failure": next(
            (event for event in events if event.get("event") == "recovery_failure"),
            None,
        ),
        "events": events,
        "tool_calls": calls,
        "action_changed": changed_action,
        "diff": diff,
        "final_success": isinstance(final_message, AIMessage) and final_message.content == "finished",
        "tests_passed": test_results[-1].get("success") if test_results else None,
    }


def _transient_timeout_case() -> dict[str, object]:
    """Measure middleware retry of one identical transient call."""
    attempts: list[str] = []
    events: list[dict[str, Any]] = []

    @tool
    def flaky_tool(value: str) -> str:
        """Timeout once, then succeed."""
        attempts.append(value)
        if len(attempts) == 1:
            raise TimeoutError("temporary timeout")
        return f"ok:{value}"

    responses = [
        AIMessage(content="", tool_calls=[{"name": "flaky_tool", "args": {"value": "x"}, "id": "call-1"}]),
        AIMessage(content="finished"),
    ]
    with TemporaryDirectory() as directory:
        result, diff = _run_agent(Path(directory), [flaky_tool], responses, events)
    return _case_result("transient-timeout", "middleware_retry", result, events, diff)


def _wrong_argument_case() -> dict[str, object]:
    """Measure model correction after a terminal parameter error."""
    events: list[dict[str, Any]] = []

    @tool
    def validate_value(value: str) -> str:
        """Accept only the corrected value."""
        if value != "correct":
            raise ValueError("value must be 'correct'")
        return "validated"

    responses = [
        AIMessage(content="", tool_calls=[{"name": "validate_value", "args": {"value": "wrong"}, "id": "bad"}]),
        AIMessage(content="", tool_calls=[{"name": "validate_value", "args": {"value": "correct"}, "id": "fixed"}]),
        AIMessage(content="finished"),
    ]
    with TemporaryDirectory() as directory:
        result, diff = _run_agent(Path(directory), [validate_value], responses, events)
    return _case_result("wrong-argument", "model_correction", result, events, diff)


def _test_failure_case() -> dict[str, object]:
    """Measure code-changing recovery after a failed test result."""
    events: list[dict[str, Any]] = []

    with TemporaryDirectory() as directory:
        workspace = Path(directory)

        @tool
        def run_injected_tests(fix: bool = False) -> str:
            """Fail until the model requests tests after applying a fix."""
            if not fix:
                return json.dumps({"success": False, "exit_code": 1, "output": "1 failed"})
            return json.dumps({"success": True, "exit_code": 0, "output": "1 passed"})

        @tool
        def apply_fix() -> str:
            """Apply the model's requested correction to the workspace."""
            (workspace / "fixed.txt").write_text("fixed\n", encoding="utf-8")
            return "fix applied"

        responses = [
            AIMessage(content="", tool_calls=[{"name": "run_injected_tests", "args": {"fix": False}, "id": "test-1"}]),
            AIMessage(content="", tool_calls=[{"name": "apply_fix", "args": {}, "id": "fix-1"}]),
            AIMessage(content="", tool_calls=[{"name": "run_injected_tests", "args": {"fix": True}, "id": "test-2"}]),
            AIMessage(content="finished"),
        ]
        result, diff = _run_agent(workspace, [run_injected_tests, apply_fix], responses, events)
    return _case_result("test-failure", "model_correction", result, events, diff)


def build_fault_report() -> dict[str, object]:
    """Run all deterministic fault-injection cases and summarize them."""
    cases = [_transient_timeout_case(), _wrong_argument_case(), _test_failure_case()]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "case_count": len(cases),
        "successful_cases": sum(case["final_success"] is True for case in cases),
        "model_correction_cases": sum(case["correction_type"] == "model_correction" for case in cases),
        "middleware_retry_cases": sum(case["correction_type"] == "middleware_retry" for case in cases),
        "cases": cases,
    }


def render_markdown(report: dict[str, object]) -> str:
    """Render a human-readable fault-injection report."""
    lines = [
        "# Fault Injection 评测汇总",
        "",
        f"- 案例数：{report['case_count']}",
        f"- 最终成功：{report['successful_cases']}",
        f"- Middleware 自动重试：{report['middleware_retry_cases']}",
        f"- 模型纠错：{report['model_correction_cases']}",
        "",
        "| 案例 | 类型 | 动作变化 | 测试通过 | diff | 最终成功 |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for case in report["cases"]:
        lines.append(
            f"| `{case['case_id']}` | `{case['correction_type']}` | "
            f"{case['action_changed']} | {case['tests_passed']} | "
            f"{len(case['diff'])} | {case['final_success']} |"
        )
    return "\n".join(lines) + "\n"


def write_fault_report(report: dict[str, object], output_dir: Path) -> tuple[Path, Path]:
    """Write JSON and Markdown fault-injection artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "fault-injection-summary.json"
    markdown_path = output_dir / "fault-injection-summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> None:
    """Run fault-injection cases from the command line."""
    parser = argparse.ArgumentParser(description="Run offline Recovery fault-injection cases.")
    parser.add_argument("--output-dir", type=Path, default=Path("evals/reports"))
    args = parser.parse_args()
    report = build_fault_report()
    json_path, markdown_path = write_fault_report(report, args.output_dir)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
