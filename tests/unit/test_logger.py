"""Tests unitaris per al mòdul de logging centralitzat i rotació d'auditoria."""

from __future__ import annotations

import json
from pathlib import Path

from src.utils.logger import AgentLogger, StructuredAgentAdapter


def test_json_logger_structure(tmp_path: Path) -> None:
    """Verifica que el logger genera una estructura JSON vàlida amb tots els camps obligatoris.

    Args:
        tmp_path: Directori temporal de PyTest per aïllar l'escriptura de fitxers de log.
    """
    log_file = tmp_path / "logs" / "agents.log"

    # Buidem la memòria cau singleton per forçar la vinculació al fitxer temporal d'aquest test
    AgentLogger._instances.clear()
    base_logger = AgentLogger.get_logger("TestAgent", log_file=str(log_file))

    logger = StructuredAgentAdapter(base_logger, "TestAgent")

    logger.info("Missatge d'informació de prova")
    logger.warning("Missatge d'advertència de prova")
    logger.error("Missatge d'error de prova")

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3

    data_info = json.loads(lines[0])
    assert data_info["level"] == "INFO"
    assert data_info["agent_id"] == "TestAgent"
    assert data_info["message"] == "Missatge d'informació de prova"
    assert "timestamp" in data_info

    data_warn = json.loads(lines[1])
    assert data_warn["level"] == "WARNING"
    assert data_warn["agent_id"] == "TestAgent"
    assert data_warn["message"] == "Missatge d'advertència de prova"

    data_err = json.loads(lines[2])
    assert data_err["level"] == "ERROR"
    assert data_err["agent_id"] == "TestAgent"
    assert data_err["message"] == "Missatge d'error de prova"


def test_json_logger_special_characters(tmp_path: Path) -> None:
    """Verifica que missatges amb caràcters especials i salts de línia no trenquen el JSON.

    Args:
        tmp_path: Directori temporal de PyTest per aïllar l'escriptura de fitxers de log.
    """
    log_file = tmp_path / "logs" / "special.log"
    AgentLogger._instances.clear()
    base_logger = AgentLogger.get_logger("SpecialAgent", log_file=str(log_file))
    logger = StructuredAgentAdapter(base_logger, "SpecialAgent")

    complex_msg = 'Dades amb cometes "internes", salts de línia \n i unicode: 🤖 àéíóú'
    logger.info(complex_msg)

    assert log_file.exists()
    line = log_file.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)

    assert parsed["level"] == "INFO"
    assert parsed["agent_id"] == "SpecialAgent"
    assert parsed["message"] == complex_msg


def test_rotating_file_handler_limit(tmp_path: Path) -> None:
    """Verifica la rotació automàtica del fitxer de log configurant un max_bytes reduït.

    Args:
        tmp_path: Directori temporal de PyTest per aïllar els fitxers rotats.
    """
    log_file = tmp_path / "logs" / "rotate.log"
    AgentLogger._instances.clear()

    # Parametritzem max_bytes=200 per verificar la rotació en mil·lisegons sense I/O pesat a disc
    base_logger = AgentLogger.get_logger(
        "RotateAgent", log_file=str(log_file), max_bytes=200, backup_count=3
    )
    logger = StructuredAgentAdapter(base_logger, "RotateAgent")

    for i in range(10):
        logger.info(f"Aquest és el missatge de prova número {i} dissenyat per ocupar espai.")

    assert log_file.exists()
    log_dir = log_file.parent
    rotated_files = list(log_dir.glob("rotate.log.*"))

    assert len(rotated_files) >= 1
