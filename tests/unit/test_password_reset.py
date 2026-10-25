"""Conjunt complet de tests unitaris i d'integració per al mòdul password_reset."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from src.password_reset import (
    GENERIC_SUCCESS_MESSAGE,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    EmailService,
    ExpiredTokenError,
    InvalidTokenError,
    PasswordResetController,
    PasswordResetTokenManager,
    RateLimiter,
    UserRepository,
    validate_email_format,
    validate_password_complexity,
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
        background_task_runner=lambda task: task(),
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

    assert validate_email_format("usuari_sense_arroba.com") is False
    assert validate_email_format("usuari@") is False
    assert validate_email_format("@exemple.com") is False
    assert validate_email_format("bad\r\nCc:victim@exemple.com") is False
    assert validate_email_format("") is False


def test_validate_password_complexity():
    """Valida les regles de complexitat segons NIST/OWASP (A07)."""
    assert validate_password_complexity("Abcdef12345!") is True
    assert validate_password_complexity("Correct-Horse-Battery-Staple-99$") is True

    assert validate_password_complexity("Curta1!") is False
    assert validate_password_complexity("A" * (PASSWORD_MAX_LENGTH + 1)) is False
    assert validate_password_complexity("sensemajuscula123!") is False
    assert validate_password_complexity("SENSEMINUSCULA123!") is False
    assert validate_password_complexity("SenseNumeroNiEspecial") is False
    assert validate_password_complexity("SenseCaràcterEspecial123") is False


def test_user_repository_stores_hashed_passwords_and_verifies():
    """Valida que les contrasenyes no s'emmagatzemen en text pla i empren scrypt."""
    repo = UserRepository()
    email = "test@exemple.com"
    raw_pwd = "ContrasenyaSegura!123"
    repo.add_user(email, initial_password=raw_pwd)

    stored = repo.get_password(email)
    assert stored is not None
    assert stored != raw_pwd
    assert "$" in stored
    assert repo.verify_password(email, raw_pwd) is True
    assert repo.verify_password(email, "PasswordIncorrecte!999") is False


# =====================================================================
# TESTS UNITARIS - GENERACIÓ, EXPIRACIÓ I PURGA DE MEMÒRIA (DoS)
# =====================================================================

def test_unit_1_token_generation_uniqueness_and_fifteen_minute_expiration(token_manager):
    """Test 1: Validar creació única, segura i expiració exacta de 15 minuts."""
    base_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    email = "usuari@exemple.com"

    token_1 = token_manager.generate_token(email, now=base_time)
    token_2 = token_manager.generate_token(email, now=base_time)

    assert token_1.token != token_2.token
    assert isinstance(token_1.token, str) and len(token_1.token) > 20

    expected_expiry = base_time + timedelta(minutes=15)
    assert token_1.expires_at == expected_expiry
    assert token_1.created_at == base_time
    assert (token_1.expires_at - token_1.created_at) == timedelta(minutes=15)


def test_unit_2_token_validation_fails_when_expired_or_tampered(token_manager):
    """Test 2: Validar que el mètode retorna fals quan expira o s'ha manipulat sense fuita d'email."""
    base_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    token_data = token_manager.generate_token("usuari@exemple.com", now=base_time)

    valid_check_time = base_time + timedelta(minutes=14, seconds=59)
    is_valid, email, err = token_manager.validate_token(token_data.token, now=valid_check_time)
    assert is_valid is True
    assert email == "usuari@exemple.com"
    assert err is None

    expired_check_time = base_time + timedelta(minutes=15, seconds=1)
    is_valid_expired, email_exp, err_msg = token_manager.validate_token(token_data.token, now=expired_check_time)
    assert is_valid_expired is False
    assert email_exp is None
    assert err_msg == "L'enllaç ha expirat."

    with pytest.raises(ExpiredTokenError):
        token_manager.verify_token(token_data.token, now=expired_check_time)

    payload_b64, sig_b64 = token_data.token.split(".")
    tampered_sig = ("b" if sig_b64[0] != "b" else "c") + sig_b64[1:]
    tampered_token = f"{payload_b64}.{tampered_sig}"

    is_valid_tampered, email_tamp, err_tampered = token_manager.validate_token(tampered_token, now=base_time)
    assert is_valid_tampered is False
    assert email_tamp is None
    assert "manipulada" in err_tampered or "invàlida" in err_tampered

    with pytest.raises(InvalidTokenError):
        token_manager.verify_token(tampered_token, now=base_time)


def test_single_use_token_revocation_and_memory_purge(token_manager):
    """Comprova el funcionament del Single-Use i la neteja de memòria dels tokens purgats."""
    base_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    token_data = token_manager.generate_token("usuari@exemple.com", now=base_time)

    assert token_manager.verify_token(token_data.token, now=base_time) == "usuari@exemple.com"

    token_manager.invalidate_token(token_data.token, now=base_time)
    assert token_manager.is_token_revoked(token_data.token, now=base_time) is True

    with pytest.raises(InvalidTokenError, match="utilitzat anteriorment"):
        token_manager.verify_token(token_data.token, now=base_time)

    future_time = base_time + timedelta(minutes=20)
    purged = token_manager.purge_expired_revocations(now=future_time)
    assert purged == 1
    assert len(token_manager._revoked_tokens) == 0


