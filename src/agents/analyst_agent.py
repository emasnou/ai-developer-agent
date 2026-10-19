from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.prompts.analyst_prompts import ANALYST_SYSTEM_PROMPT
from src.utils.logger import agent_logger

class AnalystAgent:
    def __init__(self):
        """Inicialitza els serveis de LLM i GitHub."""
        self.llm = LLMService()
        self.github = GitHubService()
        agent_logger.info("AnalystAgent inicialitzat correctament.", agent_id="AnalystAgent")

    def process_requirement_and_create_issue(self, requirement: str, issue_title: str) -> dict:
        """
        1. Rep el requeriment de l'usuari.
        2. Genera la tasca amb detalls de QA mitjançant el LLM.
        3. Publica la Issue al repositori de GitHub amb l'etiqueta 'enhancement'.
        """
        print("🤖 [AnalystAgent] Analitzant requeriments i generant matriu de QA amb Gemini...")
        agent_logger.info(f"Iniciant anàlisi de requeriment per a la tasca: {issue_title}", agent_id="AnalystAgent")
        markdown_body = self.llm.generate_task_spec(requirement, ANALYST_SYSTEM_PROMPT)
        
        print("🤖 [AnalystAgent] Creant la Issue a GitHub...")
        agent_logger.info(f"Creant Issue a GitHub: {issue_title}", agent_id="AnalystAgent")
        issue_result = self.github.create_issue(
            title=issue_title,
            body=markdown_body,
            labels=["enhancement", "agent-analyst"]
        )
        agent_logger.info(f"Issue creada amb èxit amb ID #{issue_result.get('number')}", agent_id="AnalystAgent")
        return issue_result
