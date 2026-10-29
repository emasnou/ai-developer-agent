"""Tests unitaris per a la validació d'esquemes i càlculs de mètriques FinOps."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.schemas.finops_schemas import CostBreakdown, PricingTier, TokenUsage
from src.services.finops_service import (
    CostCalculator,
    FinOpsPricingCatalog,
    ModelPricingNotFoundError,
)


def test_token_usage_valid_instantiation() -> None:
    """Verifica que TokenUsage s'instanciï correctament quan cached_tokens <= prompt_tokens."""
    usage = TokenUsage(
        prompt_tokens=100,
        completion_tokens=40,
        cached_tokens=30,
    )
    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 40
    assert usage.cached_tokens == 30
    assert usage.total_tokens == 140


def test_token_usage_cached_equals_prompt() -> None:
    """Comprova que sigui vàlid que cached_tokens sigui exactament igual a prompt_tokens."""
    usage = TokenUsage(
        prompt_tokens=80,
        completion_tokens=20,
        cached_tokens=80,
    )
    assert usage.cached_tokens == usage.prompt_tokens
    assert usage.total_tokens == 100


def test_token_usage_rejects_cached_greater_than_prompt() -> None:
    """Valida que es llanci una ValidationError si cached_tokens és superior a prompt_tokens."""
    with pytest.raises(ValidationError) as exc_info:
        TokenUsage(
            prompt_tokens=50,
            completion_tokens=20,
            cached_tokens=60,
        )
    error_str = str(exc_info.value)
    assert "cached_tokens" in error_str
    assert "no pot ser superior a prompt_tokens" in error_str


def test_token_usage_preserves_explicit_total() -> None:
    """Verifica que es respecti el total_tokens explícit si no és zero."""
    usage = TokenUsage(
        prompt_tokens=100,
        completion_tokens=50,
        cached_tokens=0,
        total_tokens=160,
    )
    assert usage.total_tokens == 160


def test_pricing_tier_validation_and_empty_check() -> None:
    """Comprova les restriccions i neteja d'identificadors a PricingTier."""
    tier = PricingTier(
        model_name="gemini-2.5-flash",
        provider="google",
        input_cost_per_k=0.000075,
        output_cost_per_k=0.0003,
        cached_cost_per_k=0.00001875,
    )
    assert tier.model_name == "gemini-2.5-flash"

    with pytest.raises(ValidationError):
        PricingTier(
            model_name="   ",
            provider="google",
            input_cost_per_k=0.001,
            output_cost_per_k=0.002,
        )


def test_cost_calculator_with_cache_deduction() -> None:
    """Valida el càlcul precís FinOps deduïnt tokens en cau dels tokens d'entrada."""
    catalog = FinOpsPricingCatalog()
    calculator = CostCalculator(catalog=catalog)

    usage = TokenUsage(
        prompt_tokens=2000,
        completion_tokens=1000,
        cached_tokens=500,
    )
    breakdown = calculator.calculate_cost("gemini-2.5-flash", usage)

    tier = catalog.get_tier("gemini-2.5-flash")
    expected_input = (1500 / 1000.0) * tier.input_cost_per_k
    expected_cached = (500 / 1000.0) * tier.cached_cost_per_k
    expected_output = (1000 / 1000.0) * tier.output_cost_per_k
    expected_total = expected_input + expected_cached + expected_output

    assert breakdown.input_cost == round(expected_input, 6)
    assert breakdown.cached_cost == round(expected_cached, 6)
    assert breakdown.output_cost == round(expected_output, 6)
    assert breakdown.total_cost == round(expected_total, 6)
    assert breakdown.currency == "USD"


def test_cost_calculator_unknown_model_raises_error() -> None:
    """Verifica que es llanci ModelPricingNotFoundError per a models no registrats."""
    calculator = CostCalculator()
    usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
    with pytest.raises(ModelPricingNotFoundError):
        calculator.calculate_cost("model-inexistent", usage)


def test_catalog_from_file_json(tmp_path: Path) -> None:
    """Comprova la càrrega del catàleg de preus des d'un fitxer JSON aïllat."""
    json_content = """[
        {
            "model_name": "test-model",
            "provider": "custom",
            "input_cost_per_k": 0.001,
            "output_cost_per_k": 0.002,
            "cached_cost_per_k": 0.0005
        }
    ]"""
    cfg_file = tmp_path / "pricing.json"
    cfg_file.write_text(json_content, encoding="utf-8")

    catalog = FinOpsPricingCatalog.from_file(cfg_file)
    assert catalog.has_tier("test-model")
    tier = catalog.get_tier("test-model")
    assert tier.provider == "custom"
    assert tier.input_cost_per_k == 0.001
