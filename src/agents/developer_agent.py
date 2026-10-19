import os
import re
import json
import subprocess
from pathlib import Path
from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.prompts.developer_prompts import (
    DEVELOPER_SYSTEM_PROMPT,
    DEVELOPER_FIX_PROMPT,
    DEVELOPER_REMEDIATION_PROMPT
)
from src.utils.logger import agent_logger

class DeveloperAgent:
    def __init__(self):
        """Inicialitza els serveis necessaris i carrega la política de codi local."""
        self.llm = LLMService()
        self.github = GitHubService()
        policy_path = Path("docs/code_policy.md")
        self.code_policy = policy_path.read_text() if policy_path.exists() else "Aplica PEP8 i OWASP Top 10."
        agent_logger.info("DeveloperAgent inicialitzat correctament.", agent_id="DeveloperAgent")

    def _parse_json_response(self, text: str) -> dict:
        """Extreu i parseja un objecte JSON de la resposta del LLM de manera resilient."""
        cleaned = re.sub(r'\s*', '', text)
        cleaned = re.sub(r'```\s*$', '', cleaned)
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        json_str = match.group(0) if match else cleaned.strip()

        try:
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError:
            sanitized = re.sub(r'[\x00-\x1F\x7F]', lambda m: f"\\u{ord(m.group(0)):04x}" if m.group(0) not in ('\n', '\r', '\t') else m.group(0), json_str)
            try:
                return json.loads(sanitized, strict=False)
            except json.JSONDecodeError as err:
                agent_logger.error(f"Error residual en parsejar JSON: {err}", agent_id="DeveloperAgent")
                sanitized_quotes = re.sub(r'(?<!\\)"', r'\\"', json_str)
                sanitized_quotes = re.sub(r'\\"(summary|files|path|action|content)\"', r'"\1"', sanitized_quotes)
                return json.loads(sanitized_quotes, strict=False)

    def _fetch_main_branch_source_files(self, repo_tree: list[str]) -> str:
        """Llegeix el contingut dels fitxers existents a 'src/' directament des de la branca 'main' de GitHub."""
        src_files = [p for p in repo_tree if p.startswith("src/") and p.endswith(".py")]
        if not src_files:
            return "No hi ha fitxers .py existents a src/ a la branca main."

        contents = []
        for file_path in src_files:
            content = self.github.get_file_content(file_path, ref="main")
            if content:
                contents.append(f"--- FITXER REMOT (main): {file_path} ---\n{content}\n")

        return "\n".join(contents) if contents else "Cap fitxer .py trobat a src/ a main."

    def _write_files_to_disk(self, files_list: list[dict]) -> list[Path]:
        """Escriu o actualitza localment només els fitxers especificats per la IA."""
        saved_paths = []
        for file_item in files_list:
            file_path = Path(file_item["path"])
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file_item["content"], encoding="utf-8")
            saved_paths.append(file_path)
            agent_logger.info(f"Fitxer preparat localment: {file_path}", agent_id="DeveloperAgent")
        return saved_paths

    def _get_target_changes_only(self, files_list: list[dict]) -> list[dict]:
        """Retorna ÚNICAMENT els fitxers generats o modificats en aquesta tasca concreta."""
        files_to_commit = []
        for file_item in files_list:
            p = Path(file_item["path"])
            if p.exists() and p.is_file():
                files_to_commit.append({
                    "path": str(p),
                    "content": p.read_text(encoding="utf-8")
                })
        return files_to_commit

    def develop_and_test(self, issue_number: int, max_retries: int = 3):
        agent_logger.info(f"Carregant la Issue #{issue_number} des de GitHub per desenvolupar.", agent_id="DeveloperAgent")
        issue = self.github.get_issue(issue_number)
        
        branch_name = f"feature/issue-{issue_number}"
        agent_logger.info(f"Creant la branca de treball '{branch_name}' a partir de 'main'.", agent_id="DeveloperAgent")
        self.github.create_branch(base_branch="main", new_branch=branch_name)

        repo_tree = self.github.get_repository_tree(ref="main")
        tree_str = "\n".join(repo_tree) if repo_tree else "Repositori buit o inicial"
        existing_files_content = self._fetch_main_branch_source_files(repo_tree)

        prompt = f"Títol de la Issue: {issue.title}\n\nEspecificació:\n{issue.body}"
        agent_logger.info(f"Generant fitxers per a la Issue #{issue_number} mitjançant LLM.", agent_id="DeveloperAgent")
        
        system_prompt = DEVELOPER_SYSTEM_PROMPT.format(
            code_policy=self.code_policy,
            repo_tree=tree_str,
            existing_files_content=existing_files_content
        )
        
        raw_response = self.llm.generate_task_spec(prompt, system_prompt)
        
        try:
            data = self._parse_json_response(raw_response)
        except Exception as e:
            agent_logger.error(f"Error en extreure el JSON multi-fitxer de la IA: {e}", agent_id="DeveloperAgent")
            return {"success": False, "attempts": 0}

        files_data = data.get("files", [])
        if not files_data:
            agent_logger.warning("La IA no ha especificat cap fitxer per modificar/crear.", agent_id="DeveloperAgent")
            return {"success": False, "attempts": 0}

        saved_paths = self._write_files_to_disk(files_data)

        env = os.environ.copy()
        src_dir = str(Path("src").resolve())
        env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"

        test_files = [str(p) for p in saved_paths if "tests/" in str(p)]
        pytest_cmd = ["pytest", "-v"] + (test_files if test_files else ["tests/"])

        for attempt in range(1, max_retries + 1):
            agent_logger.info(f"Executant bateria de tests (Intent {attempt}/{max_retries}).", agent_id="DeveloperAgent")
            try:
                test_result = subprocess.run(
                    pytest_cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=30
                )
            except subprocess.TimeoutExpired:
                agent_logger.error("Timeout de 30s excedit durant PyTest.", agent_id="DeveloperAgent")
                return {"success": False, "attempts": attempt}

            if test_result.returncode == 0:
                agent_logger.info("Tots els tests han passat amb èxit.", agent_id="DeveloperAgent")
                files_to_commit = self._get_target_changes_only(files_data)
                
                commit_msg = f"feat: resolució automàtica Issue #{issue_number} ({data.get('summary', 'multi-fitxer')})"
                self.github.commit_and_push_files(branch_name, files_to_commit, commit_msg)
                
                files_summary = "\n".join([f"- `{item['path']}`" for item in files_to_commit])
                pr_body = (
                    f"Aquesta Pull Request ha estat generada automàticament per l'**Agent Desenvolupador**.\n\n"
                    f"- **Issue resolta:** #{issue_number}\n"
                    f"- **Branca origen:** `{branch_name}`\n"
                    f"- **Resum:** {data.get('summary', 'N/A')}\n"
                    f"- **Fitxers modificats/creats:**\n{files_summary}\n"
                )
                
                pr_result = self.github.create_pull_request(
                    title=f"feat: resolució automàtica Issue #{issue_number} - {issue.title}",
                    body=pr_body,
                    head_branch=branch_name,
                    base_branch="main"
                )
                agent_logger.info(f"Pull Request creada amb èxit per a la Issue #{issue_number}.", agent_id="DeveloperAgent")
                return {
                    "success": True,
                    "attempts": attempt,
                    "files_count": len(files_to_commit),
                    "pr_url": pr_result.get("url") if pr_result else None
                }
            else:
                error_log = test_result.stdout or test_result.stderr
                agent_logger.warning(f"Els tests han fallat (Intent {attempt}). Error: {error_log}", agent_id="DeveloperAgent")
                
                if attempt < max_retries:
                    files_summary_text = "\n".join([f"Fitxer: {f['path']}\n{f['content']}\n" for f in files_data])
                    fix_prompt = DEVELOPER_FIX_PROMPT.format(
                        code_policy=self.code_policy,
                        files_summary=files_summary_text,
                        error_log=error_log
                    )
                    try:
                        raw_response = self.llm.generate_task_spec(fix_prompt, system_prompt)
                        data = self._parse_json_response(raw_response)
                        files_data = data.get("files", files_data)
                        saved_paths = self._write_files_to_disk(files_data)
                    except Exception as err:
                        agent_logger.error(f"Error durant la re-generació multi-fitxer: {err}", agent_id="DeveloperAgent")

        agent_logger.error("L'agent ha assolit el límit de reintents sense resoldre els tests.", agent_id="DeveloperAgent")
        return {"success": False, "attempts": max_retries}

    def remediate_pull_request(self, pr_number: int, max_retries: int = 3):
        agent_logger.info(f"Iniciant remediació per a la PR #{pr_number}.", agent_id="DeveloperAgent")
        pr = self.github.repo.get_pull(pr_number)
        branch_name = pr.head.ref
        review_comments = self.github.get_pr_review_comments(pr_number)
        
        if not review_comments:
            agent_logger.warning("No s'han trobat comentaris de Code Review.", agent_id="DeveloperAgent")
            return {"success": False}

        repo_tree = self.github.get_repository_tree(ref=branch_name)
        tree_str = "\n".join(repo_tree) if repo_tree else ""
        existing_files_content = self._fetch_main_branch_source_files(repo_tree)

        remediation_prompt = DEVELOPER_REMEDIATION_PROMPT.format(
            code_policy=self.code_policy,
            review_comments=review_comments
        )

        system_prompt = DEVELOPER_SYSTEM_PROMPT.format(
            code_policy=self.code_policy,
            repo_tree=tree_str,
            existing_files_content=existing_files_content
        )

        raw_response = self.llm.generate_task_spec(remediation_prompt, system_prompt)
        
        try:
            data = self._parse_json_response(raw_response)
            files_data = data.get("files", [])
            if not files_data:
                return {"success": False}

            saved_paths = self._write_files_to_disk(files_data)
            env = os.environ.copy()
            src_dir = str(Path("src").resolve())
            env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"

            test_files = [str(p) for p in saved_paths if "tests/" in str(p)]
            pytest_cmd = ["pytest", "-v"] + (test_files if test_files else ["tests/"])

            test_result = subprocess.run(pytest_cmd, capture_output=True, text=True, env=env, timeout=30)

            if test_result.returncode == 0:
                agent_logger.info("Tots els fitxers remediats han passat els tests.", agent_id="DeveloperAgent")
                files_to_commit = self._get_target_changes_only(files_data)
                self.github.commit_and_push_files(branch_name, files_to_commit, "fix: remediació multi-fitxer segons Code Review")
                return {"success": True, "branch": branch_name}
            else:
                agent_logger.error(
                    f"Els tests han fallat després de la remediació: {test_result.stdout or test_result.stderr}",
                    agent_id="DeveloperAgent"
                )
                return {"success": False}
        except Exception as e:
            agent_logger.error(f"Error en la remediació multi-fitxer: {e}", agent_id="DeveloperAgent")
            return {"success": False}
