"""Tests unitaris per al sistema de registre i rotació de logs d'auditoria (src.utils.logger)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Generator

import pytest

from src.utils.logger import AgentLogger, JSONFormatter, StructuredAgentAdapter


@pytest.fixture(autouse=True)
def cleanup_agent_logger_instances() -> Generator[None, None, None]:
    """Neteja i tanca tots els handlers de les instàncies d'AgentLogger abans i després de cada test."""
    AgentLogger.reset()
    yield
    AgentLogger.reset()


def test_agent_logger_creates_parent_directory_and_writes_json(tmp_path: Path) -> None:
    """Verifica que AgentLogger crea el directori de logs automàticament i escriu JSON vàlid."""
    log_file = tmp_path / "nested" / "dir" / "agent.log"
    logger = AgentLogger.get_logger("TestAgent", log_file=str(log_file))

    logger.info("Missatge d'auditoria de prova")

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["level"] == "INFO"
    assert record["message"] == "Missatge d'auditoria de prova"
    assert "timestamp" in record


def test_agent_logger_reuses_existing_singleton_instance(tmp_path: Path) -> None:
    """Verifica que get_logger reutilitza la instància existent per al mateix agent_name."""
    log_file = tmp_path / "agent.log"
    logger1 = AgentLogger.get_logger("SingleAgent", log_file=str(log_file))
    logger2 = AgentLogger.get_logger("SingleAgent", log_file=str(log_file))

    assert logger1 is logger2
    assert len(logger1.handlers) == 1


def test_agent_logger_reset_clears_instances_and_closes_handlers(tmp_path: Path) -> None:
    """Verifica que AgentLogger.reset tanca els handlers i buida el diccionari d'instàncies."""
    log_file = tmp_path / "agent.log"
    logger = AgentLogger.get_logger("ResetAgent", log_file=str(log_file))
    assert len(AgentLogger._instances) == 1

    AgentLogger.reset()

    assert len(AgentLogger._instances) == 0
    assert len(logger.handlers) == 0


def test_agent_logger_rotates_file_on_threshold(tmp_path: Path) -> None:
    """Verifica la rotació de fitxers emprant un llindar petit de bytes per evitar I/O lent."""
    log_file = tmp_path / "rotating.log"
    # Utilitzem un llindar reduït de 150 bytes per testejar la rotació en mil·lisegons
    logger = AgentLogger.get_logger(
        "RotatingAgent", log_file=str(log_file), max_bytes=150, backup_count=2
    )

    for i in range(10):
        logger.info(f"Línia de test número {i} per forçar rotació de fitxer")

    # Comprovem que s'ha generat com a mínim un fitxer rotat de còpia
    backup_file = tmp_path / "rotating.log.1"
    assert log_file.exists()
    assert backup_file.exists()


def test_structured_agent_adapter_injects_agent_id(tmp_path: Path) -> None:
    """Verifica que StructuredAgentAdapter injecta correctament el camp agent_id al registre."""
    log_file = tmp_path / "adapter.log"
    base_logger = AgentLogger.get_logger("AdapterAgent", log_file=str(log_file))
    adapter = StructuredAgentAdapter(base_logger, "CustomAgentID")

    adapter.info("Missatge amb agent identificat")

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["agent_id"] == "CustomAgentID"
    assert record["message"] == "Missatge amb agent identificat"


def test_json_formatter_formats_exception_info() -> None:
    """Verifica que JSONFormatter afegeix la traça d'excepció quan està present."""
    formatter = JSONFormatter()
    try:
        raise ValueError("Error simulat de prova")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error detectat",
            args=(),
            exc_info=sys.exc_info(),
        )

    formatted = formatter.format(record)
    data = json.loads(formatted)
    assert data["level"] == "ERROR"
    assert data["message"] == "Error detectat"
    assert "exception" in data
    assert "ValueError: Error simulat de prova" in data["exception"]
