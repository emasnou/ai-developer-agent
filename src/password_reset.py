"""Mòdul per a la gestió segura del restabliment de contrasenyes.

Aquest mòdul implementa la generació de tokens signats amb HMAC-SHA256, protecció
contra atacs de canal lateral (timing attacks), mitigació d'enumeració d'usuaris,
validació d'entrades per prevenir injeccions i suport per a tokens d'un sol ús.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

GENERIC_SUCCESS_MESSAGE: str = (
    "Si el correu està registrat, rebràs instruccions per restablir la contrasenya"
)

EMAIL_REGEX: re.Pattern[str] = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
)


def validate_email_format(email: str) -> bool:
    """Valida sintàcticament una adreça de correu electrònic.

    Args:
        email: Adreça de correu electrònic a verificar.

    Returns:
        bool: True si compleix el format estàndard, False en cas contrari.
    """
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


class TokenValidationError(Exception):
    """Excepció base per a errors de validació de token."""


class ExpiredTokenError(TokenValidationError):
    """Llançat quan el token ha superat el temps de validesa de 15 minuts."""


class InvalidTokenError(TokenValidationError):
    """Llançat quan el token té un format invàlid, ha estat manipulat o ja ha estat consumit."""


@dataclass(frozen=True)
class ResetTokenData:
    """Estructura de dades que conté la informació d'un token generat.

    Attributes:
        token: Token criptogràfic en format compacte de cadena de text.
        email: Adreça de correu vinculada al token.
        created_at: Data i hora de creació en UTC.
        expires_at: Data i hora de caducitat en UTC.
    """

    token: str
    email: str
    created_at: datetime
    expires_at: datetime


class PasswordResetTokenManager:
    """Genera, valida i invalida tokens criptogràficament segurs amb expiració fixa."""

    def __init__(self, secret_key: Optional[str] = None, expiration_minutes: int = 15):
        """Inicialitza el gestor de tokens.

        Args:
            secret_key: Clau secreta robusta (mínim 32 caràcters). Si és None,
                s'intenta llegir de la variable d'entorn APP_SECRET_KEY.
            expiration_minutes: Minuts de validesa del token (per defecte: 15).

        Raises:
            ValueError: Si no es proporciona una clau vàlida d'almenys 32 caràcters.
        """
        resolved_key = secret_key or os.environ.get("APP_SECRET_KEY")
        if not resolved_key or len(resolved_key) < 32:
            raise ValueError(
                "Cal proporcionar una clau secreta robusta de mínim 32 caràcters "
                "(o definir APP_SECRET_KEY)."
            )
        self._secret_key: bytes = resolved_key.encode("utf-8")
        self.expiration_minutes: int = expiration_minutes
        self._revoked_tokens: Set[str] = set()

    @staticmethod
    def _b64_encode(data: bytes) -> str:
        """Codifica en Base64 URL-safe sense caràcters de padding '='.

        Args:
            data: Bytes a codificar.

        Returns:
            str: Cadena de text en Base64 URL-safe.
        """
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    @staticmethod
    def _b64_decode(data: str) -> bytes:
        """Descodifica una cadena en Base64 URL-safe afegint el padding necessari.

        Args:
            data: Cadena en Base64 URL-safe.

        Returns:
            bytes: Bytes descodificats.
        """
        padding = 4 - (len(data) % 4)
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data)

    def generate_token(self, email: str, now: Optional[datetime] = None) -> ResetTokenData:
        """Genera un token d'un sol ús signat mitjançant HMAC-SHA256.

        Args:
            email: Adreça de correu de l'usuari sol·licitant.
            now: Marca temporal opcional per a proves de determinisme temporal.

        Returns:
            ResetTokenData: Estructura amb el token signat i metadades d'expiració.
        """
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

        signature = hmac.new(
            self._secret_key,
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature_b64 = self._b64_encode(signature)

        token_str = f"{payload_b64}.{signature_b64}"
        return ResetTokenData(
            token=token_str,
            email=email,
            created_at=now_dt,
            expires_at=expires_at,
        )

    def invalidate_token(self, token: str) -> None:
        """Marca un token com a utilitzat per impedir atacs de repetició (Single-Use).

        Args:
            token: Token criptogràfic a revocar.
        """
        self._revoked_tokens.add(token)

    def is_token_revoked(self, token: str) -> bool:
        """Comprova si el token ha estat revocat o consumit.

        Args:
            token: Token criptogràfic a comprovar.

        Returns:
            bool: True si el token està revocat, False en cas contrari.
        """
        return token in self._revoked_tokens

    def verify_token(self, token: str, now: Optional[datetime] = None) -> str:
        """Verifica la integritat, vigència i unicitat del token llançant excepcions si és invàlid.

        Args:
            token: Token compacte rebut.
            now: Marca temporal opcional per a comprovacions deterministes.

        Returns:
            str: Correu electrònic associat al token validat.

        Raises:
            InvalidTokenError: Si el format és incorrecte, la signatura no coincideix o ha estat revocat.
            ExpiredTokenError: Si el token ha superat el temps límit de vigència.
        """
        if not token or not isinstance(token, str) or "." not in token:
            raise InvalidTokenError("Format de token incorrecte o incomplet.")

        parts = token.split(".")
        if len(parts) != 2:
            raise InvalidTokenError("Format de token incorrecte.")

        payload_b64, signature_b64 = parts[0], parts[1]

        try:
            expected_signature = hmac.new(
                self._secret_key,
                payload_b64.encode("utf-8"),
                hashlib.sha256,
            ).digest()
            actual_signature = self._b64_decode(signature_b64)
            if not hmac.compare_digest(expected_signature, actual_signature):
                raise InvalidTokenError("La signatura del token ha estat manipulada o és invàlida.")

            payload_bytes = self._b64_decode(payload_b64)
            payload: Dict[str, Any] = json.loads(payload_bytes.decode("utf-8"))
        except InvalidTokenError:
            raise
        except Exception as exc:
            raise InvalidTokenError("No s'ha pogut desxifrar o interpretar el token.") from exc

        if self.is_token_revoked(token):
            raise InvalidTokenError("El token ja ha estat utilitzat anteriorment.")

        exp_timestamp = payload.get("exp")
        email = payload.get("email")

        if not exp_timestamp or not email:
            raise InvalidTokenError("Dades del token incompletes.")

        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)

        if int(now_dt.timestamp()) > exp_timestamp:
            raise ExpiredTokenError("L'enllaç ha expirat.")

        return email

    def validate_token(
        self, token: str, now: Optional[datetime] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Valida la integritat i la caducitat del token retornant una tupla de resultat.

        Args:
            token: Token a validar.
            now: Marca temporal opcional per a la validació.

        Returns:
            Tuple[bool, Optional[str], Optional[str]]: Tupla amb (és_vàlid, correu, missatge_error).
        """
        try:
            email = self.verify_token(token, now=now)
            return True, email, None
        except ExpiredTokenError:
            # Obtenim l'email si el token és estructuralment vàlid per mantenir compatibilitat
            email = None
            try:
                payload_bytes = self._b64_decode(token.split(".")[0])
                payload = json.loads(payload_bytes.decode("utf-8"))
                email = payload.get("email")
            except Exception:
                pass
            return False, email, "L'enllaç ha expirat."
        except InvalidTokenError as err:
            return False, None, str(err)


