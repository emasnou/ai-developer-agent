"""Tests unitaris per al servei MetricsTracker, càlcul de latències i eficiència."""

from __future__ import annotations

import json
import time
import pytest

from src.schemas.finops_schemas import TokenUsage
from src.services.finops_service import CostCalculator
from src.services.metrics_tracker import CallTrackingContext, MetricsTracker


def test_metrics_tracker_initialization() -> None:
    """Verifica que el MetricsTracker s'inicialitzi buit i amb calculadora per defecte."""
    tracker = MetricsTracker()
    assert len(tracker.records) == 0
    summary = tracker.get_summary()
    assert summary.total_calls == 0
    assert summary.total_cost_usd == 0.0
    assert summary.global_tps == 0.0


def test_calculate_tps_division_by_zero_protection() -> None:
    """Comprova que el càlcul de TPS previngui divisions per zero o valors negatius."""
    assert MetricsTracker.calculate_tps(100, 0.0) == 0.0
    assert MetricsTracker.calculate_tps(100, -1.0) == 0.0
    assert MetricsTracker.calculate_tps(0, 10.0) == 0.0
    assert MetricsTracker.calculate_tps(1000, 2.0) == 500.0


def test_record_call_explicit() -> None:
    """Verifica el registre manual d'una crida amb càlcul de cost i TPS."""
    tracker = MetricsTracker()
    usage = TokenUsage(prompt_tokens=1000, completion_tokens=500, cached_tokens=200)
    record = tracker.record_call(model_name="gemini-2.5-flash", usage=usage, duration_seconds=1.5)

    assert record.model_name == "gemini-2.5-flash"
    assert record.duration_seconds == 1.5
    assert record.usage.total_tokens == 1500
    assert record.tokens_per_second == 1000.0
    assert record.completion_tps == 333.33
    assert record.cost.total_cost > 0.0
    assert len(tracker.records) == 1


def test_track_call_context_manager() -> None:
    """Verifica la mesura automàtica de temps amb el context manager track_call."""
    tracker = MetricsTracker()
    with tracker.track_call("gemini-2.5-flash-lite") as ctx:
        assert isinstance(ctx, CallTrackingContext)
        assert ctx.model_name == "gemini-2.5-flash-lite"
        time.sleep(0.01)
        ctx.set_usage(prompt_tokens=500, completion_tokens=100)

    assert len(tracker.records) == 1
    rec = tracker.records[0]
    assert rec.duration_seconds >= 0.009
    assert rec.usage.prompt_tokens == 500
    assert rec.usage.completion_tokens == 100
    assert rec.tokens_per_second > 0.0


def test_track_call_with_predefined_usage() -> None:
    """Verifica track_call passant directament un TokenUsage previ."""
    tracker = MetricsTracker()
    usage = TokenUsage(prompt_tokens=200, completion_tokens=50)
    with tracker.track_call("gemini-2.5-flash", usage=usage) as ctx:
        assert ctx.usage.total_tokens == 250

    assert len(tracker.records) == 1
    assert tracker.records[0].usage.total_tokens == 250


def test_get_summary_aggregates_multiple_calls() -> None:
    """Verifica l'agregació correcta de múltiples crides i desglossament per model."""
    tracker = MetricsTracker()
    tracker.record_call(
        "gemini-2.5-flash",
        TokenUsage(prompt_tokens=1000, completion_tokens=200),
        duration_seconds=1.0,
    )
    tracker.record_call(
        "gemini-2.5-flash",
        TokenUsage(prompt_tokens=1000, completion_tokens=200),
        duration_seconds=1.0,
    )
    tracker.record_call(
        "gpt-4o-mini",
        TokenUsage(prompt_tokens=500, completion_tokens=100),
        duration_seconds=0.5,
    )

    summary = tracker.get_summary()
    assert summary.total_calls == 3
    assert summary.total_duration_seconds == 2.5
    assert summary.average_latency_seconds == pytest.approx(0.8333, abs=0.01)
    assert summary.total_tokens == 3000
    assert "gemini-2.5-flash" in summary.by_model
    assert "gpt-4o-mini" in summary.by_model
    assert summary.by_model["gemini-2.5-flash"]["calls"] == 2
    assert summary.by_model["gpt-4o-mini"]["calls"] == 1


def test_export_json_and_dict() -> None:
    """Verifica l'exportació correcta a diccionari i text JSON serialitzable."""
    tracker = MetricsTracker()
    tracker.record_call(
        "gemini-2.5-flash",
        TokenUsage(prompt_tokens=100, completion_tokens=50),
        duration_seconds=0.2,
    )
    data = tracker.export_dict()
    assert "summary" in data
    assert "calls" in data
    assert len(data["calls"]) == 1

    json_text = tracker.export_json()
    parsed = json.loads(json_text)
    assert parsed["summary"]["total_calls"] == 1
    assert parsed["summary"]["total_tokens"] == 150


def test_tracker_reset() -> None:
    """Verifica que el mètode reset() buidi els registres acumulats."""
    tracker = MetricsTracker()
    tracker.record_call(
        "gemini-2.5-flash",
        TokenUsage(prompt_tokens=100, completion_tokens=50),
        duration_seconds=0.1,
    )
    assert len(tracker.records) == 1
    tracker.reset()
    assert len(tracker.records) == 0
    assert tracker.get_summary().total_calls == 0
