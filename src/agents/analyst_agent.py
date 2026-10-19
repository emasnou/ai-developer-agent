from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.prompts.analyst_prompts import ANALYST_SYSTEM_PROMPT

class AnalystAgent:
    def __init__(self):
        """Inicialitza els serveis de LLM i GitHub."""
        self.llm = LLMService()
        self.github = GitHubService()

    def process_requirement_and_create_issue(self, requirement: str, issue_title: str) -> dict:
        """
        1. Rep el requeriment de l'usuari.
        2. Genera la tasca amb detalls de QA mitjançant el LLM.
        3. Publica la Issue al repositori de GitHub amb l'etiqueta 'enhancement'.
        """
        print("🤖 [AnalystAgent] Analitzant requeriments i generant matriu de QA amb Gemini...")
        markdown_body = self.llm.generate_task_spec(requirement, ANALYST_SYSTEM_PROMPT)
        
        print("🤖 [AnalystAgent] Creant la Issue a GitHub...")
        issue_result = self.github.create_issue(
            title=issue_title,
            body=markdown_body,
            labels=["enhancement", "agent-analyst"]
        )
        return issue_result
