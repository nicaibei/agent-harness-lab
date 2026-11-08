"""Offline checks for the package startup Recovery fixture."""

from pathlib import Path

from evals.real_recovery import STARTUP_HIDDEN_TESTS, STARTUP_PROJECT, _run_hidden_tests


def _copy_fixture(source: Path, workspace: Path) -> None:
    for item in source.rglob("*"):
        if item.is_file():
            target = workspace / item.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.read_bytes())


def test_startup_fixture_fails_then_passes_after_entrypoint_repair(tmp_path: Path) -> None:
    workspace = tmp_path / "startup-repo"
    _copy_fixture(STARTUP_PROJECT, workspace)

    before = _run_hidden_tests(workspace, STARTUP_HIDDEN_TESTS)
    assert before["success"] is False
    assert "2 failed, 1 passed" in before["output"]

    entrypoint = workspace / "service_app" / "__init__.py"
    entrypoint.write_text(
        entrypoint.read_text(encoding="utf-8").replace("service_app.configs", "service_app.config"),
        encoding="utf-8",
    )

    after = _run_hidden_tests(workspace, STARTUP_HIDDEN_TESTS)
    assert after["success"] is True
