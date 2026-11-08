"""External evaluator for the missing third-party dependency fixture."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


MISSING_PACKAGE = "agent-harness-lab-missing-dependency"


def test_project_declares_the_required_dependency() -> None:
    metadata = (Path.cwd() / "pyproject.toml").read_text(encoding="utf-8")

    assert f'"{MISSING_PACKAGE}==1.0.0"' in metadata


def test_business_module_has_the_expected_entrypoint() -> None:
    source = (Path.cwd() / "service_app" / "app.py").read_text(encoding="utf-8")

    assert "readiness_message()" in source


def test_startup_is_blocked_by_missing_dependency() -> None:
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

    if result.returncode != 0 and "agent_harness_lab_missing_dependency" in result.stderr:
        pytest.fail(
            "ENVIRONMENT_FAILURE: required dependency "
            f"{MISSING_PACKAGE} is unavailable"
        )
    assert result.returncode == 0, result.stderr
