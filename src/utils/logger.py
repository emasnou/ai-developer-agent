"""Mòdul centralitzat de registre i rotació de logs d'auditoria per als agents.

Implementa un formatador en JSON estructurat amb nivells INFO, WARNING, ERROR
i rotació automàtica de fitxers en assolir 1 MB.
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    """Formatador personalitzat per generar registres en format JSON estructurat."""

    def format(self, record: logging.LogRecord) -> str:
        """Formata un registre de log com una cadena JSON un línia.

        Args:
            record: Registre de log generat pel sistema.

        Returns:
            str: Cadena de text en format JSON.
        """
        log_entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "agent_id": getattr(record, "agent_id", "System"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


class AgentLogger:
    """Gestor centralitzat de logging per als agents del sistema."""

    def __init__(self, name: str = "AgentsAuditLogger", log_dir: str = "logs") -> None:
        """Inicialitza el logger amb rotació automàtica a 1 MB.

        Args:
            name: Nom del logger.
            log_dir: Directori on s'emmagatzemaran els fitxers de log.
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        if not self.logger.handlers:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            file_path = log_path / "agents.log"

            # Rotació a 1 MB (1024 * 1024 bytes), conservant fins a 3 còpies de respatller
            handler = RotatingFileHandler(
                str(file_path),
                maxBytes=1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setFormatter(JsonFormatter())
            self.logger.addHandler(handler)

    def info(self, message: str, agent_id: str = "System") -> None:
        """Registra un missatge informatiu.

        Args:
            message: Contingut del missatge.
            agent_id: Identificador de l'agent.
        """
        self.logger.info(message, extra={"agent_id": agent_id})

    def warning(self, message: str, agent_id: str = "System") -> None:
        """Registra un avís.

        Args:
            message: Contingut de l'avís.
            agent_id: Identificador de l'agent.
        """
        self.logger.warning(message, extra={"agent_id": agent_id})

    def error(self, message: str, agent_id: str = "System") -> None:
        """Registra un error.

        Args:
            message: Contingut de l'error.
            agent_id: Identificador de l'agent.
        """
        self.logger.error(message, extra={"agent_id": agent_id})


# Instància global compartida
agent_logger = AgentLogger()
