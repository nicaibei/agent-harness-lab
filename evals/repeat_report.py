"""Summarize repeated real Recovery runs for one task."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any


def _parse_tests(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Parse saved test-tool results from a run report."""
    tests: list[dict[str, Any]] = []
    for value in report.get("test_runs", []):
        if not isinstance(value, str):
            continue
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            tests.append(parsed)
    return tests


def _summarize(path: Path) -> dict[str, Any]:
    """Extract comparable metrics from one run artifact."""
    report = json.loads(path.read_text(encoding="utf-8"))
    tests = _parse_tests(report)
    events = report.get("events", [])
    return {
        "run_id": report.get("run_id", path.parent.name),
        "first_test_passed": tests[0].get("success") if tests else None,
        "last_test_passed": tests[-1].get("success") if tests else None,
        "recovered_after_failure": bool(
            tests and tests[0].get("success") is False and tests[-1].get("success") is True
        ),
        "completed": report.get("completed"),
        "tests_passed": report.get("tests_passed"),
        "diff_chars": len(report.get("diff", "")),
        "changed_files": sorted(
            event.get("path", "")
            for event in events
            if event.get("event") == "diff_created" and event.get("path")
        ),
        "policy_denials": sum(
            event.get("event") == "policy_decision" and event.get("decision") == "deny"
            for event in events
        ),
        "exploration_errors": sum(
            event.get("event") == "recovery_failure" and event.get("tool") != "run_tests"
            for event in events
        ),
    }


def build_report(runs_dir: Path, task_id: str) -> dict[str, Any]:
    """Build a repeated-run report for one task ID."""
    runs: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("*/run.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(report, dict) and report.get("task_id") == task_id:
            runs.append(_summarize(path))
    if not runs:
        raise ValueError(f"No runs found for task: {task_id}")
    diff_sizes = [run["diff_chars"] for run in runs]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "task_id": task_id,
        "run_count": len(runs),
        "final_successes": sum(run["tests_passed"] is True for run in runs),
        "first_test_failures": sum(run["first_test_passed"] is False for run in runs),
        "recovered_after_failure": sum(run["recovered_after_failure"] for run in runs),
        "diff_chars": {"min": min(diff_sizes), "max": max(diff_sizes), "mean": mean(diff_sizes)},
        "exploration_errors": sum(run["exploration_errors"] for run in runs),
        "runs": runs,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a repeated-run report for human review."""
    lines = [
        f"# 重复 Recovery 报告：`{report['task_id']}`",
        "",
        f"- 运行次数：{report['run_count']}",
        f"- 最终通过：{report['final_successes']}",
        f"- 首次测试失败：{report['first_test_failures']}",
        f"- 失败后恢复：{report['recovered_after_failure']}",
        f"- diff 字符数：{report['diff_chars']['min']} - {report['diff_chars']['max']}，平均 {report['diff_chars']['mean']:.1f}",
        f"- 探索工具错误：{report['exploration_errors']}",
        "",
        "| run_id | 首次测试 | 最终测试 | 失败后恢复 | diff 字符数 | Policy 拒绝 | 探索错误 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for run in report["runs"]:
        lines.append(
            f"| `{run['run_id']}` | {run['first_test_passed']} | {run['last_test_passed']} | "
            f"{run['recovered_after_failure']} | {run['diff_chars']} | {run['policy_denials']} | "
            f"{run['exploration_errors']} |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: Mapping[str, Any], output_dir: Path) -> tuple[Path, Path]:
    """Write repeated-run JSON and Markdown reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"repeat-{report['task_id']}.json"
    markdown_path = output_dir / f"repeat-{report['task_id']}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> None:
    """Build and save one repeated-task report."""
    parser = argparse.ArgumentParser(description="Summarize repeated Recovery runs.")
    parser.add_argument("--runs-dir", type=Path, default=Path("runs/recovery"))
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("evals/reports"))
    args = parser.parse_args()
    json_path, markdown_path = write_report(
        build_report(args.runs_dir, args.task_id), args.output_dir
    )
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
