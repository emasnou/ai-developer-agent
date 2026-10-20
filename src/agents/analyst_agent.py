'''Agent Analista per a la conversió de requeriments en tasques de GitHub.'''

from typing import Any, Dict
from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.prompts.analyst_prompts import ANALYST_SYSTEM_PROMPT
from src.utils.logger import get_agent_logger


class AnalystAgent:
    '''Agent responsable d analitzar requeriments i generar Issues a GitHub.'''

    def __init__(self) -> None:
        '''Inicialitza els serveis de LLM, GitHub i el logger d auditoria.'''
        self.logger = get_agent_logger('AnalystAgent')
        self.llm = LLMService()
        self.github = GitHubService()

    def process_requirement_and_create_issue(self, requirement: str, issue_title: str) -> Dict[str, Any]:
        '''Analitza el requeriment d usuari i publica la Issue a GitHub.

        Args:
            requirement: Descripció en text del requeriment.
            issue_title: Títol assignat a la Issue.

        Returns:
            Dict[str, Any]: Dades de la Issue creada a GitHub.
        '''
        self.logger.info(f'Iniciant processament del requeriment: {issue_title}')
        print('🤖 [AnalystAgent] Analitzant requeriments i generant matriu de QA amb Gemini...')
        try:
            markdown_body = self.llm.generate_task_spec(requirement, ANALYST_SYSTEM_PROMPT)
        except Exception as exc:
            self.logger.error(f'Error durant la generació de l especificació LLM: {exc}')
            raise

        print('🤖 [AnalystAgent] Creant la Issue a GitHub...')
        try:
            issue_result = self.github.create_issue(
                title=issue_title,
                body=markdown_body,
                labels=['enhancement', 'agent-analyst']
            )
            issue_num = issue_result.get('number', 'desconegut')
            self.logger.info(f'Issue #{issue_num} creada amb èxit a GitHub')
            return issue_result
        except Exception as exc:
            self.logger.error(f'Error en crear la Issue a GitHub: {exc}')
            raise
