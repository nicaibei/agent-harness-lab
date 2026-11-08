"""External hidden tests for the package startup fixture."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def _run_startup(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_project_metadata_is_present() -> None:
    metadata = (Path.cwd() / "pyproject.toml").read_text(encoding="utf-8")
    assert "service-app-startup-fixture" in metadata


def test_package_import_starts() -> None:
    result = _run_startup(
        "-c",
        "from service_app import load_settings; assert load_settings()['name'] == 'demo'",
    )
    assert result.returncode == 0, result.stderr


def test_module_entrypoint_starts() -> None:
    result = _run_startup("-m", "service_app")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "service-ready:demo"
