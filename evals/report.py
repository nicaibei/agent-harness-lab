"""Build offline evaluation reports from saved Agent run artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal


FailureCategory = Literal[
    "success",
    "test_failure",
    "model_error",
    "setup_error",
    "agent_error",
    "invalid_artifact",
]
INFRASTRUCTURE_CATEGORIES = frozenset({"model_error", "setup_error", "invalid_artifact"})
MODEL_ERROR_MARKERS = ("openai", "connection error", "quota", "model id")
SETUP_ERROR_MARKERS = ("winerror", "access denied", "workspace")


def classify_run(report: Mapping[str, object]) -> FailureCategory:
    """Classify one saved run without judging the model's code quality."""
    required = {"run_id", "task_id", "completed", "tests_passed"}
    if not required.issubset(report):
        return "invalid_artifact"
    if report["completed"] is True and report["tests_passed"] is True:
        return "success"
    if report["completed"] is True:
        return "test_failure"
    error = str(report.get("execution_error") or "").casefold()
    if any(marker in error for marker in MODEL_ERROR_MARKERS):
        return "model_error"
    if any(marker in error for marker in SETUP_ERROR_MARKERS):
        return "setup_error"
    return "agent_error"


def _compact_attempt(report: Mapping[str, object], category: FailureCategory) -> dict[str, object]:
    """Keep only fields needed for aggregation in memory."""
    events = report.get("events", [])
    test_runs = report.get("test_runs", [])
    diff = report.get("diff", "")
    return {
        "run_id": report.get("run_id"),
        "task_id": report.get("task_id"),
        "model": report.get("model"),
        "finished_at": report.get("finished_at", ""),
        "category": category,
        "completed": report.get("completed"),
        "tests_passed": report.get("tests_passed"),
        "diff_chars": len(diff) if isinstance(diff, str) else 0,
        "test_runs": len(test_runs) if isinstance(test_runs, list) else 0,
        "event_count": len(events) if isinstance(events, list) else 0,
    }


def iter_attempts(runs_dir: Path) -> Iterator[dict[str, object]]:
    """Yield compact summaries while reading one run artifact at a time."""
    for path in sorted(runs_dir.glob("*/run.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            yield {"run_id": path.parent.name, "category": "invalid_artifact"}
            continue
        if not isinstance(report, dict):
            yield {"run_id": path.parent.name, "category": "invalid_artifact"}
            continue
        category = classify_run(report)
        yield _compact_attempt(report, category)


def _latest(attempts: list[dict[str, object]]) -> dict[str, object] | None:
    """Return the newest attempt using ISO timestamps, then run ID."""
    if not attempts:
        return None
    return max(
        attempts,
        key=lambda attempt: (str(attempt.get("finished_at", "")), str(attempt.get("run_id", ""))),
    )


def build_report(runs_dir: Path) -> dict[str, object]:
    """Aggregate all saved run artifacts into a JSON-safe report."""
    attempts = list(iter_attempts(runs_dir))
    categories = Counter(str(attempt.get("category")) for attempt in attempts)
    tasks: dict[str, list[dict[str, object]]] = {}
    for attempt in attempts:
        task_id = attempt.get("task_id")
        if isinstance(task_id, str) and task_id:
            tasks.setdefault(task_id, []).append(attempt)

    task_summaries = {}
    for task_id, task_attempts in sorted(tasks.items()):
        valid = [
            attempt
            for attempt in task_attempts
            if attempt.get("category") not in INFRASTRUCTURE_CATEGORIES
        ]
        task_summaries[task_id] = {
            "attempt_count": len(task_attempts),
            "latest_attempt": _latest(task_attempts),
            "latest_valid_attempt": _latest(valid),
        }

    valid_attempts = [
        attempt
        for attempt in attempts
        if attempt.get("category") not in INFRASTRUCTURE_CATEGORIES
    ]
    successful_attempts = sum(attempt.get("category") == "success" for attempt in attempts)
    successful_valid = sum(attempt.get("category") == "success" for attempt in valid_attempts)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "runs_directory": str(runs_dir),
        "attempt_count": len(attempts),
        "task_count": len(tasks),
        "category_counts": dict(sorted(categories.items())),
        "success_count": successful_attempts,
        "attempt_success_rate": successful_attempts / len(attempts) if attempts else 0.0,
        "valid_attempt_count": len(valid_attempts),
        "valid_success_count": successful_valid,
        "valid_success_rate": successful_valid / len(valid_attempts) if valid_attempts else 0.0,
        "task_summaries": task_summaries,
    }


def render_markdown(report: Mapping[str, object]) -> str:
    """Render the compact evaluation report for human review."""
    lines = [
        "# Agent Harness 评测汇总",
        "",
        f"- 运行尝试数：{report['attempt_count']}",
        f"- 任务数：{report['task_count']}",
        f"- 全部尝试成功率：{float(report['attempt_success_rate']):.1%}",
        f"- 有效尝试数：{report['valid_attempt_count']}",
        f"- 有效尝试成功率：{float(report['valid_success_rate']):.1%}",
        "",
        "## 失败分类",
        "",
        "| 分类 | 次数 |",
        "| --- | ---: |",
    ]
    for category, count in sorted(report["category_counts"].items()):
        lines.append(f"| `{category}` | {count} |")
    lines.extend(
        [
            "",
            "## 每个任务的主要结果",
            "",
            "`latest_valid_attempt` 排除了模型、初始化和损坏产物问题，用于观察 Agent 任务表现。",
            "",
            "| 任务 | 尝试数 | 最新有效分类 | 测试通过 | diff 字符数 |",
            "| --- | ---: | --- | --- | ---: |",
        ]
    )
    for task_id, summary in report["task_summaries"].items():
        latest = summary["latest_valid_attempt"] or {}
        lines.append(
            f"| `{task_id}` | {summary['attempt_count']} | "
            f"`{latest.get('category', 'none')}` | {latest.get('tests_passed', 'n/a')} | "
            f"{latest.get('diff_chars', 'n/a')} |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: Mapping[str, object], output_dir: Path) -> tuple[Path, Path]:
    """Write JSON and Markdown evaluation artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "baseline-summary.json"
    markdown_path = output_dir / "baseline-summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> None:
    """Build a report from a runs directory."""
    parser = argparse.ArgumentParser(description="Summarize saved Agent Harness runs.")
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parser.add_argument("--output-dir", type=Path, default=Path("evals/reports"))
    args = parser.parse_args()
    report = build_report(args.runs_dir)
    json_path, markdown_path = write_report(report, args.output_dir)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
