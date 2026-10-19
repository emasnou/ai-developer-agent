"""Mòdul per a la gestió segura del restabliment de contrasenyes.

Aquest mòdul implementa la generació de tokens signats amb HMAC-SHA256, protecció
contra atacs de canal lateral (timing attacks), mitigació d'enumeració d'usuaris,
validació estricta d'entrades (OWASP Top 10), persistència de claus mitjançant derivació
segura scrypt, neteja controlada de memòria contra DoS, consum atòmic contra TOCTOU,
limitació de taxa thread-safe i compliment estricte de les directrius NIST i OWASP.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

GENERIC_SUCCESS_MESSAGE: str = (
    "Si el correu està registrat, rebràs instruccions per restablir la contrasenya"
)

EMAIL_REGEX: re.Pattern[str] = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
)

PASSWORD_MIN_LENGTH: int = 12
PASSWORD_MAX_LENGTH: int = 128


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


def validate_password_complexity(password: str) -> bool:
    """Verifica els requeriments de complexitat segons NIST i OWASP.

    La contrasenya ha de tenir entre 12 i 128 caràcters i contenir com a mínim:
    - Una lletra majúscula
    - Una lletra minúscula
    - Un dígit numèric
    - Un caràcter especial

    Args:
        password: Text pla de la contrasenya a validar.

    Returns:
        bool: True si compleix tots els criteris de complexitat, False en cas contrari.
    """
    if not isinstance(password, str):
        return False
    if not (PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH):
        return False

    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)

    return has_upper and has_lower and has_digit and has_special


class TokenValidationError(Exception):
    """Excepció base per a errors de validació de token."""


class ExpiredTokenError(TokenValidationError):
    """Llançat quan el token ha superat el temps de validesa de 15 minuts."""


class InvalidTokenError(TokenValidationError):
    """Llançat quan el token té un format invàlid, ha estat manipulat o ja ha estat consumit."""


class PasswordValidationError(Exception):
    """Llançat quan la contrasenya no assoleix els criteris de complexitat requerits."""


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
    """Genera, valida, invalida i purga tokens criptogràfics segurs amb expiració fixa."""

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
        self._revoked_tokens: Dict[str, int] = {}
        self._lock: threading.Lock = threading.Lock()
        self._last_purge_time: float = 0.0

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

        payload_b64 = self._b64_encode(json.dumps(payload, sort_keys=True).encode("utf-8"))
        sig = hmac.new(self._secret_key, payload_b64.encode("utf-8"), hashlib.sha256).digest()
        token_str = f"{payload_b64}.{self._b64_encode(sig)}"

        return ResetTokenData(
            token=token_str,
            email=email,
            created_at=now_dt,
            expires_at=expires_at,
        )

    def purge_expired_revocations(self, now: Optional[datetime] = None) -> int:
        """Purga de la memòria els tokens revocats que han superat la seva caducitat natural.

        Args:
            now: Marca temporal opcional per al càlcul de vigència.

        Returns:
            int: Nombre d'elements purgats de memòria.
        """
        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        now_ts = int(now_dt.timestamp())

        with self._lock:
            expired_tokens = [
                tok for tok, exp_ts in self._revoked_tokens.items() if exp_ts <= now_ts
            ]
            for tok in expired_tokens:
                del self._revoked_tokens[tok]
            self._last_purge_time = now_ts
            return len(expired_tokens)

    def _maybe_auto_purge(self, now_ts: int) -> None:
        """Executa una purga de memòria amortitzada si ha transcorregut la finestra.

        Args:
            now_ts: Marca temporal actual en segons Unix.
        """
        purge_interval = self.expiration_minutes * 60
        if now_ts - self._last_purge_time > purge_interval:
            stale_keys = [tok for tok, exp in self._revoked_tokens.items() if exp <= now_ts]
            for tok in stale_keys:
                self._revoked_tokens.pop(tok, None)
            self._last_purge_time = now_ts

    def invalidate_token(self, token: str, now: Optional[datetime] = None) -> None:
        """Marca un token com a utilitzat per impedir atacs de repetició (Single-Use).

        Args:
            token: Token criptogràfic a revocar.
            now: Marca temporal opcional de revocació.
        """
        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        now_ts = int(now_dt.timestamp())

        try:
            payload_part = token.split(".")[0]
            payload_dict = json.loads(self._b64_decode(payload_part).decode("utf-8"))
            exp_ts = int(payload_dict.get("exp", 0))
        except Exception:
            exp_ts = now_ts + (self.expiration_minutes * 60)

        with self._lock:
            self._revoked_tokens[token] = exp_ts
            self._maybe_auto_purge(now_ts)

    def is_token_revoked(self, token: str, now: Optional[datetime] = None) -> bool:
        """Comprova si el token ha estat revocat o consumit prèviament.

        Args:
            token: Token criptogràfic a comprovar.
            now: Marca temporal opcional.

        Returns:
            bool: True si el token és a la memòria de revocació activa, False altrament.
        """
        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        now_ts = int(now_dt.timestamp())

        with self._lock:
            exp_ts = self._revoked_tokens.get(token)
            if exp_ts is None:
                return False
            if exp_ts <= now_ts:
                del self._revoked_tokens[token]
                return False
            return True

    def _parse_and_verify_signature(self, token: str) -> Dict[str, Any]:
        """Verifica la signatura criptogràfica del token i en deserialitza el payload.

        Args:
            token: Cadena de text compacta del token.

        Returns:
            Dict[str, Any]: Payload JSON deserialitzat.

        Raises:
            InvalidTokenError: Si el format, signatura o dades són incorrectes.
        """
        if not token or not isinstance(token, str) or "." not in token:
            raise InvalidTokenError("Format de token incorrecte o incomplet.")

        parts = token.split(".")
        if len(parts) != 2:
            raise InvalidTokenError("Format de token incorrecte.")

        payload_b64, signature_b64 = parts[0], parts[1]
        try:
            expected_sig = hmac.new(
                self._secret_key,
                payload_b64.encode("utf-8"),
                hashlib.sha256,
            ).digest()
            actual_sig = self._b64_decode(signature_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                raise InvalidTokenError("La signatura del token ha estat manipulada o és invàlida.")

            payload_bytes = self._b64_decode(payload_b64)
            return json.loads(payload_bytes.decode("utf-8"))
        except InvalidTokenError:
            raise
        except Exception as exc:
            raise InvalidTokenError("No s'ha pogut desxifrar o interpretar el token.") from exc

    def _check_validity_unlocked(self, token: str, now: Optional[datetime] = None) -> str:
        """Comprova vigència i revocació d'un token sense adquirir el lock intern.

        Args:
            token: Token compacte.
            now: Data/hora opcional de validació.

        Returns:
            str: Correu electrònic associat al token.

        Raises:
            InvalidTokenError: Si el token és invàlid o està revocat.
            ExpiredTokenError: Si el token ha caducat.
        """
        payload = self._parse_and_verify_signature(token)

        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        now_ts = int(now_dt.timestamp())

        exp_revoked = self._revoked_tokens.get(token)
        if exp_revoked is not None:
            if exp_revoked > now_ts:
                raise InvalidTokenError("El token ja ha estat utilitzat anteriorment.")
            del self._revoked_tokens[token]

        exp_timestamp = payload.get("exp")
        email = payload.get("email")
        if not exp_timestamp or not email:
            raise InvalidTokenError("Dades del token incompletes.")

        if now_ts > exp_timestamp:
            raise ExpiredTokenError("L'enllaç ha expirat.")

        return email

    def verify_token(self, token: str, now: Optional[datetime] = None) -> str:
        """Verifica la integritat, vigència i unicitat del token.

        Args:
            token: Token compacte rebut.
            now: Marca temporal opcional per a comprovacions deterministes.

        Returns:
            str: Correu electrònic associat al token validat.

        Raises:
            InvalidTokenError: Si el format és incorrecte, la signatura no coincideix o ha estat revocat.
            ExpiredTokenError: Si el token ha superat el temps límit de vigència.
        """
        with self._lock:
            return self._check_validity_unlocked(token, now=now)

    def consume_token(self, token: str, now: Optional[datetime] = None) -> str:
        """Verifica i revoca el token atòmicament prevenint condicions de cursa TOCTOU.

        Args:
            token: Token compacte a verificar i invalidar.
            now: Marca temporal opcional.

        Returns:
            str: Correu electrònic validat del token.

        Raises:
            InvalidTokenError: Si el format és invàlid, manipulat o ja s'ha utilitzat.
            ExpiredTokenError: Si el token ha caducat.
        """
        now_dt = now or datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        now_ts = int(now_dt.timestamp())

        with self._lock:
            email = self._check_validity_unlocked(token, now=now_dt)
            try:
                payload_dict = json.loads(self._b64_decode(token.split(".")[0]).decode("utf-8"))
                exp_ts = int(payload_dict.get("exp", now_ts + (self.expiration_minutes * 60)))
            except Exception:
                exp_ts = now_ts + (self.expiration_minutes * 60)

            self._revoked_tokens[token] = exp_ts
            self._maybe_auto_purge(now_ts)
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
                Si el token ha expirat o és invàlid, mai retorna el correu per evitar fuites d'informació.
        """
        try:
            email = self.verify_token(token, now=now)
            return True, email, None
        except ExpiredTokenError:
            return False, None, "L'enllaç ha expirat."
        except InvalidTokenError as err:
            return False, None, str(err)


