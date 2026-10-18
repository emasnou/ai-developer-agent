from datetime import datetime, timedelta, timezone
import pytest

from password_reset import (
    GENERIC_SUCCESS_MESSAGE,
    EmailService,
    PasswordResetController,
    PasswordResetTokenManager,
    UserRepository,
)


# =====================================================================
# FIXTURES
# =====================================================================

@pytest.fixture
def token_manager():
    return PasswordResetTokenManager(secret_key="secret-test-key-1234567890")


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
# UNIT TESTS (Matriu de Proves de Qualitat)
# =====================================================================

def test_unit_1_token_generation_uniqueness_and_fifteen_minute_expiration(token_manager):
    """
    Test 1: Validar que la funció de generació de tokens crea un identificador únic,
    criptogràficament segur i amb un timestamp d'expiració establert a exactament +15 minuts.
    """
    base_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    email = "usuari@exemple.com"

    token_1 = token_manager.generate_token(email, now=base_time)
    token_2 = token_manager.generate_token(email, now=base_time)

    # Unicitat i components criptogràfics aleatoris
    assert token_1.token != token_2.token
    assert isinstance(token_1.token, str) and len(token_1.token) > 20

    # Validació de l'expiració a exactament +15 minuts
    expected_expiry = base_time + timedelta(minutes=15)
    assert token_1.expires_at == expected_expiry
    assert token_1.created_at == base_time
    assert (token_1.expires_at - token_1.created_at) == timedelta(minutes=15)


def test_unit_2_token_validation_fails_when_expired_or_tampered(token_manager):
    """
    Test 2: Validar que el mètode de validació de token retorna fals quan s'avalua
    un token generat fa més de 15 minuts o amb format manipulat.
    """
    base_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    token_data = token_manager.generate_token("usuari@exemple.com", now=base_time)

    # 1. Validació just abans o al límit dels 15 minuts (vàlid)
    valid_check_time = base_time + timedelta(minutes=14, seconds=59)
    is_valid, email, err = token_manager.validate_token(token_data.token, now=valid_check_time)
    assert is_valid is True
    assert email == "usuari@exemple.com"
    assert err is None

    # 2. Token generat fa més de 15 minuts (> 15 minuts -> caducat)
    expired_check_time = base_time + timedelta(minutes=15, seconds=1)
    is_valid_expired, _, err_msg = token_manager.validate_token(token_data.token, now=expired_check_time)
    assert is_valid_expired is False
    assert err_msg == "L'enllaç ha expirat."

    # 3. Token amb format manipulat (signatura alterada)
    payload_b64, sig_b64 = token_data.token.split(".")
    tampered_sig = sig_b64[:-2] + ("ab" if sig_b64[-2:] != "ab" else "cd")
    tampered_token = f"{payload_b64}.{tampered_sig}"

    is_valid_tampered, _, err_tampered = token_manager.validate_token(tampered_token, now=base_time)
    assert is_valid_tampered is False
    assert "manipulada" in err_tampered or "invàlida" in err_tampered

    # 4. Token amb payload corrupte o cadena no vàlida
    is_valid_corrupt, _, _ = token_manager.validate_token("cadena_invalida_sense_parts", now=base_time)
    assert is_valid_corrupt is False


def test_unit_3_response_strictly_identical_for_registered_and_unregistered_emails(controller):
    """
    Test 3: Validar que la resposta del servei/controlador (codi d'estat HTTP i missatge)
    és estrictament idèntica tant si el correu existeix a la base de dades com si no.
    """
    registered_email = "usuari@exemple.com"
    unregistered_email = "desconegut@exemple.com"

    response_registered = controller.request_password_reset(registered_email)
    response_unregistered = controller.request_password_reset(unregistered_email)

    # Ambdós han de retornar el mateix codi i text per evitar enumeració d'usuaris
    assert response_registered["status_code"] == 200
    assert response_unregistered["status_code"] == 200
    assert response_registered["message"] == GENERIC_SUCCESS_MESSAGE
    assert response_unregistered["message"] == GENERIC_SUCCESS_MESSAGE
    assert response_registered == response_unregistered


# =====================================================================
# INTEGRATION / E2E TESTS (Matriu de Proves de Qualitat)
# =====================================================================

def test_e2e_1_full_successful_flow_within_fifteen_minutes(controller, email_service):
    """
    Test 1: Simular el flux complet des de la interfície: introduir correu vàlid,
    interceptar l'enviament SMTP (Mock), extreure la URL amb el token, obrir l'enllaç
    dins del marge dels 15 minuts i verificar que el formulari de canvi de contrasenya és accessible.
    """
    now = datetime(2025, 2, 1, 9, 0, 0, tzinfo=timezone.utc)
    user_email = "usuari@exemple.com"

    # Pas 1: L'usuari sol·licita el restabliment
    response = controller.request_password_reset(user_email, now=now)
    assert response["status_code"] == 200
    assert response["message"] == GENERIC_SUCCESS_MESSAGE

    # Pas 2: Interceptar l'enviament de correu electrònic (Mock)
    assert len(email_service.sent_emails) == 1
    sent_email = email_service.sent_emails[0]
    assert sent_email["to"] == user_email
    reset_url = sent_email["reset_link"]
    assert "https://exemple.com/reset-password?token=" in reset_url

    # Extreure el token de la URL
    token = reset_url.split("token=")[1]

    # Pas 3: Obrir l'enllaç 5 minuts després (dins del marge de 15 minuts)
    access_time = now + timedelta(minutes=5)
    form_response = controller.access_reset_form(token, now=access_time)

    # Pas 4: Verificar que el formulari és accessible
    assert form_response["status_code"] == 200
    assert form_response["can_reset"] is True
    assert form_response["email"] == user_email


def test_e2e_2_unregistered_email_sends_no_email_and_shows_generic_success(controller, email_service):
    """
    Test 2: Comprovar el flux amb un correu inexistent verificant que no es fan
    crides al servei de correu electrònic i la interfície mostra l'estat d'èxit genèric.
    """
    now = datetime(2025, 2, 1, 9, 0, 0, tzinfo=timezone.utc)
    unknown_email = "desconegut@exemple.com"

    response = controller.request_password_reset(unknown_email, now=now)

    # Verificació de la interfície / resposta genèrica
    assert response["status_code"] == 200
    assert response["message"] == GENERIC_SUCCESS_MESSAGE

    # Verificació que no s'ha enviat cap correu
    assert len(email_service.sent_emails) == 0


def test_scenario_3_expired_link_redirects_and_offers_new_request(controller, email_service):
    """
    Escenari 3: Intent d'ús d'un enllaç amb token caducat (> 15 minuts).
    El sistema invalida la petició, redirigeix/retorna error indicant que l'enllaç ha expirat
    i ofereix l'opció de demanar-ne un de nou.
    """
    now = datetime(2025, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
    user_email = "usuari@exemple.com"

    # Generem la petició inicial
    controller.request_password_reset(user_email, now=now)
    token = email_service.sent_emails[0]["reset_link"].split("token=")[1]

    # Accés 15 minuts i 30 segons més tard (> 15 min)
    expired_access_time = now + timedelta(minutes=15, seconds=30)
    form_response = controller.access_reset_form(token, now=expired_access_time)

    assert form_response["status_code"] == 400
    assert form_response["can_reset"] is False
    assert form_response["can_request_new"] is True
    assert form_response["error"] == "L'enllaç ha expirat"
    assert "expirat" in form_response["message"].lower()
