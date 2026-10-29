"""Tests d'integració per a sessions d'agents i agregació de telemetria FinOps."""

from __future__ import annotations

import json
from src.schemas.finops_schemas import PricingTier, TokenUsage
from src.services.finops_service import CostCalculator, FinOpsPricingCatalog
from src.services.metrics_tracker import MetricsTracker


def test_multistep_session_with_custom_catalog_and_reporting() -> None:
    """Simula una sessió de treball multi-pas d'un agent amb diferents models i exportació."""
    catalog = FinOpsPricingCatalog()
    catalog.register_tier(
        PricingTier(
            model_name="custom-agent-model",
            provider="local",
            input_cost_per_k=0.0001,
            output_cost_per_k=0.0004,
            cached_cost_per_k=0.00002,
        )
    )
    calculator = CostCalculator(catalog=catalog)
    tracker = MetricsTracker(calculator=calculator)

    # Pas 1: Anàlisi inicial
    with tracker.track_call("gemini-2.5-flash") as step1:
        step1.set_usage(prompt_tokens=2500, completion_tokens=600, cached_tokens=500)

    # Pas 2: Generació de codi amb model personalitzat
    with tracker.track_call("custom-agent-model") as step2:
        step2.set_usage(prompt_tokens=4000, completion_tokens=1200, cached_tokens=1000)

    # Pas 3: Revisió ràpida amb model lite
    with tracker.track_call("gemini-2.5-flash-lite") as step3:
        step3.set_usage(prompt_tokens=1500, completion_tokens=300)

    summary = tracker.get_summary()
    assert summary.total_calls == 3
    assert summary.total_tokens == (3100 + 5200 + 1800)
    assert summary.total_cached_tokens == 1500
    assert summary.total_cost_usd > 0.0
    assert len(summary.by_model) == 3

    # Validació de l'exportació JSON per a auditoria FinOps
    exported_json = tracker.export_json(indent=2)
    audit_doc = json.loads(exported_json)
    assert audit_doc["summary"]["total_calls"] == 3
    assert "custom-agent-model" in audit_doc["summary"]["by_model"]
    assert audit_doc["summary"]["by_model"]["custom-agent-model"]["cached_tokens"] == 1000
    assert len(audit_doc["calls"]) == 3
