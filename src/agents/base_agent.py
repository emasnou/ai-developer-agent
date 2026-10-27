"""Classe base comuna per a tots els agents d'IA del sistema.

Centralitza la configuració del logger estructurat, la càrrega de la política de codi
i la injecció o inicialització diferida (lazy) dels serveis de LLM i GitHub per facilitar
els tests unitaris sense dependències de xarxa ni credencials externes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.services.github_service import GitHubService
from src.services.llm_service import LLMService
from src.utils.logger import AgentLogger, StructuredAgentAdapter

DEFAULT_POLICY_FALLBACK: str = "Aplica PEP8 i OWASP Top 10."


class BaseAgent:
    """Classe base que proporciona logging estructurat, política de codi i accés als serveis."""

    def __init__(
        self,
        agent_name: str,
        llm_service: Optional[LLMService] = None,
        github_service: Optional[GitHubService] = None,
        policy_path: Path = Path("docs/code_policy.md"),
        repo_name: Optional[str] = None,
    ) -> None:
        """Inicialitza l'agent amb injecció opcional de serveis i càrrega de política.

        Args:
            agent_name: Nom identificador de l'agent per als registres d'auditoria.
            llm_service: Instància opcional de LLMService (per a injecció o mocks en tests).
            github_service: Instància opcional de GitHubService (per a injecció o mocks en tests).
            policy_path: Ruta al fitxer Markdown amb la política de codi i seguretat.
            repo_name: Nom opcional del repositori (`owner/repo`) sobre el qual operar.
        """
        self._llm: Optional[LLMService] = llm_service
        self._github: Optional[GitHubService] = github_service
        self._repo_name: Optional[str] = repo_name.strip() if repo_name else None
        base_logger = AgentLogger.get_logger(agent_name)
        self.logger = StructuredAgentAdapter(base_logger, agent_name)
        self.code_policy: str = (
            policy_path.read_text(encoding="utf-8")
            if policy_path.exists()
            else DEFAULT_POLICY_FALLBACK
        )

    @property
    def active_repo_name(self) -> Optional[str]:
        """Obté el nom del repositori actiu associat a l'agent.

        Returns:
            Optional[str]: Nom del repositori (`owner/repo`) o None si no s'ha definit.
        """
        if self._github is not None and hasattr(self._github, "active_repo_name"):
            active = getattr(self._github, "active_repo_name")
            if isinstance(active, str) and active:
                return active
        return self._repo_name

    @property
    def llm(self) -> LLMService:
        """Obté la instància de LLMService, inicialitzant-la sota demanda si cal.

        Returns:
            LLMService: Client configurat del servei LLM.
        """
        if self._llm is None:
            self._llm = LLMService()
        return self._llm

    @llm.setter
    def llm(self, service: LLMService) -> None:
        """Permet substituir la instància de LLMService (útil en tests).

        Args:
            service: Nova instància o mock de LLMService.
        """
        self._llm = service

    @property
    def github(self) -> GitHubService:
        """Obté la instància de GitHubService, inicialitzant-la sota demanda si cal.

        Returns:
            GitHubService: Client configurat del servei de GitHub.
        """
        if self._github is None:
            self._github = GitHubService(repo_name=self._repo_name)
        return self._github

    @github.setter
    def github(self, service: GitHubService) -> None:
        """Permet substituir la instància de GitHubService (útil en tests).

        Args:
            service: Nova instància o mock de GitHubService.
        """
        self._github = service

