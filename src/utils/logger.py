"""Mòdul centralitzat de logging estructurat en JSON amb rotació automàtica."""

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

LOG_DIR: str = "logs"
LOG_FILE_PATH: str = os.path.join(LOG_DIR, "agents.log")
MAX_BYTES: int = 1024 * 1024  # 1 MB
BACKUP_COUNT: int = 5


class JsonFormatter(logging.Formatter):
    """Formatador de logs personalitzat per generar sortides en format JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Formata un registre de log a una cadena JSON estricta.

        Args:
            record (logging.LogRecord): El registre de log.

        Returns:
            str: El registre formatat com a JSON.
        """
        log_entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "agent_id": getattr(record, "agent_id", "system"),
            "message": record.getMessage(),
        }
        
        # Afegir dades extra si existeixen al record
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_entry.update(record.extra_data)

        return json.dumps(log_entry, ensure_ascii=False)


def get_agent_logger(agent_id: str) -> logging.Logger:
    """Retorna una instància de logger configurada per a un agent específic.

    Args:
        agent_id (str): Identificador únic de l'agent.

    Returns:
        logging.Logger: Instància de logger configurada.
    """
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)

    logger_name = f"agent_logger_{agent_id}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    # Evitar duplicitat de handlers si ja està configurat
    if not logger.handlers:
        handler = RotatingFileHandler(
            LOG_FILE_PATH,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


class AgentAdapter(logging.LoggerAdapter):
    """Adaptador per injectar automàticament l'agent_id als missatges de log."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        """Processa el missatge i injecta l'agent_id en el context del log."""
        extra = kwargs.get("extra", {})
        extra["agent_id"] = self.extra.get("agent_id", "unknown")
        kwargs["extra"] = extra
        return msg, kwargs
