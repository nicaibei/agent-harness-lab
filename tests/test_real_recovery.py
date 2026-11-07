"""Offline checks for the hidden evaluator used by the real recovery run."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

import pytest
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from evals.real_recovery import (
    HIDDEN_TESTS,
    ORDER_HIDDEN_TESTS,
    ORDER_PROJECT,
    TEMPERATURE_HIDDEN_TESTS,
    TEMPERATURE_PROJECT,
    RECOVERY_CASES,
    RECOVERY_PROJECT,
    _run_hidden_tests,
)
from evals.real_recovery import _create_hidden_test_tool
from harness.policy import PolicyMiddleware
from harness.recovery import RecoveryMiddleware


class BoundFakeChatModel(FakeMessagesListChatModel):
    """Offline model that accepts the tool binding used by create_deep_agent."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> BoundFakeChatModel:
        return self


def test_hidden_evaluator_fails_before_and_passes_after_real_code_fix(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = RECOVERY_PROJECT / "title_utils.py"
    (workspace / "title_utils.py").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    before = _run_hidden_tests(workspace, HIDDEN_TESTS)
    assert before["success"] is False

    (workspace / "title_utils.py").write_text(
        "import re\n\n\ndef normalize_title(value: str) -> str:\n"
        "    return re.sub(r\"\\s+\", \"-\", value.strip().lower())\n",
        encoding="utf-8",
    )
    after = _run_hidden_tests(workspace, HIDDEN_TESTS)

    assert after["success"] is True


@pytest.mark.parametrize(
    ("case_name", "filename", "fixed_code"),
    [
        (
            "fractional-tax",
            "tax.py",
            "\n\ndef total_with_tax(amount: float, tax_rate: float) -> float:\n"
            "    return amount + amount * tax_rate\n",
        ),
        (
            "parse-percent",
            "percent.py",
            "\n\ndef parse_percent(value: str) -> float:\n"
            "    text = value.strip()\n"
            "    return float(text[:-1]) / 100 if text.endswith(\"%\") else float(text)\n",
        ),
    ],
)
def test_additional_hidden_evaluators_fail_then_pass(
    tmp_path: Path,
    case_name: str,
    filename: str,
    fixed_code: str,
) -> None:
    case = RECOVERY_CASES[case_name]
    workspace = tmp_path / case_name
    workspace.mkdir()
    source = case.project / filename
    (workspace / filename).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert _run_hidden_tests(workspace, case.hidden_tests)["success"] is False
    (workspace / filename).write_text(fixed_code, encoding="utf-8")
    assert _run_hidden_tests(workspace, case.hidden_tests)["success"] is True


def test_cross_file_hidden_evaluator_requires_both_production_files(tmp_path: Path) -> None:
    workspace = tmp_path / "order-total"
    workspace.mkdir()
    for filename in ("order_parser.py", "order_total.py"):
        source = ORDER_PROJECT / filename
        (workspace / filename).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    before = _run_hidden_tests(workspace, ORDER_HIDDEN_TESTS)
    assert before["success"] is False

    (workspace / "order_parser.py").write_text(
        '"""Order parser."""\n\n\ndef parse_order(value: str) -> dict[str, float]:\n'
        '    quantity_text, price_text = [part.strip() for part in value.split("x")]\n'
        '    return {"quantity": int(quantity_text), "unit_price": float(price_text)}\n',
        encoding="utf-8",
    )
    (workspace / "order_total.py").write_text(
        '"""Order total calculator."""\n\n\ndef total_with_tax(order: dict[str, float], tax_rate: float) -> float:\n'
        '    subtotal = order["quantity"] * order["unit_price"]\n'
        '    return subtotal * (1 + tax_rate)\n',
        encoding="utf-8",
    )

    after = _run_hidden_tests(workspace, ORDER_HIDDEN_TESTS)
    assert after["success"] is True


def test_temperature_hidden_evaluator_requires_both_production_files(tmp_path: Path) -> None:
    workspace = tmp_path / "temperature-report"
    workspace.mkdir()
    for filename in ("temperature_parser.py", "temperature_report.py"):
        source = TEMPERATURE_PROJECT / filename
        (workspace / filename).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    before = _run_hidden_tests(workspace, TEMPERATURE_HIDDEN_TESTS)
    assert before["success"] is False

    (workspace / "temperature_parser.py").write_text(
        '"""Temperature parser."""\n\n\ndef parse_reading(value: str) -> dict[str, float | str]:\n'
        '    number_text, unit = value.split()\n'
        '    return {"value": float(number_text), "unit": unit.upper()}\n',
        encoding="utf-8",
    )
    (workspace / "temperature_report.py").write_text(
        '"""Temperature conversion."""\n\n\ndef to_celsius(reading: dict[str, float | str],) -> float:\n'
        '    value = float(reading["value"])\n'
        '    return (value - 32) * 5 / 9 if reading["unit"] == "F" else value\n',
        encoding="utf-8",
    )

    after = _run_hidden_tests(workspace, TEMPERATURE_HIDDEN_TESTS)
    assert after["success"] is True


def test_recovery_task_defaults_to_baseline_gate() -> None:
    from inspect import signature

    from evals.real_recovery import run_recovery_task

    assert signature(run_recovery_task).parameters["baseline_gate"].default is True


def test_baseline_gate_forces_hidden_failure_before_real_fix(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = RECOVERY_PROJECT / "title_utils.py"
    (workspace / "title_utils.py").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    events: list[dict[str, Any]] = []
    fixed_code = (
        "import re\n\n\ndef normalize_title(value: str) -> str:\n"
        "    return re.sub(r\"\\s+\", \"-\", value.strip().lower())\n"
    )
    agent = create_deep_agent(
        model=BoundFakeChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "write_file",
                            "args": {"file_path": "/title_utils.py", "content": fixed_code},
                            "id": "premature-edit",
                        }
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "run_tests", "args": {}, "id": "baseline-test"}],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "write_file",
                            "args": {"file_path": "/title_utils.py", "content": fixed_code},
                            "id": "approved-edit",
                        }
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "run_tests", "args": {}, "id": "final-test"}],
                ),
                AIMessage(content="finished"),
            ]
        ),
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        tools=[_create_hidden_test_tool(workspace, HIDDEN_TESTS)],
        middleware=[
            PolicyMiddleware(require_baseline_test=True, on_decision=events.append),
            RecoveryMiddleware(on_event=events.append),
        ],
        checkpointer=InMemorySaver(),
    )

    result = agent.invoke(
        {"messages": [("user", "repair the title normalizer")]},
        config={"configurable": {"thread_id": "offline-recovery"}},
    )
    tool_results = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    test_results = [
        json.loads(message.content)
        for message in tool_results
        if message.name == "run_tests"
    ]

    assert tool_results[0].status == "error"
    assert "baseline test" in str(tool_results[0].content)
    assert [item["success"] for item in test_results] == [False, True]
    assert (workspace / "title_utils.py").read_text(encoding="utf-8") == fixed_code
    assert any(event.get("decision") == "deny" for event in events)
