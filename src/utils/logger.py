'''Mòdul centralitzat de registre i rotació de logs d auditoria per als agents.'''

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
import threading

DEFAULT_LOG_DIR: str = 'logs'
DEFAULT_LOG_FILE: str = 'logs/agents.log'
DEFAULT_MAX_BYTES: int = 1048576
DEFAULT_BACKUP_COUNT: int = 5
DEFAULT_ENCODING: str = 'utf-8'

_LOGGER_CACHE: Dict[str, AgentLoggerAdapter] = {}
_CACHE_LOCK: threading.Lock = threading.Lock()


class JsonLogFormatter(logging.Formatter):
    '''Formatter personalitzat que serialitza registres de log en JSON.'''

    def format(self, record: logging.LogRecord) -> str:
        '''Serialitza el registre de log en una cadena JSON unificada.

        Args:
            record: Registre de log generat pel sistema.

        Returns:
            str: Cadena de text en format JSON vàlid.
        '''
        agent_id = getattr(record, 'agent_id', record.name)
        log_payload: Dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'agent_id': str(agent_id),
            'message': record.getMessage(),
        }

        extra_data = getattr(record, 'extra_data', None)
        if extra_data is not None:
            log_payload['extra_data'] = extra_data

        return json.dumps(log_payload, ensure_ascii=False)


class AgentLoggerAdapter(logging.LoggerAdapter):
    '''Adaptador de registre per vincular automàticament l identificador de l agent.'''

    def process(self, msg: Any, kwargs: Any) -> Tuple[Any, Any]:
        '''Modifica els paràmetres de registre per injectar l agent_id.

        Args:
            msg: Missatge o objecte de log.
            kwargs: Arguments addicionals per a la crida de log.

        Returns:
            Tuple[Any, Any]: Missatge processat i diccionari d arguments.
        '''
        extra = kwargs.setdefault('extra', {})
        agent_id = self.extra.get('agent_id', 'UnknownAgent') if self.extra else 'UnknownAgent'
        extra['agent_id'] = agent_id
        return msg, kwargs


def _create_rotating_handler(
    file_path: str,
    max_bytes: int,
    backup_count: int,
) -> RotatingFileHandler:
    '''Crea i configura el manejador de fitxer amb rotació automàtica.

    Args:
        file_path: Ruta del fitxer de destinació dels logs.
        max_bytes: Mida màxima en bytes abans d activar la rotació.
        backup_count: Nombre de còpies de seguretat a conservar.

    Returns:
        RotatingFileHandler: Manejador rotatiu configurat amb el JsonLogFormatter.
    '''
    log_path = Path(file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding=DEFAULT_ENCODING,
    )
    handler.setFormatter(JsonLogFormatter())
    return handler


def get_agent_logger(
    agent_id: str,
    log_file: str = DEFAULT_LOG_FILE,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> AgentLoggerAdapter:
    '''Obté o inicialitza un logger estructurat per a un agent determinat.

    Args:
        agent_id: Identificador únic de l agent (ex: AnalystAgent).
        log_file: Ruta del fitxer de logs (per defecte logs/agents.log).
        max_bytes: Llindar de bytes per a la rotació (per defecte 1 MB).
        backup_count: Nombre màxim de fitxers rotats a mantenir.

    Returns:
        AgentLoggerAdapter: Instància de l adaptador de registre per a l agent.
    '''
    cache_key = f'{agent_id}::{log_file}'
    with _CACHE_LOCK:
        if cache_key in _LOGGER_CACHE:
            return _LOGGER_CACHE[cache_key]

        logger_name = f'agent.{agent_id}.{log_file}'
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        resolved_target = str(Path(log_file).resolve())
        has_matching_handler = any(
            isinstance(h, RotatingFileHandler)
            and getattr(h, 'baseFilename', None) == resolved_target
            for h in logger.handlers
        )

        if not has_matching_handler:
            handler = _create_rotating_handler(log_file, max_bytes, backup_count)
            logger.addHandler(handler)

        adapter = AgentLoggerAdapter(logger, {'agent_id': agent_id})
        _LOGGER_CACHE[cache_key] = adapter
        return adapter
