"""Run a deterministic checkpoint, interrupt, and resume experiment."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent_app.baseline import (
    COPY_IGNORE,
    DEFAULT_PROJECT,
    REPOSITORY_ROOT,
    _build_diff,
    _record_event,
    _save_run_artifacts,
    _snapshot_files,
)
from harness.checkpoint import replay_events, summarize_checkpoints
from harness.checkpoint import FileCheckpointSaver


CHECKPOINT_RUNS_ROOT = REPOSITORY_ROOT / "runs" / "checkpoint"
CHECKPOINT_V2_TASK_ID = "checkpoint-resume-v2-process-restart"


class BoundFakeChatModel(FakeMessagesListChatModel):
    """Offline model that accepts the tool binding used by create_deep_agent."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> BoundFakeChatModel:
        return self


def _create_test_tool(workspace: Path) -> BaseTool:
    """Create a deterministic pytest tool for the resumed run."""

    @tool
    def run_tests() -> str:
        """Run the workspace test suite after the approved write."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        output = "\n".join(
            part for part in (result.stdout.strip(), result.stderr.strip()) if part
        )
        return json.dumps(
            {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "output": output or "(pytest produced no output)",
            },
            ensure_ascii=False,
        )

    return run_tests


def _calculator_after_resume() -> str:
    """Return the approved calculator change used by both processes."""
    return '''"""Tiny calculator project used by the checkpoint experiment."""


def add(left: float, right: float) -> float:
    """Return the sum of two numbers."""
    return left + right


def subtract(left: float, right: float) -> float:
    """Return the difference between two numbers."""
    return left - right


def divide(left: float, right: float) -> float:
    """Return the quotient between two numbers."""
    if right == 0:
        raise ValueError("Cannot divide by zero.")
    return left / right
'''


def _build_checkpoint_agent(
    workspace: Path,
    checkpointer: Any,
    responses: list[AIMessage],
) -> Any:
    """Build one process-local Agent graph for the v2 experiment."""
    return create_deep_agent(
        model=BoundFakeChatModel(responses=responses),
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        tools=[_create_test_tool(workspace)],
        interrupt_on={"write_file": True},
        checkpointer=checkpointer,
        system_prompt=(
            "You are running a deterministic checkpoint experiment. "
            "Wait for approval before the write_file call is executed."
        ),
    )


def _pause_checkpoint_process(run_dir: Path) -> None:
    """Create a checkpoint and exit before the interrupted write executes."""
    workspace = run_dir / "workspace"
    shutil.copytree(DEFAULT_PROJECT, workspace, ignore=COPY_IGNORE)
    checkpoint_path = run_dir / "checkpoint-store.json"
    checkpointer = FileCheckpointSaver(checkpoint_path)
    config = {"configurable": {"thread_id": run_dir.name}}
    events: list[dict[str, Any]] = []
    _record_event(events, "run_started", run_id=run_dir.name, task_id=CHECKPOINT_V2_TASK_ID)
    before = _snapshot_files(workspace)
    _record_event(events, "workspace_created", file_count=len(before))
    agent = _build_checkpoint_agent(
        workspace,
        checkpointer,
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {
                            "file_path": "/calculator.py",
                            "content": _calculator_after_resume(),
                        },
                        "id": "checkpoint-v2-write",
                    }
                ],
            )
        ],
    )
    paused = agent.invoke(
        {"messages": [("user", "apply the approved calculator change")]},
        config=config,
    )
    paused_snapshot = _snapshot_files(workspace)
    checkpoint = summarize_checkpoints(checkpointer, config)
    _record_event(
        events,
        "run_waiting",
        interrupted="__interrupt__" in paused,
        checkpoint_count=checkpoint["checkpoint_count"],
        diff_characters=len(_build_diff(before, paused_snapshot)),
        process_id="pause",
    )
    (run_dir / "pause.json").write_text(
        json.dumps(
            {
                "events": events,
                "before": before,
                "paused": "__interrupt__" in paused,
                "checkpoint": checkpoint,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _resume_checkpoint_process(run_dir: Path) -> None:
    """Load the durable checkpoint in a new process and finish the task."""
    workspace = run_dir / "workspace"
    pause = json.loads((run_dir / "pause.json").read_text(encoding="utf-8"))
    checkpointer = FileCheckpointSaver(run_dir / "checkpoint-store.json")
    config = {"configurable": {"thread_id": run_dir.name}}
    side_effects_before_resume = pause["events"][-1]["diff_characters"] > 0
    events = pause["events"]
    _record_event(events, "process_restarted", process_id="resume")
    agent = _build_checkpoint_agent(
        workspace,
        checkpointer,
        [
            AIMessage(
                content="",
                tool_calls=[{"name": "run_tests", "args": {}, "id": "checkpoint-v2-tests"}],
            ),
            AIMessage(content="checkpoint task finished"),
        ],
    )
    resumed = agent.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config=config,
    )
    _record_event(events, "run_resumed", thread_id=run_dir.name, process_id="resume")
    after = _snapshot_files(workspace)
    diff = _build_diff(pause["before"], after)
    test_runs = [
        message.content
        for message in resumed.get("messages", [])
        if isinstance(message, ToolMessage) and message.name == "run_tests"
    ]
    parsed_tests = [json.loads(test_run) for test_run in test_runs]
    for attempt, result in enumerate(parsed_tests, start=1):
        _record_event(events, "test_run", attempt=attempt, **result)
    tests_passed = bool(parsed_tests and parsed_tests[-1].get("success"))
    checkpoint = summarize_checkpoints(checkpointer, config)
    _record_event(
        events,
        "run_finished",
        completed=True,
        tests_passed=tests_passed,
        resumed=True,
        production_diff=bool(diff),
    )
    report = {
        "run_id": run_dir.name,
        "task_id": CHECKPOINT_V2_TASK_ID,
        "scenario": "offline-process-restart-resume",
        "completed": True,
        "tests_passed": tests_passed,
        "paused": pause["paused"],
        "resumed": True,
        "side_effects_before_resume": side_effects_before_resume,
        "production_diff": diff,
        "test_runs": test_runs,
        "events": events,
        "checkpoint_before_resume": pause["checkpoint"],
        "checkpoint_after_resume": checkpoint,
        "replay": replay_events(events),
    }
    _save_run_artifacts(
        run_dir,
        report,
        diff,
        checkpoint=checkpoint,
        replay=report["replay"],
    )


def run_checkpoint_process_restart_experiment(run_dir: Path | None = None) -> Path:
    """Run pause and resume in separate Python processes."""
    target = run_dir or (
        CHECKPOINT_RUNS_ROOT
        / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    )
    target.mkdir(parents=True, exist_ok=False)
    for phase in ("pause", "resume"):
        subprocess.run(
            [sys.executable, __file__, "--phase", phase, "--run-dir", str(target)],
            cwd=REPOSITORY_ROOT,
            check=True,
            timeout=120,
        )
    return target


def run_checkpoint_resume_experiment() -> Path:
    """Run and save one deterministic interrupt/resume experiment."""
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    run_dir = CHECKPOINT_RUNS_ROOT / run_id
    workspace = run_dir / "workspace"
    run_dir.mkdir(parents=True, exist_ok=False)
    shutil.copytree(DEFAULT_PROJECT, workspace, ignore=COPY_IGNORE)
    events: list[dict[str, Any]] = []
    _record_event(events, "run_started", run_id=run_id, task_id="checkpoint-resume-v1")
    before = _snapshot_files(workspace)
    _record_event(events, "workspace_created", file_count=len(before))

    checkpointer = InMemorySaver()
    config = {"configurable": {"thread_id": run_id}}
    calculator_after_resume = '''"""Tiny calculator project used by the checkpoint experiment."""


def add(left: float, right: float) -> float:
    """Return the sum of two numbers."""
    return left + right


def subtract(left: float, right: float) -> float:
    """Return the difference between two numbers."""
    return left - right


def divide(left: float, right: float) -> float:
    """Return the quotient between two numbers."""
    if right == 0:
        raise ValueError("Cannot divide by zero.")
    return left / right
'''
    agent = create_deep_agent(
        model=BoundFakeChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "write_file",
                            "args": {
                                "file_path": "/calculator.py",
                                "content": calculator_after_resume,
                            },
                            "id": "checkpoint-write",
                        }
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "run_tests", "args": {}, "id": "checkpoint-tests"}],
                ),
                AIMessage(content="checkpoint task finished"),
            ]
        ),
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        tools=[_create_test_tool(workspace)],
        interrupt_on={"write_file": True},
        checkpointer=checkpointer,
        system_prompt=(
            "You are running a deterministic checkpoint experiment. "
            "Wait for approval before the write_file call is executed."
        ),
    )

    paused = agent.invoke(
        {"messages": [("user", "apply the approved calculator documentation change")]},
        config=config,
    )
    paused_snapshot = _snapshot_files(workspace)
    checkpoint_before = summarize_checkpoints(checkpointer, config)
    _record_event(
        events,
        "run_waiting",
        interrupted="__interrupt__" in paused,
        checkpoint_count=checkpoint_before["checkpoint_count"],
        diff_characters=len(_build_diff(before, paused_snapshot)),
    )

    resumed = agent.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config=config,
    )
    _record_event(events, "run_resumed", thread_id=run_id)
    after = _snapshot_files(workspace)
    diff = _build_diff(before, after)
    test_runs = [
        message.content
        for message in resumed.get("messages", [])
        if isinstance(message, ToolMessage) and message.name == "run_tests"
    ]
    parsed_tests = [json.loads(test_run) for test_run in test_runs]
    for attempt, result in enumerate(parsed_tests, start=1):
        _record_event(events, "test_run", attempt=attempt, **result)
    tests_passed = bool(parsed_tests and parsed_tests[-1].get("success"))
    checkpoint_after = summarize_checkpoints(checkpointer, config)
    _record_event(
        events,
        "run_finished",
        completed=True,
        tests_passed=tests_passed,
        resumed=True,
        production_diff=bool(diff),
    )
    report = {
        "run_id": run_id,
        "task_id": "checkpoint-resume-v1",
        "scenario": "offline-interrupt-resume",
        "completed": True,
        "tests_passed": tests_passed,
        "paused": "__interrupt__" in paused,
        "resumed": True,
        "side_effects_before_resume": bool(_build_diff(before, paused_snapshot)),
        "production_diff": diff,
        "test_runs": test_runs,
        "events": events,
        "checkpoint_before_resume": checkpoint_before,
        "checkpoint_after_resume": checkpoint_after,
        "replay": replay_events(events),
    }
    _save_run_artifacts(
        run_dir,
        report,
        diff,
        checkpoint=checkpoint_after,
        replay=report["replay"],
    )
    return run_dir


def main() -> None:
    """Run the offline checkpoint experiment."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("pause", "resume"))
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    if args.phase is not None:
        if args.run_dir is None:
            parser.error("--run-dir is required with --phase")
        if args.phase == "pause":
            _pause_checkpoint_process(args.run_dir)
        else:
            _resume_checkpoint_process(args.run_dir)
        return
    print(f"Run artifacts: {run_checkpoint_resume_experiment()}")


if __name__ == "__main__":
    main()

