import os
import re
import json
import ast
import shutil
import subprocess
from pathlib import Path
from json_repair import repair_json
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
        self.code_policy = policy_path.read_text(encoding="utf-8") if policy_path.exists() else "Aplica PEP8 i OWASP Top 10."

    def _parse_json_response(self, text: str) -> dict:
        """Extreu i parseja un objecte JSON/YAML de la resposta del LLM de manera ultra-resilient."""
        import yaml

        # 1. Netejar blocs de codi Markdown (```json o ```yaml)
        cleaned = re.sub(r'```(json|yaml)?\s*', '', text)
        cleaned = re.sub(r'```\s*$', '', cleaned)

        # 2. Cercar des del primer '{' o el primer 'summary:'
        first_brace = cleaned.find('{')
        last_brace = cleaned.rfind('}')

        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_candidate = cleaned[first_brace:last_brace + 1]
        else:
            json_candidate = cleaned.strip()

        # 3. Primer intent: json_repair
        try:
            from json_repair import repair_json
            repaired = repair_json(json_candidate, return_objects=True)
            if isinstance(repaired, dict) and "files" in repaired:
                return repaired
        except Exception:
            pass

        # 4. Segon intent: parsing amb PyYAML (molt més tolerant amb codi Python multilínia)
        try:
            parsed_yaml = yaml.safe_load(cleaned)
            if isinstance(parsed_yaml, dict) and "files" in parsed_yaml:
                return parsed_yaml
        except Exception:
            pass

        # 5. Tercer intent: json.loads natiu amb strict=False
        try:
            return json.loads(json_candidate, strict=False)
        except json.JSONDecodeError as err:
            print(f"❌ Error critic de parsing en la resposta de Gemini: {err}")
            raise err

    def _prepare_workspace_environment(self, issue_number: int) -> Path:
        """
        Crea una còpia completa del directori local al workspace (incloent .env i configuracions),
        assegurant que l'entorn tingui accés a les claus i eines necessàries.
        """
        root_dir = Path(".").resolve()
        workspace_dir = root_dir / ".workspace" / f"issue_{issue_number}"

        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)

        print(f"📦 [DeveloperAgent] Duplicant entorn local cap al workspace: {workspace_dir}...")
        
        # Copiem el directori local ignorant carpetes pesades o temporals
        def ignore_patterns(path, names):
            ignored = [".git", "__pycache__", ".pytest_cache", ".venv", "venv"]
            if ".workspace" in path:
                ignored.extend(names)
            return ignored

        shutil.copytree(root_dir, workspace_dir, ignore=ignore_patterns)
        return workspace_dir

    def _download_main_branch_content(self, workspace_dir: Path):
        """
        Descarrega i sobrescriu al workspace tot el contingut de la branca 'main' de GitHub,
        per garantir que partim de l'estat oficial i pur de 'main'.
        """
        print("📥 [DeveloperAgent] Sincronitzant contingut de la branca 'main' de GitHub al workspace...")
        repo_tree = self.github.get_repository_tree(ref="main")

        for file_path in repo_tree:
            content = self.github.get_file_content(file_path, ref="main")
            if content is not None:
                target_file = workspace_dir / file_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(content, encoding="utf-8")

    def _read_workspace_source_files(self, workspace_dir: Path) -> str:
        """Llegeix el contingut dels fitxers font sincronitzats al workspace."""
        src_path = workspace_dir / "src"
        if not src_path.exists():
            return "No hi ha fitxers existents a src/"

        contents = []
        for file in src_path.rglob("*.py"):
            try:
                rel_path = file.relative_to(workspace_dir)
                text = file.read_text(encoding="utf-8")
                contents.append(f"--- FITXER ({rel_path}) ---\n{text}\n")
            except Exception as e:
                print(f"⚠️ Error en llegir el fitxer del workspace {file}: {e}")

        return "\n".join(contents) if contents else "Cap fitxer .py trobat a src/"

    def _write_files_to_workspace(self, files_list: list[dict], workspace_dir: Path) -> list[Path]:
        """Escriu els fitxers modificats/creats dins del workspace aïllat."""
        saved_paths = []
        for file_item in files_list:
            target_path = workspace_dir / file_item["path"]
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            content = file_item["content"]
            
            # Verificació bàsica de sintaxi Python
            try:
                ast.parse(content)
            except SyntaxError as e:
                print(f"⚠️ Alerta de sintaxi/indentació a {file_item['path']}: {e}")

            target_path.write_text(content, encoding="utf-8")
            saved_paths.append(target_path)
            print(f"📄 Fitxer actualitzat al Workspace: {file_item['path']}")
            
        return saved_paths

    def develop_and_test(self, issue_number: int, max_retries: int = 3):
        print(f"\n🤖 [DeveloperAgent] Carregant la Issue #{issue_number} des de GitHub...")
        issue = self.github.get_issue(issue_number)

        # 1. Preparar workspace duplicant el directori local (amb .env i eines)
        workspace_dir = self._prepare_workspace_environment(issue_number)

        # 2. Sincronitzar tot el contingut oficial de la branca 'main' de GitHub
        self._download_main_branch_content(workspace_dir)

        # 3. Crear la nova branca de treball a GitHub
        branch_name = f"feature/issue-{issue_number}"
        print(f"🌿 [DeveloperAgent] Creant la branca remota '{branch_name}' a partir de 'main'...")
        self.github.create_branch(base_branch="main", new_branch=branch_name)

        # 4. Llegir l'arbre del projecte i el contingut font del workspace
        repo_tree = self.github.get_repository_tree(ref="main")
        tree_str = "\n".join(repo_tree) if repo_tree else "Repositori buit"
        existing_files_content = self._read_workspace_source_files(workspace_dir)

        prompt = f"Títol de la Issue: {issue.title}\n\nEspecificació:\n{issue.body}"
        print("🤖 [DeveloperAgent] Generant codi i tests respectant la sintaxi Python i el context existent...")
        
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
            shutil.rmtree(workspace_dir, ignore_errors=True)
            return {"success": False, "attempts": 0}

        files_data = data.get("files", [])
        if not files_data:
            print("⚠️ La IA no ha especificat cap fitxer per modificar/crear.")
            shutil.rmtree(workspace_dir, ignore_errors=True)
            return {"success": False, "attempts": 0}

        # 5. Escriure els fitxers modificats dins del Workspace
        self._write_files_to_workspace(files_data, workspace_dir)

        # 6. Executar PyTest utilitzant l'entorn del Workspace
        env = os.environ.copy()
        src_workspace = str((workspace_dir / "src").resolve())
        env["PYTHONPATH"] = f"{src_workspace}:{env.get('PYTHONPATH', '')}"

        pytest_cmd = ["pytest", "-v", str(workspace_dir / "tests")]

        for attempt in range(1, max_retries + 1):
            print(f"\n🧪 Executant bateria de tests al Workspace (Intent {attempt}/{max_retries})...")
            
            try:
                test_result = subprocess.run(
                    pytest_cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=str(workspace_dir),
                    timeout=30
                )
            except subprocess.TimeoutExpired:
                print("⏰ Timeout de 30s excedit durant PyTest.")
                shutil.rmtree(workspace_dir, ignore_errors=True)
                return {"success": False, "attempts": attempt}

            if test_result.returncode == 0:
                print("✅ Tots els tests han passat al Workspace!")
                
                # 7. Publicar els canvis del workspace a la nova branca a GitHub
                files_to_commit = [
                    {"path": item["path"], "content": (workspace_dir / item["path"]).read_text(encoding="utf-8")}
                    for item in files_data
                ]
                
                print(f"\n🚀 [DeveloperAgent] Publicant {len(files_to_commit)} fitxers a la branca '{branch_name}'...")
                commit_msg = f"feat: resolució Issue #{issue_number} ({data.get('summary', 'multi-fitxer')})"
                self.github.commit_and_push_files(branch_name, files_to_commit, commit_msg)
                
                # Neteja final del Workspace
                shutil.rmtree(workspace_dir, ignore_errors=True)

                files_summary = "\n".join([f"- `{item['path']}`" for item in files_to_commit])
                pr_body = (
                    f"Aquesta Pull Request ha estat generada automàticament per l'**Agent Desenvolupador (Workspace Sincronitzat)**.\n\n"
                    f"- **Issue resolta:** #{issue_number}\n"
                    f"- **Branca origen:** `{branch_name}`\n"
                    f"- **Fitxers modificats/creats:**\n{files_summary}\n"
                    f"- **Tests executats:** Passats satisfactòriament en {attempt} intent/s"
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
                    print("\n🔄 [DeveloperAgent] Sol·licitant auto-correcció al Workspace...")
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
                        self._write_files_to_workspace(files_data, workspace_dir)
                    except Exception as err:
                        print(f"⚠️ Error durant la re-generació al Workspace: {err}")

        shutil.rmtree(workspace_dir, ignore_errors=True)
        print("❌ L'agent ha assolit el límit de reintents sense poder resoldre els tests.")
        return {"success": False, "attempts": max_retries}

    def remediate_pull_request(self, pr_number: int, max_retries: int = 3):
        """Remedia una PR que afecta múltiples fitxers basant-se en l'informe de Code Review."""
        print(f"\n🛠️ [DeveloperAgent] Iniciant remediació multi-fitxer per a la PR #{pr_number}...")
        
        pr = self.github.repo.get_pull(pr_number)
        branch_name = pr.head.ref
        review_comments = self.github.get_pr_review_comments(pr_number)
        
        if not review_comments:
            print("⚠️ No s'han trobat comentaris de Code Review.")
            return {"success": False}

        # Preparar el workspace
        workspace_dir = self._prepare_workspace_environment(pr_number)
        self._download_main_branch_content(workspace_dir)

        repo_tree = self.github.get_repository_tree(ref=branch_name)
        tree_str = "\n".join(repo_tree) if repo_tree else ""
        existing_files_content = self._read_workspace_source_files(workspace_dir)

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
                shutil.rmtree(workspace_dir, ignore_errors=True)
                return {"success": False}

            self._write_files_to_workspace(files_data, workspace_dir)

            env = os.environ.copy()
            src_workspace = str((workspace_dir / "src").resolve())
            env["PYTHONPATH"] = f"{src_workspace}:{env.get('PYTHONPATH', '')}"

            pytest_cmd = ["pytest", "-v", str(workspace_dir / "tests")]

            test_result = subprocess.run(
                pytest_cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(workspace_dir),
                timeout=30
            )

            if test_result.returncode == 0:
                print("✅ Tots els fitxers remediats han passat els tests!")
                files_to_commit = [
                    {"path": item["path"], "content": (workspace_dir / item["path"]).read_text(encoding="utf-8")}
                    for item in files_data
                ]
                self.github.commit_and_push_files(branch_name, files_to_commit, "fix: remediació multi-fitxer segons Code Review")
                shutil.rmtree(workspace_dir, ignore_errors=True)
                return {"success": True, "branch": branch_name}
            else:
                print("❌ Els tests han fallat després de la remediació.")
                shutil.rmtree(workspace_dir, ignore_errors=True)
                return {"success": False}
        except Exception as e:
            print(f"❌ Error en la remediació multi-fitxer: {e}")
            shutil.rmtree(workspace_dir, ignore_errors=True)
            return {"success": False}
