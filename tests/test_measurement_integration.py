"""Exercise persisted usage and file evidence through real offline Agent graphs."""

import json
from pathlib import Path

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult

from agent_app import baseline
from evals import real_recovery
from evals.formal_runner import run_model_task
from tests.test_real_recovery import BoundFakeChatModel


class FailingSecondResponseModel(BoundFakeChatModel):
    """Raise after one observed response to exercise runner exception handling."""

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: object,
    ) -> ChatResult:
        if self.i == 1:
            msg = "Injected offline model failure"
            raise RuntimeError(msg)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _tool_message(name: str, args: dict[str, object], call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}],
                     usage_metadata={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5})


def _offline_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(baseline, "load_dotenv", lambda *args: None)
    monkeypatch.setattr(real_recovery, "load_dotenv", lambda *args: None)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "offline-placeholder")
    monkeypatch.setenv("DEEPSEEK_MODEL", "fake-offline")


def test_formal_recovery_persists_partial_usage_and_automatic_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _offline_settings(monkeypatch)
    monkeypatch.setattr(real_recovery, "RECOVERY_RUNS_ROOT", tmp_path)
    fixed = ('def parse_row(value: str) -> dict[str, int | str]:\n'
             '    name, score = value.split(",")\n'
             '    return {"name": name.strip(), "score": int(score)}\n')
    responses = [
        _tool_message("run_tests", {}, "first"),
        _tool_message("write_file", {"file_path": "/row.py", "content": fixed}, "fix"),
        _tool_message("run_tests", {}, "second"),
        AIMessage(content="finished"),
    ]
    monkeypatch.setattr(real_recovery, "ChatOpenAI", lambda **kwargs: BoundFakeChatModel(responses=responses))
    result = run_model_task("real-recovery-csv-row")
    report = json.loads(Path(result["run_artifact"]).read_text(encoding="utf-8"))
    assert result["task_success"] is True
    assert result["first_test_failed"] is True
    assert result["changed_files"] == ["row.py"]
    assert result["unexpected_files"] == []
    assert result["model_usage"] == report["model_usage"]
    assert result["model_usage"]["model_invocations"] == 4
    assert result["model_usage"]["responses_with_usage"] == 3
    assert result["model_usage"]["token_usage_status"] == "partial"
    assert result["model_usage"]["observed_tokens"]["total_tokens"] == 15
    assert result["cost"] is None


def test_baseline_uses_callback_collector_and_persists_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _offline_settings(monkeypatch)
    monkeypatch.setattr(baseline, "RUNS_ROOT", tmp_path)
    original = (baseline.DEFAULT_PROJECT / "calculator.py").read_text(encoding="utf-8")
    responses = [
        _tool_message("write_file", {"file_path": "/calculator.py", "content": original +
            "\n\ndef multiply(left: float, right: float) -> float:\n    return left * right\n"}, "multiply"),
        _tool_message("run_tests", {}, "verify"),
        AIMessage(content="finished"),
    ]
    monkeypatch.setattr(baseline, "ChatOpenAI", lambda **kwargs: BoundFakeChatModel(responses=responses))
    result = run_model_task("calculator-multiply")
    report = json.loads(Path(result["run_artifact"]).read_text(encoding="utf-8"))
    assert result["task_success"] is True
    assert result["changed_files"] == ["calculator.py"]
    assert report["file_changes"]["before"]["calculator.py"] != report["file_changes"]["after"]["calculator.py"]
    assert result["model_usage"]["model_responses"] == 3
    assert result["model_usage"]["token_usage_status"] == "partial"
    assert result["model_usage"]["observed_tokens"]["total_tokens"] == 10


def test_runner_retains_prior_usage_after_later_model_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _offline_settings(monkeypatch)
    monkeypatch.setattr(real_recovery, "RECOVERY_RUNS_ROOT", tmp_path)
    responses = [_tool_message("run_tests", {}, "first"), AIMessage(content="unreachable")]
    monkeypatch.setattr(real_recovery, "ChatOpenAI", lambda **kwargs: FailingSecondResponseModel(responses=responses))
    result = run_model_task("real-recovery-csv-row")
    report = json.loads(Path(result["run_artifact"]).read_text(encoding="utf-8"))
    assert result["task_success"] is False
    assert report["completed"] is False
    assert "Injected offline model failure" in report["execution_error"]
    assert report["model_usage"]["model_invocations"] == 2
    assert report["model_usage"]["model_errors"] == 1
    assert report["model_usage"]["token_usage_status"] == "partial"
    assert report["model_usage"]["observed_tokens"]["total_tokens"] == 5
