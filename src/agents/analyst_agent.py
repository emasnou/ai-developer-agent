'''Agent d anàlisi de requeriments per a la creació de tasques a GitHub.'''

from typing import Any, Dict
from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.prompts.analyst_prompts import ANALYST_SYSTEM_PROMPT
from src.utils.logger import get_agent_logger


class AnalystAgent:
    '''Agent encarregat d analitzar requeriments i generar Issues a GitHub.'''

    def __init__(self) -> None:
        '''Inicialitza els serveis de LLM, GitHub i el logger d auditoria.'''
        self.llm: LLMService = LLMService()
        self.github: GitHubService = GitHubService()
        self.logger = get_agent_logger('AnalystAgent')

    def process_requirement_and_create_issue(
        self, requirement: str, issue_title: str
    ) -> Dict[str, Any]:
        '''Processa el requeriment de l usuari i publica la Issue a GitHub.

        Args:
            requirement: Descripció detallada del requeriment.
            issue_title: Títol de la Issue a generar.

        Returns:
            Dict[str, Any]: Resultat de la Issue creada a GitHub.
        '''
        self.logger.info(f'Iniciant anàlisi de requeriment: {issue_title}')
        print('🤖 [AnalystAgent] Analitzant requeriments i generant matriu de QA amb Gemini...')
        try:
            markdown_body = self.llm.generate_task_spec(requirement, ANALYST_SYSTEM_PROMPT)
            self.logger.info('Matriu de QA i especificació generades satisfactòriament pel LLM.')

            print('🤖 [AnalystAgent] Creant la Issue a GitHub...')
            issue_result = self.github.create_issue(
                title=issue_title,
                body=markdown_body,
                labels=['enhancement', 'agent-analyst'],
            )
            created_num = issue_result.get('number')
            self.logger.info(f'Issue #{created_num} creada satisfactòriament a GitHub.')
            return issue_result
        except Exception as error:
            self.logger.error(f'Error en processar requeriment o crear la Issue: {error}')
            raise error