def test_token_manager_atomic_consume_and_auto_purge(token_manager):
    """Verifica que consume_token invalida immediatament i executa auto-purga."""
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    token_data = token_manager.generate_token("user@test.cat", now=t0)

    email = token_manager.consume_token(token_data.token, now=t0)
    assert email == "user@test.cat"

    with pytest.raises(InvalidTokenError, match="utilitzat anteriorment"):
        token_manager.consume_token(token_data.token, now=t0)

    future_time = t0 + timedelta(minutes=20)
    token_data2 = token_manager.generate_token("user2@test.cat", now=future_time)
    token_manager.invalidate_token(token_data2.token, now=future_time)
    token_hash1 = token_manager._token_fingerprint(token_data.token)
    assert token_hash1 not in token_manager._revoked_tokens


# =====================================================================
# TESTS UNITARIS - RATE LIMITING I PURGA DE CLAUS
# =====================================================================

def test_rate_limiter_memory_leak_mitigation():
    """Comprova que les claus inactives del RateLimiter s'eliminen per evitar DoS/OOM."""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    limiter.is_allowed("user1@test.cat", current_timestamp=100.0)
    assert "user1@test.cat" in limiter._history

    limiter.purge_empty_keys(now=200.0)
    assert "user1@test.cat" not in limiter._history


def test_ip_and_email_rate_limiting(controller):
    """Comprova que el límit per IP i per correu funcionen conjuntament."""
    now = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    email = "usuari@exemple.com"
    ip = "192.168.1.10"

    for _ in range(5):
        res = controller.request_password_reset(email, ip_address=ip, now=now)
        assert res["status_code"] == 200

    res_email_blocked = controller.request_password_reset(email, ip_address=ip, now=now)
    assert res_email_blocked["status_code"] == 429
    assert res_email_blocked["error"] == "Massa peticions"

    controller_ip = PasswordResetController(
        user_repository=UserRepository(),
        email_service=EmailService(),
        token_manager=controller.token_manager,
        ip_rate_limiter=RateLimiter(max_requests=2, window_seconds=60),
        background_task_runner=lambda t: t(),
    )
    controller_ip.request_password_reset("user1@exemple.com", ip_address="10.0.0.1", now=now)
    controller_ip.request_password_reset("user2@exemple.com", ip_address="10.0.0.1", now=now)
    res_ip_blocked = controller_ip.request_password_reset("user3@exemple.com", ip_address="10.0.0.1", now=now)
    assert res_ip_blocked["status_code"] == 429
    assert "IP" in res_ip_blocked["error"]


# =====================================================================
# TESTS D'INTEGRACIÓ I FLUX COMPLET (E2E)
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


def test_e2e_full_successful_flow_with_password_change(controller, email_service, user_repo):
    """Flux complet: sol·licitud, accés al formulari, canvi i persistència segura de contrasenya."""
    now = datetime(2025, 2, 1, 9, 0, 0, tzinfo=timezone.utc)
    user_email = "usuari@exemple.com"

    resp = controller.request_password_reset(user_email, now=now)
    assert resp["status_code"] == 200
    assert len(email_service.sent_emails) == 1
    reset_link = email_service.sent_emails[0]["reset_link"]
    token = reset_link.split("token=")[1]

    access_time = now + timedelta(minutes=5)
    form_resp = controller.access_reset_form(token, now=access_time)
    assert form_resp["status_code"] == 200
    assert form_resp["can_reset"] is True

    weak_res = controller.complete_password_reset(token, "feble", now=access_time)
    assert weak_res["status_code"] == 400
    assert weak_res["error"] == "Contrasenya feble o no vàlida"
    assert controller.token_manager.is_token_revoked(token) is False

    strong_pwd = "NovaContrasenyaSegura!123"
    success_res = controller.complete_password_reset(token, strong_pwd, now=access_time)
    assert success_res["status_code"] == 200
    assert user_repo.verify_password(user_email, strong_pwd) is True
    assert user_repo.get_password(user_email) != strong_pwd

    reused_res = controller.complete_password_reset(token, strong_pwd, now=access_time)
    assert reused_res["status_code"] == 400
    assert "utilitzat" in reused_res["error"]


def test_concurrent_complete_password_reset_mitigates_toctou(controller):
    """Comprova que peticions concurrents amb el mateix token no poden passar alhora (TOCTOU)."""
    now = datetime(2025, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    token_data = controller.token_manager.generate_token("usuari@exemple.com", now=now)
    token = token_data.token
    password = "PasswordValid123!"

    def do_reset():
        return controller.complete_password_reset(token, password, now=now)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(do_reset) for _ in range(5)]
        results = [f.result() for f in futures]

    successes = [r for r in results if r["status_code"] == 200]
    failures = [r for r in results if r["status_code"] == 400]
    assert len(successes) == 1
    assert len(failures) == 4


def test_e2e_unregistered_email_does_not_send_mail(controller, email_service):
    """Usuari no registrat no rep cap correu però rep resposta 200 genèrica."""
    resp = controller.request_password_reset("inexistent@exemple.com")
    assert resp["status_code"] == 200
    assert resp["message"] == GENERIC_SUCCESS_MESSAGE
    assert len(email_service.sent_emails) == 0
