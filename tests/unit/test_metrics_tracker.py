"""Tests unitaris per al servei MetricsTracker, càlcul de latències i eficiència."""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.schemas.finops_schemas import TokenUsage
from src.services.finops_service import CostCalculator, FinOpsPricingCatalog
from src.services.llm_service import LLMService
from src.services.metrics_tracker import (
    CallTrackingContext,
    MetricsTracker,
    format_pricing_catalog_table,
    main,
)


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


def test_pricing_catalog_supports_active_gemini_3_models() -> None:
    """Verifica que el catàleg per defecte inclogui gemini-3.8-flash i gemini-3.5-flash-lite."""
    catalog = FinOpsPricingCatalog()
    assert catalog.has_tier("gemini-3.8-flash")
    assert catalog.has_tier("gemini-3.5-flash-lite")
    assert len(catalog.list_tiers()) >= 7

    calc = CostCalculator(catalog=catalog)
    usage = TokenUsage(prompt_tokens=1000, completion_tokens=500, cached_tokens=200)
    cost_primary = calc.calculate_cost("gemini-3.8-flash", usage)
    cost_fallback = calc.calculate_cost("gemini-3.5-flash-lite", usage)
    assert cost_primary.total_cost > cost_fallback.total_cost > 0.0


def test_jsonl_persistence_and_model_filtering(tmp_path: Path) -> None:
    """Verifica l'escriptura i càrrega de registres JSONL amb filtre per model."""
    metrics_file = tmp_path / "logs" / "metrics.jsonl"
    tracker = MetricsTracker()

    r1 = tracker.record_call(
        "gemini-3.8-flash",
        TokenUsage(prompt_tokens=1200, completion_tokens=300),
        duration_seconds=1.2,
    )
    r2 = tracker.record_call(
        "gemini-3.5-flash-lite",
        TokenUsage(prompt_tokens=600, completion_tokens=150),
        duration_seconds=0.6,
    )
    tracker.append_record_to_file(r1, metrics_file)
    tracker.append_record_to_file(r2, metrics_file)

    loaded_all = MetricsTracker.load_from_file(metrics_file)
    assert len(loaded_all.records) == 2
    assert loaded_all.get_summary().total_tokens == 2250

    loaded_filtered = MetricsTracker.load_from_file(metrics_file, model_filter="3.8-flash")
    assert len(loaded_filtered.records) == 1
    assert loaded_filtered.records[0].model_name == "gemini-3.8-flash"


def test_format_report_and_pricing_catalog_table() -> None:
    """Verifica el formatat visual de l'informe de telemetria i de la taula de tarifes."""
    empty_tracker = MetricsTracker()
    empty_report = empty_tracker.format_report()
    assert "No s'ha trobat cap registre de telemetria" in empty_report

    tracker = MetricsTracker()
    tracker.record_call(
        "gemini-3.8-flash",
        TokenUsage(prompt_tokens=1000, completion_tokens=500, cached_tokens=100),
        duration_seconds=1.0,
    )
    populated_report = tracker.format_report(last_n=5)
    assert "RESUM GLOBAL ACUMULAT" in populated_report
    assert "DESGLOSSAMENT PER MODEL LLM" in populated_report
    assert "DARRERES 1 CRIDES REGISTRADES" in populated_report
    assert "gemini-3.8-flash" in populated_report

    catalog_table = format_pricing_catalog_table()
    assert "CATÀLEG DE TARIFES FINOPS" in catalog_table
    assert "gemini-3.8-flash" in catalog_table
    assert "gemini-3.5-flash-lite" in catalog_table


def test_metrics_cli_main_options(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verifica el funcionament de la CLI main() amb --catalog, --json, --file i --reset."""
    metrics_file = tmp_path / "metrics.jsonl"
    tracker = MetricsTracker()
    rec = tracker.record_call(
        "gemini-3.8-flash",
        TokenUsage(prompt_tokens=400, completion_tokens=100),
        duration_seconds=0.5,
    )
    tracker.append_record_to_file(rec, metrics_file)

    assert main(["--catalog"]) == 0
    out_catalog = capsys.readouterr().out
    assert "CATÀLEG DE TARIFES FINOPS" in out_catalog

    assert main(["--file", str(metrics_file), "--json"]) == 0
    out_json = json.loads(capsys.readouterr().out)
    assert out_json["summary"]["total_calls"] == 1
    assert out_json["summary"]["total_tokens"] == 500

    assert main(["--file", str(metrics_file), "--reset"]) == 0
    assert not metrics_file.exists()


def test_llm_service_extract_token_usage_metadata_and_fallback() -> None:
    """Verifica l'extracció de tokens des de usage_metadata i l'estimació per caràcters."""
    fake_response_with_meta = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=800,
            candidates_token_count=200,
            cached_content_token_count=100,
        )
    )
    usage = LLMService._extract_token_usage(
        response=fake_response_with_meta,
        prompt="Prompt de prova",
        system_instruction="Instrucció",
        output_text="Resposta",
    )
    assert usage.prompt_tokens == 800
    assert usage.completion_tokens == 200
    assert usage.cached_tokens == 100
    assert usage.total_tokens == 1000

    fake_response_without_meta = SimpleNamespace(usage_metadata=None)
    estimated = LLMService._extract_token_usage(
        response=fake_response_without_meta,
        prompt="A" * 400,
        system_instruction="B" * 200,
        output_text="C" * 120,
    )
    assert estimated.prompt_tokens == 150
    assert estimated.completion_tokens == 30
    assert estimated.total_tokens == 180


def test_bin_ai_metrics_script_exists() -> None:
    """Verifica que l'script bash bin/ai-metrics existeixi i invoqui src.services.metrics_tracker."""
    script_path = Path(__file__).resolve().parents[2] / "bin" / "ai-metrics"
    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")
    assert "_common.sh" in content
    assert "src.services.metrics_tracker" in content
