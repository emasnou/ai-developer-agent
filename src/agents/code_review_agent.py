'''Agent CodeReview per revisar la qualitat del codi i seguretat.'''

import json
import re
from pathlib import Path
from typing import Any, Dict, List
from json_repair import repair_json
from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.prompts.review_prompts import (
    CODE_REVIEW_SYSTEM_PROMPT,
    EXTRACT_IMPROVEMENTS_PROMPT,
)
from src.utils.logger import get_agent_logger


class CodeReviewAgent:
    '''Agent per auditar Pull Requests segons criteris OWASP Top 10 i Clean Code.'''

    def __init__(self) -> None:
        '''Inicialitza serveis, polítiques de codi i registre d auditoria.'''
        self.llm: LLMService = LLMService()
        self.github: GitHubService = GitHubService()
        self.logger = get_agent_logger('CodeReviewAgent')
        policy_path = Path('docs/code_policy.md')
        self.code_policy: str = (
            policy_path.read_text(encoding='utf-8')
            if policy_path.exists()
            else 'Aplica PEP8 i OWASP Top 10.'
        )

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        '''Extreu i parseja un objecte JSON de la resposta del LLM de manera resilient.

        Args:
            text: Resposta crua retornada pel model LLM.

        Returns:
            Dict[str, Any]: Diccionari amb les dades extretes.
        '''
        try:
            parsed = repair_json(text, return_objects=True)
            if isinstance(parsed, dict):
                return parsed
        except ImportError:
            pass

        cleaned = re.sub(r'\s*', '', text)
        cleaned = re.sub(r'\s*$', '', cleaned)
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        json_str = match.group(0) if match else cleaned.strip()

        try:
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError:
            q = chr(34)
            fixed_str = re.sub(r'(?<!\\)' + q, r'\\' + q, json_str)
            pattern = r'\\' + q + r'(summary|files|path|action|content|improvements|title|description)\\' + q
            fixed_str = re.sub(pattern, q + r'\1' + q, fixed_str)
            return json.loads(fixed_str, strict=False)

    def review_pull_request(self, pr_number: int) -> Dict[str, Any]:
        '''Executa l auditoria de seguretat i nomenclatura sobre la PR.

        Args:
            pr_number: Número de la Pull Request a auditar.

        Returns:
            Dict[str, Any]: Resultat de la revisió amb l informe i aprovació.
        '''
        self.logger.info(f'Iniciant auditoria de seguretat per a la Pull Request #{pr_number}.')
        print(f'\n🔍 [CodeReviewAgent] Analitzant els canvis de la Pull Request #{pr_number}...')
        diff_content = self.github.get_pull_request_files(pr_number)
        prompt = (
            f'POLÍTICA DE CODI I SEGURETAT (OWASP TOP 10):\n{self.code_policy}\n\n'
            f'CANVIS DE LA PULL REQUEST (DIFF):\n{diff_content}'
        )

        print('🤖 [CodeReviewAgent] Executant auditoria amb Gemini...')
        review_report = self.llm.generate_task_spec(prompt, CODE_REVIEW_SYSTEM_PROMPT)
        print('💬 [CodeReviewAgent] Publicant informe de revisió a GitHub...')
        self.github.post_pr_comment(pr_number, review_report)
        is_approved = 'APROVAT' in review_report and 'CANVIS_REQUERITS' not in review_report

        if is_approved:
            self.logger.info(f'Pull Request #{pr_number} revisada amb resultat APROVAT.')
        else:
            self.logger.warning(f'Pull Request #{pr_number} revisada amb resultat CANVIS_REQUERITS.')

        return {
            'pr_number': pr_number,
            'approved': is_approved,
            'report': review_report,
        }

    def create_future_improvement_issues(
        self, pr_number: int, review_report: str
    ) -> List[Dict[str, Any]]:
        '''Extreu millores a futur de l informe de revisió i crea Issues de tipus enhancement.

        Args:
            pr_number: Número de la Pull Request analitzada.
            review_report: Text de l informe generat.

        Returns:
            List[Dict[str, Any]]: Llista de tasques creades.
        '''
        self.logger.info(f'Extreient millores futures per a la PR #{pr_number}.')
        print(f'\n💡 [CodeReviewAgent] Extreient recomanacions a futur per a la PR #{pr_number}...')
        pr = self.github.repo.get_pull(pr_number)
        files = list(pr.get_files())
        code_filename = next((f.filename for f in files if f.filename.startswith('src/')), 'src/')
        test_filename = next((f.filename for f in files if f.filename.startswith('tests/')), 'tests/')

        prompt = EXTRACT_IMPROVEMENTS_PROMPT.format(
            review_report=review_report,
            code_filename=code_filename,
            test_filename=test_filename,
        )
        raw_response = self.llm.generate_task_spec(prompt, CODE_REVIEW_SYSTEM_PROMPT)
        try:
            data = self._parse_json_response(raw_response)
            created_issues: List[Dict[str, Any]] = []
            for item in data.get('improvements', []):
                issue_res = self.github.create_issue(
                    title=item['title'],
                    body=item['description'],
                    labels=['enhancement'],
                )
                created_issues.append(issue_res)
                self.logger.info(f'Issue de millora creada: {item.get("title")}')
            return created_issues
        except Exception as error:
            self.logger.warning(f'Error en extreure millores futures per a la PR #{pr_number}: {error}')
            print(f'⚠️ Error en generar les Issues de millora: {error}')
            return []
