"""Offline usage aggregation, missing-data and callback integration checks."""

from uuid import uuid4

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from harness.usage import ModelUsageRecorder


def _result(message: AIMessage) -> LLMResult:
    return LLMResult(generations=[[ChatGeneration(message=message)]])


def test_prefers_standard_usage_without_double_counting_provider_metadata() -> None:
    recorder = ModelUsageRecorder()
    message = AIMessage(
        content="done",
        usage_metadata={"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        response_metadata={"token_usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}},
    )
    run_id = uuid4()
    recorder.on_llm_end(_result(message), run_id=run_id)
    recorder.on_llm_end(_result(message), run_id=run_id)
    summary = recorder.summary()
    assert summary["model_invocations"] == 1
    assert summary["observed_tokens"] == {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
    assert summary["token_usage_status"] == "complete"
    assert summary["provider_http_requests"] is None
    assert summary["cost"] is None


def test_missing_usage_is_partial_and_failed_invocation_preserves_previous_tokens() -> None:
    recorder = ModelUsageRecorder()
    recorder.on_llm_end(_result(AIMessage(content="one", response_metadata={
        "token_usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
    })), run_id=uuid4())
    recorder.on_llm_end(_result(AIMessage(content="two")), run_id=uuid4())
    recorder.on_llm_error(RuntimeError("offline injected failure"), run_id=uuid4())
    summary = recorder.summary()
    assert summary["model_invocations"] == 3
    assert summary["model_responses"] == 2
    assert summary["model_errors"] == 1
    assert summary["responses_with_usage"] == 1
    assert summary["token_usage_status"] == "partial"
    assert summary["observed_tokens"]["total_tokens"] == 5


def test_no_usage_stays_unknown_and_zero_usage_is_known() -> None:
    recorder = ModelUsageRecorder()
    assert recorder.summary()["token_usage_status"] == "no_calls"
    recorder.on_llm_end(_result(AIMessage(content="missing")), run_id=uuid4())
    assert recorder.summary()["observed_tokens"] is None
    assert recorder.summary()["token_usage_status"] == "unavailable"
    recorder.on_llm_end(_result(AIMessage(content="zero", usage_metadata={
        "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
    })), run_id=uuid4())
    assert recorder.summary()["token_usage_status"] == "partial"
    assert recorder.summary()["observed_tokens"]["total_tokens"] == 0


def test_real_callback_dispatch_accumulates_fake_chat_responses() -> None:
    recorder = ModelUsageRecorder()
    model = FakeMessagesListChatModel(responses=[AIMessage(content="offline", usage_metadata={
        "input_tokens": 4, "output_tokens": 1, "total_tokens": 5,
    })])
    model.invoke("first", config={"callbacks": [recorder]})
    model.invoke("second", config={"callbacks": [recorder]})
    summary = recorder.summary()
    assert summary["model_invocations"] == 2
    assert summary["model_responses"] == 2
    assert summary["observed_tokens"]["total_tokens"] == 10
    assert summary["token_usage_status"] == "complete"


def test_invalid_provider_counts_are_not_reported_as_complete() -> None:
    recorder = ModelUsageRecorder()
    for value in (True, -1, "3"):
        recorder.on_llm_end(_result(AIMessage(content="invalid", response_metadata={
            "token_usage": {"prompt_tokens": value, "completion_tokens": 2, "total_tokens": 5}
        })), run_id=uuid4())
    recorder.on_llm_end(_result(AIMessage(content="inconsistent", response_metadata={
        "token_usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 50}
    })), run_id=uuid4())
    assert recorder.summary()["token_usage_status"] == "unavailable"
    assert recorder.summary()["observed_tokens"] is None
