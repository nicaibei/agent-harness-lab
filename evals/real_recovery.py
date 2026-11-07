"""Run one real-model recovery experiment against hidden evaluator tests."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from agent_app.baseline import (
    COPY_IGNORE,
    REPOSITORY_ROOT,
    _build_diff,
    _record_event,
    _save_run_artifacts,
    _snapshot_files,
)
from harness.checkpoint import replay_events, summarize_checkpoints
from harness.policy import PolicyMiddleware
from harness.recovery import RecoveryMiddleware


RECOVERY_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_python_project"
HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_title_utils.py"
TAX_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_tax_project"
TAX_HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_tax.py"
PERCENT_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_percent_project"
PERCENT_HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_percent.py"
ORDER_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_order_project"
ORDER_HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_order_total.py"
TEMPERATURE_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_temperature_project"
TEMPERATURE_HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_temperature_report.py"
RECOVERY_RUNS_ROOT = REPOSITORY_ROOT / "runs" / "recovery"
API_KEY_ENV = "DEEPSEEK_API_KEY"
MODEL_ENV = "DEEPSEEK_MODEL"
BASE_URL_ENV = "DEEPSEEK_BASE_URL"
DEFAULT_BASE_URL = "https://api.deepseek.com"


@dataclass(frozen=True)
class RecoveryCase:
    """One hidden-evaluator task used by the real-model matrix."""

    task_id: str
    project: Path
    hidden_tests: Path
    issue: str


RECOVERY_CASES = {
    "normalize-title": RecoveryCase(
        task_id="real-recovery-normalize-title",
        project=RECOVERY_PROJECT,
        hidden_tests=HIDDEN_TESTS,
        issue=(
            "The title normalizer must trim outer whitespace, lowercase the text, "
            "collapse one or more internal whitespace characters into a single "
            "hyphen, and preserve the existing public function name."
        ),
    ),
    "fractional-tax": RecoveryCase(
        task_id="real-recovery-fractional-tax",
        project=TAX_PROJECT,
        hidden_tests=TAX_HIDDEN_TESTS,
        issue=(
            "Fix total_with_tax so tax_rate is treated as a fractional rate of "
            "amount. For example, total_with_tax(100, 0.2) must return 120, "
            "while a zero rate leaves the amount unchanged."
        ),
    ),
    "parse-percent": RecoveryCase(
        task_id="real-recovery-parse-percent",
        project=PERCENT_PROJECT,
        hidden_tests=PERCENT_HIDDEN_TESTS,
        issue=(
            "Fix parse_percent so a string with a percent suffix is converted to "
            "a fractional value, while a decimal fraction stays unchanged. "
            "For example, parse_percent('20%') must return 0.2 and "
            "parse_percent('0.5') must return 0.5."
        ),
    ),
    "order-total": RecoveryCase(
        task_id="real-recovery-order-total",
        project=ORDER_PROJECT,
        hidden_tests=ORDER_HIDDEN_TESTS,
        issue=(
            "Fix this order calculation across both production files. "
            "parse_order must parse inputs in the form 'quantity x unit_price' "
            "into numeric quantity and unit_price fields. total_with_tax must "
            "multiply quantity by unit_price and apply tax_rate as a fractional "
            "rate. For example, parse_order('3 x 10.00') should produce "
            "{'quantity': 3, 'unit_price': 10.0}, and total_with_tax on that "
            "order with 0.2 should return 36.0."
        ),
    ),
    "temperature-report": RecoveryCase(
        task_id="real-recovery-temperature-report",
        project=TEMPERATURE_PROJECT,
        hidden_tests=TEMPERATURE_HIDDEN_TESTS,
        issue=(
            "Fix this temperature conversion across both production files. "
            "parse_reading must preserve the numeric value and normalize the unit "
            "to uppercase. to_celsius must convert Fahrenheit with (F - 32) * 5 / 9 "
            "and leave Celsius unchanged. For example, parse_reading('32 F') must "
            "return {'value': 32.0, 'unit': 'F'}, 86 F must convert to 30 C, and "
            "20 C must remain 20 C."
        ),
    ),
}


def _run_hidden_tests(workspace: Path, hidden_tests: Path) -> dict[str, object]:
    """Run evaluator tests outside the Agent workspace."""
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(workspace), existing_pythonpath) if part
    )
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(hidden_tests)],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "exit_code": 124, "output": "Hidden tests timed out after 120 seconds."}
    except OSError as error:
        return {"success": False, "exit_code": 127, "output": f"Could not start pytest: {error}"}
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    return {
        "success": result.returncode == 0,
        "exit_code": result.returncode,
        "output": output or "(pytest produced no output)",
    }


def _create_hidden_test_tool(
    workspace: Path,
    hidden_tests: Path,
    on_result: Callable[[int, dict[str, object]], None] | None = None,
) -> BaseTool:
    """Create a bounded tool whose evaluator stays outside the workspace."""
    remaining_runs = 2
    attempts_used = 0

    @tool("run_tests")
    def run_tests() -> str:
        """Run the hidden evaluator against the current workspace code."""
        nonlocal attempts_used, remaining_runs
        attempts_used += 1
        if remaining_runs == 0:
            result = {
                "success": False,
                "exit_code": 125,
                "output": "Hidden test budget exhausted: at most two runs are allowed.",
            }
            if on_result is not None:
                on_result(attempts_used, result)
            return json.dumps(result)
        remaining_runs -= 1
        result = _run_hidden_tests(workspace, hidden_tests)
        if on_result is not None:
            on_result(attempts_used, result)
        return json.dumps(result, ensure_ascii=False)

    return run_tests


def _task_prompt(case: RecoveryCase) -> str:
    """Build the real recovery task prompt."""
    return (
        "Fix the coding issue in the provided Python project. "
        f"Issue: {case.issue}\n\n"
        "Inspect the implementation before editing. Use the provided "
        "run_tests tool to validate the change. If the first test run fails, inspect "
        "the failure output, make focused repairs in the necessary production files, "
        "and run the tests again. Do not "
        "modify tests or claim success unless the test tool confirms it."
    )


def run_recovery_task(
    case_name: str = "normalize-title",
    *,
    baseline_gate: bool = True,
) -> Path:
    """Run the hidden-test recovery experiment and save its artifacts."""
    load_dotenv(REPOSITORY_ROOT / ".env")
    api_key = os.environ.get(API_KEY_ENV)
    model_name = os.environ.get(MODEL_ENV)
    if not api_key:
        raise RuntimeError(f"Set the {API_KEY_ENV} environment variable before running the recovery task.")
    if not model_name:
        raise RuntimeError(f"Set the {MODEL_ENV} environment variable before running the recovery task.")
    case = RECOVERY_CASES.get(case_name)
    if case is None:
        raise ValueError(f"Unknown recovery case: {case_name}")
    source = case.project.resolve(strict=True)
    hidden_tests = case.hidden_tests.resolve(strict=True)
    started_at = datetime.now(UTC).isoformat()
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    run_dir = RECOVERY_RUNS_ROOT / run_id
    workspace = run_dir / "workspace"
    workspace.parent.mkdir(parents=True, exist_ok=False)
    events: list[dict[str, Any]] = []
    _record_event(events, "run_started", run_id=run_id, task_id=case.task_id)
    shutil.copytree(source, workspace, ignore=COPY_IGNORE)
    before = _snapshot_files(workspace)
    _record_event(events, "workspace_created", workspace=str(workspace), file_count=len(before))

    def record_recovery_event(recovery_event: dict[str, Any]) -> None:
        event_name = recovery_event.get("event", "recovery_event")
        details = {key: value for key, value in recovery_event.items() if key != "event"}
        _record_event(events, event_name, **details)

    policy = PolicyMiddleware(
        max_tool_calls=30,
        require_baseline_test=baseline_gate,
        on_decision=lambda decision: _record_event(events, "policy_decision", **decision),
    )
    recovery = RecoveryMiddleware(on_event=record_recovery_event)
    checkpointer = InMemorySaver()
    run_config = {"configurable": {"thread_id": run_id}}
    def record_test_result(attempt: int, result: dict[str, object]) -> None:
        _record_event(events, "test_run", attempt=attempt, **result)

    agent = create_deep_agent(
        model=ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=os.environ.get(BASE_URL_ENV, DEFAULT_BASE_URL),
        ),
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        tools=[_create_hidden_test_tool(workspace, hidden_tests, record_test_result)],
        middleware=[policy, recovery],
        checkpointer=checkpointer,
        system_prompt=(
            "You are a careful coding agent working in a disposable project. "
            "Only edit implementation files in the workspace. The evaluator tests "
            "are external and cannot be edited."
        ),
    )
    base_url = os.environ.get(BASE_URL_ENV, DEFAULT_BASE_URL)
    _record_event(events, "agent_started", model=model_name, base_url=base_url)
    execution_error = None
    try:
        response = agent.invoke({"messages": [HumanMessage(content=_task_prompt(case))]}, config=run_config)
    except Exception as error:  # noqa: BLE001 - retain the real experiment trace
        response = {}
        execution_error = f"{type(error).__name__}: {error}"
        _record_event(events, "agent_error", error=execution_error)

    after = _snapshot_files(workspace) if workspace.is_dir() else before
    diff = _build_diff(before, after)
    messages = response.get("messages", [])
    final_response = messages[-1].content if messages else ""
    test_runs = [
        message.content
        for message in messages
        if isinstance(message, ToolMessage) and message.name == "run_tests"
    ]
    parsed_test_runs: list[dict[str, object]] = []
    for test_run in test_runs:
        if not isinstance(test_run, str):
            continue
        parsed = json.loads(test_run)
        parsed_test_runs.append(parsed)
    tests_passed = bool(parsed_test_runs and parsed_test_runs[-1].get("success"))
    completed = execution_error is None
    _record_event(events, "agent_finished", message_count=len(messages), execution_error=execution_error)
    _record_event(events, "diff_created", changed=bool(diff), characters=len(diff))
    checkpoint_report = summarize_checkpoints(checkpointer, run_config)
    _record_event(events, "checkpoint_summary", **checkpoint_report)
    _record_event(events, "run_finished", completed=completed, tests_passed=tests_passed)
    report = {
        "run_id": run_id,
        "task_id": case.task_id,
        "scenario": "real-model-hidden-evaluator",
        "baseline_gate": baseline_gate,
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "model": model_name,
        "base_url": base_url,
        "source_project": str(source),
        "workspace": str(workspace),
        "hidden_evaluator": str(hidden_tests),
        "final_response": final_response,
        "execution_error": execution_error,
        "completed": completed,
        "tests_passed": tests_passed,
        "test_runs": test_runs,
        "diff": diff,
        "events": events,
        "checkpoint": checkpoint_report,
    }
    replay_report = replay_events(events)
    report["replay"] = replay_report
    _save_run_artifacts(run_dir, report, diff, checkpoint=checkpoint_report, replay=replay_report)
    return run_dir


def main() -> None:
    """Run the real recovery experiment from the command line."""
    parser = argparse.ArgumentParser(description="Run the hidden-test DeepSeek recovery experiment.")
    parser.add_argument("--case", choices=sorted(RECOVERY_CASES), default="normalize-title")
    parser.add_argument(
        "--no-baseline-gate",
        action="store_true",
        help="Allow file mutations before the first hidden test for the ablation experiment.",
    )
    args = parser.parse_args()
    try:
        run_dir = run_recovery_task(args.case, baseline_gate=not args.no_baseline_gate)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(f"Run artifacts: {run_dir}")
    print(f"Diff: {run_dir / 'diff.patch'}")
    print(f"Trace: {run_dir / 'run.json'}")


if __name__ == "__main__":
    main()