class UserRepository:
    """Repositori d'usuaris en memòria amb gestió segura de contrasenyes mitjançant scrypt."""

    def __init__(self, initial_users: Optional[List[str]] = None):
        """Inicialitza el repositori amb un conjunt d'usuaris opcional.

        Args:
            initial_users: Llista opcional de correus electrònics a registrar inicialment.
        """
        self._users: Dict[str, Dict[str, Any]] = {}
        for email in initial_users or []:
            self.add_user(email)

    @staticmethod
    def _hash_password(password: str) -> str:
        """Aplica derivació de clau segura basada en scrypt segons NIST/OWASP.

        Args:
            password: Text pla de la contrasenya a derivar.

        Returns:
            str: Hash formatat com salt_hex$key_hex.
        """
        salt = os.urandom(16)
        key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=16384,
            r=8,
            p=1,
            maxmem=0,
            dklen=64,
        )
        return f"{salt.hex()}${key.hex()}"

    def exists(self, email: str) -> bool:
        """Comprova si una adreça de correu està registrada.

        Args:
            email: Adreça de correu a cercar.

        Returns:
            bool: True si l'usuari existeix, False en cas contrari.
        """
        return email.strip().lower() in self._users

    def add_user(self, email: str, initial_password: Optional[str] = None) -> None:
        """Afegeix una nova adreça d'usuari al repositori amb contrasenya segura.

        Args:
            email: Adreça de correu a registrar.
            initial_password: Contrasenya inicial opcional de l'usuari.
        """
        hashed = self._hash_password(initial_password) if initial_password else None
        self._users[email.strip().lower()] = {
            "password": hashed,
            "updated_at": datetime.now(timezone.utc),
        }

    def update_password(self, email: str, new_password: str) -> bool:
        """Actualitza la contrasenya d'un usuari emmagatzemant només el seu hash segur.

        Args:
            email: Adreça de correu de l'usuari.
            new_password: Nova contrasenya de l'usuari.

        Returns:
            bool: True si s'ha actualitzat correctament, False si l'usuari no existeix.
        """
        normalized = email.strip().lower()
        if normalized not in self._users:
            return False
        self._users[normalized]["password"] = self._hash_password(new_password)
        self._users[normalized]["updated_at"] = datetime.now(timezone.utc)
        return True

    def get_password(self, email: str) -> Optional[str]:
        """Obté el hash emmagatzemat de la contrasenya d'un usuari.

        Args:
            email: Adreça de correu a consultar.

        Returns:
            Optional[str]: Hash de la contrasenya de l'usuari o None si no existeix.
        """
        user_data = self._users.get(email.strip().lower())
        return user_data["password"] if user_data else None

    def verify_password(self, email: str, password: str) -> bool:
        """Verifica si la contrasenya facilitada coincideix amb el hash emmagatzemat.

        Args:
            email: Adreça de correu de l'usuari.
            password: Text pla de la contrasenya a verificar.

        Returns:
            bool: True si coincideix, False en cas contrari.
        """
        stored = self.get_password(email)
        if not stored or "$" not in stored:
            return False
        salt_hex, key_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=16384,
            r=8,
            p=1,
            maxmem=0,
            dklen=64,
        )
        return hmac.compare_digest(actual_key, expected_key)


