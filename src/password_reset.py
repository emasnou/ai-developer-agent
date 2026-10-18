from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

GENERIC_SUCCESS_MESSAGE = (
    "Si el correu està registrat, rebràs instruccions per restablir la contrasenya"
)


class TokenValidationError(Exception):
    """Base per a errors de validació de token."""


class ExpiredTokenError(TokenValidationError):
    """Llençat quan el token ha superat el temps de validesa de 15 minuts."""


class InvalidTokenError(TokenValidationError):
    """Llençat quan el token té un format invàlid o ha estat manipulat."""


@dataclass
class ResetTokenData:
    token: str
    email: str
    created_at: datetime
    expires_at: datetime


class PasswordResetTokenManager:
    """Genera i valida tokens criptogràficament segurs amb expiració fixa de 15 minuts."""

    def __init__(self, secret_key: Optional[str] = None, expiration_minutes: int = 15):
        self._secret_key = (secret_key or secrets.token_hex(32)).encode("utf-8")
        self.expiration_minutes = expiration_minutes

    @staticmethod
    def _b64_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    @staticmethod
    def _b64_decode(data: str) -> bytes:
        padding = 4 - (len(data) % 4)
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data)

    def generate_token(self, email: str, now: Optional[datetime] = None) -> ResetTokenData:
        """Genera un token criptogràficament segur signat amb HMAC-SHA256."""
        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)

        expires_at = now_dt + timedelta(minutes=self.expiration_minutes)

        payload = {
            "email": email,
            "nonce": secrets.token_hex(16),
            "iat": int(now_dt.timestamp()),
            "exp": int(expires_at.timestamp()),
        }

        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        payload_b64 = self._b64_encode(payload_bytes)

        signature = hmac.new(self._secret_key, payload_b64.encode("utf-8"), hashlib.sha256).digest()
        signature_b64 = self._b64_encode(signature)

        token_str = f"{payload_b64}.{signature_b64}"
        return ResetTokenData(
            token=token_str,
            email=email,
            created_at=now_dt,
            expires_at=expires_at,
        )

    def validate_token(self, token: str, now: Optional[datetime] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Valida la integritat i la caducitat del token.
        Retorna (és_vàlid, email, missatge_error).
        """
        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)

        if not token or not isinstance(token, str) or "." not in token:
            return False, None, "Format de token incorrecte o incomplet."

        parts = token.split(".")
        if len(parts) != 2:
            return False, None, "Format de token incorrecte."

        payload_b64, signature_b64 = parts[0], parts[1]

        try:
            expected_signature = hmac.new(
                self._secret_key,
                payload_b64.encode("utf-8"),
                hashlib.sha256,
            ).digest()
            actual_signature = self._b64_decode(signature_b64)
            if not hmac.compare_digest(expected_signature, actual_signature):
                return False, None, "La signatura del token ha estat manipulada o és invàlida."

            payload_bytes = self._b64_decode(payload_b64)
            payload: Dict[str, Any] = json.loads(payload_bytes.decode("utf-8"))
        except Exception:
            return False, None, "No s'ha pogut desxifrar o interpretar el token."

        exp_timestamp = payload.get("exp")
        email = payload.get("email")

        if not exp_timestamp or not email:
            return False, None, "Dades del token incompletes."

        if int(now_dt.timestamp()) > exp_timestamp:
            return False, email, "L'enllaç ha expirat."

        return True, email, None


class UserRepository:
    """Repositori d'usuaris en memòria."""

    def __init__(self, initial_users: Optional[List[str]] = None):
        self._registered_emails = set(initial_users or [])

    def exists(self, email: str) -> bool:
        return email.lower() in self._registered_emails

    def add_user(self, email: str) -> None:
        self._registered_emails.add(email.lower())


class EmailService:
    """Servei d'enviament de correus (Mockable / Spy)."""

    def __init__(self):
        self.sent_emails: List[Dict[str, str]] = []

    def send_reset_email(self, to_email: str, reset_link: str) -> None:
        self.sent_emails.append({
            "to": to_email,
            "subject": "Restabliment de la teva contrasenya",
            "reset_link": reset_link,
        })


class PasswordResetController:
    """Controlador per a la gestió de sol·licituds i validació d'enllaços de recuperació."""

    def __init__(
        self,
        user_repository: UserRepository,
        email_service: EmailService,
        token_manager: PasswordResetTokenManager,
        base_url: str = "https://exemple.com/reset-password?token=",
    ):
        self.user_repo = user_repository
        self.email_service = email_service
        self.token_manager = token_manager
        self.base_url = base_url

    def request_password_reset(self, email: str, now: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Escenaris 1 i 2: Sol·licitud de restabliment.
        Retorna sempre exactament la mateixa resposta per protegir contra l'enumeració d'usuaris.
        """
        normalized_email = email.strip().lower()

        if self.user_repo.exists(normalized_email):
            token_data = self.token_manager.generate_token(normalized_email, now=now)
            reset_link = f"{self.base_url}{token_data.token}"
            self.email_service.send_reset_email(normalized_email, reset_link)

        return {
            "status_code": 200,
            "message": GENERIC_SUCCESS_MESSAGE,
        }

    def access_reset_form(self, token: str, now: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Escenari 3: Accés a la pàgina / formulari mitjançant el token rebut per correu.
        """
        is_valid, email, error_message = self.token_manager.validate_token(token, now=now)

        if is_valid:
            return {
                "status_code": 200,
                "can_reset": True,
                "message": "Accés concedit al formulari de nova contrasenya.",
                "email": email,
            }

        if error_message == "L'enllaç ha expirat.":
            return {
                "status_code": 400,
                "can_reset": False,
                "can_request_new": True,
                "error": "L'enllaç ha expirat",
                "message": "L'enllaç per restablir la contrasenya ha expirat. Podeu sol·licitar-ne un de nou.",
            }

        return {
            "status_code": 400,
            "can_reset": False,
            "can_request_new": True,
            "error": "Token invàlid",
            "message": "L'enllaç no és vàlid o ha estat manipulat. Podeu sol·licitar-ne un de nou.",
        }
