"""Run an offline migration check against the real CompositeBackend source."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import BackendProtocol, ReadResult, WriteResult
from harness.policy import PolicyMiddleware
from harness.recovery import RecoveryMiddleware
from harness.schema import EVENT_SCHEMA_VERSION, normalize_run_report
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UPSTREAM_ROOT = Path("D:/langgraph_learning/deepagent")
SOURCE_RELATIVE_PATH = Path("libs/deepagents/deepagents/backends/composite.py")
HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_composite_route_migration.py"
RUNS_ROOT = REPOSITORY_ROOT / "runs" / "migration"
TASK_ID = "composite-route-migration-v1"
REAL_TASK_ID = "composite-route-migration-real-v1"
EXPECTED_FILES = ("composite.py",)
GOOD_ROUTE_LINE = "        normalized_prefix = route_prefix if route_prefix.endswith(\"/\") else f\"{route_prefix}/\""
BAD_ROUTE_LINE = "        normalized_prefix = route_prefix.rstrip(\"/\")"


class BoundFakeChatModel(FakeMessagesListChatModel):
    """Offline model that accepts the tool binding used by create_deep_agent."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "BoundFakeChatModel":
        return self


class RecordingBackend(BackendProtocol):
    """Small backend double that records which route receives each write."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.writes: list[str] = []

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        """Read a recorded file through the backend contract."""
        del offset, limit
        content = self.files.get(file_path)
        if content is None:
            return ReadResult(error=f"File {file_path!r} not found")
        return ReadResult(file_data={"content": content, "encoding": "utf-8"})

    def write(self, file_path: str, content: str) -> WriteResult:
        """Record a write and return the backend contract result."""
        self.files[file_path] = content
        self.writes.append(file_path)
        return WriteResult(path=file_path)


def _record_event(events: list[dict[str, Any]], event: str, **details: Any) -> None:
    """Append a versioned event to the migration trace."""
    events.append(
        {
            "schema_version": EVENT_SCHEMA_VERSION,
            "event": event,
            "timestamp": datetime.now(UTC).isoformat(),
            **details,
        }
    )


def _snapshot(root: Path) -> dict[str, str]:
    """Read text files from a migration workspace."""
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def _build_diff(before: dict[str, str], after: dict[str, str]) -> str:
    """Build a minimal changed-file report for the workspace."""
    import difflib

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


def _write_route_app(workspace: Path) -> None:
    """Write the small application that exercises the copied real backend."""
    source = "\n".join(
        [
            '"""Application fixture for the CompositeBackend migration experiment."""',
            "",
            "from composite import CompositeBackend",
            "from deepagents.backends.protocol import BackendProtocol, ReadResult, WriteResult",
            "",
            "class RecordingBackend(BackendProtocol):",
            "    def __init__(self) -> None:",
            "        self.files: dict[str, str] = {}",
            "        self.writes: list[str] = []",
            "",
            "    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:",
            "        del offset, limit",
            "        content = self.files.get(file_path)",
            "        if content is None:",
            "            return ReadResult(error=f\"File {file_path!r} not found\")",
            "        return ReadResult(file_data={\"content\": content, \"encoding\": \"utf-8\"})",
            "",
            "    def write(self, file_path: str, content: str) -> WriteResult:",
            "        self.files[file_path] = content",
            "        self.writes.append(file_path)",
            "        return WriteResult(path=file_path)",
            "",
            "DEFAULT_BACKEND = RecordingBackend()",
            "ROUTED_BACKEND = RecordingBackend()",
            "BACKEND = CompositeBackend(",
            "    default=DEFAULT_BACKEND,",
            "    routes={\"/memories/\": ROUTED_BACKEND},",
            ")",
            "",
            "def reset_backends() -> None:",
            "    DEFAULT_BACKEND.files.clear()",
            "    DEFAULT_BACKEND.writes.clear()",
            "    ROUTED_BACKEND.files.clear()",
            "    ROUTED_BACKEND.writes.clear()",
            "",
            "def write_and_read(path: str, content: str) -> dict[str, object]:",
            "    write_result = BACKEND.write(path, content)",
            "    read_result = BACKEND.read(path)",
            "    read_content = None if read_result.file_data is None else read_result.file_data[\"content\"]",
            "    return {",
            "        \"write_error\": write_result.error,",
            "        \"read_content\": read_content,",
            "        \"default_writes\": list(DEFAULT_BACKEND.writes),",
            "        \"routed_writes\": list(ROUTED_BACKEND.writes),",
            "    }",
            "",
        ]
    )
    (workspace / "route_app.py").write_text(
        source,
        encoding="utf-8",
    )


def _prepare_workspace(run_dir: Path, upstream_root: Path) -> tuple[Path, dict[str, str]]:
    """Copy the real module and inject exactly one route-boundary defect."""
    source = (upstream_root / SOURCE_RELATIVE_PATH).resolve(strict=True)
    source_text = source.read_text(encoding="utf-8")
    if source_text.count(GOOD_ROUTE_LINE) != 1:
        raise ValueError("Expected exactly one CompositeBackend route-boundary line")
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=False)
    broken_text = source_text.replace(GOOD_ROUTE_LINE, BAD_ROUTE_LINE)
    (workspace / "composite.py").write_text(broken_text, encoding="utf-8")
    _write_route_app(workspace)
    before = _snapshot(workspace)
    return workspace, before


def _create_test_tool(
    workspace: Path,
    events: list[dict[str, Any]],
) -> BaseTool:
    """Create a two-run hidden evaluator tool."""
    remaining_runs = 2
    attempts = 0

    @tool("run_tests")
    def run_tests() -> str:
        """Run hidden route tests outside the Agent workspace."""
        nonlocal attempts, remaining_runs
        attempts += 1
        if remaining_runs == 0:
            result = {"success": False, "exit_code": 125, "output": "test budget exhausted"}
        else:
            remaining_runs -= 1
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(
                [str(workspace), environment.get("PYTHONPATH", "")]
            )
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", str(HIDDEN_TESTS)],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
                env=environment,
            )
            output = "\n".join(
                part for part in (completed.stdout.strip(), completed.stderr.strip()) if part
            )
            result = {
                "success": completed.returncode == 0,
                "exit_code": completed.returncode,
                "output": output or "(pytest produced no output)",
            }
        _record_event(events, "test_run", attempt=attempts, **result)
        return json.dumps(result, ensure_ascii=False)

    return run_tests


def _fake_model_responses() -> list[AIMessage]:
    """Return the deterministic offline repair trace."""
    old = BAD_ROUTE_LINE.strip()
    new = GOOD_ROUTE_LINE.strip()
    return [
        AIMessage(content="", tool_calls=[{"name": "run_tests", "args": {}, "id": "tests-before"}]),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "edit_file",
                    "args": {"file_path": "/composite.py", "old_string": old, "new_string": new},
                    "id": "repair-route-boundary",
                }
            ],
        ),
        AIMessage(content="", tool_calls=[{"name": "run_tests", "args": {}, "id": "tests-after"}]),
        AIMessage(content="migration task finished"),
    ]


def _run_agent(
    workspace: Path,
    events: list[dict[str, Any]],
    run_id: str,
    *,
    real_model: bool,
) -> dict[str, Any]:
    """Run either the deterministic or real-model trace through Deep Agents."""
    if real_model:
        load_dotenv(REPOSITORY_ROOT / ".env")
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        model_name = os.environ.get("DEEPSEEK_MODEL")
        if not api_key or not model_name:
            raise RuntimeError("DEEPSEEK_API_KEY and DEEPSEEK_MODEL are required for real mode")
        model: Any = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        model_label = model_name
    else:
        model = BoundFakeChatModel(responses=_fake_model_responses())
        model_label = "fake-offline"
    policy = PolicyMiddleware(
        max_tool_calls=20,
        require_baseline_test=True,
        on_decision=lambda decision: _record_event(events, "policy_decision", **decision),
    )
    recovery = RecoveryMiddleware(
        on_event=lambda recovery_event: _record_event(events, **recovery_event),
    )
    agent = create_deep_agent(
        model=model,
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        tools=[_create_test_tool(workspace, events)],
        middleware=[recovery, policy],
        checkpointer=InMemorySaver(),
        system_prompt=(
            "You are repairing a real SDK module in a disposable workspace. "
            "The evaluator tests are external and cannot be edited. Run the external "
            "tests before editing, inspect the failure, make one focused fix only in "
            "the implementation, then rerun the tests. Do not edit route_app.py or tests."
        ),
    )
    _record_event(events, "agent_started", model=model_label, source_module=str(SOURCE_RELATIVE_PATH))
    result = agent.invoke(
        {"messages": [HumanMessage(content="Repair the CompositeBackend route boundary.")]},
        config={"configurable": {"thread_id": run_id}},
    )
    _record_event(events, "agent_finished", message_count=len(result.get("messages", [])))
    return result


def run_experiment(*, upstream_root: Path, real_model: bool = False) -> Path:
    """Run the migration experiment and save versioned artifacts."""
    task_id = REAL_TASK_ID if real_model else TASK_ID
    report_name = "composite-route-migration-real-v1.json" if real_model else "composite-route-migration-v1.json"
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    run_dir = RUNS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    events: list[dict[str, Any]] = []
    _record_event(events, "run_started", run_id=run_id, task_id=task_id, model_mode="real" if real_model else "offline")
    workspace, before = _prepare_workspace(run_dir, upstream_root)
    _record_event(events, "workspace_created", workspace=str(workspace), file_count=len(before))
    execution_error = None
    try:
        response = _run_agent(workspace, events, run_id, real_model=real_model)
    except Exception as error:  # noqa: BLE001 - preserve the experiment failure artifact
        response = {}
        execution_error = f"{type(error).__name__}: {error}"
        _record_event(events, "agent_error", error=execution_error)
    after = _snapshot(workspace)
    diff = _build_diff(before, after)
    changed_files = sorted(
        name for name in before.keys() | after.keys() if before.get(name) != after.get(name)
    )
    unexpected_files = sorted(set(changed_files) - set(EXPECTED_FILES))
    test_runs = [
        json.loads(message.content)
        for message in response.get("messages", [])
        if isinstance(message, ToolMessage)
        and message.name == "run_tests"
        and isinstance(message.content, str)
    ]
    first_failed = bool(test_runs and test_runs[0].get("success") is False)
    tests_passed = bool(test_runs and test_runs[-1].get("success") is True)
    diff_scope_valid = not unexpected_files and bool(changed_files)
    completed = execution_error is None
    task_success = completed and first_failed and tests_passed and diff_scope_valid
    _record_event(
        events,
        "diff_scope_checked",
        changed_files=changed_files,
        expected_files=list(EXPECTED_FILES),
        unexpected_files=unexpected_files,
        diff_scope_valid=diff_scope_valid,
    )
    _record_event(
        events,
        "run_finished",
        completed=completed,
        tests_passed=tests_passed,
        task_success=task_success,
        diff_scope_valid=diff_scope_valid,
    )
    replay = {
        "schema_version": "replay.v1",
        "mode": "events-only",
        "event_count": len(events),
        "event_names": [event["event"] for event in events],
        "test_runs": len(test_runs),
        "completed": completed,
        "tests_passed": tests_passed,
    }
    report = normalize_run_report(
        {
            "run_id": run_id,
            "task_id": task_id,
            "scenario": "real-model-module-migration" if real_model else "offline-real-module-migration",
            "run_dir": str(run_dir),
            "source_module": str((upstream_root / SOURCE_RELATIVE_PATH).resolve()),
            "hidden_evaluator": str(HIDDEN_TESTS),
            "model": os.environ.get("DEEPSEEK_MODEL") if real_model else "fake-offline",
            "model_calls": sum(isinstance(message, AIMessage) for message in response.get("messages", [])),
            "cost": None,
            "cost_status": "provider_usage_not_recorded" if real_model else "not_applicable",
            "execution_error": execution_error,
            "completed": completed,
            "tests_passed": tests_passed,
            "first_test_failed": first_failed,
            "changed_files": changed_files,
            "expected_files": list(EXPECTED_FILES),
            "unexpected_files": unexpected_files,
            "diff_scope_valid": diff_scope_valid,
            "task_success": task_success,
            "test_runs": test_runs,
            "events": events,
        },
        diff,
        replay,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "diff.patch").write_text(diff, encoding="utf-8")
    (run_dir / "run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "replay.json").write_text(json.dumps(replay, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = REPOSITORY_ROOT / "evals" / "reports" / report_name
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    """Run the offline CompositeBackend migration experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path, default=Path(os.environ.get("DEEPAGENTS_REPO", DEFAULT_UPSTREAM_ROOT)))
    parser.add_argument("--real", action="store_true", help="Use one real DeepSeek task instead of the offline Fake Model.")
    args = parser.parse_args()
    report_path = run_experiment(upstream_root=args.upstream_root, real_model=args.real)
    print(f"Migration report: {report_path}")


if __name__ == "__main__":
    main()
