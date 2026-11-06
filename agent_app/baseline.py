"""Minimal model-backed code task agent with isolated run workspaces."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver

from harness.checkpoint import replay_events, summarize_checkpoints
from harness.policy import PolicyMiddleware
from harness.recovery import RecoveryMiddleware


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT = REPOSITORY_ROOT / "examples" / "tiny_python_project"
API_KEY_ENV = "DEEPSEEK_API_KEY"
RUNS_ROOT = REPOSITORY_ROOT / "runs"
MODEL_ENV = "DEEPSEEK_MODEL"
BASE_URL_ENV = "DEEPSEEK_BASE_URL"
DEFAULT_BASE_URL = "https://api.deepseek.com"
COPY_IGNORE = shutil.ignore_patterns(
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)


def _snapshot_files(root: Path) -> dict[str, str]:
    """Read UTF-8 text files for a before/after unified diff."""
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        if set(relative_path.parts) & {
            ".git",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "__pycache__",
        }:
            continue
        try:
            snapshot[relative_path.as_posix()] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return snapshot


def _build_diff(before: dict[str, str], after: dict[str, str]) -> str:
    """Build a unified diff for changed, created, and deleted text files."""
    chunks: list[str] = []
    for name in sorted(before.keys() | after.keys()):
        old = before.get(name, "")
        new = after.get(name, "")
        if old == new:
            continue
        chunks.extend(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{name}" if name in before else "/dev/null",
                tofile=f"b/{name}" if name in after else "/dev/null",
            )
        )
    return "".join(chunks)


def _save_run_artifacts(
    run_dir: Path,
    report: dict[str, Any],
    diff: str,
    *,
    checkpoint: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
) -> None:
    """Persist run artifacts even if the workspace removed its parent directory."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "diff.patch").write_text(diff, encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if checkpoint is not None:
        (run_dir / "checkpoint.json").write_text(
            json.dumps(checkpoint, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if replay is not None:
        (run_dir / "replay.json").write_text(
            json.dumps(replay, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _record_event(events: list[dict[str, Any]], event: str, **details: Any) -> None:
    """Append a timestamped, JSON-serializable run event."""
    events.append(
        {
            "event": event,
            "timestamp": datetime.now(UTC).isoformat(),
            **details,
        }
    )


def _create_test_tool(workspace: Path) -> BaseTool:
    """Create a tool that runs only the workspace's pytest suite."""
    remaining_runs = 2

    @tool
    def run_tests() -> str:
        """Run the Python test suite in the assigned project workspace."""
        nonlocal remaining_runs
        if remaining_runs == 0:
            return json.dumps(
                {
                    "success": False,
                    "exit_code": 125,
                    "output": "Test run budget exhausted: this task allows at most two test runs.",
                }
            )
        remaining_runs -= 1
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return json.dumps(
                {"success": False, "exit_code": 124, "output": "Tests timed out after 120 seconds."}
            )
        except OSError as error:
            return json.dumps(
                {"success": False, "exit_code": 127, "output": f"Could not start pytest: {error}"}
            )

        output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        return json.dumps(
            {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "output": output or "(pytest produced no output)",
            },
            ensure_ascii=False,
        )

    return run_tests


def _task_prompt(issue: str) -> str:
    """Build a bounded task prompt for the baseline agent."""
    return (
        "Resolve the following coding issue in the provided repository.\n\n"
        f"Issue:\n{issue}\n\n"
        "Inspect the existing code and tests before editing. Make the smallest "
        "appropriate change. Run the provided run_tests tool after editing. "
        "If tests fail, inspect the output and make one focused repair attempt, "
        "then run the tests once more. Finish with a concise summary of changes "
        "and test results. Do not claim tests passed unless the tool confirms it."
    )


def run_task(issue: str, project: Path, *, task_id: str | None = None) -> Path:
    """Run one issue in a fresh copy and save its diff, trace, and result."""
    load_dotenv(REPOSITORY_ROOT / ".env")
    source = project.resolve(strict=True)
    if not source.is_dir():
        raise ValueError(f"Project path is not a directory: {source}")
    if not any(source.rglob("test_*.py")) and not any(source.rglob("*_test.py")):
        raise ValueError(f"No pytest files found under project: {source}")
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(f"Set the {API_KEY_ENV} environment variable before running a model task.")
    model_name = os.environ.get(MODEL_ENV)
    if not model_name:
        raise RuntimeError(f"Set the {MODEL_ENV} environment variable to a model ID enabled in your DeepSeek account.")
    base_url = os.environ.get(BASE_URL_ENV, DEFAULT_BASE_URL)

    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    run_dir = RUNS_ROOT / run_id
    workspace = run_dir / "workspace"
    workspace.parent.mkdir(parents=True, exist_ok=False)
    events: list[dict[str, Any]] = []
    _record_event(events, "run_started", run_id=run_id, task_id=task_id)
    shutil.copytree(source, workspace, ignore=COPY_IGNORE)

    before = _snapshot_files(workspace)
    issue_time = datetime.now(UTC).isoformat()
    _record_event(
        events,
        "workspace_created",
        workspace=str(workspace),
        file_count=len(before),
    )
    test_tool = _create_test_tool(workspace)
    def record_recovery_event(recovery_event: dict[str, Any]) -> None:
        event_name = recovery_event.get("event", "recovery_event")
        details = {key: value for key, value in recovery_event.items() if key != "event"}
        _record_event(events, event_name, **details)

    policy = PolicyMiddleware(
        max_tool_calls=30,
        on_decision=lambda decision: _record_event(events, "policy_decision", **decision),
    )
    recovery = RecoveryMiddleware(on_event=record_recovery_event)
    checkpointer = InMemorySaver()
    run_config = {"configurable": {"thread_id": run_id}}
    agent = create_deep_agent(
        model=ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
        ),
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        tools=[test_tool],
        middleware=[policy, recovery],
        checkpointer=checkpointer,
        system_prompt=(
            "You are a careful coding agent working in a disposable copy of a "
            "small Python project. Use filesystem tools to inspect and edit files. "
            "Use run_tests to validate changes. You do not have a general shell tool."
        ),
    )
    _record_event(events, "agent_started", model=model_name, base_url=base_url)
    execution_error = None
    try:
        response = agent.invoke(
            {"messages": [HumanMessage(content=_task_prompt(issue))]},
            config=run_config,
        )
    except Exception as error:  # noqa: BLE001 - retain a trace for failed agent runs
        response = {}
        execution_error = f"{type(error).__name__}: {error}"
        _record_event(events, "agent_error", error=execution_error)

    if not workspace.is_dir():
        execution_error = execution_error or "The agent workspace disappeared before the run completed."
    after = _snapshot_files(workspace) if workspace.is_dir() else before
    diff = _build_diff(before, after)
    messages = response.get("messages", [])
    final_response = messages[-1].content if messages else ""
    test_runs = [
        message.content
        for message in messages
        if isinstance(message, ToolMessage) and message.name == "run_tests"
    ]
    parsed_test_runs = []
    for attempt, test_run in enumerate(test_runs, start=1):
        if not isinstance(test_run, str):
            continue
        parsed = json.loads(test_run)
        parsed_test_runs.append(parsed)
        _record_event(
            events,
            "test_run",
            attempt=attempt,
            success=parsed.get("success"),
            exit_code=parsed.get("exit_code"),
            output=parsed.get("output", ""),
        )
    tests_passed = bool(parsed_test_runs and parsed_test_runs[-1].get("success"))
    _record_event(
        events,
        "agent_finished",
        message_count=len(messages),
        execution_error=execution_error,
    )
    _record_event(events, "diff_created", changed=bool(diff), characters=len(diff))
    completed = execution_error is None
    checkpoint_report = summarize_checkpoints(checkpointer, run_config)
    _record_event(events, "checkpoint_summary", **checkpoint_report)
    _record_event(
        events,
        "run_finished",
        completed=completed,
        tests_passed=tests_passed,
    )
    report = {
        "run_id": run_id,
        "task_id": task_id,
        "started_at": issue_time,
        "finished_at": datetime.now(UTC).isoformat(),
        "model": model_name,
        "base_url": base_url,
        "issue": issue,
        "source_project": str(source),
        "workspace": str(workspace),
        "workspace_exists": workspace.is_dir(),
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
    _save_run_artifacts(
        run_dir,
        report,
        diff,
        checkpoint=checkpoint_report,
        replay=replay_report,
    )
    return run_dir


def main() -> None:
    """Parse command-line arguments and run the baseline agent."""
    parser = argparse.ArgumentParser(description="Run the Issue-to-PR baseline agent.")
    task_args = parser.add_mutually_exclusive_group(required=True)
    task_args.add_argument("--issue", help="Coding issue for the agent to resolve.")
    task_args.add_argument("--task-id", help="Task identifier from evals/tasks.json.")
    args = parser.parse_args()
    issue = args.issue
    if args.task_id:
        task_file = REPOSITORY_ROOT / "evals" / "tasks.json"
        tasks = json.loads(task_file.read_text(encoding="utf-8"))
        task = next((item for item in tasks if item["id"] == args.task_id), None)
        if task is None:
            parser.error(f"Unknown task id: {args.task_id}")
        issue = task["issue"]
    try:
        run_dir = run_task(issue, DEFAULT_PROJECT, task_id=args.task_id)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(f"Run artifacts: {run_dir}")
    print(f"Diff: {run_dir / 'diff.patch'}")
    print(f"Trace: {run_dir / 'run.json'}")


if __name__ == "__main__":
    main()
