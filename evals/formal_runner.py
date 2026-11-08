"""Build a deterministic execution plan for the formal task manifest."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import subprocess
import sys
from typing import Literal

from evals.formal_task_manifest import FormalTaskSpec, load_manifest


PLAN_SCHEMA_VERSION = "formal-plan.v1"
OFFLINE_RESULT_SCHEMA_VERSION = "formal-offline.v1"
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
    parser.add_argument(
        "--run-offline",
        action="store_true",
        help="Run only the explicitly assigned harness_offline pytest nodes.",
    )
    args = parser.parse_args()
    if args.run_offline:
        result = run_offline_tasks(split=args.split)
        output = write_plan(result, args.output)
        print(f"Offline tasks: {output}")
        print(f"Passed: {result['passed']}/{result['task_count']}; model calls: 0")
        return
    plan = build_plan(split=args.split)
    output = write_plan(plan, args.output)
    print(f"Formal plan: {output}")
    print(f"Tasks: {plan['task_count']}; model calls scheduled: {plan['model_calls_scheduled']}")


if __name__ == "__main__":
    main()
