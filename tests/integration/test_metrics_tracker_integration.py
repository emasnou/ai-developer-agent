"""Proves d'integració per a MetricsTracker, control de buffer circular i gestió de memòria."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.schemas.finops_schemas import TokenUsage
from src.services.finops_service import CostCalculator
from src.services.metrics_tracker import MetricsTracker


def test_metrics_tracker_circular_buffer_retains_fixed_maxlen(tmp_path: Path) -> None:
    """Comprova que MetricsTracker amb max_records manté exactament la capacitat configurada (FIFO)."""
    tracker = MetricsTracker(max_records=3)
    assert tracker.max_records == 3

    # Registrem 5 crides consecutives
    for i in range(1, 6):
        usage = TokenUsage(prompt_tokens=100 * i, completion_tokens=50 * i)
        tracker.record_call(model_name="gemini-2.5-flash", usage=usage, duration_seconds=1.0)

    # Només s'han de conservar les 3 darreres crides (crides 3, 4 i 5)
    records = tracker.records
    assert len(records) == 3
    assert records[0].usage.prompt_tokens == 300
    assert records[1].usage.prompt_tokens == 400
    assert records[2].usage.prompt_tokens == 500

    # El resum s'ha de calcular sobre els 3 registres vigents al buffer
    summary = tracker.get_summary()
    assert summary.total_calls == 3
    assert summary.total_prompt_tokens == 1200
    assert summary.total_completion_tokens == 600


def test_metrics_tracker_purge_oldest_removes_exact_count() -> None:
    """Verifica que purge_oldest purga els registres més antics de forma determinista."""
    tracker = MetricsTracker(max_records=10)
    for i in range(1, 5):
        usage = TokenUsage(prompt_tokens=10 * i, completion_tokens=10 * i)
        tracker.record_call(model_name="gemini-2.5-flash", usage=usage, duration_seconds=0.5)

    assert len(tracker.records) == 4
    purged = tracker.purge_oldest(2)
    assert purged == 2
    remaining = tracker.records
    assert len(remaining) == 2
    # Els restants han de ser el 3 i el 4
    assert remaining[0].usage.prompt_tokens == 30
    assert remaining[1].usage.prompt_tokens == 40


def test_metrics_tracker_purge_oldest_handles_excessive_count() -> None:
    """Verifica que purge_oldest no falla si es demana purgar més elements dels existents."""
    tracker = MetricsTracker()
    usage = TokenUsage(prompt_tokens=50, completion_tokens=50)
    tracker.record_call(model_name="gemini-2.5-flash", usage=usage, duration_seconds=0.2)

    purged = tracker.purge_oldest(10)
    assert purged == 1
    assert len(tracker.records) == 0


def test_metrics_tracker_invalid_max_records_raises_value_error() -> None:
    """Garanteix que un valor invàlid per a max_records llança ValueError."""
    with pytest.raises(ValueError, match="strictament positiu"):
        MetricsTracker(max_records=0)

    with pytest.raises(ValueError, match="strictament positiu"):
        MetricsTracker(max_records=-5)


def test_metrics_tracker_invalid_purge_count_raises_value_error() -> None:
    """Garanteix que purgar un nombre no positiu llança ValueError."""
    tracker = MetricsTracker()
    with pytest.raises(ValueError, match="strictament positiu"):
        tracker.purge_oldest(0)

    with pytest.raises(ValueError, match="strictament positiu"):
        tracker.purge_oldest(-1)


def test_metrics_tracker_unlimited_default_preserves_all_records() -> None:
    """Comprova que amb max_records=None es conserva el comportament històric il·limitat."""
    tracker = MetricsTracker(max_records=None)
    assert tracker.max_records is None

    for _i in range(1, 10):
        usage = TokenUsage(prompt_tokens=10, completion_tokens=10)
        tracker.record_call(model_name="gemini-2.5-flash", usage=usage, duration_seconds=0.1)

    assert len(tracker.records) == 9


def test_metrics_tracker_export_and_json_with_bounded_buffer(tmp_path: Path) -> None:
    """Verifica que l'exportació en diccionari i JSON reflecteix el buffer circular correctament."""
    tracker = MetricsTracker(max_records=2)
    for i in range(1, 4):
        usage = TokenUsage(prompt_tokens=20 * i, completion_tokens=10 * i)
        tracker.record_call(model_name="gemini-2.5-flash", usage=usage, duration_seconds=0.1)

    export_dict = tracker.export_dict()
    assert export_dict["summary"]["total_calls"] == 2
    assert len(export_dict["calls"]) == 2

    json_str = tracker.export_json()
    parsed = json.loads(json_str)
    assert parsed["summary"]["total_calls"] == 2
    assert len(parsed["calls"]) == 2

    # Validació d'escriptura a disc temporal amb tmp_path (OWASP A01)
    dump_file = tmp_path / "metrics_export.json"
    dump_file.write_text(json_str, encoding="utf-8")
    assert dump_file.exists()
