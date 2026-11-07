"""Offline tests for the expanded task manifest."""

from evals.task_manifest import ALLOWED_CATEGORIES, load_manifest


def test_expanded_manifest_has_unique_valid_task_specs() -> None:
    tasks = load_manifest()

    assert len(tasks) == 6
    assert len({task.task_id for task in tasks}) == len(tasks)
    assert {task.category for task in tasks} == ALLOWED_CATEGORIES
    assert all(task.repeat_target >= 1 for task in tasks)
    assert sum(len(task.expected_files) > 1 for task in tasks) == 2
