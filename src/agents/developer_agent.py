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
class DeveloperAgent:
    def __init__(self):
        self.llm = LLMService()
        self.github = GitHubService()

    def _parse_json_response(self, text: str) -> dict:
        """Extreu i parseja un objecte JSON de la resposta del LLM de manera segura."""
        # Neteja blocs de codi markdown tipus ```json ... ```
        cleaned = re.sub(r'```json\s*', '', text)
        cleaned = re.sub(r'```\s*$', '', cleaned)
        
        # Cerca el primer bloc delimitat per { i }
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            json_str = cleaned.strip()

        return json.loads(json_str)

    def develop_and_test(self, issue_number: int, max_retries: int = 3):
        print(f"\n🤖 [DeveloperAgent] Carregant la Issue #{issue_number} des de GitHub...")
        issue = self.github.get_issue(issue_number)
        
        # 1. Sol·licitar la primera versió del codi i tests a Gemini
        prompt = f"Títol de la Issue: {issue.title}\n\nEspecificació:\n{issue.body}"
        print("🤖 [DeveloperAgent] Generant codi i tests unitaris amb Gemini...")
        
        raw_response = self.llm.generate_task_spec(prompt, DEVELOPER_SYSTEM_PROMPT)
        
        try:
            data = self._parse_json_response(raw_response)
        except Exception as e:
            print(f"❌ Error en extreure el JSON inicial de la IA: {e}")
            return {"success": False, "attempts": 0}

        code_path = Path("src") / data["code_filename"]
        test_path = Path("tests/unit") / data["test_filename"]

        # Assegurar que els directoris existeixen i guardar fitxers
        code_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.parent.mkdir(parents=True, exist_ok=True)

        code_path.write_text(data["code_content"])
        test_path.write_text(data["test_content"])
        print(f"📄 Codi generat a: {code_path}")
        print(f"🧪 Tests generats a: {test_path}")

        # 2. Configurar entorn incloent 'src' al PYTHONPATH per a PyTest
        env = os.environ.copy()
        src_dir = str(Path("src").resolve())
        env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"

        # 3. Bucle d'execució i auto-correcció
        for attempt in range(1, max_retries + 1):
            print(f"\n🧪 Executant bateria de tests (Intent {attempt}/{max_retries})...")
            
            test_result = subprocess.run(
                ["pytest", str(test_path)],
                capture_output=True,
                text=True,
                env=env
            )
            if test_result.returncode == 0:
                print("✅ Tots els tests han passat amb èxit!")
                
                # 4. Publicar el codi i crear la Pull Request a GitHub
                branch_name = f"feature/issue-{issue_number}"
                print(f"\n🚀 [DeveloperAgent] Publicant canvis a GitHub...")
                
                # A) Crear branca
                self.github.create_branch(base_branch="main", new_branch=branch_name)
                
                # B) Fer commit dels fitxers generats
                files_to_commit = [
                    {"path": str(code_path), "content": data["code_content"]},
                    {"path": str(test_path), "content": data["test_content"]}
                ]
                commit_msg = f"feat: resolució automàtica de la Issue #{issue_number}"
                self.github.commit_and_push_files(branch_name, files_to_commit, commit_msg)
                
                # C) Obrir la Pull Request
                pr_body = (
                    f"Aquesta Pull Request ha estat generada automàticament per l'**Agent Desenvolupador**.\n\n"
                    f"- **Issue resolta:** #{issue_number}\n"
                    f"- **Tests executats:** {data['test_filename']} (Passats en {attempt} intent/s)\n"
                    f"- **Codi generat:** `{data['code_filename']}`"
                )
                pr_result = self.github.create_pull_request(
                    title=f"feat: resolució automàtica Issue #{issue_number} - {issue.title}",
                    body=pr_body,
                    head_branch=branch_name,
                    base_branch="main"
                )

                return {
                    "success": True,
                    "code_file": code_path,
                    "test_file": test_path,
                    "attempts": attempt,
                    "pr_url": pr_result.get("url") if pr_result else None
                }
            else:
                print(f"❌ Els tests han fallat (Intent {attempt}).")
                error_log = test_result.stdout or test_result.stderr
                print("--- Error de PyTest ---")
                print(error_log)
                
                if attempt < max_retries:
                    print("\n🔄 [DeveloperAgent] Sol·licitant auto-correcció a Gemini...")
                    
                    fix_prompt = DEVELOPER_FIX_PROMPT.format(
                        code_content=data["code_content"],
                        test_content=data["test_content"],
                        error_log=error_log,
                        code_filename=data["code_filename"],
                        test_filename=data["test_filename"]
                    )
                    
                    try:
                        raw_response = self.llm.generate_task_spec(fix_prompt, DEVELOPER_SYSTEM_PROMPT)
                        data = self._parse_json_response(raw_response)
                        
                        # Sobreescriure fitxers amb el codi i tests corregits
                        code_path.write_text(data["code_content"])
                        test_path.write_text(data["test_content"])
                        print(f"🛠️ Codi i tests actualitzats localment. Reintentant...")
                    except Exception as err:
                        print(f"⚠️ Error durant el parsing de la resposta d'auto-correcció: {err}")

        print("❌ L'agent ha assolit el límit de reintents sense poder resoldre els tests.")
        return {"success": False, "attempts": max_retries}
    def remediate_pull_request(self, pr_number: int, max_retries: int = 3):
        print(f"\n🛠️ [DeveloperAgent] Iniciant procés de remediació per a la PR #{pr_number}...")
        
        pr = self.github.repo.get_pull(pr_number)
        branch_name = pr.head.ref
        
        # 1. Obtenir comentaris de Code Review i el contingut dels fitxers
        review_comments = self.github.get_pr_review_comments(pr_number)
        
        if not review_comments:
            print("⚠️ No s'han trobat comentaris de Code Review a la PR.")
            return {"success": False}

        # Obtenir els fitxers actuals de la PR des de GitHub
        files = pr.get_files()
        code_file = next((f for f in files if f.filename.startswith("src/")), None)
        test_file = next((f for f in files if f.filename.startswith("tests/")), None)

        if not code_file or not test_file:
            print("❌ No s'han pogut identificar els fitxers de codi o test a la PR.")
            return {"success": False}

        code_content = self.github.repo.get_contents(code_file.filename, ref=branch_name).decoded_content.decode("utf-8")
        test_content = self.github.repo.get_contents(test_file.filename, ref=branch_name).decoded_content.decode("utf-8")

        code_filename = Path(code_file.filename).name
        test_filename = Path(test_file.filename).name

        # 2. Demanar a Gemini que apliqui la remediació basada en el Code Review
        print("🤖 [DeveloperAgent] Refactoritzant el codi segons l'informe de seguretat i estil...")
        remediation_prompt = DEVELOPER_REMEDIATION_PROMPT.format(
            code_filename=code_filename,
            code_content=code_content,
            test_filename=test_filename,
            test_content=test_content,
            review_comments=review_comments
        )

        raw_response = self.llm.generate_task_spec(remediation_prompt, DEVELOPER_SYSTEM_PROMPT)
        data = self._parse_json_response(raw_response)

        # 3. Guardar localment els fitxers corregits
        code_path = Path("src") / data["code_filename"]
        test_path = Path("tests/unit") / data["test_filename"]
        
        code_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.parent.mkdir(parents=True, exist_ok=True)

        code_path.write_text(data["code_content"])
        test_path.write_text(data["test_content"])

        # 4. Executar bateria de tests locals per assegurar la no-regressió
        env = os.environ.copy()
        src_dir = str(Path("src").resolve())
        env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"

        print("\n🧪 Verificant que el codi remediat passa els tests...")
        
        try:
            # Afegim un timeout de 30 segons per evitar bloquejos infinits
            test_result = subprocess.run(
                ["pytest", "-v", str(test_path)],
                capture_output=True,
                text=True,
                env=env,
                timeout=1800  # Temps màxim d'execució en segons
            )

            if test_result.returncode == 0:
                print("✅ El codi remediat ha passat tots els tests!")
                
                files_to_commit = [
                    {"path": str(code_path), "content": data["code_content"]},
                    {"path": str(test_path), "content": data["test_content"]}
                ]
                self.github.commit_and_push_files(branch_name, files_to_commit, "fix: remediació de seguretat i estandards segons Code Review")
                
                print(f"🚀 Canvis corregits enviats a la branca '{branch_name}'.")
                return {"success": True, "branch": branch_name}
            else:
                print("❌ Els tests han fallat després de la remediació.")
                print("--- Sortida de PyTest (stdout) ---")
                print(test_result.stdout)
                print("--- Errors de PyTest (stderr) ---")
                print(test_result.stderr)
                return {"success": False}

        except subprocess.TimeoutExpired as timeout_err:
            print("\n⏰ ERROR: L'execució de PyTest ha superat el temps límit (Timeout de 30s).")
            print("⚠️ És molt possible que el codi remediat contingui un bucle infinit o una crida bloquejant (ex: input()).")
            if timeout_err.stdout:
                print("--- Sortida registrada abans del bloqueig ---")
                print(timeout_err.stdout.decode('utf-8') if isinstance(timeout_err.stdout, bytes) else timeout_err.stdout)
            return {"success": False}        

        if test_result.returncode == 0:
            print("✅ El codi remediat ha passat tots els tests!")
            
            # 5. Fer push dels canvis a la branca existent a GitHub
            files_to_commit = [
                {"path": str(code_path), "content": data["code_content"]},
                {"path": str(test_path), "content": data["test_content"]}
            ]
            self.github.commit_and_push_files(branch_name, files_to_commit, "fix: remediació de seguretat i estandards segons Code Review")
            
            print(f"🚀 Canvis corregits enviats a la branca '{branch_name}'.")
            return {"success": True, "branch": branch_name}
        else:
            print("❌ Els tests han fallat després de la remediació.")
            print(test_result.stdout or test_result.stderr)
            return {"success": False}