class EmailService:
    """Servei d'enviament de correus electrònics amb registre segur entre fils."""

    def __init__(self, async_dispatch: bool = False):
        """Inicialitza el servei amb un historial d'enviaments buit.

        Args:
            async_dispatch: Si és True, l'enviament intern es despatxa en un nou fil.
        """
        self.sent_emails: List[Dict[str, str]] = []
        self.async_dispatch: bool = async_dispatch
        self._lock: threading.Lock = threading.Lock()

    def _record_email(self, to_email: str, reset_link: str) -> None:
        """Registra l'enviament del correu de manera segura entre fils.

        Args:
            to_email: Correu de destí.
            reset_link: Enllaç de restabliment de contrasenya.
        """
        with self._lock:
            self.sent_emails.append({
                "to": to_email,
                "subject": "Restabliment de la teva contrasenya",
                "reset_link": reset_link,
            })

    def send_reset_email(self, to_email: str, reset_link: str) -> None:
        """Envia un correu amb l'enllaç de restabliment.

        Args:
            to_email: Destinatari del correu.
            reset_link: Enllaç complet per restablir la contrasenya.
        """
        if self.async_dispatch:
            thread = threading.Thread(
                target=self._record_email,
                args=(to_email, reset_link),
                daemon=True,
            )
            thread.start()
        else:
            self._record_email(to_email, reset_link)


