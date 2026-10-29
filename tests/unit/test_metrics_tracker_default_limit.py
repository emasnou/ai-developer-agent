"""Proves unitàries per verificar el límit de memòria per defecte a MetricsTracker."""

from __future__ import annotations

import pytest

from src.schemas.finops_schemas import TokenUsage
from src.services.metrics_tracker import DEFAULT_MAX_RECORDS_LIMIT, MetricsTracker


def test_metrics_tracker_default_init_uses_default_limit() -> None:
    """Verifica que una nova instància de MetricsTracker adopti DEFAULT_MAX_RECORDS_LIMIT.

    Given: No s'especifica cap paràmetre max_records al constructor.
    When: S'instancia MetricsTracker().
    Then: El límit de registres és exactament DEFAULT_MAX_RECORDS_LIMIT (10000).
    """
    tracker = MetricsTracker()
    assert tracker.max_records == DEFAULT_MAX_RECORDS_LIMIT
    assert tracker.max_records == 10000
    assert len(tracker.records) == 0


def test_metrics_tracker_explicit_custom_limit() -> None:
    """Verifica que es respecti un límit personalitzat quan es passa explícitament.

    Given: S'indica max_records=25.
    When: S'instancia MetricsTracker(max_records=25).
    Then: max_records reflecteix el valor 25.
    """
    tracker = MetricsTracker(max_records=25)
    assert tracker.max_records == 25


def test_metrics_tracker_explicit_none_allows_unbounded() -> None:
    """Verifica que es pugui desactivar el límit passant explícitament max_records=None.

    Given: S'indica max_records=None de forma explícita.
    When: S'instancia MetricsTracker(max_records=None).
    Then: max_records és None.
    """
    tracker = MetricsTracker(max_records=None)
    assert tracker.max_records is None


def test_metrics_tracker_fifo_eviction_with_custom_limit() -> None:
    """Verifica l'evicció FIFO amb un llindar petit per executar-se ràpidament.

    Given: Un tracker configurat amb max_records=2.
    When: Es registren 3 crides consecutives.
    Then: El primer registre és expulsat i en queden exactament 2.
    """
    tracker = MetricsTracker(max_records=2)
    usage = TokenUsage(prompt_tokens=10, completion_tokens=20, cached_tokens=0)

    tracker.record_call(model_name="gemini-2.5-flash", usage=usage, duration_seconds=0.1)
    tracker.record_call(model_name="gemini-2.5-flash-lite", usage=usage, duration_seconds=0.2)
    assert len(tracker.records) == 2

    tracker.record_call(model_name="gemini-1.5-pro", usage=usage, duration_seconds=0.3)
    records = tracker.records
    assert len(records) == 2
    assert records[0].model_name == "gemini-2.5-flash-lite"
    assert records[1].model_name == "gemini-1.5-pro"


def test_metrics_tracker_invalid_limit_raises_value_error() -> None:
    """Verifica que valors menors o iguals a zero llancin ValueError.

    Given: Valors negatius o zero per a max_records.
    When: S'intenta instanciar MetricsTracker.
    Then: Es llança ValueError.
    """
    with pytest.raises(ValueError, match="estrictament positiu"):
        MetricsTracker(max_records=0)

    with pytest.raises(ValueError, match="estrictament positiu"):
        MetricsTracker(max_records=-10)
