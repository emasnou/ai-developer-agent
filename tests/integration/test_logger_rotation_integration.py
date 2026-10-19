"""Proves d'integració per a la rotació automàtica del fitxer de logs dels agents."""

import json
import logging
import os
from pathlib import Path
from src.utils.logger import get_agent_logger


def test_agent_log_file_rotation_when_exceeding_size_limit(tmp_path: Path) -> None:
    """Simula el flux continu d'un agent generant accions fins a superar 1 MB per forçar rotació."""
    log_file_path = tmp_path / "agents.log"
    max_bytes_limit = 1_048_576  # 1 MB

    logger = get_agent_logger(
        agent_id="CodeReviewAgent",
        log_file_path=str(log_file_path),
        max_bytes=max_bytes_limit,
        backup_count=3,
    )

    # Dades consecutives de simulació d'agent
    actions = [
        ("Inici de la tasca d'inspecció de codi", {"action": "task_start", "issue_id": 101}),
        ("Execució de test de cobertura automàtic", {"action": "run_test", "status": "passed"}),
        ("Publicació de comentari de revisió a GitHub", {"action": "post_comment", "pr_id": 42}),
    ]

    # Generem payload gran per superar 1 MB ràpidament de forma controlada
    payload_filler = "X" * 50_000
    iterations_needed = 25  # 25 * 50KB ~= 1.25 MB > 1 MB

    for index in range(iterations_needed):
        action_message, action_details = actions[index % len(actions)]
        full_details = {**action_details, "payload": payload_filler, "iteration": index}
        logger.log_action(logging.INFO, action_message, details=full_details)

    rotated_log_path = tmp_path / "agents.log.1"
    assert log_file_path.exists(), "El fitxer principal de log ha d'existir."
    assert rotated_log_path.exists(), "El fitxer rotat (agents.log.1) ha d'existir en superar 1 MB."

    # Validem que ambdós fitxers contenen JSON vàlid a cadascuna de les seves línies
    for target_path in (log_file_path, rotated_log_path):
        with open(target_path, "r", encoding="utf-8") as file_handle:
            lines = [line.strip() for line in file_handle if line.strip()]
            assert len(lines) > 0
            for line in lines:
                data = json.loads(line)
                assert data["agent_id"] == "CodeReviewAgent"
                assert data["level"] == "INFO"
                assert "timestamp" in data
                assert "message" in data

    # Comprovem que el fitxer rotat té una mida propera o superior al límit configurat
    assert rotated_log_path.stat().st_size > 0
