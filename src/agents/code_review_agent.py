"""Agent CodeReview per auditar la qualitat del codi, el rendiment i la seguretat (OWASP Top 10)."""

from __future__ import annotations

from typing import Any, Optional

from src.agents.base_agent import BaseAgent
from src.prompts.review_prompts import CODE_REVIEW_SYSTEM_PROMPT, EXTRACT_IMPROVEMENTS_PROMPT
from src.schemas.agent_schemas import CodeReviewResponse, ImprovementsResponse
from src.services.github_service import GitHubService
from src.services.llm_service import LLMService
from src.utils.json_parser import parse_generic_json_response


class CodeReviewAgent(BaseAgent):
    """Agent encarregat d'auditar Pull Requests i generar Issues de millora contínua."""

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        github_service: Optional[GitHubService] = None,
    ) -> None:
        """Inicialitza el CodeReviewAgent amb accés diferit als serveis, política i logger.

        Args:
            llm_service: Instància opcional de LLMService per a injecció de dependències.
            github_service: Instància opcional de GitHubService per a injecció de dependències.
        """
        super().__init__(
            agent_name="CodeReviewAgent",
            llm_service=llm_service,
            github_service=github_service,
        )

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """Extreu i parseja un objecte JSON de la resposta del LLM de manera resilient.

        Args:
            text: Resposta en text cru retornada pel model LLM.

        Returns:
            dict[str, Any]: Diccionari extret o `{}` si no es pot parsejar.
        """
        return parse_generic_json_response(text)

    def review_pull_request(self, pr_number: int) -> dict[str, Any]:
        """Executa l'auditoria de seguretat, nomenclatura i rendiment sobre una Pull Request.

        Args:
            pr_number: Número identificador de la Pull Request a GitHub.

        Returns:
            dict[str, Any]: Diccionari amb `pr_number`, `approved` (bool) i `report` (str).

        Raises:
            Exception: Si es produeix un error durant la comunicació amb el LLM.
        """
        self.logger.info(f"Inici de revisió de codi per a la Pull Request #{pr_number}.")
        print(f"\n🔍 [CodeReviewAgent] Analitzant els canvis de la Pull Request #{pr_number}...")

        diff_content = self.github.get_pull_request_files(pr_number)
        prompt = (
            f"POLÍTICA DE CODI I SEGURETAT (OWASP TOP 10):\n{self.code_policy}\n\n"
            f"CANVIS DE LA PULL REQUEST (DIFF):\n{diff_content}"
        )

        print("🤖 [CodeReviewAgent] Executant auditoria amb Gemini...")
        try:
            raw_response = self.llm.generate_task_spec(
                prompt,
                CODE_REVIEW_SYSTEM_PROMPT,
                response_schema=CodeReviewResponse,
            )
        except Exception as e:
            self.logger.error(f"Error en l'auditoria de la PR #{pr_number} amb el LLM: {e}")
            raise

        parsed = self._parse_json_response(raw_response)
        report_markdown = (
            parsed.get("report")
            or parsed.get("summary")
            or parsed.get("content")
            or raw_response
        )

        print("💬 [CodeReviewAgent] Publicant informe de revisió a GitHub...")
        try:
            self.github.post_pr_comment(pr_number, report_markdown)
            self.logger.info(f"Informe de revisió publicat a la PR #{pr_number}.")
        except Exception as e:
            self.logger.error(f"Error en publicar el comentari a la PR #{pr_number}: {e}")

        if "approved" in parsed:
            is_approved = bool(parsed["approved"])
        else:
            is_approved = "APROVAT" in report_markdown and "CANVIS_REQUERITS" not in report_markdown

        self.logger.info(f"Revisió finalitzada per a la PR #{pr_number}. Aprovat: {is_approved}.")
        return {
            "pr_number": pr_number,
            "approved": is_approved,
            "report": report_markdown,
        }

    def create_future_improvement_issues(
        self, pr_number: int, review_report: str
    ) -> list[dict[str, Any]]:
        """Extreu millores a futur de l'informe de review i crea GitHub Issues amb 'enhancement'.

        Args:
            pr_number: Número identificador de la Pull Request revisada.
            review_report: Contingut en Markdown de l'informe d'auditoria.

        Returns:
            list[dict[str, Any]]: Llista d'Issues creades a GitHub.
        """
        self.logger.info(f"Extreient millores a futur per a la PR #{pr_number}.")
        print(f"\n💡 [CodeReviewAgent] Extreient recomanacions a futur per a la PR #{pr_number}...")

        pr = self.github.repo.get_pull(pr_number)
        files = list(pr.get_files())
        code_filename = next((f.filename for f in files if f.filename.startswith("src/")), "src/")
        test_filename = next((f.filename for f in files if f.filename.startswith("tests/")), "tests/")

        prompt = EXTRACT_IMPROVEMENTS_PROMPT.format(
            review_report=review_report,
            code_filename=code_filename,
            test_filename=test_filename,
        )

        raw_response = self.llm.generate_task_spec(
            prompt,
            CODE_REVIEW_SYSTEM_PROMPT,
            response_schema=ImprovementsResponse,
        )

        try:
            data = self._parse_json_response(raw_response)
            created_issues: list[dict[str, Any]] = []

            for item in data.get("improvements", []):
                print(f"📌 Creant Issue de millora: {item['title']}...")
                issue_res = self.github.create_issue(
                    title=item["title"],
                    body=item["description"],
                    labels=["enhancement"],
                )
                created_issues.append(issue_res)
                self.logger.info(f"Issue de millora creada: {item['title']}")

            return created_issues
        except Exception as e:
            self.logger.error(f"Error en generar les Issues de millora: {e}")
            print(f"⚠️ Error en generar les Issues de millora: {e}")
            return []

