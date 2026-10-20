'''Agent CodeReview per revisar la qualitat del codi i seguretat.'''

import json
import re
from pathlib import Path
from typing import Any, Dict, List
from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.prompts.review_prompts import CODE_REVIEW_SYSTEM_PROMPT, EXTRACT_IMPROVEMENTS_PROMPT
from src.utils.logger import get_agent_logger


class CodeReviewAgent:
    '''Agent auditor de Pull Requests segons la política de codi i seguretat.'''

    def __init__(self) -> None:
        '''Inicialitza serveis, polítiques locals i logger estructurat.'''
        self.logger = get_agent_logger('CodeReviewAgent')
        self.llm = LLMService()
        self.github = GitHubService()
        policy_path = Path('docs/code_policy.md')
        self.code_policy = policy_path.read_text(encoding='utf-8') if policy_path.exists() else 'Aplica PEP8 i OWASP Top 10.'

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        '''Extreu i parseja un objecte JSON de la resposta del LLM de manera resilient.

        Args:
            text: Text pla obtingut del model LLM.

        Returns:
            Dict[str, Any]: Objecte JSON deserialitzat.
        '''
        try:
            from json_repair import repair_json
            parsed = repair_json(text, return_objects=True)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        cleaned = re.sub(r'\s*', '', text)
        cleaned = re.sub(r'\s*$', '', cleaned)
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        json_str = match.group(0) if match else cleaned.strip()

        try:
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError:
            double_quote = chr(34)
            fixed_str = re.sub(r'(?<!\\)' + double_quote, r'\\' + double_quote, json_str)
            restore_pattern = r'\\' + double_quote + r'(summary|files|path|action|content|improvements|title|description)\\' + double_quote
            fixed_str = re.sub(restore_pattern, double_quote + r'\1' + double_quote, fixed_str)
            return json.loads(fixed_str, strict=False)

    def review_pull_request(self, pr_number: int) -> Dict[str, Any]:
        '''Executa l auditoria de seguretat (OWASP Top 10), nomenclatura i performance sobre la PR.

        Args:
            pr_number: Número de la Pull Request a revisar.

        Returns:
            Dict[str, Any]: Diccionari amb el resultat i informe de revisió.
        '''
        self.logger.info(f'Iniciant auditoria per a la Pull Request #{pr_number}')
        print(f'\n🔍 [CodeReviewAgent] Analitzant els canvis de la Pull Request #{pr_number}...')

        try:
            diff_content = self.github.get_pull_request_files(pr_number)
            prompt = (
                f'POLÍTICA DE CODI I SEGURETAT (OWASP TOP 10):\n{self.code_policy}\n\n'
                f'CANVIS DE LA PULL REQUEST (DIFF):\n{diff_content}'
            )
            print('🤖 [CodeReviewAgent] Executant auditoria de seguretat, nomenclatura i performance amb Gemini...')
            review_report = self.llm.generate_task_spec(prompt, CODE_REVIEW_SYSTEM_PROMPT)

            print('💬 [CodeReviewAgent] Publicant informe de revisió a GitHub...')
            self.github.post_pr_comment(pr_number, review_report)

            is_approved = 'APROVAT' in review_report and 'CANVIS_REQUERITS' not in review_report
            self.logger.info(f'Auditoria de la PR #{pr_number} finalitzada. Aprovat: {is_approved}')

            return {
                'pr_number': pr_number,
                'approved': is_approved,
                'report': review_report,
            }
        except Exception as exc:
            self.logger.error(f'Error en l auditoria de la PR #{pr_number}: {exc}')
            raise

    def create_future_improvement_issues(self, pr_number: int, review_report: str) -> List[Dict[str, Any]]:
        '''Extreu millores a futur de l informe de review i crea GitHub Issues amb l etiqueta enhancement.

        Args:
            pr_number: Número identificador de la Pull Request.
            review_report: Contingut textual de l informe de revisió.

        Returns:
            List[Dict[str, Any]]: Llista de les Issues creades a GitHub.
        '''
        self.logger.info(f'Extreient recomanacions de millora per a la PR #{pr_number}')
        print(f'\n💡 [CodeReviewAgent] Extreient recomanacions a futur per a la PR #{pr_number}...')

        try:
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
            data = self._parse_json_response(raw_response)
            created_issues: List[Dict[str, Any]] = []

            for item in data.get('improvements', []):
                print(f'📌 Creant Issue de millora: {item["title"]}...')
                issue_res = self.github.create_issue(
                    title=item['title'],
                    body=item['description'],
                    labels=['enhancement'],
                )
                created_issues.append(issue_res)

            self.logger.info(f'S han registrat {len(created_issues)} Issues de millora per a la PR #{pr_number}')
            return created_issues
        except Exception as exc:
            self.logger.error(f'Error en extreure millores per a la PR #{pr_number}: {exc}')
            return []
