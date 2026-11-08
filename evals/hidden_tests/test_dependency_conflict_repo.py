"""External evaluator for the single-package version conflict fixture."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


def test_project_declares_version_2() -> None:
    metadata = (Path.cwd() / "pyproject.toml").read_text(encoding="utf-8")

    assert '"agent-harness-lab-conflict-dependency==2.0.0"' in metadata


def test_business_module_has_the_expected_entrypoint() -> None:
    source = (Path.cwd() / "service_app" / "app.py").read_text(encoding="utf-8")

    assert "readiness_message()" in source


def test_startup_uses_the_required_dependency_version() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from agent_harness_lab_conflict_dependency import "
                "__version__, readiness_message; "
                "print(__version__); print(readiness_message())"
            ),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0 and "1.0.0" in result.stdout:
        pytest.fail(
            "DEPENDENCY_CONFLICT: environment has 1.0.0 but project requires 2.0.0"
        )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["2.0.0", "dependency-v2-ready"]
