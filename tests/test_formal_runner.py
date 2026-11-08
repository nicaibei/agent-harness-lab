"""Offline tests for formal evaluation plan generation."""

from evals.formal_runner import PLAN_SCHEMA_VERSION, build_plan


def test_full_plan_separates_model_and_harness_boundaries() -> None:
    plan = build_plan()

    assert plan["schema_version"] == PLAN_SCHEMA_VERSION
    assert plan["task_count"] == 30
    assert plan["split_counts"] == {"holdout": 14, "train": 16}
    assert plan["execution_mode_counts"] == {"agent_model": 22, "harness_offline": 8}
    assert plan["model_calls_scheduled"] == 22
    assert all("task_id" in task for task in plan["tasks"])


def test_holdout_plan_contains_no_train_tasks() -> None:
    plan = build_plan(split="holdout")

    assert plan["task_count"] == 14
    assert all(task["split"] == "holdout" for task in plan["tasks"])
    assert all(task["execution_mode"] == "agent_model" for task in plan["tasks"] if task["strata"] != "security")
    assert all(task["model_required"] is False for task in plan["tasks"] if task["strata"] == "security")
