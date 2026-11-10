"""External evaluator for the real FilesystemMiddleware permission boundary."""

import permission_app


def test_secret_read_is_denied() -> None:
    result = permission_app.check_read("/secrets/key.txt")

    assert result["status"] == "error"
    assert "permission denied" in result["content"].lower()


def test_secret_write_is_denied() -> None:
    result = permission_app.check_write("/secrets/key.txt")

    assert result["status"] == "error"
    assert "permission denied" in result["content"].lower()


def test_workspace_write_is_allowed() -> None:
    result = permission_app.check_write("/workspace/note.txt")

    assert result["status"] != "error"
