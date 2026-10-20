'''Mòdul centralitzat de registre i rotació de logs d auditoria per als agents.'''

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_LOG_DIR: Path = Path('logs')
DEFAULT_LOG_FILE: str = 'agents.log'
DEFAULT_LOG_PATH: Path = DEFAULT_LOG_DIR / DEFAULT_LOG_FILE
ONE_MEGABYTE: int = 1024 * 1024
DEFAULT_BACKUP_COUNT: int = 5


class AgentJsonFormatter(logging.Formatter):
    '''Formatejador que serialitza els registres en línies JSON estructurades.'''

    def format(self, record: logging.LogRecord) -> str:
        '''Serialitza el registre en una cadena de text JSON d una sola línia.

        Args:
            record: Registre de log generat pel sistema de logging.

        Returns:
            str: Cadena JSON vàlida amb els camps requerits.
        '''
        timestamp_str = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat()
        agent_id = getattr(record, 'agent_id', None)
        if not agent_id:
            agent_id = record.name.replace('agent.', '')

        log_payload: Dict[str, Any] = {
            'timestamp': timestamp_str,
            'level': record.levelname,
            'agent_id': agent_id,
            'message': record.getMessage(),
        }

        extra_data = getattr(record, 'extra_data', None)
        if isinstance(extra_data, dict):
            log_payload['extra_data'] = extra_data

        return json.dumps(log_payload, ensure_ascii=False)


def create_rotating_handler(
    file_path: Path,
    max_bytes: int = ONE_MEGABYTE,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> RotatingFileHandler:
    '''Crea i configura un manipulador amb rotació automàtica i format JSON.

    Args:
        file_path: Ruta del fitxer de registre.
        max_bytes: Mida màxima en bytes abans de rotar (per defecte 1 MB).
        backup_count: Nombre màxim de còpies de rotació mantingudes.

    Returns:
        RotatingFileHandler: Manipulador configurat.
    '''
    file_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        filename=str(file_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
    )
    handler.setFormatter(AgentJsonFormatter())
    return handler


def get_agent_logger(
    agent_id: str,
    log_file_path: Optional[Path] = None,
    max_bytes: int = ONE_MEGABYTE,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Logger:
    '''Obté o inicialitza el logger per a un agent concret.

    Args:
        agent_id: Identificador únic de l agent (ex: AnalystAgent).
        log_file_path: Ruta opcional personalitzada per al fitxer de log.
        max_bytes: Mida màxima en bytes abans de la rotació automàtica.
        backup_count: Nombre de fitxers de rotació a conservar.

    Returns:
        logging.Logger: Instància de Logger configurada amb rotació de fitxer.
    '''
    logger_name = f'agent.{agent_id}'
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    target_path = log_file_path or DEFAULT_LOG_PATH
    target_resolved = target_path.resolve()

    already_configured = False
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            if Path(handler.baseFilename).resolve() == target_resolved:
                already_configured = True
                break

    if not already_configured:
        handler = create_rotating_handler(
            file_path=target_path,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )
        logger.addHandler(handler)

    logger.propagate = False
    return logger


def close_agent_logger(logger: logging.Logger) -> None:
    '''Tanca i allibera tots els manipuladors d un logger.

    Args:
        logger: Instància de Logger a tancar.
    '''
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
