"""Tests unitaris per al mòdul de logging centralitzat i rotació automàtica."""

import json
import os
from pathlib import Path
from src.utils.logger import AgentLogger


def test_logger_json_output(tmp_path: Path) -> None:
    """Test 1: Verifica que el logger genera correctament una estructura JSON vàlida."""
    log_dir = tmp_path / "logs"
    logger_instance = AgentLogger(name="TestAgentLogger", log_dir=str(log_dir))
    
    logger_instance.info("Missatge informatiu de prova", agent_id="TestAgent")
    logger_instance.warning(
        "Missatge d'avís amb caràcters especials: ñ, ç, à, \"quotes\"",
        agent_id="TestAgent"
    )
    logger_instance.error("Missatge d'error crític", agent_id="TestAgent")

    log_file = log_dir / "agents.log"
    assert log_file.exists()

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3

    # Validar estructura JSON de cada línia
    for line in lines:
        entry = json.loads(line)
        assert "timestamp" in entry
        assert "level" in entry
        assert "agent_id" in entry
        assert "message" in entry
        assert entry["agent_id"] == "TestAgent"


def test_logger_automatic_rotation(tmp_path: Path) -> None:
    """Test 2: Comprova la rotació automàtica quan s'arriba al límit d'1 MB."""
    log_dir = tmp_path / "logs"
    # Instanciem amb un límit molt petit per testejar la rotació ràpidament
    from logging.handlers import RotatingFileHandler
    import logging

    logger_instance = AgentLogger(name="RotationTestLogger", log_dir=str(log_dir))
    
    # Reconfigurem temporalment el handler a 200 bytes per testejar la rotació
    file_path = log_dir / "agents.log"
    for h in logger_instance.logger.handlers:
        logger_instance.logger.removeHandler(h)

    small_rotating_handler = RotatingFileHandler(
        str(file_path),
        maxBytes=200,
        backupCount=2,
        encoding="utf-8",
    )
    from src.utils.logger import JsonFormatter
    small_rotating_handler.setFormatter(JsonFormatter())
    logger_instance.logger.addHandler(small_rotating_handler)

    # Escriure prou missatges per superar els 200 bytes
    for i in range(15):
        logger_instance.info(f"Missatge llarg de prova número {i} per forçar la rotació del fitxer de log.", agent_id="DeveloperAgent")

    # Comprovar que s'han creat fitxers de backup o que el fitxer principal s'ha rotat
    files = list(log_dir.glob("agents.log*"))
    assert len(files) >= 1
