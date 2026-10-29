"""Tests unitaris per a l'AnalyticsAgent i la reutilització de serialització JSON."""

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
from src.schemas.analytics_schemas import AnalyticsQuery, AnalyticsResponse


def test_analytics_agent_initialization() -> None:
    """Comprova la correcta inicialització de l'AnalyticsAgent amb paràmetres per defecte."""
    agent = AnalyticsAgent()
    assert agent.max_payload_size == 10 * 1024 * 1024
    assert agent._cached_serialized_payload is None


def test_check_payload_size_success_and_caches_value() -> None:
    """Valida que _check_payload_size retorni i guardi a la memòria cau la cadena serialitzada."""
    agent = AnalyticsAgent()
    data = {"metriques": [1, 2, 3]}
    serialized = agent._check_payload_size(data, max_allowed_bytes=1024)

    assert isinstance(serialized, str)
    assert agent._cached_serialized_payload == serialized
    assert "\"metriques\"" in serialized


def test_check_payload_size_exceeded_raises_error() -> None:
    """Verifica que se superi el límit de bytes es llanci AnalyticsValidationError."""
    agent = AnalyticsAgent()
    data = {"text": "a" * 100}
    with pytest.raises(AnalyticsValidationError, match="supera el límit màxim permès"):
        agent._check_payload_size(data, max_allowed_bytes=10)


def test_check_payload_size_unserializable_raises_error() -> None:
    """Verifica que dades no serialitzables llancin AnalyticsValidationError."""
    agent = AnalyticsAgent()
    # Un conjunt (set) no és directament serialitzable a JSON estàndard
    data = {"clau": {1, 2, 3}}
    with pytest.raises(AnalyticsValidationError, match="no és serialitzable"):
        agent._check_payload_size(data, max_allowed_bytes=1024)


def test_validate_request_with_dict_and_query_string() -> None:
    """Comprova que validate_request accepti consulta de text i diccionari de dades."""
    agent = AnalyticsAgent()
    res = agent.validate_request("Quantitat total", {"total": 42})
    assert isinstance(res, AnalyticsQuery)
    assert res.query == "Quantitat total"
    assert res.data_payload == {"total": 42}
    assert agent._cached_serialized_payload is not None


def test_validate_request_with_analytics_query_object() -> None:
    """Comprova que validate_request accepti directament un objecte AnalyticsQuery."""
    agent = AnalyticsAgent()
    query_obj = AnalyticsQuery(query="Ràtio de conversió", data_payload={"visites": 100})
    res = agent.validate_request(query_obj)
    assert res == query_obj
    assert agent._cached_serialized_payload is not None


def test_validate_request_invalid_inputs() -> None:
    """Verifica que consultes buides o dades absents llancin AnalyticsValidationError."""
    agent = AnalyticsAgent()
    with pytest.raises(AnalyticsValidationError, match="no pot estar buida"):
        agent.validate_request("   ", {"dada": 1})

    with pytest.raises(AnalyticsValidationError, match="Cal proporcionar un conjunt de dades"):
        agent.validate_request("Consulta vàlida", None)

    with pytest.raises(AnalyticsValidationError, match="Format de dades incompatible"):
        agent.validate_request("Consulta vàlida", "cadena_no_valida")  # type: ignore[arg-type]

    with pytest.raises(AnalyticsValidationError, match="és buit"):
        agent.validate_request("Consulta vàlida", {})


def test_build_user_prompt_reuses_cached_payload_without_re_serializing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Garanteix que _build_user_prompt reutilitzi la serialització prèvia sense cridar json.dumps."""
    agent = AnalyticsAgent()
    data = {"registres": [{"id": 1, "valor": 100}]}
    req = agent.validate_request("Inspeccionar registres", data)

    assert agent._cached_serialized_payload is not None
    expected_payload = agent._cached_serialized_payload

    dumps_called = False
    original_dumps = json.dumps

    def spy_dumps(*args: Any, **kwargs: Any) -> str:
        nonlocal dumps_called
        dumps_called = True
        return original_dumps(*args, **kwargs)

    monkeypatch.setattr(json, "dumps", spy_dumps)

    prompt = agent._build_user_prompt(req)
    assert not dumps_called, "json.dumps s'ha executat novament en lloc de reutilitzar la cau"
    assert expected_payload in prompt
    assert "Inspeccionar registres" in prompt


def test_build_user_prompt_with_explicit_serialized_payload() -> None:
    """Comprova que es pugui passar un payload serialitzat explícitament a _build_user_prompt."""
    agent = AnalyticsAgent()
    req = AnalyticsQuery(query="Test", data_payload={"a": 1}, context="Entorn de proves")
    custom_json = '{"a": 1, "origen": "custom"}'
    prompt = agent._build_user_prompt(req, serialized_payload=custom_json)

    assert custom_json in prompt
    assert "Context addicional: Entorn de proves" in prompt


def test_analyze_success_and_cache_cleanup() -> None:
    """Comprova el cicle complet d'analyze, la resposta esperada i la neteja de memòria cau."""
    mock_llm = MagicMock()
    fake_response_json = json.dumps({
        "status": "success",
        "summary": "Resum de vendes excel·lent",
        "insights": [{
            "title": "Creixement positiu",
            "description": "Les vendes han pujat un 15%",
            "severity": "positive",
        }],
        "metrics": [{
            "name": "creixement",
            "value": 15.0,
            "unit": "%",
        }],
    })
    mock_llm.generate_task_spec.return_value = fake_response_json

    agent = AnalyticsAgent(llm_service=mock_llm)
    result = agent.analyze("Evolució de vendes", {"mes": "gener", "total": 1000})

    assert isinstance(result, AnalyticsResponse)
    assert result.status == "success"
    assert result.summary == "Resum de vendes excel·lent"
    assert len(result.insights) == 1
    assert result.insights[0].title == "Creixement positiu"
    assert len(result.metrics) == 1
    assert result.metrics[0].value == 15.0
    # Comprovem que s'hagi alliberat la memòria cau post-execució per protegir la memòria
    assert agent._cached_serialized_payload is None


def test_analyze_llm_failure_raises_processing_error() -> None:
    """Comprova que errors en la invocació del LLM es transformin en AnalyticsProcessingError."""
    mock_llm = MagicMock()
    mock_llm.generate_task_spec.side_effect = RuntimeError("Connexió refusada pel servei LLM")

    agent = AnalyticsAgent(llm_service=mock_llm)
    with pytest.raises(AnalyticsProcessingError, match="Error en comunicar amb el motor analític"):
        agent.analyze("Consulta fallida", {"clau": "valor"})


def test_parse_model_output_invalid_json_raises_processing_error() -> None:
    """Comprova que respostes invàlides del LLM llancin AnalyticsProcessingError."""
    agent = AnalyticsAgent()
    with pytest.raises(AnalyticsProcessingError, match="No s'ha pogut interpretar"):
        agent._parse_model_output("resposta no vàlida en text pla sense json")
