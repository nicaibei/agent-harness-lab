"""Run an offline and real-model migration check for FilesystemMiddleware."""

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
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware.filesystem import FilesystemPermission
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
SOURCE_RELATIVE_PATH = Path("libs/deepagents/deepagents/middleware/filesystem.py")
HIDDEN_TESTS = REPOSITORY_ROOT / "evals" / "hidden_tests" / "test_filesystem_permission_migration.py"
RUNS_ROOT = REPOSITORY_ROOT / "runs" / "migration-permissions"
TASK_ID = "filesystem-permission-migration-v1"
REAL_TASK_ID = "filesystem-permission-migration-real-v1"
EXPECTED_FILES = ("filesystem.py",)
DIRECT_CHECK = '    if _check_fs_permission(rules, operation, validated_path) == "deny":'
BROKEN_CHECK = "    if False:  # injected migration defect"


class BoundFakeChatModel(FakeMessagesListChatModel):
    """Offline model that accepts the tool binding used by create_deep_agent."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "BoundFakeChatModel":
        return self


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
        if path.is_file() and "__pycache__" not in path.parts and "data" not in path.parts
    }


def _build_diff(before: dict[str, str], after: dict[str, str]) -> str:
    """Build a unified diff for changed workspace files."""
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


def _write_permission_app(workspace: Path) -> None:
    """Write the application fixture that invokes the copied middleware tools."""
    source = "\n".join(
        [
            '"""Application fixture for the FilesystemMiddleware migration."""',
            "",
            "from langchain.tools import ToolRuntime",
            "from deepagents.backends import FilesystemBackend",
            "from filesystem import FilesystemMiddleware, FilesystemPermission",
            "",
            "ROOT = __import__(\"pathlib\").Path(__file__).parent / \"data\"",
            "ROOT.joinpath(\"secrets\").mkdir(parents=True, exist_ok=True)",
            "ROOT.joinpath(\"workspace\").mkdir(parents=True, exist_ok=True)",
            "ROOT.joinpath(\"secrets\", \"key.txt\").write_text(\"top secret\", encoding=\"utf-8\")",
            "",
            "def _runtime() -> ToolRuntime:",
            "    return ToolRuntime(state={}, context=None, tool_call_id=\"migration\", store=None, stream_writer=lambda _: None, config={})",
            "",
            "def _middleware() -> FilesystemMiddleware:",
            "    return FilesystemMiddleware(",
            "        backend=FilesystemBackend(root_dir=ROOT, virtual_mode=True),",
            "        permissions=[FilesystemPermission(operations=[\"read\", \"write\"], paths=[\"/secrets/**\"], mode=\"deny\")],",
            "    )",
            "",
            "def _run(name: str, args: dict[str, object]) -> dict[str, object]:",
            "    tool = next(item for item in _middleware().tools if item.name == name)",
            "    result = tool.invoke({**args, \"runtime\": _runtime()})",
            "    return {\"status\": getattr(result, \"status\", \"success\"), \"content\": getattr(result, \"content\", str(result))}",
            "",
            "def check_read(path: str) -> dict[str, object]:",
            "    return _run(\"read_file\", {\"file_path\": path})",
            "",
            "def check_write(path: str) -> dict[str, object]:",
            "    return _run(\"write_file\", {\"file_path\": path, \"content\": \"candidate\"})",
            "",
        ]
    )
    (workspace / "permission_app.py").write_text(source, encoding="utf-8")


def _prepare_workspace(run_dir: Path, upstream_root: Path) -> tuple[Path, dict[str, str]]:
    """Copy the real middleware and inject one direct-permission defect."""
    source = (upstream_root / SOURCE_RELATIVE_PATH).resolve(strict=True)
    source_text = source.read_text(encoding="utf-8")
    if source_text.count(DIRECT_CHECK) != 1:
        raise ValueError("Expected exactly one direct permission check")
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=False)
    broken_text = source_text.replace(DIRECT_CHECK, BROKEN_CHECK)
    (workspace / "filesystem.py").write_text(broken_text, encoding="utf-8")
    _write_permission_app(workspace)
    before = _snapshot(workspace)
    return workspace, before


def _create_test_tool(workspace: Path, events: list[dict[str, Any]]) -> BaseTool:
    """Create a two-run hidden evaluator tool."""
    remaining_runs = 2
    attempts = 0

    @tool("run_tests")
    def run_tests() -> str:
        """Run external permission tests outside the Agent workspace."""
        nonlocal attempts, remaining_runs
        attempts += 1
        if remaining_runs == 0:
            result = {"success": False, "exit_code": 125, "output": "test budget exhausted"}
        else:
            remaining_runs -= 1
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join([str(workspace), environment.get("PYTHONPATH", "")])
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", str(HIDDEN_TESTS)],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
                env=environment,
            )
            output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
            result = {"success": completed.returncode == 0, "exit_code": completed.returncode, "output": output or "(pytest produced no output)"}
        _record_event(events, "test_run", attempt=attempts, **result)
        return json.dumps(result, ensure_ascii=False)

    return run_tests


def _fake_responses() -> list[AIMessage]:
    """Return the deterministic offline repair trace."""
    return [
        AIMessage(content="", tool_calls=[{"name": "run_tests", "args": {}, "id": "tests-before"}]),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "edit_file",
                    "args": {"file_path": "/filesystem.py", "old_string": BROKEN_CHECK, "new_string": DIRECT_CHECK},
                    "id": "repair-permission-check",
                }
            ],
        ),
        AIMessage(content="", tool_calls=[{"name": "run_tests", "args": {}, "id": "tests-after"}]),
        AIMessage(content="permission task finished"),
    ]


def _run_agent(workspace: Path, events: list[dict[str, Any]], run_id: str, *, real_model: bool) -> dict[str, Any]:
    """Run an offline or real model through the same Deep Agent harness."""
    if real_model:
        load_dotenv(REPOSITORY_ROOT / ".env")
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        model_name = os.environ.get("DEEPSEEK_MODEL")
        if not api_key or not model_name:
            raise RuntimeError("DEEPSEEK_API_KEY and DEEPSEEK_MODEL are required for real mode")
        model: Any = ChatOpenAI(model=model_name, api_key=api_key, base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
        model_label = model_name
    else:
        model = BoundFakeChatModel(responses=_fake_responses())
        model_label = "fake-offline"
    policy = PolicyMiddleware(max_tool_calls=20, require_baseline_test=True, on_decision=lambda decision: _record_event(events, "policy_decision", **decision))
    recovery = RecoveryMiddleware(on_event=lambda recovery_event: _record_event(events, **recovery_event))
    agent = create_deep_agent(
        model=model,
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        tools=[_create_test_tool(workspace, events)],
        middleware=[recovery, policy],
        checkpointer=InMemorySaver(),
        system_prompt=(
            "You are repairing a real SDK middleware module in a disposable workspace. "
            "The evaluator tests are external and cannot be edited. Run tests before editing, "
            "inspect the failure, make one focused fix only in filesystem.py, then rerun tests."
        ),
    )
    _record_event(events, "agent_started", model=model_label, source_module=str(SOURCE_RELATIVE_PATH))
    result = agent.invoke(
        {"messages": [HumanMessage(content="Repair the FilesystemMiddleware permission boundary.")]},
        config={"configurable": {"thread_id": run_id}},
    )
    _record_event(events, "agent_finished", message_count=len(result.get("messages", [])))
    return result


def run_experiment(*, upstream_root: Path, real_model: bool = False) -> Path:
    """Run the permission migration experiment and save versioned artifacts."""
    task_id = REAL_TASK_ID if real_model else TASK_ID
    report_name = "filesystem-permission-migration-real-v1.json" if real_model else "filesystem-permission-migration-v1.json"
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
    changed_files = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    unexpected_files = sorted(set(changed_files) - set(EXPECTED_FILES))
    test_runs = [
        json.loads(message.content)
        for message in response.get("messages", [])
        if isinstance(message, ToolMessage) and message.name == "run_tests" and isinstance(message.content, str)
    ]
    first_failed = bool(test_runs and test_runs[0].get("success") is False)
    tests_passed = bool(test_runs and test_runs[-1].get("success") is True)
    completed = execution_error is None
    diff_scope_valid = not unexpected_files and bool(changed_files)
    task_success = completed and first_failed and tests_passed and diff_scope_valid
    _record_event(events, "diff_scope_checked", changed_files=changed_files, expected_files=list(EXPECTED_FILES), unexpected_files=unexpected_files, diff_scope_valid=diff_scope_valid)
    _record_event(events, "run_finished", completed=completed, tests_passed=tests_passed, task_success=task_success, diff_scope_valid=diff_scope_valid)
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
            "scenario": "real-model-permission-migration" if real_model else "offline-real-module-migration",
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
    (run_dir / "diff.patch").write_text(diff, encoding="utf-8")
    (run_dir / "run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "replay.json").write_text(json.dumps(replay, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = REPOSITORY_ROOT / "evals" / "reports" / report_name
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    """Run the FilesystemMiddleware permission migration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path, default=Path(os.environ.get("DEEPAGENTS_REPO", DEFAULT_UPSTREAM_ROOT)))
    parser.add_argument("--real", action="store_true", help="Use one real DeepSeek task instead of the offline Fake Model.")
    args = parser.parse_args()
    print(f"Permission migration report: {run_experiment(upstream_root=args.upstream_root, real_model=args.real)}")


if __name__ == "__main__":
    main()
