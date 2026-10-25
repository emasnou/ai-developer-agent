"""Mòdul de configuració i càrrega segura de variables d'entorn.

Desacobla la càrrega de variables de la seva validació estricta en temps d'importació
per permetre l'execució de tests unitaris sense dependre de fitxers .env ni connexions externes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Carrega les variables del fitxer .env si existeix
load_dotenv()

GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")
GITHUB_REPO: Optional[str] = os.getenv("GITHUB_REPO")
GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
APP_SECRET_KEY: Optional[str] = os.getenv("APP_SECRET_KEY")


@dataclass(frozen=True)
class AppConfig:
    """Estructura de configuració validada de l'aplicació.

    Attributes:
        github_token: Token d'autenticació per a l'API de GitHub.
        github_repo: Repositori de destinació en format 'propietari/nom'.
        gemini_api_key: Clau d'accés a l'API de Google Gemini.
        app_secret_key: Clau secreta opcional per a mòduls criptogràfics.
    """

    github_token: Optional[str] = None
    github_repo: Optional[str] = None
    gemini_api_key: Optional[str] = None
    app_secret_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> AppConfig:
        """Construeix una instància de configuració llegint l'entorn actual.

        Returns:
            AppConfig: Instància amb els valors actuals de les variables d'entorn.
        """
        return cls(
            github_token=os.getenv("GITHUB_TOKEN", GITHUB_TOKEN),
            github_repo=os.getenv("GITHUB_REPO", GITHUB_REPO),
            gemini_api_key=os.getenv("GEMINI_API_KEY", GEMINI_API_KEY),
            app_secret_key=os.getenv("APP_SECRET_KEY", APP_SECRET_KEY),
        )

    def validate_github(self) -> None:
        """Verifica que les credencials de GitHub estiguin definides.

        Raises:
            ValueError: Si falta GITHUB_TOKEN o GITHUB_REPO.
        """
        if not self.github_token:
            raise ValueError("Falta la variable GITHUB_TOKEN al fitxer .env")
        if not self.github_repo:
            raise ValueError("Falta la variable GITHUB_REPO al fitxer .env")

    def validate_gemini(self) -> None:
        """Verifica que la clau de l'API de Gemini estigui definida.

        Raises:
            ValueError: Si falta GEMINI_API_KEY.
        """
        if not self.gemini_api_key:
            raise ValueError("Falta la variable GEMINI_API_KEY al fitxer .env")


