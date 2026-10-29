"""Tests unitaris per a la validació de mètriques FinOps i coherència de consum de tokens."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.schemas.finops_schemas import CostBreakdown, PricingTier, TokenUsage
from src.services.finops_service import (
    CostCalculator,
    FinOpsPricingCatalog,
    ModelPricingNotFoundError,
)


def test_token_usage_auto_calculates_total_when_omitted() -> None:
    """Comprova que total_tokens es calcula automàticament si no s'especifica manualment."""
    usage = TokenUsage(prompt_tokens=150, completion_tokens=50)
    assert usage.prompt_tokens == 150
    assert usage.completion_tokens == 50
    assert usage.total_tokens == 200


def test_token_usage_allows_valid_explicit_total() -> None:
    """Comprova que total_tokens és permès quan és igual a la suma de prompt i completion."""
    usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    assert usage.total_tokens == 150


def test_token_usage_allows_larger_explicit_total() -> None:
    """Comprova que total_tokens pot ser major o igual a la suma (ex: sobrecàrrega de proveïdor)."""
    usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=180)
    assert usage.total_tokens == 180


def test_token_usage_raises_error_when_total_tokens_is_lower_than_sum() -> None:
    """Verifica que es llança ValueError quan total_tokens és inferior a la suma requerida."""
    with pytest.raises(ValueError, match="no pot ser inferior a la suma"):
        TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=120)


def test_token_usage_raises_error_when_cached_tokens_exceeds_prompt() -> None:
    """Verifica que es llança ValueError quan cached_tokens és superior a prompt_tokens."""
    with pytest.raises(ValueError, match="cached_tokens.*no pot ser superior"):
        TokenUsage(prompt_tokens=50, completion_tokens=20, cached_tokens=60)


def test_pricing_tier_validations() -> None:
    """Valida la creació i comprovació de camps no buits a PricingTier."""
    tier = PricingTier(
        model_name="gemini-2.5-flash",
        provider="google",
        input_cost_per_k=0.000075,
        output_cost_per_k=0.0003,
    )
    assert tier.model_name == "gemini-2.5-flash"
    assert tier.input_cost_per_k == 0.000075

    with pytest.raises(ValueError, match="no pot estar buit"):
        PricingTier(
            model_name="   ",
            provider="google",
            input_cost_per_k=0.01,
            output_cost_per_k=0.02,
        )


def test_cost_calculator_computes_exact_breakdown() -> None:
    """Comprova el càlcul precís de costos amb deducció de tokens en cau."""
    catalog = FinOpsPricingCatalog()
    calculator = CostCalculator(catalog=catalog)

    usage = TokenUsage(
        prompt_tokens=2000,
        completion_tokens=1000,
        cached_tokens=500,
        total_tokens=3000,
    )
    breakdown = calculator.calculate_cost("gemini-2.5-flash", usage)

    assert isinstance(breakdown, CostBreakdown)
    assert breakdown.model_name == "gemini-2.5-flash"
    assert breakdown.currency == "USD"
    assert breakdown.total_cost > 0
    assert breakdown.input_cost >= 0
    assert breakdown.cached_cost >= 0
    assert breakdown.output_cost >= 0


def test_cost_calculator_batch_processing() -> None:
    """Verifica el càlcul de costos en lot (batch)."""
    calculator = CostCalculator()
    usages = [
        ("gemini-2.5-flash", TokenUsage(prompt_tokens=1000, completion_tokens=500)),
        ("gemini-2.5-flash-lite", TokenUsage(prompt_tokens=2000, completion_tokens=200)),
    ]
    results = calculator.calculate_batch_cost(usages)
    assert len(results) == 2
    assert results[0].model_name == "gemini-2.5-flash"
    assert results[1].model_name == "gemini-2.5-flash-lite"


def test_cost_calculator_raises_on_unknown_model() -> None:
    """Verifica que es llança ModelPricingNotFoundError si el model no està al catàleg."""
    calculator = CostCalculator()
    usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
    with pytest.raises(ModelPricingNotFoundError):
        calculator.calculate_cost("model-desconegut-xyz", usage)


def test_finops_pricing_catalog_from_json_file(tmp_path: Path) -> None:
    """Comprova la càrrega del catàleg FinOps des d'un fitxer JSON aïllat amb tmp_path."""
    custom_pricing = [
        {
            "model_name": "custom-llm",
            "provider": "custom",
            "input_cost_per_k": 0.001,
            "output_cost_per_k": 0.002,
            "cached_cost_per_k": 0.0005,
        }
    ]
    json_file = tmp_path / "pricing.json"
    json_file.write_text(json.dumps(custom_pricing), encoding="utf-8")

    catalog = FinOpsPricingCatalog.from_file(json_file)
    assert catalog.has_tier("custom-llm")
    tier = catalog.get_tier("custom-llm")
    assert tier.input_cost_per_k == 0.001
