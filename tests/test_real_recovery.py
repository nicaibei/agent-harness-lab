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
    CSV_HIDDEN_TESTS,
    CSV_PROJECT,
    DURATION_HIDDEN_TESTS,
    DURATION_PROJECT,
    HIDDEN_TESTS,
    INVENTORY_CONFIG_PROJECT,
    INVENTORY_HIDDEN_TESTS,
    ORDER_HIDDEN_TESTS,
    ORDER_PROJECT,
    TEMPERATURE_HIDDEN_TESTS,
    TEMPERATURE_PROJECT,
    SAFE_MATH_HIDDEN_TESTS,
    SAFE_MATH_PROJECT,
    UNIQUE_HIDDEN_TESTS,
    UNIQUE_PROJECT,
    RECOVERY_CASES,
    RECOVERY_PROJECT,
    _parse_test_runs,
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


@pytest.mark.parametrize(
    ("case_name", "project", "hidden_tests", "filename", "fixed_code"),
    [
        (
            "csv-row",
            CSV_PROJECT,
            CSV_HIDDEN_TESTS,
            "row.py",
            '"""CSV row parser."""\n\n\ndef parse_row(value: str) -> dict[str, int | str]:\n'
            '    name, score_text = [part.strip() for part in value.split(",")]\n'
            '    return {"name": name, "score": int(score_text)}\n',
        ),
        (
            "stable-unique",
            UNIQUE_PROJECT,
            UNIQUE_HIDDEN_TESTS,
            "unique.py",
            '"""Stable deduplication."""\n\n\ndef unique_in_order(values: list[int]) -> list[int]:\n'
            '    seen: set[int] = set()\n'
            '    result: list[int] = []\n'
            '    for value in values:\n'
            '        if value not in seen:\n'
            '            seen.add(value)\n'
            '            result.append(value)\n'
            '    return result\n',
        ),
        (
            "safe-divide",
            SAFE_MATH_PROJECT,
            SAFE_MATH_HIDDEN_TESTS,
            "safe_math.py",
            '"""Safe division."""\n\n\ndef safe_divide(left: float, right: float) -> float | None:\n'
            '    return None if right == 0 else left / right\n',
        ),
        (
            "parse-duration",
            DURATION_PROJECT,
            DURATION_HIDDEN_TESTS,
            "duration.py",
            '"""Duration parser."""\n\n\ndef parse_duration(value: str) -> int:\n'
            '    total = 0\n'
            '    for token in value.split():\n'
            '        amount = int(token[:-1])\n'
            '        total += amount * (3600 if token.endswith("h") else 60)\n'
            '    return total\n',
        ),
    ],
)
def test_expanded_hidden_evaluators_fail_then_pass(
    tmp_path: Path,
    case_name: str,
    project: Path,
    hidden_tests: Path,
    filename: str,
    fixed_code: str,
) -> None:
    workspace = tmp_path / case_name
    workspace.mkdir()
    source = project / filename
    (workspace / filename).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert _run_hidden_tests(workspace, hidden_tests)["success"] is False
    (workspace / filename).write_text(fixed_code, encoding="utf-8")
    assert _run_hidden_tests(workspace, hidden_tests)["success"] is True


def test_inventory_config_evaluator_requires_only_config_repair(tmp_path: Path) -> None:
    workspace = tmp_path / "inventory-config"
    for source in INVENTORY_CONFIG_PROJECT.rglob("*"):
        if source.is_file():
            target = workspace / source.relative_to(INVENTORY_CONFIG_PROJECT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())

    before = _run_hidden_tests(workspace, INVENTORY_HIDDEN_TESTS)
    assert before["success"] is False
    assert "2 failed, 1 passed" in before["output"]
    original_settings = (
        INVENTORY_CONFIG_PROJECT / "inventory_app" / "settings.py"
    ).read_text(encoding="utf-8")
    assert (workspace / "inventory_app" / "settings.py").read_text(encoding="utf-8") == original_settings

    config_path = workspace / "config" / "checkout.json"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace('"tax_rate": 20', '"tax_rate": 0.2'),
        encoding="utf-8",
    )
    after = _run_hidden_tests(workspace, INVENTORY_HIDDEN_TESTS)
    assert after["success"] is True


def test_recovery_task_defaults_to_baseline_gate() -> None:
    from inspect import signature

    from evals.real_recovery import run_recovery_task

    assert signature(run_recovery_task).parameters["baseline_gate"].default is True


def test_parse_test_runs_records_malformed_tool_messages() -> None:
    errors: list[dict[str, str]] = []

    parsed = _parse_test_runs(
        ["not-json", '{"success": false}', '{"success": true}'],
        on_error=errors.append,
    )

    assert parsed == [{"success": False}, {"success": True}]
    assert errors[0]["content_preview"] == "not-json"


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
