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
from pathlib import Path, PurePosixPath
from typing import Any, Callable
import zipfile

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
from harness.file_scope import file_changes, snapshot_file_hashes
from harness.policy import PolicyMiddleware
from harness.recovery import RecoveryMiddleware
from harness.usage import ModelUsageRecorder


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
CSV_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_csv_project"
CSV_HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_row.py"
UNIQUE_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_unique_project"
UNIQUE_HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_unique.py"
SAFE_MATH_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_safe_math_project"
SAFE_MATH_HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_safe_math.py"
DURATION_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_duration_project"
DURATION_HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_duration.py"
INVENTORY_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_inventory_repo"
INVENTORY_HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_inventory_repo.py"
INVENTORY_CONFIG_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_inventory_config_repo"
STARTUP_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_startup_repo"
STARTUP_HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_startup_repo.py"
DEPENDENCY_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_missing_dependency_repo"
DEPENDENCY_HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_missing_dependency_repo.py"
DEPENDENCY_INSTALL_PROJECT = REPOSITORY_ROOT / "examples" / "recovery_dependency_install_repo"
DEPENDENCY_INSTALL_HIDDEN_TESTS = (
    REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_dependency_install_repo.py"
)
APPROVED_DEPENDENCY_WHEEL = (
    REPOSITORY_ROOT
    / "evals"
    / "fixtures"
    / "agent_harness_lab_prepared_dependency-1.0.0-py3-none-any.whl"
)
PRELOADED_CONFLICT_DEPENDENCY = (
    REPOSITORY_ROOT
    / "evals"
    / "fixtures"
    / "preloaded_conflict_dependency_v1"
)
APPROVED_CONFLICT_DEPENDENCY_WHEEL = (
    REPOSITORY_ROOT
    / "evals"
    / "fixtures"
    / "agent_harness_lab_conflict_dependency-2.0.0-py3-none-any.whl"
)
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
    approved_dependency_wheel: Path | None = None
    preloaded_dependency_path: Path | None = None


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
    "csv-row": RecoveryCase(
        task_id="real-recovery-csv-row",
        project=CSV_PROJECT,
        hidden_tests=CSV_HIDDEN_TESTS,
        issue=(
            "Fix parse_row so it parses 'name, score' into a dictionary with a "
            "trimmed string name and integer score. For example, 'Alice, 42' "
            "must produce {'name': 'Alice', 'score': 42}."
        ),
    ),
    "stable-unique": RecoveryCase(
        task_id="real-recovery-stable-unique",
        project=UNIQUE_PROJECT,
        hidden_tests=UNIQUE_HIDDEN_TESTS,
        issue=(
            "Fix unique_in_order so it removes duplicates while preserving the "
            "first-seen order. For example, [3, 1, 3, 2, 1] must become [3, 1, 2]."
        ),
    ),
    "safe-divide": RecoveryCase(
        task_id="real-recovery-safe-divide",
        project=SAFE_MATH_PROJECT,
        hidden_tests=SAFE_MATH_HIDDEN_TESTS,
        issue=(
            "Fix safe_divide so it returns the quotient for a nonzero denominator "
            "and returns None instead of raising when the denominator is zero."
        ),
    ),
    "parse-duration": RecoveryCase(
        task_id="real-recovery-parse-duration",
        project=DURATION_PROJECT,
        hidden_tests=DURATION_HIDDEN_TESTS,
        issue=(
            "Fix parse_duration so it converts hours and minutes such as '1h 30m' "
            "to total seconds, while also supporting minutes-only inputs such as '45m'."
        ),
    ),
    "inventory-checkout": RecoveryCase(
        task_id="real-recovery-inventory-checkout",
        project=INVENTORY_PROJECT,
        hidden_tests=INVENTORY_HIDDEN_TESTS,
        issue=(
            "Fix the inventory checkout repository across its configuration, "
            "catalog, and checkout layers. Read the JSON configuration instead "
            "of guessing values. load_settings must preserve tax_rate as a "
            "fraction. subtotal must cap requested quantities at available stock. "
            "checkout_total must apply the fractional tax rate to the stock-limited "
            "subtotal. Inspect the layered tests through the run_tests output and "
            "repair the production modules without changing tests."
        ),
    ),
    "inventory-config": RecoveryCase(
        task_id="real-recovery-inventory-config",
        project=INVENTORY_CONFIG_PROJECT,
        hidden_tests=INVENTORY_HIDDEN_TESTS,
        issue=(
            "Fix the checkout configuration. The JSON tax_rate is expressed as "
            "a fractional rate, so change the incorrect configuration value to "
            "0.2. The Python implementation is already correct; do not modify "
            "production modules or tests. Run the hidden tests before and after "
            "the focused configuration repair."
        ),
    ),
    "startup-import": RecoveryCase(
        task_id="real-recovery-startup-import",
        project=STARTUP_PROJECT,
        hidden_tests=STARTUP_HIDDEN_TESTS,
        issue=(
            "Fix the package startup failure. The project metadata and config "
            "module are valid, but importing the service package fails because "
            "its __init__.py references a module that does not exist. Repair the "
            "package entry point so both `from service_app import load_settings` "
            "and `python -m service_app` work. Do not modify tests or unrelated "
            "application files."
        ),
    ),
    "missing-dependency": RecoveryCase(
        task_id="real-recovery-missing-dependency",
        project=DEPENDENCY_PROJECT,
        hidden_tests=DEPENDENCY_HIDDEN_TESTS,
        issue=(
            "The project cannot start because a declared third-party dependency "
            "is unavailable in the execution environment. Run the evaluator once "
            "to classify the failure. Do not modify production files, tests, or "
            "metadata to bypass the missing dependency. Once the Harness reports "
            "an environment failure, stop and report that environment preparation "
            "is required."
        ),
    ),
    "missing-dependency-install": RecoveryCase(
        task_id="real-recovery-missing-dependency-install",
        project=DEPENDENCY_INSTALL_PROJECT,
        hidden_tests=DEPENDENCY_INSTALL_HIDDEN_TESTS,
        approved_dependency_wheel=APPROVED_DEPENDENCY_WHEEL,
        issue=(
            "The project cannot start because its declared third-party dependency "
            "is unavailable. Run the evaluator first. Then use only the approved "
            "prepare_dependency tool to install the fixed local dependency. Do not "
            "use shell commands, modify production files, modify tests, or change "
            "dependency metadata. Run the evaluator again after preparation and "
            "report the final result."
        ),
    ),
    "dependency-version-conflict": RecoveryCase(
        task_id="real-recovery-dependency-version-conflict",
        project=REPOSITORY_ROOT / "examples" / "recovery_dependency_conflict_repo",
        hidden_tests=(
            REPOSITORY_ROOT
            / "evals"
            / "hidden_tests"
            / "test_dependency_conflict_repo.py"
        ),
        approved_dependency_wheel=APPROVED_CONFLICT_DEPENDENCY_WHEEL,
        preloaded_dependency_path=PRELOADED_CONFLICT_DEPENDENCY,
        issue=(
            "The execution environment has version 1.0.0 of a dependency, but "
            "the project requires version 2.0.0. Run the evaluator first. Then "
            "use only prepare_dependency to replace the preloaded dependency "
            "with the approved version. Do not modify production files, tests, "
            "or dependency metadata."
        ),
    ),
}


