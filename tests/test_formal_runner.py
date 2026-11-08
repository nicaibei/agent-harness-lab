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
    assert sum(task["offline_target"] is not None for task in plan["tasks"]) == 8
    offline_targets = [task["offline_target"] for task in plan["tasks"] if task["offline_target"]]
    assert len(offline_targets) == len(set(offline_targets))


def test_holdout_plan_contains_no_train_tasks() -> None:
    plan = build_plan(split="holdout")

    assert plan["task_count"] == 14
    assert all(task["split"] == "holdout" for task in plan["tasks"])
    assert all(task["execution_mode"] == "agent_model" for task in plan["tasks"] if task["strata"] != "security")
    assert all(task["model_required"] is False for task in plan["tasks"] if task["strata"] == "security")


def test_model_task_adapter_runs_one_baseline_task_without_retry(tmp_path, monkeypatch) -> None:
    import agent_app.baseline as baseline
    from evals.formal_runner import run_model_task

    calls: list[tuple[str, str]] = []
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(
        '{"completed": true, "tests_passed": true, "execution_error": null, "model": "fake"}',
        encoding="utf-8",
    )

    def fake_run_task(issue, project, *, task_id):
        calls.append((issue, task_id))
        return run_dir

    monkeypatch.setattr(baseline, "run_task", fake_run_task)
    result = run_model_task("calculator-add-floats")

    assert len(calls) == 1
    assert calls[0][1] == "calculator-add-floats"
    assert result["model_calls_requested"] == 1
    assert result["tests_passed"] is True