class RateLimiter:
    """Limitador de taxa thread-safe basat en finestres lliscants i gestió eficient de memòria."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 300):
        """Inicialitza el limitador de taxa.

        Args:
            max_requests: Nombre màxim de peticions permeses dins la finestra.
            window_seconds: Mida de la finestra de temps en segons.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}
        self._lock: threading.Lock = threading.Lock()
        self._last_global_purge: float = 0.0

    def purge_empty_keys(self, now: Optional[float] = None) -> None:
        """Elimina les claus que ja no tenen cap petició vigent dins la finestra.

        Args:
            now: Marca temporal en segons.
        """
        current_time = now if now is not None else time.time()
        with self._lock:
            cutoff = current_time - self.window_seconds
            stale_keys = []
            for identifier, records in list(self._history.items()):
                active = [t for t in records if t > cutoff]
                if not active:
                    stale_keys.append(identifier)
                else:
                    self._history[identifier] = active
            for k in stale_keys:
                self._history.pop(k, None)

    def is_allowed(self, identifier: str, current_timestamp: Optional[float] = None) -> bool:
        """Comprova de manera thread-safe i optimitzada si la petició és permesa.

        Args:
            identifier: Clau identificadora (correu electrònic o adreça IP).
            current_timestamp: Marca temporal en segons.

        Returns:
            bool: True si la petició és admesa, False si s'ha superat el límit.
        """
        now = current_timestamp if current_timestamp is not None else time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            records = self._history.get(identifier, [])
            valid_records = [t for t in records if t > cutoff]

            if len(valid_records) >= self.max_requests:
                self._history[identifier] = valid_records
                return False

            valid_records.append(now)
            self._history[identifier] = valid_records

            if now - self._last_global_purge > self.window_seconds:
                self._last_global_purge = now
                empty_keys = [
                    k for k, v in list(self._history.items()) if not any(t > cutoff for t in v)
                ]
                for k in empty_keys:
                    self._history.pop(k, None)

            return True


