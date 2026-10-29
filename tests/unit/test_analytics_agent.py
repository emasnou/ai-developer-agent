"""Tests unitaris per a l'Agent Analític d'IA (`AnalyticsAgent`) i els seus esquemes de dades."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock
import pytest

from src.agents.analytics_agent import (
    AnalyticsAgent,
    AnalyticsProcessingError,
    AnalyticsValidationError,
)
from src.schemas.analytics_schemas import (
    AnalyticsInsight,
    AnalyticsMetric,
    AnalyticsQuery,
    AnalyticsResponse,
)


def test_analytics_query_validation_success() -> None:
    """Comprova la creació correcta d'un objecte AnalyticsQuery vàlid."""
    payload = {"temps_resposta_ms": [120, 150, 95, 300]}
    query = AnalyticsQuery(query="Analitzar latència mitjana", data_payload=payload)
    assert query.query == "Analitzar latència mitjana"
    assert query.data_payload == payload


def test_analytics_query_empty_query_raises_validation_error() -> None:
    """Comprova que una consulta buida llança un error de validació Pydantic."""
    with pytest.raises(ValueError, match="no pot estar buida"):
        AnalyticsQuery(query="   ", data_payload={"a": 1})


def test_analytics_query_empty_data_raises_validation_error() -> None:
    """Comprova que un conjunt de dades buit llança un error de validació Pydantic."""
    with pytest.raises(ValueError, match="no pot estar buit"):
        AnalyticsQuery(query="Consulta", data_payload={})


def test_analytics_agent_validation_empty_query_raises() -> None:
    """Valida que l'agent rebutgi consultes buides amb AnalyticsValidationError."""
    agent = AnalyticsAgent(llm_service=MagicMock())
    with pytest.raises(AnalyticsValidationError, match="no pot estar buida"):
        agent.validate_request("   ", data={"key": "value"})


def test_analytics_agent_validation_missing_data_raises() -> None:
    """Valida que l'agent rebutgi peticions sense dades associades."""
    agent = AnalyticsAgent(llm_service=MagicMock())
    with pytest.raises(AnalyticsValidationError, match="Cal proporcionar un conjunt de dades"):
        agent.validate_request("Pregunta vàlida", data=None)


def test_analytics_agent_validation_incompatible_data_type_raises() -> None:
    """Valida que l'agent rebutgi formats de dades incompatibles (p. ex. enters o cadenes)."""
    agent = AnalyticsAgent(llm_service=MagicMock())
    with pytest.raises(AnalyticsValidationError, match="Format de dades incompatible"):
        agent.validate_request("Pregunta", data=12345)  # type: ignore[arg-type]


def test_analytics_agent_validation_empty_dict_data_raises() -> None:
    """Valida que l'agent rebutgi diccionaris buits de dades."""
    agent = AnalyticsAgent(llm_service=MagicMock())
    with pytest.raises(AnalyticsValidationError, match="El conjunt de dades proporcionat és buit"):
        agent.validate_request("Pregunta", data={})


def test_analytics_agent_analyze_success_with_mocked_llm() -> None:
    """Verifica el flux d'anàlisi amb èxit quan el model respon amb JSON estructurat."""
    mock_llm = MagicMock()
    mock_response = {
        "status": "success",
        "summary": "La latència mitjana s'ha reduït un 25% respecte a la setmana anterior.",
        "insights": [
            {
                "title": "Estabilitat general",
                "description": "El 95% de les crides es troben per sota dels 200 ms.",
                "severity": "positive",
                "actionable_recommendation": "Mantenir la configuració de memòria cau activa.",
            }
        ],
        "metrics": [
            {
                "name": "Latència P95",
                "value": 185.5,
                "unit": "ms",
                "trend": "down",
            }
        ],
        "metadata": {"dataset_records": 4},
    }
    mock_llm.generate_task_spec.return_value = json.dumps(mock_response)

    agent = AnalyticsAgent(llm_service=mock_llm)
    result = agent.analyze(
        query="Avaluar el rendiment de la latència",
        data={"latencies": [120, 140, 185, 110]},
    )

    assert isinstance(result, AnalyticsResponse)
    assert result.status == "success"
    assert "reduït un 25%" in result.summary
    assert len(result.insights) == 1
    assert result.insights[0].severity == "positive"
    assert len(result.metrics) == 1
    assert result.metrics[0].name == "Latència P95"
    assert result.metrics[0].value == 185.5
    mock_llm.generate_task_spec.assert_called_once()


def test_analytics_agent_analyze_propagates_processing_error_on_llm_failure() -> None:
    """Comprova que una fallada en la crida al LLM llança una excepció AnalyticsProcessingError controlada."""
    mock_llm = MagicMock()
    mock_llm.generate_task_spec.side_effect = RuntimeError("Connexió interrompuda")

    agent = AnalyticsAgent(llm_service=mock_llm)
    with pytest.raises(AnalyticsProcessingError, match="Error en comunicar amb el motor analític"):
        agent.analyze(query="Avaluar", data={"elements": [1, 2, 3]})


def test_analytics_agent_analyze_invalid_model_output_raises_processing_error() -> None:
    """Comprova que si el model retorna una sortida incomprensible es llança AnalyticsProcessingError."""
    mock_llm = MagicMock()
    mock_llm.generate_task_spec.return_value = "RESPOSTA_NO_JSON_INCOMPRENSIBLE"

    agent = AnalyticsAgent(llm_service=mock_llm)
    with pytest.raises(AnalyticsProcessingError, match="No s'ha pogut interpretar la resposta analítica"):
        agent.analyze(query="Avaluar", data={"elements": [1, 2, 3]})
