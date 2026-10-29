"""Tests unitaris per als models de telemetria i el motor de càlcul FinOps."""

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


def test_token_usage_validation_and_defaults() -> None:
    """Comprova la creació correcta de TokenUsage amb càlcul automàtic de total_tokens."""
    usage = TokenUsage(prompt_tokens=1500, completion_tokens=500)
    assert usage.prompt_tokens == 1500
    assert usage.completion_tokens == 500
    assert usage.cached_tokens == 0
    assert usage.total_tokens == 2000


def test_token_usage_rejects_negative_numbers() -> None:
    """Verifica que TokenUsage rebutgi valors negatius via Pydantic."""
    with pytest.raises(ValidationError):
        TokenUsage(prompt_tokens=-10, completion_tokens=100)

    with pytest.raises(ValidationError):
        TokenUsage(prompt_tokens=100, completion_tokens=-5)

    with pytest.raises(ValidationError):
        TokenUsage(prompt_tokens=100, completion_tokens=50, cached_tokens=-1)


def test_pricing_tier_validation() -> None:
    """Comprova la validació d'una tarifa PricingTier."""
    tier = PricingTier(
        model_name="gemini-2.5-flash",
        provider="google",
        input_cost_per_k=0.000075,
        output_cost_per_k=0.0003,
        cached_cost_per_k=0.00001875,
    )
    assert tier.model_name == "gemini-2.5-flash"
    assert tier.input_cost_per_k == 0.000075

    with pytest.raises(ValidationError):
        PricingTier(
            model_name="   ",
            provider="google",
            input_cost_per_k=0.01,
            output_cost_per_k=0.02,
        )

    with pytest.raises(ValidationError):
        PricingTier(
            model_name="model",
            provider="google",
            input_cost_per_k=-0.01,
            output_cost_per_k=0.02,
        )


def test_cost_breakdown_structure() -> None:
    """Comprova l'estructura del model CostBreakdown i la seva serialització."""
    cb = CostBreakdown(
        model_name="gemini-2.5-flash",
        input_cost=0.000112,
        output_cost=0.00015,
        cached_cost=0.0,
        total_cost=0.000262,
    )
    data = cb.model_dump()
    assert data["model_name"] == "gemini-2.5-flash"
    assert data["currency"] == "USD"
    assert data["total_cost"] == 0.000262


def test_cost_calculator_scenario_1() -> None:
    """Escenari 1: Càlcul precís de costos a partir d'un model registrat."""
    catalog = FinOpsPricingCatalog(initial_catalog={})
    catalog.register_tier(
        PricingTier(
            model_name="test-model",
            provider="custom",
            input_cost_per_k=0.001,
            output_cost_per_k=0.002,
            cached_cost_per_k=0.0005,
        )
    )
    calculator = CostCalculator(catalog=catalog)
    usage = TokenUsage(prompt_tokens=1500, completion_tokens=500)

    result = calculator.calculate_cost("test-model", usage)

    # 1500 / 1000 * 0.001 = 0.0015
    # 500 / 1000 * 0.002 = 0.001
    # Total = 0.0025
    assert result.input_cost == 0.0015
    assert result.output_cost == 0.001
    assert result.cached_cost == 0.0
    assert result.total_cost == 0.0025
    assert result.model_name == "test-model"


