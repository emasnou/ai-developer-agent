"""Mòdul de configuració i càrrega segura de variables d'entorn.

Desacobla la càrrega de variables de la seva validació estricta en temps d'importació
per permetre l'execució de tests unitaris sense dependre de fitxers .env ni connexions externes,
i dóna suport a la configuració multi-repositori de GitHub.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Carreguem .env de forma permissiva (sense fallar si no existeix) per permetre
# l'execució de tests unitaris en entorns CI/CD aïllats sense fitxers de secrets
load_dotenv()


def _ensure_local_git_hooks_executable() -> None:
    """Garanteix permisos d'execució (`0o755`) als hooks locals de Git si existeixen."""
    hooks_dir = Path(__file__).resolve().parents[2] / ".git" / "hooks"
    for hook_name in ("pre-commit", "post-commit"):
        hook_path = hooks_dir / hook_name
        if hook_path.is_file():
            try:
                current_mode = hook_path.stat().st_mode & 0o777
                if current_mode != 0o755:
                    hook_path.chmod(0o755)
            except OSError:
                pass


_ensure_local_git_hooks_executable()

GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")
GITHUB_REPO: Optional[str] = os.getenv("GITHUB_REPO")
GITHUB_REPOS_RAW: Optional[str] = os.getenv("GITHUB_REPOS")
GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
APP_SECRET_KEY: Optional[str] = os.getenv("APP_SECRET_KEY")


def parse_repo_list(
    raw_repos: Optional[str], default_repo: Optional[str] = None
) -> tuple[str, ...]:
    """Analitza una cadena de repositoris separats per comes i retorna una tupla sense duplicats.

    Args:
        raw_repos: Cadena amb noms de repositori separats per comes (ex: 'org/repo1,org/repo2').
        default_repo: Repositori principal opcional per incloure al principi de la llista.

    Returns:
        tuple[str, ...]: Tupla ordenada i sense duplicats dels repositoris configurats.
    """
    repos: list[str] = []
    if default_repo and default_repo.strip():
        repos.append(default_repo.strip())

    if raw_repos:
        for item in raw_repos.split(","):
            cleaned = item.strip()
            if cleaned and cleaned not in repos:
                repos.append(cleaned)

    return tuple(repos)


GITHUB_REPOS: tuple[str, ...] = parse_repo_list(GITHUB_REPOS_RAW, GITHUB_REPO)


@dataclass(frozen=True)
class AppConfig:
    """Estructura de configuració validada de l'aplicació.

    Attributes:
        github_token: Token d'autenticació per a l'API de GitHub.
        github_repo: Repositori actiu per defecte en format 'propietari/nom'.
        github_repos: Tupla de repositoris configurats disponibles per seleccionar.
        gemini_api_key: Clau d'accés a l'API de Google Gemini.
        app_secret_key: Clau secreta opcional per a mòduls criptogràfics.
    """

    github_token: Optional[str] = None
    github_repo: Optional[str] = None
    github_repos: tuple[str, ...] = ()
    gemini_api_key: Optional[str] = None
    app_secret_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> AppConfig:
        """Construeix una instància de configuració llegint l'entorn actual.

        Returns:
            AppConfig: Instància amb els valors actuals de les variables d'entorn.
        """
        default_repo = os.getenv("GITHUB_REPO", GITHUB_REPO)
        raw_repos = os.getenv("GITHUB_REPOS", GITHUB_REPOS_RAW)
        return cls(
            github_token=os.getenv("GITHUB_TOKEN", GITHUB_TOKEN),
            github_repo=default_repo,
            github_repos=parse_repo_list(raw_repos, default_repo),
            gemini_api_key=os.getenv("GEMINI_API_KEY", GEMINI_API_KEY),
            app_secret_key=os.getenv("APP_SECRET_KEY", APP_SECRET_KEY),
        )

    def validate_github(self, require_repo: bool = True) -> None:
        """Verifica que les credencials de GitHub estiguin definides.

        Args:
            require_repo: Si és True, exigeix també que `github_repo` estigui definit.

        Raises:
            ValueError: Si falta GITHUB_TOKEN o (quan s'exigeix) GITHUB_REPO.
        """
        if not self.github_token:
            raise ValueError("Falta la variable GITHUB_TOKEN al fitxer .env")
        if require_repo and not self.github_repo:
            raise ValueError("Falta seleccionar un repositori o definir GITHUB_REPO al fitxer .env")

    def validate_gemini(self) -> None:
        """Verifica que la clau de l'API de Gemini estigui definida.

        Raises:
            ValueError: Si falta GEMINI_API_KEY.
        """
        if not self.gemini_api_key:
            raise ValueError("Falta la variable GEMINI_API_KEY al fitxer .env")
