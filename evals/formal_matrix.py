"""Build a unified offline matrix without rerunning any model calls."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    """Load one JSON report."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Report must contain an object: {path}")
    return value


def build_report(reports_dir: Path) -> dict[str, Any]:
    """Aggregate existing reports with separate denominators per experiment."""
    baseline = _load(reports_dir / "baseline-summary.json")
    recovery = _load(reports_dir / "recovery-matrix-summary.json")
    fault = _load(reports_dir / "fault-injection-summary.json")
    ablation = _load(reports_dir / "cross-file-ablation-summary.json")
    negative = _load(reports_dir / "cross-file-negative-summary.json")
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "definition": {
            "task_success": "completed=true and final tests_passed=true",
            "recovery_success": "first test fails, a valid production diff exists, and final test passes",
            "modified_but_failed": "production diff exists but final hidden tests fail",
            "no_global_rate": "groups keep separate denominators and are not merged into one success rate",
        },
        "groups": {
            "baseline": {
                "attempts": baseline["attempt_count"],
                "tasks": baseline["task_count"],
                "successes": baseline["success_count"],
                "infrastructure_failures": baseline["attempt_count"] - baseline["valid_attempt_count"],
                "valid_success_rate": baseline["valid_success_rate"],
            },
            "fault_injection": {
                "cases": fault["case_count"],
                "successful_cases": fault["successful_cases"],
                "middleware_retry_cases": fault["middleware_retry_cases"],
                "model_correction_cases": fault["model_correction_cases"],
                "successful_model_corrections": fault["successful_model_corrections"],
                "failed_cases": fault["failed_cases"],
            },
            "real_recovery": {
                "runs": recovery["run_count"],
                "final_test_passes": recovery["successful_runs"],
                "recovered_after_failure": recovery["recovered_after_failure"],
                "edited_before_first_test": recovery["edited_before_first_test"],
            },
            "cross_file_ablation": {
                "variants": len(ablation["results"]),
                "both_files_passed": sum(
                    result["variant"] == "both" and result["success"]
                    for result in ablation["results"]
                ),
                "partial_or_initial_failed": sum(
                    not result["success"] for result in ablation["results"]
                ),
                "matrix_matches_expectation": ablation["passed_expected_matrix"],
            },
            "cross_file_negative": {
                "cases": len(negative["results"]),
                "modified_but_failed": sum(
                    result["classification"] == "modified_but_failed"
                    for result in negative["results"]
                ),
                "classification_matches_expectation": negative["all_classified_correctly"],
            },
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render the unified matrix with explicit group denominators."""
    groups = report["groups"]
    baseline = groups["baseline"]
    fault = groups["fault_injection"]
    recovery = groups["real_recovery"]
    ablation = groups["cross_file_ablation"]
    negative = groups["cross_file_negative"]
    lines = [
        "# Agent Harness 正式评测矩阵 v1",
        "",
        "不同实验保留自己的分母，不计算一个混合成功率。",
        "",
        "| 实验组 | 样本数 | 主要结果 |",
        "| --- | ---: | --- |",
        f"| Baseline | {baseline['attempts']} 次尝试 / {baseline['tasks']} 个任务 | "
        f"{baseline['successes']} 次成功；基础设施失败 {baseline['infrastructure_failures']} 次；有效成功率 {baseline['valid_success_rate']:.1%} |",
        f"| 故障注入 | {fault['cases']} 个案例 | "
        f"Middleware 重试 {fault['middleware_retry_cases']}；模型纠错成功 {fault['successful_model_corrections']}；失败 {fault['failed_cases']} |",
        f"| 真实 Recovery | {recovery['runs']} 次运行 | "
        f"最终通过 {recovery['final_test_passes']}；失败后恢复 {recovery['recovered_after_failure']}；测试前编辑 {recovery['edited_before_first_test']} |",
        f"| 跨文件消融 | {ablation['variants']} 个变体 | "
        f"双文件通过 {ablation['both_files_passed']}；其他变体失败 {ablation['partial_or_initial_failed']}；矩阵符合预期 {ablation['matrix_matches_expectation']} |",
        f"| 跨文件负面 | {negative['cases']} 个案例 | "
        f"修改但失败 {negative['modified_but_failed']}；分类符合预期 {negative['classification_matches_expectation']} |",
        "",
        "## 判定规则",
        "",
        f"- 任务成功：`{report['definition']['task_success']}`。",
        f"- Recovery 成功：`{report['definition']['recovery_success']}`。",
        f"- 负面结果：`{report['definition']['modified_but_failed']}`。",
        f"- 统计原则：{report['definition']['no_global_rate']}。",
        "",
        "## 当前结论",
        "",
        "Baseline、真实 Recovery、跨文件消融和负面案例已经形成可复查的证据链。当前数据适合说明 Harness 机制和评测口径，仍不足以推断大型真实仓库中的总体恢复率。",
    ]
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    """Write unified JSON and Markdown reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "formal-evaluation-matrix-v1.json"
    markdown_path = output_dir / "formal-evaluation-matrix-v1.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> None:
    """Build the formal matrix from existing report artifacts."""
    parser = argparse.ArgumentParser(description="Build the formal evaluation matrix.")
    parser.add_argument("--reports-dir", type=Path, default=Path("evals/reports"))
    parser.add_argument("--output-dir", type=Path, default=Path("evals/reports"))
    args = parser.parse_args()
    json_path, markdown_path = write_report(build_report(args.reports_dir), args.output_dir)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
