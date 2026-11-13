"""Estimate observed token cost using an explicitly supplied price interval."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation


def _time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result if result.utcoffset() is not None else None


def _rate(value: object) -> Decimal | None:
    if not isinstance(value, str):
        return None
    try:
        result = Decimal(value)
    except InvalidOperation:
        return None
    return result if result.is_finite() and result >= 0 else None


def estimate_cost(
    usage: object,
    pricing: object,
    *,
    model: str | None,
    started_at: str | None,
    finished_at: str | None,
) -> dict[str, object]:
    """Estimate cost in the configured currency under one bounded price interval.

    The supplied interval must already account for provider price changes, peak
    hours, and holidays. This is not an invoice or a count of HTTP attempts.
    """
    result: dict[str, object] = {"amount": None, "currency": None, "status": "unavailable"}
    if pricing is None:
        return {**result, "status": "pricing_not_configured"}
    if not isinstance(pricing, Mapping) or not isinstance(usage, Mapping):
        return result
    if not all(
        isinstance(pricing.get(key), str) and pricing[key]
        for key in ("id", "source", "model")
    ):
        return {**result, "status": "invalid_pricing"}
    result["pricing_id"] = pricing["id"]
    currency = pricing.get("currency")
    if not isinstance(currency, str) or re.fullmatch(r"[A-Z]{3}", currency) is None:
        return {**result, "status": "invalid_pricing"}
    if model != pricing["model"]:
        return {**result, "status": "model_mismatch"}
    start, end = _time(started_at), _time(finished_at)
    valid_from, valid_until = _time(pricing.get("valid_from")), _time(pricing.get("valid_until"))
    if not all((start, end, valid_from, valid_until)):
        return {**result, "status": "price_interval_unknown"}
    if not valid_from <= start <= end < valid_until:
        return {**result, "status": "outside_price_interval"}
    if (
        usage.get("token_usage_status") != "complete"
        or usage.get("cache_usage_status") != "complete"
    ):
        return {**result, "status": "incomplete_usage"}
    tokens, cache = usage.get("observed_tokens"), usage.get("observed_cache_tokens")
    if not isinstance(tokens, Mapping) or not isinstance(cache, Mapping):
        return {**result, "status": "incomplete_usage"}
    counts = [cache.get("hit_tokens"), cache.get("miss_tokens"), tokens.get("output_tokens")]
    if not all(type(count) is int and count >= 0 for count in counts):
        return {**result, "status": "incomplete_usage"}
    if (
        type(tokens.get("input_tokens")) is not int
        or counts[0] + counts[1] != tokens["input_tokens"]
    ):
        return {**result, "status": "incomplete_usage"}
    if (
        type(tokens.get("total_tokens")) is not int
        or tokens["total_tokens"] != tokens["input_tokens"] + counts[2]
    ):
        return {**result, "status": "incomplete_usage"}
    rates = [
        _rate(pricing.get(key))
        for key in ("hit_per_million", "miss_per_million", "output_per_million")
    ]
    if any(rate is None for rate in rates):
        return {**result, "status": "invalid_pricing"}
    amount = sum(
        Decimal(count) * rate for count, rate in zip(counts, rates)
    ) / Decimal(1_000_000)
    return {**result, "amount": str(amount), "currency": currency, "status": "estimated"}
