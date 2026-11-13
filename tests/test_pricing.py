"""Check estimates are bounded by explicit pricing and complete observations."""

from copy import deepcopy

from harness.pricing import estimate_cost


def _pricing() -> dict[str, object]:
    return {
        "id": "offline-example-v1",
        "source": "offline-test",
        "model": "test-model",
        "currency": "USD",
        "valid_from": "2026-11-13T05:00:00+00:00",
        "valid_until": "2026-11-13T06:00:00+00:00",
        "hit_per_million": "0.003",
        "miss_per_million": "0.15",
        "output_per_million": "0.6",
    }


def _usage() -> dict[str, object]:
    return {
        "token_usage_status": "complete",
        "cache_usage_status": "complete",
        "observed_tokens": {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100},
        "observed_cache_tokens": {"hit_tokens": 600, "miss_tokens": 400},
    }


def _estimate(
    usage: object,
    pricing: object,
    *,
    model: str = "test-model",
    end: str = "2026-11-13T05:19:00+00:00",
) -> dict[str, object]:
    return estimate_cost(
        usage, pricing, model=model, started_at="2026-11-13T05:18:00+00:00", finished_at=end,
    )


def test_complete_usage_gets_decimal_estimate() -> None:
    result = _estimate(_usage(), _pricing())
    assert result == {
        "amount": "0.0001218", "currency": "USD", "status": "estimated",
        "pricing_id": "offline-example-v1",
    }


def test_cny_pricing_preserves_currency_in_estimate() -> None:
    pricing = _pricing()
    pricing.update(
        currency="CNY", hit_per_million="0.02", miss_per_million="1", output_per_million="4",
    )
    result = _estimate(_usage(), pricing)
    assert result["amount"] == "0.000812"
    assert result["currency"] == "CNY"


def test_incomplete_unknown_or_inconsistent_evidence_cannot_produce_estimate() -> None:
    usage = _usage()
    usage["cache_usage_status"] = "partial"
    assert _estimate(usage, _pricing())["status"] == "incomplete_usage"
    usage = _usage()
    usage["observed_cache_tokens"] = {"hit_tokens": 600, "miss_tokens": 399}
    assert _estimate(usage, _pricing())["status"] == "incomplete_usage"
    assert _estimate(_usage(), None)["status"] == "pricing_not_configured"
    assert _estimate(_usage(), _pricing(), model="other")["status"] == "model_mismatch"
    assert _estimate(
        _usage(), _pricing(), end="2026-11-13T06:00:00+00:00",
    )["status"] == "outside_price_interval"
    pricing = deepcopy(_pricing())
    pricing["valid_from"] = None
    assert _estimate(_usage(), pricing)["status"] == "price_interval_unknown"
    pricing = deepcopy(_pricing())
    pricing["output_per_million"] = "NaN"
    assert _estimate(_usage(), pricing)["status"] == "invalid_pricing"
    pricing = _pricing()
    pricing["currency"] = "dollars"
    assert _estimate(_usage(), pricing)["status"] == "invalid_pricing"
