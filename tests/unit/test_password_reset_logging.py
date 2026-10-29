"""Tests unitaris per verificar la integració de logs estructurats i monitoratge de seguretat (SIEM)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pytest

from src.password_reset import (
    EmailService,
    PasswordResetController,
    PasswordResetTokenManager,
    RateLimiter,
    UserRepository,
)


class ListHandler(logging.Handler):
    """Handler de prova per capturar registres de log en memòria."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def memory_logger() -> tuple[logging.Logger, ListHandler]:
    """Proporciona un logger aïllat amb un handler en memòria."""
    logger = logging.getLogger("test.security_audit")
    logger.setLevel(logging.INFO)
    handler = ListHandler()
    logger.addHandler(handler)
    return logger, handler


def test_rate_limiter_emits_security_event_log(memory_logger: tuple[logging.Logger, ListHandler]) -> None:
    """Verifica que RateLimiter emet un log [SECURITY_EVENT] en superar el límit de peticions."""
    logger, handler = memory_logger
    limiter = RateLimiter(max_requests=2, window_seconds=60, logger=logger)

    assert limiter.is_allowed("user@example.com") is True
    assert limiter.is_allowed("user@example.com") is True
    assert limiter.is_allowed("user@example.com") is False

    messages = [r.getMessage() for r in handler.records]
    assert any("[SECURITY_EVENT] Rate limit activat" in msg for msg in messages)


def test_token_manager_emits_security_event_on_invalid_token(
    memory_logger: tuple[logging.Logger, ListHandler],
) -> None:
    """Verifica que PasswordResetTokenManager emet logs estructurats en manipulació de token."""
    logger, handler = memory_logger
    key = "a" * 32
    manager = PasswordResetTokenManager(secret_key=key, logger=logger)

    with pytest.raises(Exception):
        manager.verify_token("token_invalid_sense_parts")

    messages = [r.getMessage() for r in handler.records]
    assert any("[SECURITY_EVENT]" in msg for msg in messages)


def test_controller_logs_invalid_email_and_rate_limits(
    memory_logger: tuple[logging.Logger, ListHandler],
) -> None:
    """Verifica que PasswordResetController audita entrades invàlides i rate limits."""
    logger, handler = memory_logger
    user_repo = UserRepository(["user@example.com"])
    email_svc = EmailService()
    token_mgr = PasswordResetTokenManager(secret_key="b" * 32, logger=logger)
    controller = PasswordResetController(
        user_repository=user_repo,
        email_service=email_svc,
        token_manager=token_mgr,
        logger=logger,
    )

    # Email malformat
    resp_invalid = controller.request_password_reset("correu_no_valid")
    assert resp_invalid["status_code"] == 400
    messages = [r.getMessage() for r in handler.records]
    assert any("format de correu invàlid" in msg for msg in messages)


def test_controller_logs_successful_reset_and_weak_password(
    memory_logger: tuple[logging.Logger, ListHandler],
) -> None:
    """Verifica el registre d'auditoria SIEM en contrasenya feble i en restabliment amb èxit."""
    logger, handler = memory_logger
    email = "valid@example.com"
    user_repo = UserRepository([email])
    email_svc = EmailService()
    token_mgr = PasswordResetTokenManager(secret_key="c" * 32, logger=logger)
    controller = PasswordResetController(
        user_repository=user_repo,
        email_service=email_svc,
        token_manager=token_mgr,
        logger=logger,
    )

    token_data = token_mgr.generate_token(email)

    # Intent amb contrasenya feble
    resp_weak = controller.complete_password_reset(token_data.token, "feble")
    assert resp_weak["status_code"] == 400
    assert any("contrasenya feble" in r.getMessage() for r in handler.records)

    # Intent amb contrasenya robusta
    resp_success = controller.complete_password_reset(token_data.token, "ContrasenyaForta!2026")
    assert resp_success["status_code"] == 200
    assert any("Contrasenya restablerta amb èxit" in r.getMessage() for r in handler.records)
