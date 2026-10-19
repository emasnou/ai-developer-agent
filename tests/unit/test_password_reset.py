"""Conjunt de tests unitaris i d'integració per al mòdul password_reset."""

from datetime import datetime, timedelta, timezone
import pytest

from password_reset import (
    GENERIC_SUCCESS_MESSAGE,
    EmailService,
    ExpiredTokenError,
    InvalidTokenError,
    PasswordResetController,
    PasswordResetTokenManager,
    RateLimiter,
    UserRepository,
    validate_email_format,
)


# =====================================================================
# FIXTURES
# =====================================================================

@pytest.fixture
def strong_secret() -> str:
    return "super-secret-key-that-is-at-least-32-chars-long!"


@pytest.fixture
def token_manager(strong_secret):
    return PasswordResetTokenManager(secret_key=strong_secret)


@pytest.fixture
def user_repo():
    return UserRepository(initial_users=["usuari@exemple.com"])


@pytest.fixture
def email_service():
    return EmailService()


@pytest.fixture
def controller(user_repo, email_service, token_manager):
    return PasswordResetController(
        user_repository=user_repo,
        email_service=email_service,
        token_manager=token_manager,
        base_url="https://exemple.com/reset-password?token=",
    )


# =====================================================================
# TESTS UNITARIS - GESTIÓ DE SECRETS I ENTRADES (OWASP)
# =====================================================================

def test_token_manager_rejects_weak_or_missing_secret():
    """Valida que el gestor rebutja claus curtes o buides per reforçar OWASP A02."""
    with pytest.raises(ValueError, match="mínim 32 caràcters"):
        PasswordResetTokenManager(secret_key="clau-massa-curta")

    with pytest.raises(ValueError, match="mínim 32 caràcters"):
        PasswordResetTokenManager(secret_key="")


def test_validate_email_format():
    """Comprova la correcta validació de format d'adreces electròniques (OWASP A03/A04)."""
    assert validate_email_format("valid.user@exemple.com") is True
    assert validate_email_format("user+test@sub.domain.cat") is True

    # Formats invàlids o intents d'injecció SMTP
    assert validate_email_format("usuari_sense_arroba.com") is False
    assert validate_email_format("usuari@") is False
    assert validate_email_format("@exemple.com") is False
    assert validate_email_format("bad\r\nCc:victim@exemple.com") is False
    assert validate_email_format("") is False


# =====================================================================
# TESTS UNITARIS - GENERACIÓ I VALIDACIÓ DE TOKENS
# =====================================================================

def test_unit_1_token_generation_uniqueness_and_fifteen_minute_expiration(token_manager):
    """Test 1: Validar creació única, segura i expiració exacta de 15 minuts."""
    base_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    email = "usuari@exemple.com"

    token_1 = token_manager.generate_token(email, now=base_time)
    token_2 = token_manager.generate_token(email, now=base_time)

    # Unicitat de cada token
    assert token_1.token != token_2.token
    assert isinstance(token_1.token, str) and len(token_1.token) > 20

    # Expiració de 15 minuts
    expected_expiry = base_time + timedelta(minutes=15)
    assert token_1.expires_at == expected_expiry
    assert token_1.created_at == base_time
    assert (token_1.expires_at - token_1.created_at) == timedelta(minutes=15)


def test_unit_2_token_validation_fails_when_expired_or_tampered(token_manager):
    """Test 2: Validar que el mètode retorna fals quan expira o s'ha manipulat."""
    base_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    token_data = token_manager.generate_token("usuari@exemple.com", now=base_time)

    # Límit just abans dels 15 minuts (vàlid)
    valid_check_time = base_time + timedelta(minutes=14, seconds=59)
    is_valid, email, err = token_manager.validate_token(token_data.token, now=valid_check_time)
    assert is_valid is True
    assert email == "usuari@exemple.com"
    assert err is None

    # Token caducat
    expired_check_time = base_time + timedelta(minutes=15, seconds=1)
    is_valid_expired, _, err_msg = token_manager.validate_token(token_data.token, now=expired_check_time)
    assert is_valid_expired is False
    assert err_msg == "L'enllaç ha expirat."

    # Validació mitjançant verify_token que llença excepcions específiques
    with pytest.raises(ExpiredTokenError):
        token_manager.verify_token(token_data.token, now=expired_check_time)

    # Token manipulat (signatura alterada)
    payload_b64, sig_b64 = token_data.token.split(".")
    tampered_sig = sig_b64[:-2] + ("ab" if sig_b64[-2:] != "ab" else "cd")
    tampered_token = f"{payload_b64}.{tampered_sig}"

    is_valid_tampered, _, err_tampered = token_manager.validate_token(tampered_token, now=base_time)
    assert is_valid_tampered is False
    assert "manipulada" in err_tampered or "invàlida" in err_tampered

    with pytest.raises(InvalidTokenError):
        token_manager.verify_token(tampered_token, now=base_time)

    # Token buit o malmès
    is_valid_corrupt, _, _ = token_manager.validate_token("cadena_invalida_sense_parts", now=base_time)
    assert is_valid_corrupt is False


