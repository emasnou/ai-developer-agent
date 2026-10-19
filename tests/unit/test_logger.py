"""Tests unitaris per al mòdul de logging centralitzat src/utils/logger.py."""

import json
import os
import pytest
from src.utils.logger import AgentAdapter, get_agent_logger, LOG_FILE_PATH, LOG_DIR


@pytest.fixture(autouse=True)
def clean_logs() -> None:
    """Neteja els fitxers de log abans i després de cada test."""
    if os.path.exists(LOG_FILE_PATH):
        os.remove(LOG_FILE_PATH)
    yield
    if os.path.exists(LOG_FILE_PATH):
        os.remove(LOG_FILE_PATH)


def test_logger_json_structure_and_levels() -> None:
    """Test 1: Verifica que s'genera una estructura JSON vàlida amb els camps requerits (INFO, WARNING, ERROR)."""
    agent_id = "TestAgent"
    base_logger = get_agent_logger(agent_id)
    logger = AgentAdapter(base_logger, {"agent_id": agent_id})

    logger.info("Missatge informatiu de prova")
    logger.warning(
        "Missatge d'advertència de prova", extra={"extra_data": {"code": 403}}
    )
    logger.error("Missatge d'error de prova")

    assert os.path.exists(LOG_FILE_PATH)

    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 3

    # Validar primer registre (INFO)
    log_1 = json.loads(lines[0])
    assert log_1["level"] == "INFO"
    assert log_1["agent_id"] == agent_id
    assert log_1["message"] == "Missatge informatiu de prova"
    assert "timestamp" in log_1

    # Validar segon registre (WARNING amb extra data)
    log_2 = json.loads(lines[1])
    assert log_2["level"] == "WARNING"
    assert log_2["agent_id"] == agent_id
    assert log_2["message"] == "Missatge d'advertència de prova"
    assert log_2.get("code") == 403

    # Validar tercer registre (ERROR)
    log_3 = json.loads(lines[2])
    assert log_3["level"] == "ERROR"
    assert log_3["agent_id"] == agent_id
    assert log_3["message"] == "Missatge d'error de prova"


def test_logger_special_characters_and_nested_structures() -> None:
    """Test 2: Comprovació del cas límit amb caràcters especials i estructures imbricades."""
    agent_id = "SpecialAgent"
    base_logger = get_agent_logger(agent_id)
    logger = AgentAdapter(base_logger, {"agent_id": agent_id})

    complex_message = (
        'Missatge amb caràcters especials: \n\t àéíóú çñ "quotes" i JSON imbricat: '
        '{"key": "value", "list": [1, 2, 3]}'
    )

    logger.info(complex_message)

    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        line = f.readline()

    # Assegurar que la línia sencera és un JSON vàlid
    parsed_log = json.loads(line)
    assert parsed_log["level"] == "INFO"
    assert parsed_log["agent_id"] == agent_id
    assert complex_message in parsed_log["message"]
