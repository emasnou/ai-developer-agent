"""Tests unitaris per al mòdul de logging estructurat i rotació d'auditoria."""

from __future__ import annotations

import concurrent.futures
import json
import logging
from pathlib import Path

import pytest

from src.utils.logger import AgentLogger, JSONFormatter, StructuredAgentAdapter


@pytest.fixture(autouse=True)
def cleanup_logger_instances() -> None:
    """Garanteix la neteja d'instàncies abans i després de cada test."""
    AgentLogger.reset()
    yield
    AgentLogger.reset()


def test_json_formatter_structure() -> None:
    """Verifica que el formatador JSON inclogui els camps timestamp, level, agent_id i message."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="agent.TestAgent",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Missatge de prova",
        args=(),
        exc_info=None,
    )
    record.agent_id = "TestAgent"  # type: ignore[attr-defined]
    output = formatter.format(record)

    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["agent_id"] == "TestAgent"
    assert data["message"] == "Missatge de prova"
    assert "timestamp" in data


def test_agent_logger_creation_and_singleton(tmp_path: Path) -> None:
    """Comprova que AgentLogger creï el fitxer i reutilitzi la instància creada."""
    log_file = tmp_path / "logs" / "agent_test.log"
    logger1 = AgentLogger.get_logger("Agent1", log_file=str(log_file))
    logger2 = AgentLogger.get_logger("Agent1", log_file=str(log_file))

    assert logger1 is logger2
    assert log_file.parent.exists()

    adapter = StructuredAgentAdapter(logger1, "Agent1")
    adapter.info("Execució iniciada")

    # Forcem el buidat dels handlers
    for handler in logger1.handlers:
        handler.flush()

    content = log_file.read_text(encoding="utf-8")
    assert "Execució iniciada" in content
    assert "Agent1" in content


def test_agent_logger_reset_closes_handlers(tmp_path: Path) -> None:
    """Valida que reset() buidi les instàncies i desconnecti els handlers."""
    log_file = tmp_path / "logs" / "reset_test.log"
    logger = AgentLogger.get_logger("AgentReset", log_file=str(log_file))
    assert len(logger.handlers) > 0
    assert "AgentReset" in AgentLogger._instances

    AgentLogger.reset()
    assert len(AgentLogger._instances) == 0
    assert len(logger.handlers) == 0


def test_agent_logger_multithreaded_concurrency(tmp_path: Path) -> None:
    """Comprova que crides concurrents a get_logger() i reset() no provoquin condicions de cursa."""
    log_file = tmp_path / "concurrent.log"
    errors: list[Exception] = []

    def worker_action(index: int) -> None:
        try:
            name = f"ConcurrentAgent_{index % 5}"
            logger = AgentLogger.get_logger(name, log_file=str(log_file))
            adapter = StructuredAgentAdapter(logger, name)
            adapter.info(f"Acció des del thread {index}")
            if index % 3 == 0:
                AgentLogger.reset()
        except Exception as exc:
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_action, i) for i in range(50)]
        concurrent.futures.wait(futures)

    assert not errors, f"S'han produït errors de concurrència: {errors}"
