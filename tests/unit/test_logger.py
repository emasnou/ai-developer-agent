"""
Tests unitaris per al mòdul de logging centralitzat (src/utils/logger.py).
"""

import json
import os
import tempfile
import pytest
from src.utils.logger import get_agent_logger


@pytest.fixture
def temp_log_file() -> str:
    """
    Fixture per crear un fitxer de log temporal durant les proves.

    Yields:
        str: Ruta al fitxer temporal de log.
    """
    fd, path = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_logger_json_format_and_levels(temp_log_file: str) -> None:
    """
    Test 1: Verificar que src/utils/logger.py genera correctament una estructura
    JSON vàlida amb els camps requerits per a INFO, WARNING i ERROR.

    Args:
        temp_log_file (str): Ruta del fitxer temporal de log proveïda per la fixture.
    """
    agent_id = "TestAgent"
    logger = get_agent_logger(agent_id=agent_id, log_file=temp_log_file)

    logger.info("Missatge informatiu de prova")
    logger.warning("Missatge d'advertència de prova")
    logger.error("Missatge d'error de prova")

    with open(temp_log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 3

    levels = ["INFO", "WARNING", "ERROR"]
    messages = [
        "Missatge informatiu de prova",
        "Missatge d'advertència de prova",
        "Missatge d'error de prova",
    ]

    for i, line in enumerate(lines):
        data = json.loads(line.strip())
        assert "timestamp" in data
        assert data["level"] == levels[i]
        assert data["agent_id"] == agent_id
        assert data["message"] == messages[i]


def test_logger_special_characters_and_nested_structures(temp_log_file: str) -> None:
    """
    Test 2: Comprovació del cas límit on el missatge conté caràcters
    especials o estructures imbricades convertides a string, assegurant
    que no trenquen el format JSON de la línia de log.

    Args:
        temp_log_file (str): Ruta del fitxer temporal de log proveïda per la fixture.
    """
    agent_id = "SpecialAgent"
    logger = get_agent_logger(agent_id=agent_id, log_file=temp_log_file)

    complex_payload = {
        "action": "test_action",
        "details": {"status": 200, "items": [1, 2, 3]},
        "unicode_chars": "ñ, ç, á, é, í, ó, ú, 🚀"
    }
    message_str = json.dumps(complex_payload, ensure_ascii=False)

    logger.info(message_str)

    with open(temp_log_file, "r", encoding="utf-8") as f:
        line = f.readline()

    # Verificar que la línia global és un JSON vàlid
    parsed_line = json.loads(line.strip())
    assert parsed_line["agent_id"] == agent_id
    assert parsed_line["level"] == "INFO"

    # Verificar que el missatge interior es pot deserialitzar correctament
    inner_data = json.loads(parsed_line["message"])
    assert inner_data["action"] == "test_action"
    assert inner_data["unicode_chars"] == "ñ, ç, á, é, í, ó, ú, 🚀"
    assert inner_data["details"]["items"] == [1, 2, 3]
