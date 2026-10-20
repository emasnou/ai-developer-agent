'''Bateria de proves unitàries i d integració per al mòdul de logging dels agents.'''

import json
from pathlib import Path
from typing import Any, Dict
import pytest

from src.utils.logger import (
    DEFAULT_MAX_BYTES,
    JsonLogFormatter,
    get_agent_logger,
)


def test_json_log_structure_all_levels(tmp_path: Path) -> None:
    '''Verifica que el logger generi una estructura JSON vàlida amb tots els camps per a INFO, WARNING i ERROR.'''
    log_file = tmp_path / 'audit_levels.log'
    logger = get_agent_logger('TestAnalystAgent', log_file=str(log_file))

    logger.info('Missatge informatiu de prova')
    logger.warning('Alerta de prova')
    logger.error('Error crític de prova')

    lines = log_file.read_text(encoding='utf-8').strip().split('\n')
    assert len(lines) == 3

    expected_levels = ['INFO', 'WARNING', 'ERROR']
    expected_messages = ['Missatge informatiu de prova', 'Alerta de prova', 'Error crític de prova']

    for line, expected_level, expected_msg in zip(lines, expected_levels, expected_messages):
        data: Dict[str, Any] = json.loads(line)
        assert 'timestamp' in data
        assert data['level'] == expected_level
        assert data['agent_id'] == 'TestAnalystAgent'
        assert data['message'] == expected_msg


def test_json_log_special_characters_and_nested_payload(tmp_path: Path) -> None:
    '''Comprova que caràcters especials, cometes, salts de línia i estructures complexes no trenquin el JSON.'''
    log_file = tmp_path / 'audit_special.log'
    logger = get_agent_logger('SecurityReviewer', log_file=str(log_file))

    special_message = 'Text amb caràcters: "cometes", \'simples\', salts \n de línia, \t tabulacions i emojis 🤖🛡️'
    logger.info(special_message, extra={'extra_data': {'pr_id': 42, 'tags': ['security', 'owasp'], 'meta': {'nested': True}}})

    lines = log_file.read_text(encoding='utf-8').strip().split('\n')
    assert len(lines) == 1

    parsed_log = json.loads(lines[0])
    assert parsed_log['agent_id'] == 'SecurityReviewer'
    assert parsed_log['message'] == special_message
    assert parsed_log['extra_data']['pr_id'] == 42
    assert parsed_log['extra_data']['meta']['nested'] is True


def test_log_rotation_on_configured_threshold(tmp_path: Path) -> None:
    '''Valida que s activi la rotació automàtica quan s assoleix el límit de bytes configurat.'''
    log_file = tmp_path / 'audit_rotation.log'
    max_threshold = 400
    logger = get_agent_logger('DeveloperAgent', log_file=str(log_file), max_bytes=max_threshold, backup_count=3)

    for i in range(25):
        logger.info(f'Iteració de registre número {i:03d} per provocar la rotació automàtica del fitxer.')

    rotated_backup = Path(str(log_file) + '.1')
    assert log_file.exists()
    assert rotated_backup.exists()

    for target in [log_file, rotated_backup]:
        content = target.read_text(encoding='utf-8').strip()
        for entry in content.split('\n'):
            if entry:
                data = json.loads(entry)
                assert data['agent_id'] == 'DeveloperAgent'
                assert 'level' in data


def test_log_rotation_one_megabyte_limit(tmp_path: Path) -> None:
    '''Simula l escriptura consecutiva d accions fins a superar 1 MB per verificar la rotació.'''
    log_file = tmp_path / 'agents.log'
    logger = get_agent_logger('AuditorAgent', log_file=str(log_file), max_bytes=DEFAULT_MAX_BYTES, backup_count=2)

    block_text = 'A' * 102400
    for idx in range(12):
        logger.info(f'Bloc gran {idx}: {block_text}')

    rotated_backup = Path(str(log_file) + '.1')
    assert log_file.exists()
    assert rotated_backup.exists()

    first_line_active = log_file.read_text(encoding='utf-8').split('\n')[0]
    first_line_backup = rotated_backup.read_text(encoding='utf-8').split('\n')[0]
    assert json.loads(first_line_active)['agent_id'] == 'AuditorAgent'
    assert json.loads(first_line_backup)['agent_id'] == 'AuditorAgent'