class UserRepository:
    """Repositori d'usuaris en memòria."""

    def __init__(self, initial_users: Optional[List[str]] = None):
        """Inicialitza el repositori amb un conjunt d'usuaris opcional.

        Args:
            initial_users: Llista opcional de correus electrònics a registrar inicialment.
        """
        self._registered_emails: Set[str] = {
            email.strip().lower() for email in (initial_users or [])
        }

    def exists(self, email: str) -> bool:
        """Comprova si una adreça de correu està registrada.

        Args:
            email: Adreça de correu a cercar.

        Returns:
            bool: True si l'usuari existeix, False en cas contrari.
        """
        return email.strip().lower() in self._registered_emails

    def add_user(self, email: str) -> None:
        """Afegeix una nova adreça d'usuari al repositori.

        Args:
            email: Adreça de correu a registrar.
        """
        self._registered_emails.add(email.strip().lower())


class EmailService:
    """Servei d'enviament de correus electrònics (Mockable / Spy)."""

    def __init__(self):
        """Inicialitza el servei amb un historial d'enviaments buit."""
        self.sent_emails: List[Dict[str, str]] = []

    def send_reset_email(self, to_email: str, reset_link: str) -> None:
        """Envia un correu amb l'enllaç de restabliment.

        Args:
            to_email: Destinatari del correu.
            reset_link: Enllaç complet per restablir la contrasenya.
        """
        self.sent_emails.append({
            "to": to_email,
            "subject": "Restabliment de la teva contrasenya",
            "reset_link": reset_link,
        })


class RateLimiter:
    """Limitador de taxa per evitar atacs de denegació de servei i Email Bombing."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 300):
        """Inicialitza el limitador de taxa.

        Args:
            max_requests: Nombre màxim de peticions permeses dins la finestra.
            window_seconds: Mida de la finestra de temps en segons.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}

    def is_allowed(self, identifier: str, current_timestamp: Optional[float] = None) -> bool:
        """Comprova si la petició per a l'identificador donat és permesa.

        Args:
            identifier: Clau identificadora (p. ex. correu electrònic o adreça IP).
            current_timestamp: Marca temporal en segons (per defecte: time.time()).

        Returns:
            bool: True si es troba dins dels límits admesos, False si ha superat el límit.
        """
        now = current_timestamp if current_timestamp is not None else time.time()
        records = self._history.setdefault(identifier, [])
        # Purga de peticions fora de la finestra
        self._history[identifier] = [t for t in records if now - t < self.window_seconds]

        if len(self._history[identifier]) >= self.max_requests:
            return False

        self._history[identifier].append(now)
        return True


