"""
Agent CodeReview per revisar la qualitat del codi i seguretat.
"""
import json
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
        """Extreu un objecte JSON de la resposta del LLM de manera segura."""
        cleaned = re.sub(r'```json\s*', '', text)
        cleaned = re.sub(r'```\s*$', '', cleaned)
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        return json.loads(match.group(0) if match else cleaned.strip())

    def review_pull_request(self, pr_number: int) -> dict:
        """Executa l'auditoria de seguretat (OWASP Top 10), nomenclatura i performance sobre la PR."""
        print(f"\n🔍 [CodeReviewAgent] Analitzant els canvis de la Pull Request #{pr_number}...")
        
        diff_content = self.github.get_pull_request_files(pr_number)
        
        prompt = (
            f"POLÍTICA DE CODI I SEGURETAT (OWASP TOP 10):\n{self.code_policy}\n\n"
            f"CANVIS DE LA PULL REQUEST (DIFF):\n{diff_content}"
        )
        
        print("🤖 [CodeReviewAgent] Executant auditoria de seguretat, nomenclatura i performance amb Gemini...")
        review_report = self.llm.generate_task_spec(prompt, CODE_REVIEW_SYSTEM_PROMPT)
        
        print("💬 [CodeReviewAgent] Publicant informe de revisió a GitHub...")
        self.github.post_pr_comment(pr_number, review_report)
        
        is_approved = "APROVAT" in review_report and "CANVIS_REQUERITS" not in review_report
        
        return {
            "pr_number": pr_number,
            "approved": is_approved,
            "report": review_report
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
