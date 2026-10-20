"""
Agent CodeReview per revisar la qualitat del codi i seguretat.
"""
import json
from json_repair import repair_json
import re
from pathlib import Path
from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.prompts.review_prompts import CODE_REVIEW_SYSTEM_PROMPT, EXTRACT_IMPROVEMENTS_PROMPT

class CodeReviewAgent:
    def __init__(self):
        """Inicialitza els serveis i carrega la política de codi local."""
        self.llm = LLMService()
        self.github = GitHubService()
        policy_path = Path("docs/code_policy.md")
        self.code_policy = policy_path.read_text() if policy_path.exists() else "Aplica PEP8 i OWASP Top 10."

    def _parse_json_response(self, text: str) -> dict:
        """Extreu i parseja un objecte JSON de la resposta del LLM de manera resilient."""
        # Intenta utilitzar la llibreria json_repair si està instal·lada
        try:
            parsed = repair_json(text, return_objects=True)
            if isinstance(parsed, dict):
                return parsed
        except ImportError:
            pass

        # Fallback manual si json_repair no està instal·lat
        cleaned = re.sub(r'```json\s*', '', text)
        cleaned = re.sub(r'```\s*$', '', cleaned)
        
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        json_str = match.group(0) if match else cleaned.strip()

        try:
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError:
            # Reemplacem cometes no escapades o caràcters de control dins de valors multilínia
            sanitized = re.sub(
                r'[\x00-\x1F\x7F]',
                lambda m: f"\\u{ord(m.group(0)):04x}" if m.group(0) not in ('\n', '\r', '\t') else m.group(0),
                json_str
            )
            try:
                return json.loads(sanitized, strict=False)
            except json.JSONDecodeError:
                # Reemplaça cometes problemàtiques que no estiguin precedides per \
                fixed_str = re.sub(r'(?<!\\)"', r'\"', json_str)
                # Restaura cometes de les claus principals del JSON
                fixed_str = re.sub(r'\\"(summary|files|path|action|content)\\"', r'"\1"', fixed_str)
                return json.loads(fixed_str, strict=False)

    def review_pull_request(self, pr_number: int) -> dict:
        '''Executa l auditoria de seguretat, nomenclatura i rendiment sobre la PR.'''
        self.logger.info(f'Inici de revisio de codi per a la Pull Request #{pr_number}.')
        print(f'\n🔍 [CodeReviewAgent] Analitzant els canvis de la Pull Request #{pr_number}...')

        diff_content = self.github.get_pull_request_files(pr_number)
        prompt = (
            f'POLÍTICA DE CODI I SEGURETAT (OWASP TOP 10):\n{self.code_policy}\n\n'
            f'CANVIS DE LA PULL REQUEST (DIFF):\n{diff_content}'
        )

        print('🤖 [CodeReviewAgent] Executant auditoria amb Gemini...')
        raw_response = self.llm.generate_task_spec(prompt, CODE_REVIEW_SYSTEM_PROMPT)

        # Extreiem el Markdown de la resposta JSON o fem el parsejat resilient
        report_markdown = raw_response
        try:
            parsed = self._parse_json_response(raw_response)
            if isinstance(parsed, dict):
                # Si el JSON conté una clau 'report', 'summary' o 'content', extreiem el contingut Markdown
                report_markdown = parsed.get('report') or parsed.get('summary') or parsed.get('content') or raw_response
        except Exception:
            # Si no és JSON o falla el parsejat, fem servir el text directament
            report_markdown = raw_response

        print('💬 [CodeReviewAgent] Publicant informe de revisió a GitHub...')
        self.github.post_pr_comment(pr_number, report_markdown)

        is_approved = 'APROVAT' in report_markdown and 'CANVIS_REQUERITS' not in report_markdown
        self.logger.info(
            f'Revisió finalitzada per a la PR #{pr_number}. Aprovat: {is_approved}.'
        )

        return {
            'pr_number': pr_number,
            'approved': is_approved,
            'report': report_markdown,
        }


    def create_future_improvement_issues(self, pr_number: int, review_report: str) -> list:
        """Extreu millores a futur de l'informe de review i crea GitHub Issues amb l'etiqueta 'enhancement'."""
        print(f"\n💡 [CodeReviewAgent] Extreient recomanacions a futur per a la PR #{pr_number}...")
        
        pr = self.github.repo.get_pull(pr_number)
        files = list(pr.get_files())
        code_filename = next((f.filename for f in files if f.filename.startswith("src/")), "src/")
        test_filename = next((f.filename for f in files if f.filename.startswith("tests/")), "tests/")

        prompt = EXTRACT_IMPROVEMENTS_PROMPT.format(
            review_report=review_report,
            code_filename=code_filename,
            test_filename=test_filename
        )

        raw_response = self.llm.generate_task_spec(prompt, CODE_REVIEW_SYSTEM_PROMPT)
        
        try:
            data = self._parse_json_response(raw_response)
            created_issues = []

            for item in data.get("improvements", []):
                print(f"📌 Creant Issue de millora: {item['title']}...")
                issue_res = self.github.create_issue(
                    title=item["title"],
                    body=item["description"],
                    labels=["enhancement"]
                )
                created_issues.append(issue_res)

            return created_issues
        except Exception as e:
            print(f"⚠️ Error en generar les Issues de millora: {e}")
            return []
