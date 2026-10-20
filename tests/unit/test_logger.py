"""Tests unitaris per al mòdul de logging centralitzat i rotació d'auditoria."""

import json
import logging
from pathlib import Path
from src.utils.logger import AgentLogger, StructuredAgentAdapter


def test_json_logger_structure(tmp_path):
    """Verifica que el logger genera correctament una estructura JSON vàlida amb tots els camps."""
    log_file = tmp_path / "logs" / "agents.log"
    
    base_logger = AgentLogger.get_logger("TestAgent", log_file=str(log_file))
    # Netejar instàncies prèvies per forçar el fitxer temporal
    AgentLogger._instances.clear()
    base_logger = AgentLogger.get_logger("TestAgent", log_file=str(log_file))
    
    logger = StructuredAgentAdapter(base_logger, "TestAgent")

    logger.info("Missatge d'informació de prova")
    logger.warning("Missatge d'advertència de prova")
    logger.error("Missatge d'error de prova")

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3

    # Validar nivell INFO
    data_info = json.loads(lines[0])
    assert data_info["level"] == "INFO"
    assert data_info["agent_id"] == "TestAgent"
    assert data_info["message"] == "Missatge d'informació de prova"
    assert "timestamp" in data_info

    # Validar nivell WARNING
    data_warn = json.loads(lines[1])
    assert data_warn["level"] == "WARNING"
    assert data_warn["agent_id"] == "TestAgent"
    assert data_warn["message"] == "Missatge d'advertència de prova"

    # Validar nivell ERROR
    data_err = json.loads(lines[2])
    assert data_err["level"] == "ERROR"
    assert data_err["agent_id"] == "TestAgent"
    assert data_err["message"] == "Missatge d'error de prova"


def test_json_logger_special_characters(tmp_path):
    """Verifica que missatges amb caràcters especials i estructures imbricades es registren sense trencar el JSON."""
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


def test_rotating_file_handler_limit(tmp_path):
    """Verifica la rotació automàtica del fitxer de log configurant un maxBytes reduït."""
    log_file = tmp_path / "logs" / "rotate.log"
    AgentLogger._instances.clear()
    
    # Configurem un maxBytes molt petit (ex: 200 bytes) per provar la rotació ràpidament
    base_logger = AgentLogger.get_logger("RotateAgent", log_file=str(log_file), max_bytes=200, backup_count=3)
    logger = StructuredAgentAdapter(base_logger, "RotateAgent")

    # Escrivim suficients missatges per superar els 200 bytes
    for i in range(10):
        logger.info(f"Aquest és el missatge de prova número {i} dissenyat per ocupar espai.")

    # Comprovem que s'ha generat el fitxer principal i almenys un fitxer rotat
    assert log_file.exists()
    log_dir = log_file.parent
    rotated_files = list(log_dir.glob("rotate.log.*"))
    
    assert len(rotated_files) >= 1
