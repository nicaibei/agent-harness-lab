"""Build a deterministic execution plan for the formal task manifest."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Literal

from evals.formal_task_manifest import FormalTaskSpec, load_manifest
from harness.file_scope import assess_file_scope


PLAN_SCHEMA_VERSION = "formal-plan.v1"
OFFLINE_RESULT_SCHEMA_VERSION = "formal-offline.v1"
MODEL_RESULT_SCHEMA_VERSION = "formal-model-result.v1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ExecutionMode = Literal["agent_model", "harness_offline"]


def _execution_mode(task: FormalTaskSpec) -> ExecutionMode:
    """Choose the execution boundary without invoking a model."""
    if task.strata in {"runtime", "security"}:
        return "harness_offline"
    return "agent_model"


def build_plan(*, split: str | None = None) -> dict[str, object]:
    """Build a JSON-safe plan for one split or the whole manifest."""
    tasks = load_manifest()
    if split is not None and split not in {"train", "holdout"}:
        raise ValueError(f"Unknown formal evaluation split: {split}")
    selected = [task for task in tasks if split is None or task.split == split]
    entries = [_plan_entry(task) for task in selected]
    mode_counts = Counter(entry["execution_mode"] for entry in entries)
    split_counts = Counter(task.split for task in selected)
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "manifest": "evals/formal_tasks.json",
        "task_count": len(entries),
        "split_counts": dict(sorted(split_counts.items())),
        "execution_mode_counts": dict(sorted(mode_counts.items())),
        "model_calls_scheduled": mode_counts.get("agent_model", 0),
        "tasks": entries,
    }


def _plan_entry(task: FormalTaskSpec) -> dict[str, object]:
    """Convert one validated task into an execution boundary record."""
    mode = _execution_mode(task)
    return {
        "task_id": task.task_id,
        "split": task.split,
        "strata": task.strata,
        "category": task.category,
        "difficulty": task.difficulty,
        "execution_mode": mode,
        "model_required": mode == "agent_model",
        "project": task.project,
        "evaluator": task.evaluator,
        "offline_target": task.offline_target,
        "expected_files": list(task.expected_files),
        "manifest_status": task.status,
    }


def run_offline_tasks(*, split: str | None = None) -> dict[str, object]:
    """Run only manifest tasks explicitly assigned to local pytest nodes."""
    plan = build_plan(split=split)
    results: list[dict[str, object]] = []
    for entry in plan["tasks"]:
        if entry["execution_mode"] != "harness_offline":
            continue
        target = entry["offline_target"]
        if not isinstance(target, str) or not target:
            raise ValueError(f"Offline task has no pytest target: {entry['task_id']}")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", target],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        output = "\n".join(
            part for part in (result.stdout.strip(), result.stderr.strip()) if part
        )
        results.append(
            {
                "task_id": entry["task_id"],
                "target": target,
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "output": output or "(pytest produced no output)",
            }
        )
    return {
        "schema_version": OFFLINE_RESULT_SCHEMA_VERSION,
        "task_count": len(results),
        "passed": sum(result["success"] is True for result in results),
        "failed": sum(result["success"] is False for result in results),
        "model_calls": 0,
        "results": results,
    }


def run_model_task(task_id: str) -> dict[str, object]:
    """Run exactly one explicitly selected train task through its existing runner."""
    task = next((item for item in load_manifest() if item.task_id == task_id), None)
    if task is None:
        raise ValueError(f"Unknown formal evaluation task: {task_id}")
    if task.split != "train":
        raise ValueError("Real model runs are limited to train tasks until holdout is authorized")
    if _execution_mode(task) != "agent_model":
        raise ValueError(f"Task is not a model task: {task_id}")

    started_at = datetime.now(UTC)
    started = perf_counter()
    if task.strata == "baseline":
        from agent_app.baseline import run_task

        run_dir = run_task(task.issue, Path(task.project), task_id=task.task_id)
    else:
        from evals.real_recovery import run_recovery_task

        case_name = task.task_id.removeprefix("real-recovery-")
        run_dir = run_recovery_task(case_name)
    elapsed_seconds = perf_counter() - started
    finished_at = datetime.now(UTC)
    report_path = run_dir / "run.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assessment = _assess_model_result(task, report)
    return {
        "schema_version": MODEL_RESULT_SCHEMA_VERSION,
        "task_id": task.task_id,
        "split": task.split,
        "run_dir": str(run_dir),
        "run_artifact": str(report_path),
        "scenario": report.get("scenario"),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "latency_seconds": round(elapsed_seconds, 3),
        "model_calls_requested": 1,
        "model_calls_requested_semantics": "legacy field: agent task invocations, not API requests",
        "task_runs_requested": 1,
        "completed": report.get("completed"),
        "tests_passed": report.get("tests_passed"),
        "execution_error": report.get("execution_error"),
        "model": report.get("model"),
        "diff_chars": len(report.get("diff", "")) if isinstance(report.get("diff"), str) else 0,
        "test_run_count": len(report.get("test_runs", [])) if isinstance(report.get("test_runs"), list) else 0,
        "event_count": len(report.get("events", [])) if isinstance(report.get("events"), list) else 0,
        **assessment,
        "model_usage": report.get("model_usage"),
        "cost": None,
        "cost_status": "pricing_not_configured" if report.get("model_usage") else "not_collected_by_runner",
    }


def _assess_model_result(task: FormalTaskSpec, report: dict[str, object]) -> dict[str, object]:
    """Combine task outcome with trusted workspace change evidence."""
    scope = assess_file_scope(report.get("file_changes"), task.expected_files)
    test_runs = report.get("test_runs", [])
    first = test_runs[0] if isinstance(test_runs, list) and test_runs else None
    if isinstance(first, str):
        try:
            first = json.loads(first)
        except json.JSONDecodeError:
            first = None
    first_failed = first.get("success") is False if isinstance(first, dict) else None
    required = (
        report.get("completed") is True
        and report.get("execution_error") is None
        and report.get("tests_passed") is True
    )
    if task.strata == "recovery":
        required = required and first_failed is True
    success: bool | None = False
    if required:
        success = None if scope["diff_scope_valid"] is None else (
            scope["diff_scope_valid"] is True and bool(scope["changed_files"])
        )
    return {**scope, "first_test_failed": first_failed, "task_success": success}


def write_plan(plan: dict[str, object], output: Path) -> Path:
    """Write one deterministic execution plan as JSON."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    """Write an offline execution plan without calling a model."""
    parser = argparse.ArgumentParser(description="Build the formal evaluation execution plan.")
    parser.add_argument("--split", choices=("train", "holdout"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evals/reports/formal-run-plan-v1.json"),
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--run-offline",
        action="store_true",
        help="Run only the explicitly assigned harness_offline pytest nodes.",
    )
    actions.add_argument(
        "--run-model",
        metavar="TASK_ID",
        help="Run exactly one authorized train agent_model task; no automatic retry.",
    )
    args = parser.parse_args()
    if args.run_offline:
        result = run_offline_tasks(split=args.split)
        output = write_plan(result, args.output)
        print(f"Offline tasks: {output}")
        print(f"Passed: {result['passed']}/{result['task_count']}; model calls: 0")
        return
    if args.run_model is not None:
        result = run_model_task(args.run_model)
        output = write_plan(result, args.output)
        print(f"Model result: {output}")
        print(
            f"Task: {result['task_id']}; tests_passed: {result['tests_passed']}; "
            f"task_success: {result['task_success']}; diff_scope_valid: {result['diff_scope_valid']}"
        )
        return
    plan = build_plan(split=args.split)
    output = write_plan(plan, args.output)
    print(f"Formal plan: {output}")
    print(f"Tasks: {plan['task_count']}; model calls scheduled: {plan['model_calls_scheduled']}")


if __name__ == "__main__":
    main()
