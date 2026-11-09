"""External evaluator for the real CompositeBackend route boundary."""

import route_app


def test_memories_path_uses_routed_backend() -> None:
    """A path inside /memories/ is stored by the routed backend."""
    route_app.reset_backends()

    result = route_app.write_and_read("/memories/note.txt", "persistent")

    assert result["write_error"] is None
    assert result["read_content"] == "persistent"
    assert result["default_writes"] == []
    assert result["routed_writes"] == ["/note.txt"]


def test_memories_old_prefix_stays_on_default_backend() -> None:
    """A near-prefix must not be treated as the /memories/ route."""
    route_app.reset_backends()

    result = route_app.write_and_read("/memories-old/note.txt", "temporary")

    assert result["write_error"] is None
    assert result["read_content"] == "temporary"
    assert result["default_writes"] == ["/memories-old/note.txt"]
    assert result["routed_writes"] == []