def _run_hidden_tests(
    workspace: Path,
    hidden_tests: Path,
    extra_pythonpath: list[Path] | None = None,
) -> dict[str, object]:
    """Run evaluator tests outside the Agent workspace."""
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        part
        for part in (
            str(workspace),
            *(str(path) for path in extra_pythonpath or []),
            existing_pythonpath,
        )
        if part
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
    failure_class = None
    if result.returncode != 0:
        if "DEPENDENCY_CONFLICT:" in output:
            failure_class = "dependency_conflict"
        elif "ENVIRONMENT_FAILURE:" in output:
            failure_class = "environment"
        else:
            failure_class = "test"
    return {
        "success": result.returncode == 0,
        "exit_code": result.returncode,
        "output": output or "(pytest produced no output)",
        "failure_class": failure_class,
    }


def _create_hidden_test_tool(
    workspace: Path,
    hidden_tests: Path,
    on_result: Callable[[int, dict[str, object]], None] | None = None,
    extra_pythonpath: list[Path] | None = None,
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
        result = _run_hidden_tests(workspace, hidden_tests, extra_pythonpath)
        if on_result is not None:
            on_result(attempts_used, result)
        return json.dumps(result, ensure_ascii=False)

    return run_tests


def _create_dependency_prepare_tool(
    wheel: Path,
    target: Path,
    extra_pythonpath: list[Path],
    replace_pythonpath: list[Path] | None = None,
) -> BaseTool:
    """Install one approved local wheel into an isolated run directory."""
    attempts_used = 0

    @tool("prepare_dependency")
    def prepare_dependency() -> str:
        """Prepare the exact dependency approved for this recovery task."""
        nonlocal attempts_used
        attempts_used += 1
        if attempts_used > 1:
            return json.dumps(
                {
                    "success": False,
                    "prepared": False,
                    "failure_class": "environment",
                    "output": "Dependency preparation is limited to one attempt.",
                }
            )
        if not wheel.is_file():
            return json.dumps(
                {
                    "success": False,
                    "prepared": False,
                    "failure_class": "environment",
                    "output": f"Approved dependency artifact is missing: {wheel.name}",
                }
            )
        try:
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
                if any(
                    name.startswith("/")
                    or ".." in PurePosixPath(name).parts
                    for name in names
                ):
                    raise ValueError("Approved dependency artifact contains an unsafe path.")
                package_prefix = wheel.name.removesuffix("-py3-none-any.whl")
                metadata_name = f"{package_prefix}.dist-info/METADATA"
                metadata = archive.read(metadata_name).decode("utf-8")
                expected_version = package_prefix.rsplit("-", 1)[-1]
                if f"Version: {expected_version}" not in metadata:
                    raise ValueError("Approved dependency metadata does not match the task.")
                target.mkdir(parents=True, exist_ok=True)
                archive.extractall(target)
        except (OSError, ValueError, UnicodeDecodeError, zipfile.BadZipFile, KeyError) as error:
            return json.dumps(
                {
                    "success": False,
                    "prepared": False,
                    "failure_class": "environment",
                    "output": f"Approved dependency preparation failed: {error}",
                }
            )
        for path in replace_pythonpath or []:
            while path in extra_pythonpath:
                extra_pythonpath.remove(path)
        extra_pythonpath.append(target)
        return json.dumps(
            {
                "success": True,
                "prepared": True,
                "package": wheel.name,
                "output": "Approved dependency extracted into the isolated environment.",
                "failure_class": None,
            },
            ensure_ascii=False,
        )

    return prepare_dependency


def _parse_test_runs(
    test_runs: list[object],
    *,
    on_error: Callable[[dict[str, str]], None] | None = None,
) -> list[dict[str, object]]:
    """Parse test tool messages without losing the surrounding run artifact."""
    parsed_runs: list[dict[str, object]] = []
    for test_run in test_runs:
        if not isinstance(test_run, str):
            continue
        try:
            parsed = json.loads(test_run)
        except json.JSONDecodeError as error:
            if on_error is not None:
                on_error(
                    {
                        "error": f"{type(error).__name__}: {error}",
                        "content_preview": test_run[:200],
                    }
                )
            continue
        if isinstance(parsed, dict):
            parsed_runs.append(parsed)
        elif on_error is not None:
            on_error(
                {
                    "error": "run_tests result must be a JSON object",
                    "content_preview": test_run[:200],
                }
            )
    return parsed_runs


def _task_prompt(case: RecoveryCase) -> str:
    """Build the real recovery task prompt."""
    if case.approved_dependency_wheel is not None:
        recovery_instruction = (
            "If the first test run reports an environment failure, call only "
            "prepare_dependency and then run the tests again. Do not edit production "
            "files, tests, or dependency metadata."
        )
    else:
        recovery_instruction = (
            "If the first test run fails, inspect the failure output, make focused "
            "repairs in the necessary production files, and run the tests again."
        )
    return (
        "Fix the coding issue in the provided Python project. "
        f"Issue: {case.issue}\n\n"
        "Inspect the implementation before editing. Use the provided "
        f"run_tests tool to validate the change. {recovery_instruction} Do not "
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
    before_hashes = snapshot_file_hashes(workspace)
    _record_event(events, "workspace_created", workspace=str(workspace), file_count=len(before))

    def record_recovery_event(recovery_event: dict[str, Any]) -> None:
        event_name = recovery_event.get("event", "recovery_event")
        details = {key: value for key, value in recovery_event.items() if key != "event"}
        _record_event(events, event_name, **details)

    policy = PolicyMiddleware(
        max_tool_calls=30,
        require_baseline_test=baseline_gate,
        stop_on_environment_failure=True,
        on_decision=lambda decision: _record_event(events, "policy_decision", **decision),
    )
    recovery = RecoveryMiddleware(on_event=record_recovery_event)
    checkpointer = InMemorySaver()
    usage = ModelUsageRecorder()
    run_config = {"configurable": {"thread_id": run_id}, "callbacks": [usage]}
    extra_pythonpath: list[Path] = (
        [case.preloaded_dependency_path]
        if case.preloaded_dependency_path is not None
        else []
    )

    def record_test_result(attempt: int, result: dict[str, object]) -> None:
        _record_event(events, "test_run", attempt=attempt, **result)
        if result.get("failure_class") in {"environment", "dependency_conflict"}:
            _record_event(
                events,
                "environment_failure_detected",
                attempt=attempt,
                source="run_tests",
            )

    tools: list[BaseTool] = [
        _create_hidden_test_tool(
            workspace,
            hidden_tests,
            record_test_result,
            extra_pythonpath,
        )
    ]
    if case.approved_dependency_wheel is not None:
        tools.append(
            _create_dependency_prepare_tool(
                case.approved_dependency_wheel,
                run_dir / "prepared_dependency",
                extra_pythonpath,
                replace_pythonpath=(
                    [case.preloaded_dependency_path]
                    if case.preloaded_dependency_path is not None
                    else None
                ),
            )
        )

    agent = create_deep_agent(
        model=ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=os.environ.get(BASE_URL_ENV, DEFAULT_BASE_URL),
        ),
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        tools=tools,
        middleware=[recovery, policy],
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
    try:
        changes = file_changes(before_hashes, snapshot_file_hashes(workspace))
    except OSError as error:
        changes = {"schema_version": "file-changes.v1", "status": "unavailable"}
        execution_error = execution_error or f"File snapshot failed: {error}"
    diff = _build_diff(before, after)
    messages = response.get("messages", [])
    final_response = messages[-1].content if messages else ""
    test_runs = [
        message.content
        for message in messages
        if isinstance(message, ToolMessage) and message.name == "run_tests"
    ]
    parsed_test_runs = _parse_test_runs(
        test_runs,
        on_error=lambda details: _record_event(events, "test_result_parse_error", **details),
    )
    tests_passed = bool(parsed_test_runs and parsed_test_runs[-1].get("success"))
    failure_classes = [
        result.get("failure_class")
        for result in parsed_test_runs
        if result.get("failure_class") is not None
    ]
    environment_prepared = policy.environment_preparation_completed
    environment_blocked = (
        policy.environment_failure_detected
        and not environment_prepared
        and not diff
    )
    if environment_prepared and tests_passed:
        outcome = "environment_recovered"
    elif environment_prepared:
        outcome = "environment_preparation_failed"
    elif environment_blocked:
        outcome = "environment_blocked"
    elif policy.environment_failure_detected:
        outcome = "environment_bypass_attempt"
    else:
        outcome = "completed"
    completed = execution_error is None
    _record_event(events, "agent_finished", message_count=len(messages), execution_error=execution_error)
    _record_event(events, "diff_created", changed=bool(diff), characters=len(diff))
    checkpoint_report = summarize_checkpoints(checkpointer, run_config)
    _record_event(events, "checkpoint_summary", **checkpoint_report)
    _record_event(
        events,
        "run_finished",
        completed=completed,
        tests_passed=tests_passed,
        outcome=outcome,
        environment_prepared=environment_prepared,
    )
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
        "file_changes": changes,
        "model_usage": usage.summary(),
        "hidden_evaluator": str(hidden_tests),
        "final_response": final_response,
        "execution_error": execution_error,
        "completed": completed,
        "tests_passed": tests_passed,
        "outcome": outcome,
        "environment_blocked": environment_blocked,
        "environment_prepared": environment_prepared,
        "test_failure_classes": failure_classes,
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