def test_cost_calculator_with_cached_tokens() -> None:
    """Verifica que els tokens en cau es tarifin amb el preu reduït de memòria cau."""
    catalog = FinOpsPricingCatalog(initial_catalog={})
    catalog.register_tier(
        PricingTier(
            model_name="test-cache-model",
            provider="custom",
            input_cost_per_k=0.002,
            output_cost_per_k=0.004,
            cached_cost_per_k=0.0005,
        )
    )
    calculator = CostCalculator(catalog=catalog)
    # 1000 tokens de prompt, dels quals 400 són cached
    usage = TokenUsage(prompt_tokens=1000, completion_tokens=200, cached_tokens=400)

    result = calculator.calculate_cost("test-cache-model", usage)
    # No-cached prompt: (1000 - 400) / 1000 * 0.002 = 600 * 0.000002 = 0.0012
    # Cached prompt: 400 / 1000 * 0.0005 = 0.0002
    # Output: 200 / 1000 * 0.004 = 0.0008
    # Total = 0.0012 + 0.0002 + 0.0008 = 0.0022
    assert result.input_cost == 0.0012
    assert result.cached_cost == 0.0002
    assert result.output_cost == 0.0008
    assert result.total_cost == 0.0022


def test_cost_calculator_model_not_found_error() -> None:
    """Escenari 2: Llançament de ModelPricingNotFoundError quan no es troba la tarifa."""
    calculator = CostCalculator()
    usage = TokenUsage(prompt_tokens=500, completion_tokens=100)

    with pytest.raises(ModelPricingNotFoundError) as exc_info:
        calculator.calculate_cost("model-desconegut-123", usage)

    assert "model-desconegut-123" in str(exc_info.value)


def test_pricing_catalog_file_loading_json(tmp_path: Path) -> None:
    """Comprova la càrrega de catàleg des d'un fitxer JSON."""
    json_file = tmp_path / "pricing.json"
    json_file.write_text(
        """[
            {
                "model_name": "model-json-1",
                "provider": "custom",
                "input_cost_per_k": 0.001,
                "output_cost_per_k": 0.002,
                "cached_cost_per_k": 0.0001
            }
        ]""",
        encoding="utf-8",
    )

    catalog = FinOpsPricingCatalog.from_file(json_file)
    assert catalog.has_tier("model-json-1")
    tier = catalog.get_tier("model-json-1")
    assert tier.input_cost_per_k == 0.001


def test_pricing_catalog_file_loading_yaml(tmp_path: Path) -> None:
    """Comprova la càrrega de catàleg des d'un fitxer YAML."""
    yaml_file = tmp_path / "pricing.yaml"
    yaml_file.write_text(
        """
- model_name: model-yaml-1
  provider: custom
  input_cost_per_k: 0.003
  output_cost_per_k: 0.006
  cached_cost_per_k: 0.0005
""",
        encoding="utf-8",
    )

    catalog = FinOpsPricingCatalog.from_file(yaml_file)
    assert catalog.has_tier("model-yaml-1")
    tier = catalog.get_tier("model-yaml-1")
    assert tier.output_cost_per_k == 0.006


def test_pricing_catalog_file_not_found(tmp_path: Path) -> None:
    """Comprova que es llanci FileNotFoundError si el fitxer no existeix."""
    with pytest.raises(FileNotFoundError):
        FinOpsPricingCatalog.from_file(tmp_path / "no_existeix.yaml")


def test_pricing_catalog_unsupported_format(tmp_path: Path) -> None:
    """Comprova que es llanci ValueError si l'extensió no és suportada."""
    invalid_file = tmp_path / "pricing.txt"
    invalid_file.write_text("contingut", encoding="utf-8")
    with pytest.raises(ValueError):
        FinOpsPricingCatalog.from_file(invalid_file)


def test_batch_cost_calculation() -> None:
    """Comprova el càlcul d'un lot d'usos de diferents models."""
    calculator = CostCalculator()
    batch = [
        ("gemini-2.5-flash", TokenUsage(prompt_tokens=1000, completion_tokens=1000)),
        ("gemini-2.5-flash-lite", TokenUsage(prompt_tokens=2000, completion_tokens=500)),
    ]
    results = calculator.calculate_batch_cost(batch)
    assert len(results) == 2
    assert results[0].model_name == "gemini-2.5-flash"
    assert results[1].model_name == "gemini-2.5-flash-lite"
    assert results[0].total_cost > 0
    assert results[1].total_cost > 0