def test_single_use_token_revocation(token_manager):
    """Comprova que un token marcat com a utilitzat no es pot tornar a fer servir (Single-Use)."""
    base_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    token_data = token_manager.generate_token("usuari@exemple.com", now=base_time)

    # El token és vàlid inicialment
    assert token_manager.verify_token(token_data.token, now=base_time) == "usuari@exemple.com"

    # Invalidem el token (en utilitzar-lo)
    token_manager.invalidate_token(token_data.token)
    assert token_manager.is_token_revoked(token_data.token) is True

    # En tornar-lo a verificar ha de fallar com a token invàlid
    with pytest.raises(InvalidTokenError, match="utilitzat anteriorment"):
        token_manager.verify_token(token_data.token, now=base_time)


# =====================================================================
# TESTS UNITARIS - PROTECCIÓ CONTRA ENUMERACIÓ I ATACS D'ENTRADA
# =====================================================================

def test_unit_3_response_strictly_identical_for_registered_and_unregistered_emails(controller):
    """Test 3: Resposta estrictament idèntica tant si el correu existeix com si no."""
    registered_email = "usuari@exemple.com"
    unregistered_email = "desconegut@exemple.com"

    response_registered = controller.request_password_reset(registered_email)
    response_unregistered = controller.request_password_reset(unregistered_email)

    assert response_registered["status_code"] == 200
    assert response_unregistered["status_code"] == 200
    assert response_registered["message"] == GENERIC_SUCCESS_MESSAGE
    assert response_unregistered["message"] == GENERIC_SUCCESS_MESSAGE
    assert response_registered == response_unregistered


def test_request_password_reset_rejects_invalid_email(controller):
    """Comprova que les sol·licituds amb emails invàlids són rebutjades immediatament."""
    response = controller.request_password_reset("invalid-email-format")
    assert response["status_code"] == 400
    assert response["error"] == "Format de correu invàlid"


def test_rate_limiter_blocks_excessive_requests(controller):
    """Comprova que el limitador de taxa bloqueja ràfegues de sol·licituds (Email Bombing)."""
    email = "usuari@exemple.com"
    base_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # Realitzem 5 sol·licituds permeses
    for _ in range(5):
        res = controller.request_password_reset(email, now=base_time)
        assert res["status_code"] == 200

    # La 6a sol·licitud ha de ser denegada amb codi 429
    res_blocked = controller.request_password_reset(email, now=base_time)
    assert res_blocked["status_code"] == 429
    assert res_blocked["error"] == "Massa peticions"


# =====================================================================
# TESTS D'INTEGRACIÓ I FLUX COMPLET (E2E)
# =====================================================================

def test_e2e_1_full_successful_flow_within_fifteen_minutes(controller, email_service):
    """Test 1 E2E: Flux complet d'enviament, recepció i accés al formulari dins el marge."""
    now = datetime(2025, 2, 1, 9, 0, 0, tzinfo=timezone.utc)
    user_email = "usuari@exemple.com"

    response = controller.request_password_reset(user_email, now=now)
    assert response["status_code"] == 200
    assert response["message"] == GENERIC_SUCCESS_MESSAGE

    assert len(email_service.sent_emails) == 1
    sent_email = email_service.sent_emails[0]
    assert sent_email["to"] == user_email
    reset_url = sent_email["reset_link"]
    assert "https://exemple.com/reset-password?token=" in reset_url

    token = reset_url.split("token=")[1]

    # Accés al cap de 5 minuts
    access_time = now + timedelta(minutes=5)
    form_response = controller.access_reset_form(token, now=access_time)

    assert form_response["status_code"] == 200
    assert form_response["can_reset"] is True
    assert form_response["email"] == user_email

    # Completa el restabliment (Single-Use Token)
    completion_response = controller.complete_password_reset(token, "NovaContrasenyaSegura!123", now=access_time)
    assert completion_response["status_code"] == 200

    # Un segon intent amb el mateix token ha de ser rebutjat
    reused_response = controller.access_reset_form(token, now=access_time)
    assert reused_response["status_code"] == 400
    assert reused_response["can_reset"] is False


def test_e2e_2_unregistered_email_sends_no_email_and_shows_generic_success(controller, email_service):
    """Test 2 E2E: Correu desconegut no genera correu però retorna l'estat genèric d'èxit."""
    now = datetime(2025, 2, 1, 9, 0, 0, tzinfo=timezone.utc)
    unknown_email = "desconegut@exemple.com"

    response = controller.request_password_reset(unknown_email, now=now)

    assert response["status_code"] == 200
    assert response["message"] == GENERIC_SUCCESS_MESSAGE
    assert len(email_service.sent_emails) == 0


def test_scenario_3_expired_link_redirects_and_offers_new_request(controller, email_service):
    """Escenari 3: Token expirat ofereix sol·licitar-ne un de nou."""
    now = datetime(2025, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
    user_email = "usuari@exemple.com"

    controller.request_password_reset(user_email, now=now)
    token = email_service.sent_emails[0]["reset_link"].split("token=")[1]

    expired_access_time = now + timedelta(minutes=15, seconds=30)
    form_response = controller.access_reset_form(token, now=expired_access_time)

    assert form_response["status_code"] == 400
    assert form_response["can_reset"] is False
    assert form_response["can_request_new"] is True
    assert form_response["error"] == "L'enllaç ha expirat"
    assert "expirat" in form_response["message"].lower()
