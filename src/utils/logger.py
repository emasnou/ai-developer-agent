"""Mòdul centralitzat de registre i rotació de logs d'auditoria per als agents.

Aquest mòdul implementa un formatador JSON estructurat amb nivells INFO, WARNING i ERROR,
garantint la creació automàtica del directori de logs i la rotació automàtica per mida.
"""

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Formatador personalitzat per generar registres de log en format JSON estructurat."""

    def format(self, record: logging.LogRecord) -> str:
        """Converteix un LogRecord en una cadena JSON estructurada.

        Args:
            record: Registre de log generat pel sistema de logging.

        Returns:
            str: Cadena en format JSON amb timestamp, level, agent_id i message.
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "agent_id": getattr(record, "agent_id", "System"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)


class AgentLogger:
    """Gestor centralitzat de logger d'auditoria per als agents de programari."""

    _instances: Dict[str, logging.Logger] = {}

    @classmethod
    def get_logger(
        cls,
        agent_name: str,
        log_file: str = "logs/agents.log",
        max_bytes: int = 1024 * 1024,
        backup_count: int = 5,
    ) -> logging.Logger:
        """Obté o configura una instància de Logger amb rotació per mida i format JSON.

        Args:
            agent_name: Identificador únic de l'agent.
            log_file: Ruta del fitxer de log.
            max_bytes: Mida màxima en bytes abans de rotar (per defecte 1 MB).
            backup_count: Nombre màxim de fitxer de còpia de seguretat a conservar.

        Returns:
            logging.Logger: Instància configurada del logger.
        """
        if agent_name in cls._instances:
            return cls._instances[agent_name]

        logger = logging.getLogger(f"agent.{agent_name}")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        if not logger.handlers:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            handler = RotatingFileHandler(
                filename=str(log_path),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            handler.setFormatter(JSONFormatter())
            logger.addHandler(handler)

        cls._instances[agent_name] = logger
        return logger


class StructuredAgentAdapter(logging.LoggerAdapter):
    """Adaptador per injectar automàticament l'agent_id en totes les crides de log."""

    def __init__(self, logger: logging.Logger, agent_id: str):
        super().__init__(logger, {"agent_id": agent_id})

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict]:
        kwargs.setdefault("extra", {})["agent_id"] = self.extra["agent_id"]
        return msg, kwargs
