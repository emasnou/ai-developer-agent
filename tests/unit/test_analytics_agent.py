"""Tests unitaris per a l'AnalyticsAgent i la validació de límits de càrrega útil (max_payload_size)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.agents.analytics_agent import (
    DEFAULT_MAX_PAYLOAD_SIZE,
    AnalyticsAgent,
    AnalyticsProcessingError,
    AnalyticsValidationError,
)
from src.schemas.analytics_schemas import AnalyticsQuery


def test_analytics_agent_default_max_payload_size() -> None:
    """Comprova que el valor per defecte de max_payload_size és 10 MB."""
    mock_llm = MagicMock()
    agent = AnalyticsAgent(llm_service=mock_llm)
    assert agent.max_payload_size == DEFAULT_MAX_PAYLOAD_SIZE
    assert agent.max_payload_size == 10 * 1024 * 1024


def test_analytics_agent_custom_max_payload_size() -> None:
    """Verifica que es pot configurar un límit de mida màxima personalitzat al constructor."""
    mock_llm = MagicMock()
    agent = AnalyticsAgent(llm_service=mock_llm, max_payload_size=500)
    assert agent.max_payload_size == 500


def test_validate_request_accepts_payload_within_limit() -> None:
    """Comprova que un payload per sota del llindar es valida satisfactòriament."""
    mock_llm = MagicMock()
    agent = AnalyticsAgent(llm_service=mock_llm, max_payload_size=1000)
    data = {"items": [{"id": 1, "name": "test"}]}
    result = agent.validate_request("Analitzar vendes", data)
    assert isinstance(result, AnalyticsQuery)
    assert result.query == "Analitzar vendes"
    assert result.data_payload == data


def test_validate_request_raises_when_payload_exceeds_limit() -> None:
    """Verifica que es llança AnalyticsValidationError quan les dades superen el límit permès."""
    mock_llm = MagicMock()
    agent = AnalyticsAgent(llm_service=mock_llm, max_payload_size=50)
    large_data = {"records": ["a" * 100]}

    with pytest.raises(AnalyticsValidationError) as exc_info:
        agent.validate_request("Consulta amb dades massives", large_data)

    assert "supera el límit màxim permès" in str(exc_info.value)
    assert "50 bytes" in str(exc_info.value)


def test_validate_request_override_limit_param() -> None:
    """Comprova que el paràmetre max_payload_size sobreescriu el valor de la instància."""
    mock_llm = MagicMock()
    # La instància permet 10000 bytes, però a la crida s'exigeix límit de 30 bytes
    agent = AnalyticsAgent(llm_service=mock_llm, max_payload_size=10000)
    data = {"key": "valor que fa més de trenta caràcters seguríssim"}

    with pytest.raises(AnalyticsValidationError) as exc_info:
        agent.validate_request("Consulta", data, max_payload_size=30)

    assert "supera el límit màxim permès de 30 bytes" in str(exc_info.value)


def test_validate_request_with_analytics_query_object_exceeding_limit() -> None:
    """Verifica la comprovació de mida quan s'introdueix directament un objecte AnalyticsQuery."""
    mock_llm = MagicMock()
    agent = AnalyticsAgent(llm_service=mock_llm, max_payload_size=40)
    query_obj = AnalyticsQuery(
        query="Consulta tipada",
        data_payload={"items": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
    )

    with pytest.raises(AnalyticsValidationError) as exc_info:
        agent.validate_request(query_obj)

    assert "supera el límit màxim permès" in str(exc_info.value)


def test_validate_request_empty_or_invalid_inputs() -> None:
    """Verifica que es llancen excepcions davant consultes o dades buides o incompatibles."""
    mock_llm = MagicMock()
    agent = AnalyticsAgent(llm_service=mock_llm)

    with pytest.raises(AnalyticsValidationError, match="buida ni ser invàlida"):
        agent.validate_request("   ", {"a": 1})

    with pytest.raises(AnalyticsValidationError, match="Cal proporcionar un conjunt de dades"):
        agent.validate_request("Vendes", None)

    with pytest.raises(AnalyticsValidationError, match="buit"):
        agent.validate_request("Vendes", {})

    with pytest.raises(AnalyticsValidationError, match="Format de dades incompatible"):
        agent.validate_request("Vendes", "string_no_permesa")  # type: ignore[arg-type]


def test_analyze_method_propagates_payload_size_limit() -> None:
    """Comprova que el mètode analyze respecta el límit de payload i atura el flux abans del LLM."""
    mock_llm = MagicMock()
    agent = AnalyticsAgent(llm_service=mock_llm, max_payload_size=25)
    data = {"long_text": "aquest text supera els 25 caràcters de sobres"}

    with pytest.raises(AnalyticsValidationError):
        agent.analyze("Consulta", data)

    # El LLM no ha de ser invocat si la petició falla la validació de mida
    mock_llm.generate_task_spec.assert_not_called()


def test_analyze_method_success_flow() -> None:
    """Verifica un flux complet d'anàlisi satisfactori amb mock de resposta del LLM."""
    mock_llm = MagicMock()
    llm_output = json.dumps({
        "status": "success",
        "summary": "Resum de les vendes trimestrals.",
        "insights": [
            {
                "title": "Creixement positiu",
                "description": "Les vendes han pujat un 15%.",
                "severity": "positive",
            }
        ],
        "metrics": [
            {
                "name": "vendes_totals",
                "value": 150000.0,
                "unit": "EUR",
                "trend": "up",
            }
        ],
    })
    mock_llm.generate_task_spec.return_value = llm_output
    agent = AnalyticsAgent(llm_service=mock_llm, max_payload_size=5000)

    response = agent.analyze("Com van anar les vendes?", {"q1": 50000, "q2": 100000})

    assert response.status == "success"
    assert response.summary == "Resum de les vendes trimestrals."
    assert len(response.insights) == 1
    assert response.insights[0].title == "Creixement positiu"
    assert len(response.metrics) == 1
    assert response.metrics[0].value == 150000.0
    mock_llm.generate_task_spec.assert_called_once()
