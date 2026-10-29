"""Proves unitàries per als esquemes FinOps, restriccions de tokens i serveis de càlcul de costos."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.schemas import CostBreakdown, PricingTier, TokenUsage
from src.services.finops_service import (
    CostCalculator,
    FinOpsPricingCatalog,
    ModelPricingNotFoundError,
)


def test_token_usage_defaults() -> None:
    """Verifica que TokenUsage s'inicialitzi correctament amb valors per defecte."""
    usage = TokenUsage()
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.cached_tokens == 0
    assert usage.total_tokens == 0


def test_token_usage_automatic_total_calculation() -> None:
    """Verifica que el total de tokens es calculi automàticament si és zero."""
    usage = TokenUsage(prompt_tokens=150, completion_tokens=50)
    assert usage.total_tokens == 200


def test_token_usage_rejects_negative_prompt_tokens() -> None:
    """Comprova que es llanci ValidationError si prompt_tokens és menor que 0."""
    with pytest.raises(ValidationError) as exc_info:
        TokenUsage(prompt_tokens=-1)
    assert "greater than or equal to 0" in str(exc_info.value)


def test_token_usage_rejects_negative_completion_tokens() -> None:
    """Comprova que es llanci ValidationError si completion_tokens és menor que 0."""
    with pytest.raises(ValidationError) as exc_info:
        TokenUsage(completion_tokens=-5)
    assert "greater than or equal to 0" in str(exc_info.value)


def test_token_usage_rejects_negative_cached_tokens() -> None:
    """Comprova que es llanci ValidationError si cached_tokens és menor que 0."""
    with pytest.raises(ValidationError) as exc_info:
        TokenUsage(cached_tokens=-10)
    assert "greater than or equal to 0" in str(exc_info.value)


def test_token_usage_rejects_negative_total_tokens() -> None:
    """Comprova que es llanci ValidationError si total_tokens és menor que 0."""
    with pytest.raises(ValidationError) as exc_info:
        TokenUsage(total_tokens=-20)
    assert "greater than or equal to 0" in str(exc_info.value)


def test_token_usage_rejects_cached_greater_than_prompt() -> None:
    """Comprova que cached_tokens no pugui superar prompt_tokens."""
    with pytest.raises(ValidationError) as exc_info:
        TokenUsage(prompt_tokens=50, cached_tokens=100)
    assert "no pot ser superior a prompt_tokens" in str(exc_info.value)


def test_token_usage_rejects_inconsistent_total_tokens() -> None:
    """Comprova que total_tokens no pugui ser inferior a prompt_tokens + completion_tokens."""
    with pytest.raises(ValidationError) as exc_info:
        TokenUsage(prompt_tokens=50, completion_tokens=50, total_tokens=80)
    assert "no pot ser inferior a la suma" in str(exc_info.value)


def test_pricing_tier_validations() -> None:
    """Verifica que PricingTier no accepti valors negatius de cost ni noms buits."""
    tier = PricingTier(
        model_name="custom-model",
        provider="custom-provider",
        input_cost_per_k=0.001,
        output_cost_per_k=0.002,
    )
    assert tier.model_name == "custom-model"

    with pytest.raises(ValidationError):
        PricingTier(
            model_name="",
            input_cost_per_k=0.001,
            output_cost_per_k=0.002,
        )

    with pytest.raises(ValidationError):
        PricingTier(
            model_name="model",
            input_cost_per_k=-0.001,
            output_cost_per_k=0.002,
        )


def test_cost_breakdown_schema() -> None:
    """Verifica la creació i camps obligatoris de CostBreakdown."""
    breakdown = CostBreakdown(
        model_name="gemini-2.5-flash",
        input_cost=0.000075,
        output_cost=0.0003,
        cached_cost=0.0,
        total_cost=0.000375,
    )
    assert breakdown.total_cost == 0.000375
    assert breakdown.currency == "USD"


def test_finops_pricing_catalog_defaults() -> None:
    """Verifica la càrrega per defecte del catàleg de preus FinOps."""
    catalog = FinOpsPricingCatalog()
    assert catalog.has_tier("gemini-2.5-flash")
    tier = catalog.get_tier("gemini-2.5-flash")
    assert tier.provider == "google"
    assert tier.input_cost_per_k > 0


def test_finops_pricing_catalog_not_found() -> None:
    """Comprova que es llanci ModelPricingNotFoundError per a models desconeguts."""
    catalog = FinOpsPricingCatalog()
    with pytest.raises(ModelPricingNotFoundError) as exc_info:
        catalog.get_tier("model-inexistent")
    assert exc_info.value.model_name == "model-inexistent"


def test_finops_pricing_catalog_from_json(tmp_path: Path) -> None:
    """Verifica la càrrega d'un catàleg des d'un fitxer JSON aïllat a tmp_path."""
    catalog_data = [
        {
            "model_name": "test-model",
            "provider": "test-provider",
            "input_cost_per_k": 0.0001,
            "output_cost_per_k": 0.0004,
            "cached_cost_per_k": 0.00002,
        }
    ]
    json_file = tmp_path / "pricing.json"
    json_file.write_text(json.dumps(catalog_data), encoding="utf-8")

    catalog = FinOpsPricingCatalog.from_file(json_file)
    assert catalog.has_tier("test-model")
    tier = catalog.get_tier("test-model")
    assert tier.input_cost_per_k == 0.0001


def test_cost_calculator_with_and_without_cached_tokens() -> None:
    """Verifica el càlcul matemàtic exacte del cost amb i sense tokens en cau."""
    catalog = FinOpsPricingCatalog()
    calculator = CostCalculator(catalog=catalog)

    # Sense cau
    usage_no_cache = TokenUsage(prompt_tokens=1000, completion_tokens=1000)
    cost_no_cache = calculator.calculate_cost("gemini-2.5-flash", usage_no_cache)
    assert cost_no_cache.input_cost == 0.000075
    assert cost_no_cache.output_cost == 0.0003
    assert cost_no_cache.total_cost == 0.000375

    # Amb cau
    usage_cache = TokenUsage(prompt_tokens=1000, completion_tokens=1000, cached_tokens=500)
    cost_cache = calculator.calculate_cost("gemini-2.5-flash", usage_cache)
    # 500 uncached prompt * 0.000075/1000 = 0.0000375
    # 500 cached * 0.00001875/1000 = 0.000009375
    # 1000 output * 0.0003/1000 = 0.0003
    # total = 0.000346875 -> arrodonit a 6 decimals: 0.000347
    assert cost_cache.cached_cost == round(500 / 1000 * 0.00001875, 6)
    assert cost_cache.total_cost == round(0.0000375 + 0.000009375 + 0.0003, 6)


def test_cost_calculator_batch() -> None:
    """Verifica el càlcul per lots (batch) de costos FinOps."""
    calculator = CostCalculator()
    batch = [
        ("gemini-2.5-flash", TokenUsage(prompt_tokens=1000, completion_tokens=500)),
        ("gpt-4o-mini", TokenUsage(prompt_tokens=2000, completion_tokens=1000)),
    ]
    results = calculator.calculate_batch_cost(batch)
    assert len(results) == 2
    assert results[0].model_name == "gemini-2.5-flash"
    assert results[1].model_name == "gpt-4o-mini"
