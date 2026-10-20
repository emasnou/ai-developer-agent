'''Bateria de proves unitàries i d integració per al logger d auditoria dels agents.'''

import json
from pathlib import Path
from typing import Generator
import pytest
from src.utils.logger import (
    ONE_MEGABYTE,
    AgentJsonFormatter,
    close_agent_logger,
    get_agent_logger,
)


@pytest.fixture
def temp_log_file(tmp_path: Path) -> Generator[Path, None, None]:
    '''Proporciona una ruta temporal neta per a cada prova de registre.'''
    log_path = tmp_path / 'agents.log'
    yield log_path


def test_json_log_structure_info(temp_log_file: Path) -> None:
    '''Verifica que el nivell INFO generi un JSON vàlid amb els camps requerits.'''
    logger = get_agent_logger('AnalystAgent', log_file_path=temp_log_file)
    sample_msg = 'Iniciant anàlisi de requeriment d usuari.'
    logger.info(sample_msg)

    assert temp_log_file.exists()
    content = temp_log_file.read_text(encoding='utf-8').strip()
    last_line = content.split('\n')[-1]
    parsed = json.loads(last_line)

    assert 'timestamp' in parsed
    assert parsed['level'] == 'INFO'
    assert parsed['agent_id'] == 'AnalystAgent'
    assert parsed['message'] == sample_msg
    close_agent_logger(logger)


def test_json_log_structure_warning_and_error(temp_log_file: Path) -> None:
    '''Verifica l enregistrament correcte dels nivells WARNING i ERROR.'''
    logger = get_agent_logger('DeveloperAgent', log_file_path=temp_log_file)
    warn_msg = 'Primer intent de tests fallat, reintentant auto-correcció.'
    err_msg = 'Superat el límit de reintents sense èxit.'

    logger.warning(warn_msg)
    logger.error(err_msg)

    lines = [
        line
        for line in temp_log_file.read_text(encoding='utf-8').split('\n')
        if line.strip()
    ]
    assert len(lines) >= 2

    warn_data = json.loads(lines[-2])
    assert warn_data['level'] == 'WARNING'
    assert warn_data['agent_id'] == 'DeveloperAgent'
    assert warn_data['message'] == warn_msg

    err_data = json.loads(lines[-1])
    assert err_data['level'] == 'ERROR'
    assert err_data['agent_id'] == 'DeveloperAgent'
    assert err_data['message'] == err_msg
    close_agent_logger(logger)


def test_log_message_with_special_characters_and_nested_structures(
    temp_log_file: Path,
) -> None:
    '''Comprova que caràcters especials i estructures imbricades no trenquin el JSON.'''
    logger = get_agent_logger('CodeReviewAgent', log_file_path=temp_log_file)
    complex_msg = (
        'Informe OWASP Top 10: <script>alert(1)</script> & chars: \\n, \\t, \'quotes\' '
        'Detalls: {"owasp_category": "A03", "status": "resolved"} 🤖 ¡Acció vàlida!'
    )
    logger.info(complex_msg)

    last_line = temp_log_file.read_text(encoding='utf-8').strip().split('\n')[-1]
    parsed = json.loads(last_line)

    assert parsed['level'] == 'INFO'
    assert parsed['agent_id'] == 'CodeReviewAgent'
    assert parsed['message'] == complex_msg
    close_agent_logger(logger)


def test_log_rotation_on_size_limit(tmp_path: Path) -> None:
    '''Comprova la rotació automàtica del fitxer quan supera la mida límit.'''
    small_limit_bytes = 2048
    rot_file = tmp_path / 'rotation_test.log'
    logger = get_agent_logger(
        'RotationAgent',
        log_file_path=rot_file,
        max_bytes=small_limit_bytes,
        backup_count=2,
    )

    payload_chunk = 'Dades d auditoria de prova repetitives: ' + ('Z' * 180)
    for _ in range(25):
        logger.info(payload_chunk)

    backup_rotated_file = tmp_path / 'rotation_test.log.1'
    assert rot_file.exists()
    assert backup_rotated_file.exists()
    assert backup_rotated_file.stat().st_size > 0

    for candidate in [rot_file, backup_rotated_file]:
        for line in candidate.read_text(encoding='utf-8').splitlines():
            if line.strip():
                record_json = json.loads(line)
                assert 'timestamp' in record_json
                assert record_json['agent_id'] == 'RotationAgent'

    close_agent_logger(logger)


def test_agent_workflow_simulation_rotation(tmp_path: Path) -> None:
    '''Simula el flux consecutiu d un agent fins a forçar la rotació de fitxer.'''
    e2e_log_file = tmp_path / 'agents.log'
    logger = get_agent_logger(
        'DeveloperAgent',
        log_file_path=e2e_log_file,
        max_bytes=3072,
        backup_count=3,
    )

    # 1. Inici de tasca
    logger.info('Inici de tasca: Desenvolupament de la Issue #77')
    # 2. Execució de proves
    for step in range(35):
        logger.info(f'Executant verificació #{step}: ' + ('P' * 140))
    # 3. Comentari a GitHub
    logger.info('Comentari publicat a la PR #15 amb l estat dels tests')

    assert e2e_log_file.exists()
    rotated_backup = tmp_path / 'agents.log.1'
    assert rotated_backup.exists()
    assert rotated_backup.stat().st_size > 0

    close_agent_logger(logger)
