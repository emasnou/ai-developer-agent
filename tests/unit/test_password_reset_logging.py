"""Tests unitaris per verificar la protecció contra Log Injection (CWE-117) a password_reset."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

from src.password_reset import (
    EmailService,
    PasswordResetController,
    PasswordResetTokenManager,
    UserRepository,
    sanitize_log_input,
)


def test_sanitize_log_input_strips_newlines() -> None:
    """Verifica que sanitize_log_input elimini retorns de carro i salts de línia."""
    malicious = "user@example.com\r\n[SECURITY_EVENT] Fals esdeveniment injectat\n"
    cleaned = sanitize_log_input(malicious)
    assert "\r" not in cleaned
    assert "\n" not in cleaned
    assert cleaned == "user@example.com[SECURITY_EVENT] Fals esdeveniment injectat"


def test_sanitize_log_input_handles_non_string() -> None:
    """Verifica que valors no cadena retornin cadena buida de forma defensiva."""
    # Ignorem el tipat per provar robustesa defensiva en temps d'execució
    assert sanitize_log_input(None) == ""  # type: ignore[arg-type]
    assert sanitize_log_input(12345) == ""  # type: ignore[arg-type]


def test_request_password_reset_sanitizes_invalid_email_in_logs(
    tmp_path: Path,
) -> None:
    """Verifica que un email invàlid amb salts de línia sigui sanejat abans d'escriure al log."""
    user_repo = UserRepository()
    email_service = EmailService()
    token_manager = PasswordResetTokenManager(secret_key="a" * 32)
    mock_logger = MagicMock(spec=logging.Logger)

    controller = PasswordResetController(
        user_repository=user_repo,
        email_service=email_service,
        token_manager=token_manager,
        logger=mock_logger,
    )

    malicious_email = "victim@malicious.com\r\n[SIEM_AUDIT] Admin privileges granted!\n"
    response = controller.request_password_reset(malicious_email)

    assert response["status_code"] == 400
    assert response["error"] == "Format de correu invàlid"

    # Verifiquem les crides al logger
    assert mock_logger.warning.called
    warning_msg = mock_logger.warning.call_args[0][0]
    assert "\r" not in warning_msg
    assert "\n" not in warning_msg
    assert "victim@malicious.com[SIEM_AUDIT] Admin privileges granted!" in warning_msg
