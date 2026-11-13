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
    assert result["task_success"] is None
    assert result["diff_scope_valid"] is None
    assert result["model_usage"] is None
    assert result["cost_status"] == "not_collected_by_runner"


def test_passing_tests_with_unlisted_empty_file_are_not_success(tmp_path, monkeypatch) -> None:
    import json

    import agent_app.baseline as baseline
    from evals.formal_runner import run_model_task
    from harness.file_scope import file_changes, snapshot_file_hashes

    run_dir = tmp_path / "run"
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "test_calculator.py").write_text("before", encoding="utf-8")
    before = snapshot_file_hashes(workspace)
    (workspace / "test_calculator.py").write_text("after", encoding="utf-8")
    (workspace / "unlisted.txt").touch()
    report = {
        "completed": True, "tests_passed": True, "execution_error": None,
        "file_changes": file_changes(before, snapshot_file_hashes(workspace)),
    }
    (run_dir / "run.json").write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(baseline, "run_task", lambda *args, **kwargs: run_dir)
    result = run_model_task("calculator-add-floats")
    assert result["tests_passed"] is True
    assert result["unexpected_files"] == ["unlisted.txt"]
    assert result["diff_scope_valid"] is False
    assert result["task_success"] is False


def test_recovery_requires_first_failure_and_nonempty_allowed_change() -> None:
    from evals.formal_runner import _assess_model_result
    from evals.formal_task_manifest import load_manifest
    from harness.file_scope import file_changes

    task = next(item for item in load_manifest() if item.task_id == "real-recovery-csv-row")
    report = {
        "completed": True, "tests_passed": True, "execution_error": None,
        "test_runs": ['{"success": false}', '{"success": true}'],
        "file_changes": file_changes({"row.py": "old"}, {"row.py": "new"}),
    }
    assert _assess_model_result(task, report)["task_success"] is True
    report["test_runs"] = ['{"success": true}']
    assert _assess_model_result(task, report)["task_success"] is False
    report["test_runs"] = ['{"success": false}', '{"success": true}']
    report["file_changes"] = file_changes({"row.py": "old"}, {"row.py": "old"})
    assert _assess_model_result(task, report)["task_success"] is False


def test_model_task_reports_estimate_separately_from_unknown_actual_cost(
    tmp_path, monkeypatch,
) -> None:
    import json

    import agent_app.baseline as baseline
    from evals.formal_runner import run_model_task

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    report = {
        "model": "example",
        "started_at": "2026-11-13T05:18:00+00:00",
        "finished_at": "2026-11-13T05:19:00+00:00",
        "model_usage": {
            "token_usage_status": "complete",
            "cache_usage_status": "complete",
            "observed_tokens": {
                "input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100,
            },
            "observed_cache_tokens": {"hit_tokens": 600, "miss_tokens": 400},
        },
    }
    (run_dir / "run.json").write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(baseline, "run_task", lambda *args, **kwargs: run_dir)
    pricing = {
        "id": "offline", "source": "offline", "model": "example", "currency": "USD",
        "valid_from": "2026-11-13T05:00:00+00:00",
        "valid_until": "2026-11-13T06:00:00+00:00",
        "hit_per_million": "0.003", "miss_per_million": "0.15",
        "output_per_million": "0.6",
    }
    result = run_model_task("calculator-add-floats", pricing=pricing)
    assert result["cost_estimate"]["amount"] == "0.0001218"
    assert result["cost_estimate"]["currency"] == "USD"
    assert result["cost_estimate"]["status"] == "estimated"
    assert result["cost"] is None
    assert result["cost_status"] == "actual_cost_not_recorded"
