"""Tests unitaris per a la validació d'esquemes FinOps, càlcul de costos i mètriques."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.schemas.finops_schemas import (
    CallMetricRecord,
    CostBreakdown,
    PricingTier,
    SessionSummary,
    TokenUsage,
)
from src.services.finops_service import (
    CostCalculator,
    FinOpsPricingCatalog,
    ModelPricingNotFoundError,
)
from src.services.metrics_tracker import MetricsTracker


@pytest.mark.parametrize(
    "field_name,negative_value",
    [
        ("prompt_tokens", -1),
        ("prompt_tokens", -50),
        ("completion_tokens", -1),
        ("completion_tokens", -25),
        ("cached_tokens", -1),
        ("cached_tokens", -10),
        ("total_tokens", -1),
        ("total_tokens", -100),
    ],
)
def test_token_usage_negative_values_raise_validation_error(
    field_name: str, negative_value: int
) -> None:
    """Verifica que qualsevol camp numèric amb restricció ge=0 rebutgi valors negatius.

    Args:
        field_name: Nom de l'atribut numèric de TokenUsage a testejar.
        negative_value: Valor numèric negatiu invàlid.
    """
    payload: dict[str, int] = {field_name: negative_value}
    with pytest.raises(ValidationError) as exc_info:
        TokenUsage(**payload)

    errors = exc_info.value.errors()
    assert any(err["loc"][0] == field_name for err in errors)
    assert any(
        "greater_than_equal" in err["type"] or "greater than or equal to 0" in err["msg"]
        for err in errors
    )


def test_token_usage_cached_tokens_cannot_exceed_prompt_tokens() -> None:
    """Comprova que cached_tokens no pugui superar prompt_tokens."""
    with pytest.raises(ValidationError, match="cached_tokens .* no pot ser superior"):
        TokenUsage(prompt_tokens=100, cached_tokens=150, completion_tokens=50)


def test_token_usage_total_tokens_computed_automatically() -> None:
    """Verifica que total_tokens es calculi automàticament si és zero."""
    usage = TokenUsage(prompt_tokens=200, completion_tokens=100, cached_tokens=50)
    assert usage.total_tokens == 300


def test_token_usage_manual_total_tokens_validation() -> None:
    """Verifica que total_tokens manual no pugui ser menor que la suma real."""
    with pytest.raises(ValidationError, match="total_tokens .* no pot ser inferior"):
        TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=150)

    valid_manual = TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=250)
    assert valid_manual.total_tokens == 250


def test_pricing_tier_validations() -> None:
    """Verifica les validacions d'atributs del model PricingTier."""
    tier = PricingTier(
        model_name="gemini-2.5-flash",
        provider="google",
        input_cost_per_k=0.000075,
        output_cost_per_k=0.0003,
    )
    assert tier.model_name == "gemini-2.5-flash"
    assert tier.input_cost_per_k == 0.000075

    with pytest.raises(ValidationError):
        PricingTier(
            model_name="   ",
            provider="google",
            input_cost_per_k=0.001,
            output_cost_per_k=0.002,
        )


def test_cost_calculator_gemini_pricing() -> None:
    """Valida el càlcul de cost per al model gemini-2.5-flash."""
    calculator = CostCalculator()
    usage = TokenUsage(prompt_tokens=2000, completion_tokens=1000, cached_tokens=500)

    breakdown = calculator.calculate_cost("gemini-2.5-flash", usage)

    assert breakdown.model_name == "gemini-2.5-flash"
    assert breakdown.total_cost > 0.0
    assert breakdown.currency == "USD"
    assert breakdown.input_cost == pytest.approx(1.5 * 0.000075, rel=1e-5)
    assert breakdown.cached_cost == pytest.approx(0.5 * 0.00001875, rel=1e-5)
    assert breakdown.output_cost == pytest.approx(1.0 * 0.0003, rel=1e-5)


def test_cost_calculator_unknown_model_raises_error() -> None:
    """Comprova que consultar un model desconegut llanci ModelPricingNotFoundError."""
    calculator = CostCalculator()
    usage = TokenUsage(prompt_tokens=100, completion_tokens=100)
    with pytest.raises(ModelPricingNotFoundError):
        calculator.calculate_cost("unknown-model-xyz", usage)


def test_finops_catalog_from_file_json(tmp_path: Path) -> None:
    """Verifica la càrrega del catàleg de tarifes des d'un fitxer JSON temporari."""
    catalog_file = tmp_path / "pricing.json"
    data: dict[str, Any] = {
        "custom-model": {
            "model_name": "custom-model",
            "provider": "custom",
            "input_cost_per_k": 0.01,
            "output_cost_per_k": 0.02,
            "cached_cost_per_k": 0.005,
        }
    }
    catalog_file.write_text(json.dumps(data), encoding="utf-8")

    catalog = FinOpsPricingCatalog.from_file(catalog_file)
    assert catalog.has_tier("custom-model")
    tier = catalog.get_tier("custom-model")
    assert tier.input_cost_per_k == 0.01


def test_metrics_tracker_session_summary() -> None:
    """Verifica que MetricsTracker generi un SessionSummary correcte."""
    tracker = MetricsTracker()
    usage1 = TokenUsage(prompt_tokens=1000, completion_tokens=500)
    usage2 = TokenUsage(prompt_tokens=2000, completion_tokens=1000)

    tracker.record_call("gemini-2.5-flash", usage1, duration_seconds=1.5)
    tracker.record_call("gemini-2.5-flash", usage2, duration_seconds=2.5)

    summary = tracker.get_summary()
    assert summary.total_calls == 2
    assert summary.total_tokens == 4500
    assert summary.total_prompt_tokens == 3000
    assert summary.total_completion_tokens == 1500
    assert summary.total_duration_seconds == 4.0
    assert summary.average_latency_seconds == 2.0
    assert "gemini-2.5-flash" in summary.by_model
