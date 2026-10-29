"""Tests unitaris per a la validació del logging i la longitud de línia a password_reset.py."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.password_reset import (
    EmailService,
    PasswordResetController,
    PasswordResetTokenManager,
    UserRepository,
    sanitize_log_input,
)


class ListLogHandler(logging.Handler):
    """Handler de registre en memòria per capturar missatges durant els tests unitaris."""

    def __init__(self) -> None:
        """Inicialitza el handler amb una llista buida de registres."""
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Afegeix el registre emès a la llista interna en memòria."""
        self.records.append(record)


def test_password_reset_source_code_max_line_length() -> None:
    """Verifica que cap línia de src/password_reset.py no superi els 100 caràcters (PEP 8 / Ruff)."""
    source_file = Path("src/password_reset.py")
    assert source_file.is_file(), "El fitxer src/password_reset.py ha d'existir."

    lines = source_file.read_text(encoding="utf-8").splitlines()
    long_lines: list[tuple[int, int, str]] = []

    for line_num, line in enumerate(lines, start=1):
        if len(line) > 100:
            long_lines.append((line_num, len(line), line))

    error_msg = "\n".join(
        f"Línia {num} ({length} caràcters): {text}" for num, length, text in long_lines
    )
    assert not long_lines, f"Detectades línies que superen els 100 caràcters:\n{error_msg}"


def test_logging_invalid_email_format_captured() -> None:
    """Comprova que un format de correu invàlid genera un registre SECURITY_EVENT complet."""
    mock_logger = MagicMock(spec=logging.Logger)
    user_repo = UserRepository()
    email_svc = EmailService()
    token_mgr = PasswordResetTokenManager(
        secret_key="clau_secreta_de_prova_amb_mes_de_32_caracters_12345",
        logger=mock_logger,
    )
    controller = PasswordResetController(
        user_repository=user_repo,
        email_service=email_svc,
        token_manager=token_mgr,
        logger=mock_logger,
    )

    response = controller.request_password_reset("invalid-email")
    assert response["status_code"] == 400

    warning_calls = [call.args[0] for call in mock_logger.warning.call_args_list if call.args]
    assert any(
        "[SECURITY_EVENT] Intent de sol·licitud amb format de correu invàlid: invalid-email"
        in msg
        for msg in warning_calls
    )


def test_logging_weak_password_captured() -> None:
    """Comprova que una contrasenya que no compleix la complexitat genera el SECURITY_EVENT."""
    mock_logger = MagicMock(spec=logging.Logger)
    user_repo = UserRepository(["user@example.com"])
    email_svc = EmailService()
    token_mgr = PasswordResetTokenManager(
        secret_key="clau_secreta_de_prova_amb_mes_de_32_caracters_12345",
        logger=mock_logger,
    )
    controller = PasswordResetController(
        user_repository=user_repo,
        email_service=email_svc,
        token_manager=token_mgr,
        logger=mock_logger,
    )

    token_data = token_mgr.generate_token("user@example.com")
    response = controller.complete_password_reset(token_data.token, "feble")
    assert response["status_code"] == 400

    warning_calls = [call.args[0] for call in mock_logger.warning.call_args_list if call.args]
    assert any(
        "[SECURITY_EVENT] Intent de restabliment amb contrasenya feble que no compleix requisits."
        in msg
        for msg in warning_calls
    )


def test_logging_non_existent_user_mitigates_enumeration() -> None:
    """Comprova que una sol·licitud per a compte no existent registra SIEM_AUDIT adequat."""
    mock_logger = MagicMock(spec=logging.Logger)
    user_repo = UserRepository()
    email_svc = EmailService()
    token_mgr = PasswordResetTokenManager(
        secret_key="clau_secreta_de_prova_amb_mes_de_32_caracters_12345",
        logger=mock_logger,
    )
    controller = PasswordResetController(
        user_repository=user_repo,
        email_service=email_svc,
        token_manager=token_mgr,
        logger=mock_logger,
    )

    response = controller.request_password_reset("noexistent@example.com")
    assert response["status_code"] == 200

    info_calls = [call.args[0] for call in mock_logger.info.call_args_list if call.args]
    assert any(
        "[SIEM_AUDIT] Sol·licitud per a compte no existent mitiga enumeració: noexistent@example.com"
        in msg
        for msg in info_calls
    )


def test_sanitize_log_input_strips_crlf() -> None:
    """Verifica que sanitize_log_input neutralitza salts de línia per prevenir Log Injection."""
    raw_input = "victim@example.com\r\n[SECURITY_EVENT] Injeccio Maliciosa"
    sanitized = sanitize_log_input(raw_input)
    assert "\r" not in sanitized
    assert "\n" not in sanitized
    assert sanitized == "victim@example.com[SECURITY_EVENT] Injeccio Maliciosa"
