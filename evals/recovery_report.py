"""Summarize real hidden-evaluator recovery runs."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _test_results(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Parse saved test tool results from one recovery run."""
    results: list[dict[str, Any]] = []
    for value in report.get("test_runs", []):
        if not isinstance(value, str):
            continue
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            results.append(parsed)
    return results


def _summarize(path: Path) -> dict[str, Any]:
    """Extract comparison fields without retaining full messages or diffs."""
    report = json.loads(path.read_text(encoding="utf-8"))
    tests = _test_results(report)
    events = report.get("events", [])
    return {
        "run_id": report.get("run_id"),
        "task_id": report.get("task_id"),
        "model": report.get("model"),
        "baseline_gate": report.get("baseline_gate", "unknown"),
        "completed": report.get("completed"),
        "tests_passed": report.get("tests_passed"),
        "test_run_count": len(tests),
        "first_test_passed": tests[0].get("success") if tests else None,
        "last_test_passed": tests[-1].get("success") if tests else None,
        "test_failure_results": sum(test.get("success") is False for test in tests),
        "recovered_after_failure": bool(
            tests and tests[0].get("success") is False and tests[-1].get("success") is True
        ),
        "policy_denials": sum(
            event.get("event") == "policy_decision" and event.get("decision") == "deny"
            for event in events
        ),
        "recovery_failures": sum(event.get("event") == "recovery_failure" for event in events),
        "test_recovery_failures": sum(
            event.get("event") == "recovery_failure" and event.get("tool") == "run_tests"
            for event in events
        ),
        "recovery_terminals": sum(event.get("event") == "recovery_terminal" for event in events),
        "diff_chars": len(report.get("diff", "")),
    }


def build_report(runs_dir: Path) -> dict[str, Any]:
    """Build a compact report for every saved recovery run."""
    runs = []
    for path in sorted(runs_dir.glob("*/run.json")):
        try:
            runs.append(_summarize(path))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "runs_directory": str(runs_dir),
        "run_count": len(runs),
        "successful_runs": sum(run["tests_passed"] is True for run in runs),
        "recovered_after_failure": sum(run["recovered_after_failure"] for run in runs),
        "runs": runs,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the recovery matrix for review."""
    lines = [
        "# Real Recovery 矩阵汇总",
        "",
        f"- 运行数：{report['run_count']}",
        f"- 最终测试通过：{report['successful_runs']}",
        f"- 失败后恢复成功：{report['recovered_after_failure']}",
        "",
        "| 任务 | 基线门 | 首次测试 | 最后测试 | 失败后恢复 | Policy 拒绝 | 测试失败结果 | 测试 Recovery 事件 | diff |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for run in report["runs"]:
        lines.append(
            f"| `{run['task_id']}` | {run['baseline_gate']} | {run['first_test_passed']} | "
            f"{run['last_test_passed']} | {run['recovered_after_failure']} | {run['policy_denials']} | "
            f"{run['test_failure_results']} | {run['test_recovery_failures']} | {run['diff_chars']} |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: Mapping[str, Any], output_dir: Path) -> tuple[Path, Path]:
    """Write JSON and Markdown recovery matrix reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "recovery-matrix-summary.json"
    markdown_path = output_dir / "recovery-matrix-summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> None:
    """Build a recovery matrix report from saved runs."""
    parser = argparse.ArgumentParser(description="Summarize real hidden-evaluator recovery runs.")
    parser.add_argument("--runs-dir", type=Path, default=Path("runs/recovery"))
    parser.add_argument("--output-dir", type=Path, default=Path("evals/reports"))
    args = parser.parse_args()
    json_path, markdown_path = write_report(build_report(args.runs_dir), args.output_dir)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
