"""Offline validation for the formal train/holdout task manifest."""

from evals.formal_task_manifest import load_manifest


def test_formal_manifest_has_30_unique_leak_free_tasks() -> None:
    tasks = load_manifest()

    assert len(tasks) == 30
    assert len({task.task_id for task in tasks}) == 30
    assert {task.split for task in tasks} == {"train", "holdout"}
    assert {task.strata for task in tasks} == {
        "baseline",
        "recovery",
        "cross_file",
        "repository_integration",
        "environment",
        "runtime",
        "security",
    }
    train_projects = {task.project for task in tasks if task.split == "train"}
    holdout_projects = {task.project for task in tasks if task.split == "holdout"}
    assert train_projects.isdisjoint(holdout_projects)
    assert all(
        task.offline_target is not None
        for task in tasks
        if task.strata in {"runtime", "security"}
    )
