"""Agent Analista encarregat de transformar requeriments funcionals en Issues de GitHub."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from src.agents.base_agent import BaseAgent
from src.prompts.analyst_prompts import build_analyst_system_prompt
from src.services.github_service import GitHubService
from src.services.llm_service import LLMService
from src.utils.github_templates import FEATURE_ISSUE_TEMPLATE_REL_PATH


class AnalystAgent(BaseAgent):
    """Agent especialitzat en l'anàlisi funcional, BDD i generació de matrius de QA."""

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        github_service: Optional[GitHubService] = None,
        repo_name: Optional[str] = None,
        issue_template_path: Path = Path(FEATURE_ISSUE_TEMPLATE_REL_PATH),
    ) -> None:
        """Inicialitza l'Agent Analista amb els serveis de LLM, GitHub, plantilla i logging.

        Args:
            llm_service: Instància opcional de LLMService per a injecció de dependències.
            github_service: Instància opcional de GitHubService per a injecció de dependències.
            repo_name: Nom opcional del repositori (`owner/repo`) on crear les Issues.
            issue_template_path: Ruta de la plantilla d'Issue de GitHub a aplicar.
        """
        super().__init__(
            agent_name="AnalystAgent",
            llm_service=llm_service,
            github_service=github_service,
            repo_name=repo_name,
        )
        self.issue_template_path: Path = issue_template_path

    def process_requirement_and_create_issue(
        self, requirement: str, issue_title: str
    ) -> dict[str, Any]:
        """Analitza el requeriment de l'usuari i publica una Issue estructurada a GitHub.

        Utilitza la plantilla `.github/ISSUE_TEMPLATE/feature_request.md` per garantir
        que la Issue inclogui Història d'Usuari, Criteris d'Acceptació BDD i Matriu de QA.

        Args:
            requirement: Descripció en llenguatge natural de la funcionalitat requerida.
            issue_title: Títol resumit per a la Issue de GitHub.

        Returns:
            dict[str, Any]: Diccionari amb el número, títol i URL de la Issue creada.

        Raises:
            Exception: Si es produeix un error durant la generació del LLM o la crida a GitHub.
        """
        self.logger.info(f"Iniciant anàlisi de requeriment per a la tasca: '{issue_title}'")
        print("🤖 [AnalystAgent] Analitzant requeriments i generant matriu de QA amb Gemini...")
        system_prompt = build_analyst_system_prompt(template_path=self.issue_template_path)
        try:
            markdown_body = self.llm.generate_task_spec(
                requirement,
                system_prompt,
                force_json=False,
            )
        except Exception as e:
            self.logger.error(f"Error en generar l'especificació amb el LLM: {e}")
            raise

        print("🤖 [AnalystAgent] Creant la Issue a GitHub...")
        try:
            issue_result = self.github.create_issue(
                title=issue_title,
                body=markdown_body,
                labels=["enhancement", "agent-analyst"],
            )
            self.logger.info(f"Issue creada amb èxit a GitHub: {issue_result.get('url')}")
            return issue_result
        except Exception as e:
            self.logger.error(f"Error en publicar la Issue a GitHub: {e}")
            raise
