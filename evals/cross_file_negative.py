"""Run controlled negative cases for cross-file Recovery evaluation."""

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
class NegativeCase:
    """A case where both production files change but the result stays wrong."""

    name: str
    project: Path
    hidden_tests: Path
    changed_files: Mapping[str, str]


CASES = (
    NegativeCase(
        name="order-total",
        project=ORDER_PROJECT,
        hidden_tests=ORDER_HIDDEN_TESTS,
        changed_files={
            "order_parser.py": (
                '"""Order parser with a partial repair."""\n\n\ndef parse_order(value: str) -> dict[str, float]:\n'
                '    quantity_text, price_text = [part.strip() for part in value.split("x")]\n'
                '    return {"quantity": int(quantity_text), "unit_price": float(price_text)}\n'
            ),
            "order_total.py": (
                '"""Order total calculator with a partial repair."""\n\n\ndef total_with_tax(order: dict[str, float], tax_rate: float) -> float:\n'
                '    subtotal = order["quantity"] + order["unit_price"]\n'
                '    return subtotal + subtotal * tax_rate\n'
            ),
        },
    ),
    NegativeCase(
        name="temperature-report",
        project=TEMPERATURE_PROJECT,
        hidden_tests=TEMPERATURE_HIDDEN_TESTS,
        changed_files={
            "temperature_parser.py": (
                '"""Temperature parser with a partial repair."""\n\n\ndef parse_reading(value: str) -> dict[str, float | str]:\n'
                '    number_text, unit = value.split()\n'
                '    return {"value": float(number_text), "unit": unit.upper()}\n'
            ),
            "temperature_report.py": (
                '"""Temperature conversion with a partial repair."""\n\n\ndef to_celsius(reading: dict[str, float | str]) -> float:\n'
                '    value = float(reading["value"])\n'
                '    return value - 32 if reading["unit"] == "F" else value\n'
            ),
        },
    ),
)


def run_negative_case(case: NegativeCase, root: Path) -> dict[str, object]:
    """Apply both partial repairs and record the failing hidden evaluation."""
    workspace = root / case.name
    shutil.copytree(case.project, workspace)
    for filename, content in case.changed_files.items():
        (workspace / filename).write_text(content, encoding="utf-8")
    result = _run_hidden_tests(workspace, case.hidden_tests)
    return {
        "case": case.name,
        "changed_files": list(case.changed_files),
        "diff_expected": True,
        "tests_passed": result["success"],
        "expected_tests_passed": False,
        "classification": "modified_but_failed",
    }


def build_report() -> dict[str, object]:
    """Run all controlled negative cases in temporary workspaces."""
    with tempfile.TemporaryDirectory(prefix="cross-file-negative-") as directory:
        root = Path(directory)
        results = [run_negative_case(case, root) for case in CASES]
    return {
        "experiment": "cross-file-recovery-negative-v1",
        "results": results,
        "all_classified_correctly": all(
            result["tests_passed"] is False
            and result["classification"] == "modified_but_failed"
            for result in results
        ),
    }


def render_markdown(report: Mapping[str, object]) -> str:
    """Render the negative-case results for review."""
    lines = [
        "# Cross-file Recovery 负面案例汇总",
        "",
        f"- 分类全部正确：{report['all_classified_correctly']}",
        "",
        "| 任务 | 修改文件数 | 最终测试 | 分类 |",
        "| --- | ---: | --- | --- |",
    ]
    for result in report["results"]:
        lines.append(
            f"| `{result['case']}` | {len(result['changed_files'])} | "
            f"{result['tests_passed']} | `{result['classification']}` |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: Mapping[str, object], output_dir: Path) -> tuple[Path, Path]:
    """Write JSON and Markdown negative-case reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "cross-file-negative-summary.json"
    markdown_path = output_dir / "cross-file-negative-summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> None:
    """Run and save the controlled negative matrix."""
    parser = argparse.ArgumentParser(description="Run cross-file negative Recovery cases.")
    parser.add_argument("--output-dir", type=Path, default=Path("evals/reports"))
    args = parser.parse_args()
    json_path, markdown_path = write_report(build_report(), args.output_dir)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
