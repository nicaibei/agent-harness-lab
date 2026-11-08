"""External evaluator for the controlled dependency-preparation fixture."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


MISSING_PACKAGE = "agent_harness_lab_prepared_dependency"


def test_project_declares_the_required_dependency() -> None:
    metadata = (Path.cwd() / "pyproject.toml").read_text(encoding="utf-8")

    assert '"agent-harness-lab-prepared-dependency==1.0.0"' in metadata


def test_business_module_has_the_expected_entrypoint() -> None:
    source = (Path.cwd() / "service_app" / "app.py").read_text(encoding="utf-8")

    assert "readiness_message()" in source


def test_startup_works_after_dependency_preparation() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from service_app import readiness_message; print(readiness_message())",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0 and f"No module named '{MISSING_PACKAGE}'" in result.stderr:
        pytest.fail(
            "ENVIRONMENT_FAILURE: required dependency "
            "agent-harness-lab-prepared-dependency is unavailable"
        )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "dependency-ready"