class PasswordResetController:
    """Controlador per a la gestió de sol·licituds i validació d'enllaços de recuperació."""

    def __init__(self,
        user_repository: UserRepository,
        email_service: EmailService,
        token_manager: PasswordResetTokenManager,
        base_url: str = "https://exemple.com/reset-password?token=",
        rate_limiter: Optional[RateLimiter] = None,
        ip_rate_limiter: Optional[RateLimiter] = None,
        background_task_runner: Optional[Callable[[Callable[[], None]], None]] = None,
    ):
        """Inicialitza el controlador de restabliment.

        Args:
            user_repository: Repositori d'usuaris amb persistència.
            email_service: Servei d'enviament de missatgeria.
            token_manager: Gestor criptogràfic de tokens.
            base_url: URL base de l'enllaç de restabliment.
            rate_limiter: Limitador de peticions per correu electrònic.
            ip_rate_limiter: Limitador de peticions per adreça IP d'origen (OWASP A07).
            background_task_runner: Executor asíncron per a tasques d'I/O en segon pla.
        """
        self.user_repo = user_repository
        self.email_service = email_service
        self.token_manager = token_manager
        self.base_url = base_url
        self.rate_limiter = rate_limiter or RateLimiter()
        self.ip_rate_limiter = ip_rate_limiter or RateLimiter(max_requests=20, window_seconds=300)
        self._background_task_runner = background_task_runner

    def _dispatch_task(self, task: Callable[[], None]) -> None:
        """Executa una tasca en segon pla per mitigar timing attacks d'I/O.

        Args:
            task: Funció sense paràmetres a executar en segon pla.
        """
        if self._background_task_runner:
            self._background_task_runner(task)
        else:
            thread = threading.Thread(target=task, daemon=True)
            thread.start()

    def _check_rate_limits(
        self, email: str, ip_address: Optional[str], timestamp: float
    ) -> Optional[Dict[str, Any]]:
        """Valida els límits de taxa per IP i correu electrònic.

        Args:
            email: Correu electrònic normalitzat.
            ip_address: Adreça IP opcional del client.
            timestamp: Marca temporal en segons de la petició.

        Returns:
            Optional[Dict[str, Any]]: Resposta d'error 429 si se superen límits, None si és admesa.
        """
        if ip_address and not self.ip_rate_limiter.is_allowed(ip_address, current_timestamp=timestamp):
            return {
                "status_code": 429,
                "error": "Massa peticions des d'aquesta IP",
                "message": "S'ha superat el límit de peticions permès per a la vostra adreça IP.",
            }
        if not self.rate_limiter.is_allowed(email, current_timestamp=timestamp):
            return {
                "status_code": 429,
                "error": "Massa peticions",
                "message": "S'han superat el nombre de peticions permeses. Torneu-ho a provar més tard.",
            }
        return None

    def request_password_reset(
        self,
        email: str,
        ip_address: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Processa la sol·licitud de restabliment garantint seguretat OWASP i temps constant.

        Args:
            email: Adreça de correu introduïda per l'usuari.
            ip_address: Adreça IP del client que sol·licita l'acció (opcional).
            now: Marca temporal opcional per a determinisme en proves.

        Returns:
            Dict[str, Any]: Resposta estàndard en format diccionari.
        """
        if not validate_email_format(email):
            return {
                "status_code": 400,
                "error": "Format de correu invàlid",
                "message": "L'adreça de correu electrònic introduïda no té un format vàlid.",
            }

        normalized_email = email.strip().lower()
        current_ts = now.timestamp() if now else time.time()

        rate_limit_error = self._check_rate_limits(normalized_email, ip_address, current_ts)
        if rate_limit_error:
            return rate_limit_error

        token_data = self.token_manager.generate_token(normalized_email, now=now)
        if self.user_repo.exists(normalized_email):
            reset_link = f"{self.base_url}{token_data.token}"
            self._dispatch_task(
                lambda: self.email_service.send_reset_email(normalized_email, reset_link)
            )

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

    def complete_password_reset(
        self, token: str, new_password: str, now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Completa el restabliment avaluant la complexitat i consumint el token atòmicament.

        Args:
            token: Token que serà verificat i revocat atòmicament.
            new_password: Nova contrasenya escollida.
            now: Marca temporal opcional.

        Returns:
            Dict[str, Any]: Resposta de la petició de canvi de contrasenya.
        """
        if not validate_password_complexity(new_password):
            return {
                "status_code": 400,
                "error": "Contrasenya feble o no vàlida",
                "message": (
                    "La contrasenya ha de tenir entre 12 i 128 caràcters i incloure "
                    "almenys una majúscula, una minúscula, un número i un caràcter especial."
                ),
            }

        try:
            email = self.token_manager.consume_token(token, now=now)
        except TokenValidationError as err:
            return {
                "status_code": 400,
                "error": str(err),
                "message": "No s'ha pogut canviar la contrasenya amb el token indicat.",
            }

        updated = self.user_repo.update_password(email, new_password)
        if not updated:
            return {
                "status_code": 404,
                "error": "Usuari no trobat",
                "message": "No s'ha trobat cap compte d'usuari vinculat al correu del token.",
            }

        return {
            "status_code": 200,
            "message": "Contrasenya actualitzada correctament.",
            "email": email,
        }
