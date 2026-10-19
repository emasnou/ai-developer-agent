import os
import re
import json
import ast
import shutil
import subprocess
from pathlib import Path
from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.prompts.developer_prompts import (
    DEVELOPER_SYSTEM_PROMPT,
    DEVELOPER_FIX_PROMPT,
    DEVELOPER_REMEDIATION_PROMPT
)

class DeveloperAgent:
    def __init__(self):
        """Inicialitza els serveis necessaris i carrega la política de codi local."""
        self.llm = LLMService()
        self.github = GitHubService()
        policy_path = Path("docs/code_policy.md")
        self.code_policy = policy_path.read_text() if policy_path.exists() else "Aplica PEP8 i OWASP Top 10."

    def _parse_json_response(self, text: str) -> dict:
        """Extreu i parseja un objecte JSON de la resposta del LLM de manera resilient."""
        cleaned = re.sub(r'```json\s*', '', text)
        cleaned = re.sub(r'```\s*$', '', cleaned)
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        json_str = match.group(0) if match else cleaned.strip()

        try:
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError:
            sanitized = re.sub(
                r'[\x00-\x1F\x7F]',
                lambda m: f"\\u{ord(m.group(0)):04x}" if m.group(0) not in ('\n', '\r', '\t') else m.group(0),
                json_str
            )
            return json.loads(sanitized, strict=False)

    def _fetch_main_branch_source_files(self, repo_tree: list[str]) -> str:
        """Llegeix el contingut dels fitxers existents a 'src/' directament des de 'main' a GitHub."""
        src_files = [p for p in repo_tree if p.startswith("src/") and p.endswith(".py")]
        if not src_files:
            return "No hi ha fitxers .py existents a src/ a la branca main."

        contents = []
        for file_path in src_files:
            content = self.github.get_file_content(file_path, ref="main")
            if content:
                contents.append(f"--- FITXER REMOT (main): {file_path} ---\n{content}\n")

        return "\n".join(contents) if contents else "Cap fitxer .py trobat a src/ a main."

    def _write_files_to_sandbox(self, files_list: list[dict], sandbox_dir: Path) -> list[Path]:
        """
        Escriu els fitxers dins de la carpeta d'aïllament (sandbox) per no contaminar
        el codi de l'agent en execució, verificant la sintaxi de Python.
        """
        saved_paths = []
        for file_item in files_list:
            target_path = sandbox_dir / file_item["path"]
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            content = file_item["content"]
            
            # Verificació de sintaxi i preservació d'espais
            try:
                ast.parse(content)
            except SyntaxError as e:
                print(f"⚠️ Alerta de sintaxi/indentació a {file_item['path']}: {e}")

            target_path.write_text(content, encoding="utf-8")
            saved_paths.append(target_path)
            print(f"📄 Fitxer preparat al Sandbox: {file_item['path']}")
            
        return saved_paths

    def develop_and_test(self, issue_number: int, max_retries: int = 3):
        print(f"\n🤖 [DeveloperAgent] Carregant la Issue #{issue_number} des de GitHub...")
        issue = self.github.get_issue(issue_number)
        
        # 1. Crear la branca remota a GitHub des de 'main'
        branch_name = f"feature/issue-{issue_number}"
        print(f"🌿 [DeveloperAgent] Creant la branca remota '{branch_name}' a partir de 'main'...")
        self.github.create_branch(base_branch="main", new_branch=branch_name)

        # 2. Obtenir context de main des de GitHub
        repo_tree = self.github.get_repository_tree(ref="main")
        tree_str = "\n".join(repo_tree) if repo_tree else "Repositori buit"
        existing_files_content = self._fetch_main_branch_source_files(repo_tree)

        # 3. Definir directori de treball aïllat (Sandbox)
        sandbox_dir = Path(".workspace") / f"issue_{issue_number}"
        if sandbox_dir.exists():
            shutil.rmtree(sandbox_dir)
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        prompt = f"Títol de la Issue: {issue.title}\n\nEspecificació:\n{issue.body}"
        print("🤖 [DeveloperAgent] Generant codi i tests amb respecte de la indentació Python...")
        
        system_prompt = DEVELOPER_SYSTEM_PROMPT.format(
            code_policy=self.code_policy,
            repo_tree=tree_str,
            existing_files_content=existing_files_content
        )
        
        raw_response = self.llm.generate_task_spec(prompt, system_prompt)
        
        try:
            data = self._parse_json_response(raw_response)
        except Exception as e:
            print(f"❌ Error en extreure el JSON multi-fitxer: {e}")
            return {"success": False, "attempts": 0}

        files_data = data.get("files", [])
        if not files_data:
            print("⚠️ La IA no ha especificat cap fitxer per modificar/crear.")
            return {"success": False, "attempts": 0}

        # 4. Escriure fitxers ÚNICAMENT al Sandbox aïllat
        self._write_files_to_sandbox(files_data, sandbox_dir)

        # 5. Executar PyTest des del directori Sandbox
        env = os.environ.copy()
        src_sandbox = str((sandbox_dir / "src").resolve())
        env["PYTHONPATH"] = f"{src_sandbox}:{env.get('PYTHONPATH', '')}"

        pytest_cmd = ["pytest", "-v", str(sandbox_dir / "tests")]

        for attempt in range(1, max_retries + 1):
            print(f"\n🧪 Executant bateria de tests al Sandbox (Intent {attempt}/{max_retries})...")
            
            try:
                test_result = subprocess.run(
                    pytest_cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=30
                )
            except subprocess.TimeoutExpired:
                print("⏰ Timeout de 30s excedit durant PyTest.")
                return {"success": False, "attempts": attempt}

            if test_result.returncode == 0:
                print("✅ Tots els tests han passat al Sandbox!")
                
                # 6. Pujar el contingut generat a GitHub des del Sandbox
                files_to_commit = [
                    {"path": item["path"], "content": item["content"]}
                    for item in files_data
                ]
                
                print(f"\n🚀 [DeveloperAgent] Publicant {len(files_to_commit)} fitxers a la branca '{branch_name}'...")
                commit_msg = f"feat: resolució Issue #{issue_number} ({data.get('summary', 'multi-fitxer')})"
                self.github.commit_and_push_files(branch_name, files_to_commit, commit_msg)
                
                # Netejar el Sandbox
                shutil.rmtree(sandbox_dir, ignore_errors=True)

                files_summary = "\n".join([f"- `{item['path']}`" for item in files_to_commit])
                pr_body = (
                    f"Aquesta Pull Request ha estat generada automàticament per l'**Agent Desenvolupador (Sandbox Multi-Fitxer)**.\n\n"
                    f"- **Issue resolta:** #{issue_number}\n"
                    f"- **Branca origen:** `{branch_name}`\n"
                    f"- **Fitxers modificats/creats:**\n{files_summary}\n"
                    f"- **Tests executats:** Passats en {attempt} intent/s"
                )
                
                pr_result = self.github.create_pull_request(
                    title=f"feat: resolució automàtica Issue #{issue_number} - {issue.title}",
                    body=pr_body,
                    head_branch=branch_name,
                    base_branch="main"
                )

                return {
                    "success": True,
                    "attempts": attempt,
                    "files_count": len(files_to_commit),
                    "pr_url": pr_result.get("url") if pr_result else None
                }
            else:
                print(f"❌ Els tests han fallat (Intent {attempt}).")
                error_log = test_result.stdout or test_result.stderr
                print("--- Error de PyTest ---")
                print(error_log)
                
                if attempt < max_retries:
                    print("\n🔄 [DeveloperAgent] Sol·licitant auto-correcció al Sandbox...")
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
                        self._write_files_to_sandbox(files_data, sandbox_dir)
                    except Exception as err:
                        print(f"⚠️ Error durant la re-generació al Sandbox: {err}")

        shutil.rmtree(sandbox_dir, ignore_errors=True)
        print("❌ L'agent ha assolit el límit de reintents sense poder resoldre els tests.")
        return {"success": False, "attempts": max_retries}