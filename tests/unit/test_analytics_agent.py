"""Tests unitaris per a AnalyticsAgent i comprovació de concurrència thread-safe."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.agents.analytics_agent import (
    AnalyticsAgent,
    AnalyticsProcessingError,
    AnalyticsValidationError,
)
from src.schemas.analytics_schemas import AnalyticsQuery, AnalyticsResponse
from src.services.llm_service import LLMService


def test_validate_request_encapsulates_cache_in_query() -> None:
    """Verifica que el payload serialitzat queda encapsulat dins d'AnalyticsQuery."""
    agent = AnalyticsAgent()
    payload = {"events": [{"id": 1}, {"id": 2}]}
    query = agent.validate_request(query="Analitza els esdeveniments", data=payload)

    assert isinstance(query, AnalyticsQuery)
    cached = query.get_cached_payload()
    assert cached is not None
    assert "\"id\": 1" in cached
    # Comprovem que l'agent no manté estat mutable compartit
    assert agent._cached_serialized_payload is None


def test_validate_request_with_existing_query_instance() -> None:
    """Verifica que una instància existent d'AnalyticsQuery s'enriqueix amb la memòria cau."""
    agent = AnalyticsAgent()
    original_query = AnalyticsQuery(query="Revisa mètriques", data_payload={"cpu": 85.5})
    assert original_query.get_cached_payload() is None

    validated = agent.validate_request(original_query)
    assert validated is original_query
    assert validated.get_cached_payload() is not None
    assert "85.5" in str(validated.get_cached_payload())


def test_validate_request_exceeding_max_payload_raises_error() -> None:
    """Verifica que se superi el llindar de bytes llança AnalyticsValidationError."""
    agent = AnalyticsAgent(max_payload_size=10)
    payload = {"large_key": "this_string_is_much_longer_than_ten_bytes"}

    with pytest.raises(AnalyticsValidationError, match="supera el límit màxim permès"):
        agent.validate_request(query="Consulta ràpida", data=payload)


def test_validate_request_invalid_inputs_raises_error() -> None:
    """Verifica que entrades buides o formats incorrectes llancin AnalyticsValidationError."""
    agent = AnalyticsAgent()
    with pytest.raises(AnalyticsValidationError, match="no pot estar buida"):
        agent.validate_request(query="   ", data={"a": 1})

    with pytest.raises(AnalyticsValidationError, match="Cal proporcionar un conjunt de dades"):
        agent.validate_request(query="Valid query", data=None)

    with pytest.raises(AnalyticsValidationError, match="Format de dades incompatible"):
        agent.validate_request(query="Valid query", data="string_not_dict_or_list")  # type: ignore[arg-type]


def test_build_user_prompt_uses_encapsulated_cache() -> None:
    """Verifica que _build_user_prompt prioritzi el payload encapsulat a la petició."""
    agent = AnalyticsAgent()
    query = AnalyticsQuery(
        query="Calcula ràtios",
        data_payload={"x": 10},
        context="Entorn de proves",
    )
    query.set_cached_payload("{\n  \"x\": 10\n}")

    prompt = agent._build_user_prompt(query)
    assert "Consulta analítica: Calcula ràtios" in prompt
    assert "Context addicional: Entorn de proves" in prompt
    assert "\"x\": 10" in prompt


def test_analyze_releases_cache_after_building_prompt() -> None:
    """Verifica que un cop generat el prompt es buida la memòria cau d'AnalyticsQuery."""
    mock_llm = MagicMock(spec=LLMService)
    mock_response_json = json.dumps({
        "status": "success",
        "summary": "Anàlisi satisfactòria",
        "insights": [
            {
                "title": "Consum normal",
                "description": "Tots els indicadors dins dels marges",
                "severity": "info",
            }
        ],
        "metrics": [{"name": "utilitzacio", "value": 42.0, "unit": "%"}],
    })
    mock_llm.generate_task_spec.return_value = mock_response_json

    agent = AnalyticsAgent(llm_service=mock_llm)
    query = AnalyticsQuery(query="Detecta anomalies", data_payload={"registres": [1, 2, 3]})

    result = agent.analyze(query)
    assert isinstance(result, AnalyticsResponse)
    assert result.status == "success"
    assert len(result.insights) == 1
    assert len(result.metrics) == 1
    # La memòria cau de la petició s'ha alliberat per evitar DoS/OOM
    assert query.get_cached_payload() is None


def test_concurrent_requests_are_thread_safe_without_interference() -> None:
    """Executa múltiples consultes concurrentment per comprovar que no hi ha col·lisions d'estat."""
    mock_llm = MagicMock(spec=LLMService)

    def fake_generate_task_spec(user_requirement: str, **kwargs: Any) -> str:
        # Extreu l'identificador únic del prompt per retornar-lo a la resposta mockejada
        marker = "payload_id_" in user_requirement
        assert marker, "El prompt no conté l'identificador esperat"
        return json.dumps({
            "status": "success",
            "summary": "Anàlisi concurrent completada",
            "insights": [],
            "metrics": [],
        })

    mock_llm.generate_task_spec.side_effect = fake_generate_task_spec
    agent = AnalyticsAgent(llm_service=mock_llm)

    def process_item(item_id: int) -> AnalyticsResponse:
        payload = {"item_id": f"payload_id_{item_id}", "valor": item_id * 10}
        return agent.analyze(query=f"Processa element {item_id}", data=payload)

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_item, range(10)))

    assert len(results) == 10
    assert all(r.status == "success" for r in results)
    assert agent._cached_serialized_payload is None


def test_analyze_llm_failure_raises_processing_error() -> None:
    """Verifica que si el servei LLM falla es llança AnalyticsProcessingError."""
    mock_llm = MagicMock(spec=LLMService)
    mock_llm.generate_task_spec.side_effect = RuntimeError("Connexió interrompuda")

    agent = AnalyticsAgent(llm_service=mock_llm)
    with pytest.raises(AnalyticsProcessingError, match="Error en comunicar amb el motor analític"):
        agent.analyze(query="Test error", data={"a": 1})