class PasswordResetController:
    """Controlador per a la gestió de sol·licituds i validació d'enllaços de recuperació."""

    def __init__(
        self,
        user_repository: UserRepository,
        email_service: EmailService,
        token_manager: PasswordResetTokenManager,
        base_url: str = "https://exemple.com/reset-password?token=",
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """Inicialitza el controlador de restabliment.

        Args:
            user_repository: Repositori d'usuaris.
            email_service: Servei d'enviament de missatgeria.
            token_manager: Gestor criptogràfic de tokens.
            base_url: URL base de l'enllaç de restabliment.
            rate_limiter: Limitador de peticions opcional.
        """
        self.user_repo = user_repository
        self.email_service = email_service
        self.token_manager = token_manager
        self.base_url = base_url
        self.rate_limiter = rate_limiter or RateLimiter()

    def request_password_reset(self, email: str, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Processa la sol·licitud de restabliment garantint seguretat OWASP i temps constant.

        Args:
            email: Adreça de correu introduïda per l'usuari.
            now: Marca temporal opcional per a determinisme en proves.

        Returns:
            Dict[str, Any]: Resposta estàndard en format diccionari.
        """
        # 1. Validació de seguretat d'entrada per evitar injeccions
        if not validate_email_format(email):
            return {
                "status_code": 400,
                "error": "Format de correu invàlid",
                "message": "L'adreça de correu electrònic introduïda no té un format vàlid.",
            }

        normalized_email = email.strip().lower()

        # 2. Limitació de taxa (Rate Limiting) per evitar DoS / Email Bombing
        current_ts = now.timestamp() if now else time.time()
        if not self.rate_limiter.is_allowed(normalized_email, current_timestamp=current_ts):
            return {
                "status_code": 429,
                "error": "Massa peticions",
                "message": "S'han superat el nombre de peticions permeses. Torneu-ho a provar més tard.",
            }

        # 3. Mitigació d'atac de temporització: execució de càrrega equivalent
        if self.user_repo.exists(normalized_email):
            token_data = self.token_manager.generate_token(normalized_email, now=now)
            reset_link = f"{self.base_url}{token_data.token}"
            self.email_service.send_reset_email(normalized_email, reset_link)
        else:
            # Generem un token fictici per mantenir la càrrega criptogràfica constant
            _dummy_data = self.token_manager.generate_token(normalized_email, now=now)

        # Resposta genèrica d'èxit idèntica per a tots els casos vàlids
        return {
            "status_code": 200,
            "message": GENERIC_SUCCESS_MESSAGE,
        }

    def access_reset_form(self, token: str, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Valida l'accés al formulari de nova contrasenya mitjançant el token rebut.

        Args:
            token: Token proporcionat pel client.
            now: Marca temporal opcional per a comprovacions temporals.

        Returns:
            Dict[str, Any]: Dades de resolució de l'accés.
        """
        try:
            email = self.token_manager.verify_token(token, now=now)
            return {
                "status_code": 200,
                "can_reset": True,
                "message": "Accés concedit al formulari de nova contrasenya.",
                "email": email,
            }
        except ExpiredTokenError:
            return {
                "status_code": 400,
                "can_reset": False,
                "can_request_new": True,
                "error": "L'enllaç ha expirat",
                "message": "L'enllaç per restablir la contrasenya ha expirat. Podeu sol·licitar-ne un de nou.",
            }
        except InvalidTokenError:
            return {
                "status_code": 400,
                "can_reset": False,
                "can_request_new": True,
                "error": "Token invàlid",
                "message": "L'enllaç no és vàlid o ha estat manipulat. Podeu sol·licitar-ne un de nou.",
            }

    def complete_password_reset(self, token: str, new_password: str, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Completa el restabliment consumint el token d'un sol ús.

        Args:
            token: Token que serà verificat i posteriorment revocat.
            new_password: Nova contrasenya escollida.
            now: Marca temporal opcional.

        Returns:
            Dict[str, Any]: Resposta de la petició de canvi de contrasenya.
        """
        try:
            email = self.token_manager.verify_token(token, now=now)
            # Invalida immediatament el token per garantir Single-Use
            self.token_manager.invalidate_token(token)
            return {
                "status_code": 200,
                "message": "Contrasenya actualitzada correctament.",
                "email": email,
            }
        except TokenValidationError as err:
            return {
                "status_code": 400,
                "error": str(err),
                "message": "No s'ha pogut canviar la contrasenya amb el token indicat.",
            }
