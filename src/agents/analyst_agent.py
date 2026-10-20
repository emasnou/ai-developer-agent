from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.prompts.analyst_prompts import ANALYST_SYSTEM_PROMPT
from src.utils.logger import AgentLogger, StructuredAgentAdapter

class AnalystAgent:
    def __init__(self):
        """Inicialitza els serveis de LLM i GitHub i el sistema de logging."""
        self.llm = LLMService()
        self.github = GitHubService()
        base_logger = AgentLogger.get_logger("AnalystAgent")
        self.logger = StructuredAgentAdapter(base_logger, "AnalystAgent")

    def process_requirement_and_create_issue(self, requirement: str, issue_title: str) -> dict:
        """
        1. Rep el requeriment de l'usuari.
        2. Genera la tasca amb detalls de QA mitjançant el LLM.
        3. Publica la Issue al repositori de GitHub amb l'etiqueta 'enhancement'.
        """
        self.logger.info(f"Iniciant anàlisi de requeriment per a la tasca: '{issue_title}'")
        print("🤖 [AnalystAgent] Analitzant requeriments i generant matriu de QA amb Gemini...")
        try:
            markdown_body = self.llm.generate_task_spec(
                requirement,
                ANALYST_SYSTEM_PROMPT,
                force_json=False
            )
        except Exception as e:
            self.logger.error(f"Error en generar l'especificació amb el LLM: {e}")
            raise e
        
        print("🤖 [AnalystAgent] Creant la Issue a GitHub...")
        try:
            issue_result = self.github.create_issue(
                title=issue_title,
                body=markdown_body,
                labels=["enhancement", "agent-analyst"]
            )
            self.logger.info(f"Issue creada amb èxit a GitHub: {issue_result.get('url')}")
            return issue_result
        except Exception as e:
            self.logger.error(f"Error en publicar la Issue a GitHub: {e}")
            raise e
