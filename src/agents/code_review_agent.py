"""
Agent CodeReview per revisar la qualitat del codi i seguretat.
"""
import json
from json_repair import repair_json
import re
from pathlib import Path
from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.schemas.agent_schemas import CodeReviewResponse, ImprovementsResponse
from src.prompts.review_prompts import CODE_REVIEW_SYSTEM_PROMPT, EXTRACT_IMPROVEMENTS_PROMPT
from src.utils.logger import AgentLogger, StructuredAgentAdapter

class CodeReviewAgent:
    def __init__(self):
        """Inicialitza els serveis, carrega la política de codi local i el logger."""
        self.llm = LLMService()
        self.github = GitHubService()
        base_logger = AgentLogger.get_logger("CodeReviewAgent")
        self.logger = StructuredAgentAdapter(base_logger, "CodeReviewAgent")
        policy_path = Path("docs/code_policy.md")
        self.code_policy = policy_path.read_text() if policy_path.exists() else "Aplica PEP8 i OWASP Top 10."

    def _parse_json_response(self, text: str) -> dict:
        """Extreu i parseja un objecte JSON de la resposta del LLM de manera resilient."""
        if not text or not text.strip():
            return {}

        try:
            parsed = json.loads(text.strip(), strict=False)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        cleaned = re.sub(r'```(?:json|yaml)?\s*', '', text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r'```\s*$', '', cleaned, flags=re.MULTILINE).strip()

        try:
            parsed = json.loads(cleaned, strict=False)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        try:
            parsed = repair_json(cleaned, return_objects=True)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                for elem in parsed:
                    if isinstance(elem, dict) and any(k in elem for k in ["approved", "report", "improvements"]):
                        return elem
        except Exception:
            pass

        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        json_str = match.group(0) if match else cleaned.strip()

        try:
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError:
            try:
                sanitized = re.sub(r'\\(?![\\"/bfnrtu]|u[0-9a-fA-F]{4})', r'\\\\', json_str)
                return json.loads(sanitized, strict=False)
            except Exception:
                return {}

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
        try:
            raw_response = self.llm.generate_task_spec(
                prompt,
                CODE_REVIEW_SYSTEM_PROMPT,
                response_schema=CodeReviewResponse
            )
        except Exception as e:
            self.logger.error(f'Error en l\'auditoria de la PR #{pr_number} amb el LLM: {e}')
            raise e

        report_markdown = raw_response
        try:
            parsed = self._parse_json_response(raw_response)
            if isinstance(parsed, dict):
                report_markdown = parsed.get('report') or parsed.get('summary') or parsed.get('content') or raw_response
        except Exception:
            report_markdown = raw_response

        print('💬 [CodeReviewAgent] Publicant informe de revisió a GitHub...')
        try:
            self.github.post_pr_comment(pr_number, report_markdown)
            self.logger.info(f'Informe de revisió publicat a la PR #{pr_number}.')
        except Exception as e:
            self.logger.error(f'Error en publicar el comentari a la PR #{pr_number}: {e}')

        if isinstance(parsed, dict) and "approved" in parsed:
            is_approved = bool(parsed["approved"])
        else:
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
        self.logger.info(f'Extreient millores a futur per a la PR #{pr_number}.')
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

        raw_response = self.llm.generate_task_spec(
            prompt,
            CODE_REVIEW_SYSTEM_PROMPT,
            response_schema=ImprovementsResponse
        )
        
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
                self.logger.info(f"Issue de millora creada: {item['title']}")

            return created_issues
        except Exception as e:
            self.logger.error(f"Error en generar les Issues de millora: {e}")
            print(f"⚠️ Error en generar les Issues de millora: {e}")
            return []
