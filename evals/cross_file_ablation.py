"""Run offline file-level ablations for cross-file Recovery fixtures."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from evals.real_recovery import (
    ORDER_HIDDEN_TESTS,
    ORDER_PROJECT,
    TEMPERATURE_HIDDEN_TESTS,
    TEMPERATURE_PROJECT,
    _run_hidden_tests,
)


@dataclass(frozen=True)
class AblationCase:
    """A cross-file fixture and its independently repaired files."""

    name: str
    project: Path
    hidden_tests: Path
    fixed_files: Mapping[str, str]


ORDER_CASE = AblationCase(
    name="order-total",
    project=ORDER_PROJECT,
    hidden_tests=ORDER_HIDDEN_TESTS,
    fixed_files={
        "order_parser.py": (
            '"""Order parser."""\n\n\ndef parse_order(value: str) -> dict[str, float]:\n'
            '    quantity_text, price_text = [part.strip() for part in value.split("x")]\n'
            '    return {"quantity": int(quantity_text), "unit_price": float(price_text)}\n'
        ),
        "order_total.py": (
            '"""Order total calculator."""\n\n\ndef total_with_tax(order: dict[str, float], tax_rate: float) -> float:\n'
            '    subtotal = order["quantity"] * order["unit_price"]\n'
            '    return subtotal * (1 + tax_rate)\n'
        ),
    },
)


TEMPERATURE_CASE = AblationCase(
    name="temperature-report",
    project=TEMPERATURE_PROJECT,
    hidden_tests=TEMPERATURE_HIDDEN_TESTS,
    fixed_files={
        "temperature_parser.py": (
            '"""Temperature parser."""\n\n\ndef parse_reading(value: str) -> dict[str, float | str]:\n'
            '    number_text, unit = value.split()\n'
            '    return {"value": float(number_text), "unit": unit.upper()}\n'
        ),
        "temperature_report.py": (
            '"""Temperature conversion."""\n\n\ndef to_celsius(reading: dict[str, float | str]) -> float:\n'
            '    value = float(reading["value"])\n'
            '    return (value - 32) * 5 / 9 if reading["unit"] == "F" else value\n'
        ),
    },
)


CASES = (ORDER_CASE, TEMPERATURE_CASE)
VARIANTS = ("initial", "first-only", "second-only", "both")


def _variant_files(case: AblationCase, variant: str) -> tuple[str, ...]:
    if variant == "initial":
        return ()
    if variant == "both":
        return tuple(case.fixed_files)
    index = 0 if variant == "first-only" else 1
    return (tuple(case.fixed_files)[index],)


def run_ablation_case(case: AblationCase, root: Path) -> list[dict[str, object]]:
    """Run hidden tests for each file-repair variant of one fixture."""
    results: list[dict[str, object]] = []
    source_files = tuple(case.fixed_files)
    for variant in VARIANTS:
        workspace = root / case.name / variant
        shutil.copytree(case.project, workspace)
        for filename in _variant_files(case, variant):
            (workspace / filename).write_text(case.fixed_files[filename], encoding="utf-8")
        result = _run_hidden_tests(workspace, case.hidden_tests)
        results.append(
            {
                "case": case.name,
                "variant": variant,
                "changed_files": list(_variant_files(case, variant)),
                "success": result["success"],
                "expected_success": variant == "both",
                "all_files": list(source_files),
            }
        )
    return results


def build_report() -> dict[str, object]:
    """Run all ablations in disposable temporary workspaces."""
    with tempfile.TemporaryDirectory(prefix="cross-file-ablation-") as directory:
        root = Path(directory)
        results = [item for case in CASES for item in run_ablation_case(case, root)]
    return {
        "experiment": "cross-file-recovery-file-ablation-v1",
        "cases": [case.name for case in CASES],
        "variants": list(VARIANTS),
        "results": results,
        "passed_expected_matrix": all(
            result["success"] == result["expected_success"] for result in results
        ),
    }


def render_markdown(report: Mapping[str, object]) -> str:
    """Render the ablation matrix for review."""
    lines = [
        "# Cross-file Recovery 文件级消融汇总",
        "",
        f"- 矩阵符合预期：{report['passed_expected_matrix']}",
        "",
        "| 任务 | 变体 | 修改文件 | 测试结果 | 预期结果 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in report["results"]:
        files = ", ".join(result["changed_files"]) or "无"
        lines.append(
            f"| `{result['case']}` | `{result['variant']}` | {files} | "
            f"{result['success']} | {result['expected_success']} |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: Mapping[str, object], output_dir: Path) -> tuple[Path, Path]:
    """Write JSON and Markdown ablation reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "cross-file-ablation-summary.json"
    markdown_path = output_dir / "cross-file-ablation-summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> None:
    """Run and save the offline cross-file ablation matrix."""
    parser = argparse.ArgumentParser(description="Run cross-file Recovery file ablations.")
    parser.add_argument("--output-dir", type=Path, default=Path("evals/reports"))
    args = parser.parse_args()
    json_path, markdown_path = write_report(build_report(), args.output_dir)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
