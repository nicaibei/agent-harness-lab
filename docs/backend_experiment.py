"""Run a model-free experiment for Deep Agents backends.

Run from libs/deepagents:

    uv run python ../../docs/experiments/backend_experiment.py

The experiment uses a minimal LangGraph node because StateBackend reads and
writes the LangGraph files channel from an active graph execution context.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.backends.protocol import BackendProtocol
from deepagents.middleware.filesystem import FilesystemState
from langgraph.graph import END, START, StateGraph


def summarize(
    operation: str,
    input_path: str,
    backend: BackendProtocol,
    result: Any,
    *,
    normalized_path: str | None = None,
) -> dict[str, Any]:
    """Convert a backend result into a stable experiment record."""
    error = getattr(result, "error", None)
    record: dict[str, Any] = {
        "operation": operation,
        "input_path": input_path,
        "backend": type(backend).__name__,
        "normalized_path": normalized_path,
        "result_type": type(result).__name__,
        "success": error is None,
        "error": error,
    }
    returned_path = getattr(result, "path", None)
    if returned_path is not None:
        record["returned_path"] = returned_path
    occurrences = getattr(result, "occurrences", None)
    if occurrences is not None:
        record["occurrences"] = occurrences
    file_data = getattr(result, "file_data", None)
    if file_data is not None:
        record["content"] = file_data.get("content")
    return record


def summarize_exception(
    operation: str,
    input_path: str,
    backend: BackendProtocol,
    error: Exception,
    *,
    normalized_path: str | None = None,
) -> dict[str, Any]:
    """Record an exception raised before a backend result was created."""
    return {
        "operation": operation,
        "input_path": input_path,
        "backend": type(backend).__name__,
        "normalized_path": normalized_path,
        "result_type": type(error).__name__,
        "success": False,
        "error": str(error),
    }


def write_with_exception_record(
    operation: str,
    input_path: str,
    backend: BackendProtocol,
    content: str,
    *,
    normalized_path: str | None = None,
) -> dict[str, Any]:
    """Run write while preserving exceptions in the experiment report."""
    try:
        result = backend.write(input_path, content)
    except Exception as error:  # noqa: BLE001 - experiment records backend boundaries
        return summarize_exception(
            operation,
            input_path,
            backend,
            error,
            normalized_path=normalized_path,
        )
    return summarize(
        operation,
        input_path,
        backend,
        result,
        normalized_path=normalized_path,
    )


def run_state_experiment() -> list[dict[str, Any]]:
    """Verify StateBackend CRUD and its path-key behavior."""
    backend = StateBackend()
    records: list[dict[str, Any]] = []
    path = "/state/demo.txt"
    records.append(summarize("write", path, backend, backend.write(path, "hello state")))
    records.append(summarize("read", path, backend, backend.read(path)))
    records.append(summarize("edit", path, backend, backend.edit(path, "state", "backend")))
    records.append(summarize("read_after_edit", path, backend, backend.read(path)))
    records.append(summarize("delete", path, backend, backend.delete(path)))
    records.append(summarize("read_after_delete", path, backend, backend.read(path)))

    traversal_path = "/../state-escape.txt"
    records.append(
        write_with_exception_record(
            "path_traversal_write",
            traversal_path,
            backend,
            "state accepts this key",
        )
    )
    records.append(summarize("path_traversal_cleanup", traversal_path, backend, backend.delete(traversal_path)))
    return records


def run_filesystem_experiment(root: Path) -> list[dict[str, Any]]:
    """Verify virtual filesystem paths and traversal rejection."""
    backend = FilesystemBackend(root_dir=root, virtual_mode=True)
    records: list[dict[str, Any]] = []
    path = "/filesystem/demo.txt"
    records.append(summarize("write", path, backend, backend.write(path, "hello filesystem")))
    records.append(summarize("read", path, backend, backend.read(path)))
    records.append(summarize("edit", path, backend, backend.edit(path, "filesystem", "backend")))
    records.append(summarize("read_after_edit", path, backend, backend.read(path)))
    records.append(
        summarize(
            "host_mapping_check",
            path,
            backend,
            backend.read(path),
            normalized_path=str(root / "filesystem" / "demo.txt"),
        )
    )
    traversal_path = "/../filesystem-escape.txt"
    records.append(
        write_with_exception_record(
            "path_traversal_write",
            traversal_path,
            backend,
            "blocked",
        )
    )
    records.append(summarize("delete", path, backend, backend.delete(path)))
    return records


def run_composite_experiment(root: Path) -> list[dict[str, Any]]:
    """Verify route selection, prefix restoration, and route-specific safety."""
    state_backend = StateBackend()
    filesystem_backend = FilesystemBackend(root_dir=root, virtual_mode=True)
    backend = CompositeBackend(
        default=state_backend,
        routes={"/memory/": state_backend, "/workspace/": filesystem_backend},
    )
    records: list[dict[str, Any]] = []

    for path, content in (
        ("/memory/note.txt", "memory value"),
        ("/workspace/note.txt", "workspace value"),
    ):
        selected, normalized = backend._get_backend_and_key(path)
        records.append(
            summarize(
                "route_write",
                path,
                selected,
                backend.write(path, content),
                normalized_path=normalized,
            )
        )
        selected, normalized = backend._get_backend_and_key(path)
        records.append(
            summarize(
                "route_read",
                path,
                selected,
                backend.read(path),
                normalized_path=normalized,
            )
        )
        selected, normalized = backend._get_backend_and_key(path)
        records.append(
            summarize(
                "route_edit",
                path,
                selected,
                backend.edit(path, "value", "edited"),
                normalized_path=normalized,
            )
        )
        selected, normalized = backend._get_backend_and_key(path)
        records.append(
            summarize(
                "route_delete",
                path,
                selected,
                backend.delete(path),
                normalized_path=normalized,
            )
        )

    traversal_cases = (
        "/memory/../memory-escape.txt",
        "/workspace/../workspace-escape.txt",
    )
    for path in traversal_cases:
        selected, normalized = backend._get_backend_and_key(path)
        records.append(
            write_with_exception_record(
                "route_path_traversal_write",
                path,
                selected,
                "path traversal probe",
                normalized_path=normalized,
            )
        )
    return records


def run_experiment() -> dict[str, Any]:
    """Run all backend checks inside one minimal LangGraph execution."""
    with tempfile.TemporaryDirectory(prefix="deepagents-backend-") as temp_dir:
        root = Path(temp_dir)
        report: dict[str, Any] = {"filesystem_root": str(root), "records": []}

        def experiment_node(state: FilesystemState) -> dict[str, Any]:
            del state
            records = report["records"]
            records.extend(run_state_experiment())
            records.extend(run_filesystem_experiment(root))
            records.extend(run_composite_experiment(root))
            return {}

        graph = StateGraph(FilesystemState)
        graph.add_node("backend_experiment", experiment_node)
        graph.add_edge(START, "backend_experiment")
        graph.add_edge("backend_experiment", END)
        graph.compile().invoke({"messages": [], "files": {}})
        return report


def main() -> None:
    """Print the experiment report as JSON."""
    report = run_experiment()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
