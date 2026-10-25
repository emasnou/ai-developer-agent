"""Agent Desenvolupador per a la generació, validació amb PyTest i remediació de codi en workspaces aïllats."""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from src.agents.base_agent import BaseAgent
from src.prompts.developer_prompts import (
    DEVELOPER_FIX_PROMPT,
    DEVELOPER_REMEDIATION_PROMPT,
    DEVELOPER_SYSTEM_PROMPT,
)
from src.schemas.agent_schemas import DeveloperPlan
from src.services.github_service import GitHubService
from src.services.llm_service import LLMService
from src.utils.json_parser import parse_developer_json_response

_SENSITIVE_ENV_VARS = ("GITHUB_TOKEN", "GEMINI_API_KEY", "OPENAI_API_KEY")
_WORKSPACE_IGNORED_ITEMS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "logs",
    ".env",
}


class DeveloperAgent(BaseAgent):
    """Agent autònom que gestiona el cicle de codificació, tests en workspace i Pull Requests."""

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        github_service: Optional[GitHubService] = None,
    ) -> None:
        """Inicialitza el DeveloperAgent amb injecció opcional de serveis, política i logger.

        Args:
            llm_service: Instància opcional de LLMService per a injecció de dependències.
            github_service: Instància opcional de GitHubService per a injecció de dependències.
        """
        super().__init__(
            agent_name="DeveloperAgent",
            llm_service=llm_service,
            github_service=github_service,
        )

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """Extreu i normalitza el pla de fitxers JSON/YAML de la resposta del LLM.

        Args:
            text: Resposta en text cru retornada pel model LLM.

        Returns:
            dict[str, Any]: Diccionari amb `summary` i la llista `files` normalitzada.

        Raises:
            ValueError: Si la resposta és buida.
            Exception: Si cap estratègia de parseig no aconsegueix recuperar un JSON vàlid.
        """
        try:
            return parse_developer_json_response(text)
        except Exception as exc:
            self.logger.error(f"No s'ha pogut parsejar cap JSON vàlid del LLM: {exc}")
            raise

    def _prepare_workspace_environment(self, issue_number: int) -> Path:
        """Crea una còpia aïllada del projecte al workspace excloent secrets (.env) i logs.

        Args:
            issue_number: Número d'Issue o PR que identifica el workspace.

        Returns:
            Path: Ruta absoluta del directori del workspace creat.
        """
        root_dir = Path(".").resolve()
        workspace_dir = root_dir / ".workspace" / f"issue_{issue_number}"

        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)

        self.logger.info(f"Duplicant entorn local cap al workspace: {workspace_dir}")
        print(f"📦 [DeveloperAgent] Duplicant entorn local cap al workspace: {workspace_dir}...")

        def ignore_patterns(path: str, names: list[str]) -> list[str]:
            ignored = [n for n in names if n in _WORKSPACE_IGNORED_ITEMS or n.endswith(".env")]
            if ".workspace" in path:
                ignored.extend(names)
            return ignored

        shutil.copytree(root_dir, workspace_dir, ignore=ignore_patterns)
        return workspace_dir

    def _download_branch_content(self, workspace_dir: Path, ref: str = "main") -> None:
        """Descarrega i sincronitza al workspace el contingut d'una branca remota de GitHub.

        Args:
            workspace_dir: Ruta del workspace local on escriure els fitxers.
            ref: Nom de la branca o referència de Git a sincronitzar (per defecte 'main').
        """
        self.logger.info(f"Sincronitzant contingut de la branca '{ref}' de GitHub al workspace...")
        print(f"📥 [DeveloperAgent] Sincronitzant contingut de la branca '{ref}' al workspace...")
        repo_tree = self.github.get_repository_tree(ref=ref)

        for file_path in repo_tree:
            content = self.github.get_file_content(file_path, ref=ref)
            if content is not None:
                target_file = workspace_dir / file_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(content, encoding="utf-8")

    def _download_main_branch_content(self, workspace_dir: Path) -> None:
        """Sincronitza al workspace el contingut de la branca 'main' de GitHub.

        Args:
            workspace_dir: Ruta del workspace local.
        """
        self._download_branch_content(workspace_dir, ref="main")

    def _read_workspace_source_files(self, workspace_dir: Path) -> str:
        """Llegeix el contingut dels fitxers font sincronitzats al workspace.

        Args:
            workspace_dir: Ruta del workspace local.

        Returns:
            str: Contingut concatenat dels fitxers Python dins de `src/`.
        """
        src_path = workspace_dir / "src"
        if not src_path.exists():
            return "No hi ha fitxers existents al directori src/"

        contents: list[str] = []
        for file in sorted(src_path.rglob("*.py")):
            try:
                rel_path = file.relative_to(workspace_dir)
                text = file.read_text(encoding="utf-8")
                contents.append(f"--- FITXER ({rel_path}) ---\n{text}\n")
            except Exception as e:
                self.logger.warning(f"Error en llegir el fitxer del workspace {file}: {e}")

        return "\n".join(contents) if contents else "Cap fitxer .py trobat a src/"

    def _write_files_to_workspace(
        self, files_list: list[dict[str, Any]], workspace_dir: Path
    ) -> list[Path]:
        """Escriu els fitxers modificats o creats dins del workspace aïllat i en valida la sintaxi.

        Args:
            files_list: Llista de diccionaris amb `path` i `content`.
            workspace_dir: Ruta del workspace local.

        Returns:
            list[Path]: Llista de rutes dels fitxers escrits.
        """
        saved_paths: list[Path] = []
        for file_item in files_list:
            target_path = workspace_dir / file_item["path"]
            target_path.parent.mkdir(parents=True, exist_ok=True)
            content = file_item["content"]

            try:
                ast.parse(content)
            except SyntaxError as e:
                self.logger.warning(f"Alerta de sintaxi/indentació a {file_item['path']}: {e}")

            target_path.write_text(content, encoding="utf-8")
            saved_paths.append(target_path)
            self.logger.info(f"Fitxer actualitzat al Workspace: {file_item['path']}")
            print(f"📄 Fitxer actualitzat al Workspace: {file_item['path']}")

        return saved_paths

    @staticmethod
    def _build_workspace_env(workspace_dir: Path) -> dict[str, str]:
        """Construeix un entorn d'execució aïllat per a PyTest filtrant secrets sensibles.

         Fixa el `PYTHONPATH` exclusivament als directoris del workspace (`workspace_dir`
        i `workspace_dir/src`) sense heretar rutes de l'entorn amfitrió per evitar
        contaminació creuada entre el repositori arrel i el workspace.

        Args:
            workspace_dir: Ruta del workspace local per configurar el PYTHONPATH.

        Returns:
            dict[str, str]: Variables d'entorn segures i aïllades per al subprocés de test.
        """
        env = {k: v for k, v in os.environ.items() if k not in _SENSITIVE_ENV_VARS}
        root_workspace = str(workspace_dir.resolve())
        src_workspace = str((workspace_dir / "src").resolve())
        env["PYTHONPATH"] = os.pathsep.join([root_workspace, src_workspace])
        return env

    def _run_pytest_command(
        self, cmd: list[str], workspace_dir: Path, env: dict[str, str], phase_label: str
    ) -> tuple[bool, str]:
        """Executa una comanda PyTest amb límit de temps i captura de sortida.

        Args:
            cmd: Llista d'arguments de la comanda pytest.
            workspace_dir: Directori de treball on executar el subprocés.
            env: Variables d'entorn per al subprocés.
            phase_label: Descripció de la fase per als logs d'error.

        Returns:
            tuple[bool, str]: Tupla `(èxit, registre_error)`.
        """
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(workspace_dir),
                timeout=35,
                check=False,
            )
            if res.returncode != 0:
                output = f"{res.stdout or ''}\n{res.stderr or ''}".strip()
                self.logger.error(f"Els {phase_label} han fallat.")
                return False, output
            return True, ""
        except subprocess.TimeoutExpired:
            msg = f"⏰ Timeout excedit durant l'execució dels {phase_label}."
            self.logger.error(msg)
            return False, msg

    def _run_workspace_tests(
        self, workspace_dir: Path, files_data: list[dict[str, Any]], env: dict[str, str]
    ) -> tuple[bool, str]:
        """Executa els tests en dues fases: tests específics de la Issue i regressió unitària.

        Args:
            workspace_dir: Ruta del workspace local.
            files_data: Fitxers generats o modificats en el cicle actual.
            env: Variables d'entorn per a PyTest.

        Returns:
            tuple[bool, str]: `(True, "")` si tots els tests passen, o `(False, error_log)`.
        """
        targeted_tests = [
            str(workspace_dir / f["path"])
            for f in files_data
            if f.get("path", "").startswith("tests/") and (workspace_dir / f["path"]).exists()
        ]

        if targeted_tests:
            self.logger.info(f"Executant {len(targeted_tests)} test(s) específics de la Issue...")
            print(f"🎯 [Tests] Executant {len(targeted_tests)} test(s) específics de la Issue...")
            cmd = ["pytest", "-v", "-x", "--tb=short", *targeted_tests]
            passed, output = self._run_pytest_command(cmd, workspace_dir, env, "tests específics")
            if not passed:
                return False, output

        unit_dir = workspace_dir / "tests" / "unit"
        if unit_dir.exists():
            self.logger.info("Executant regressió de tests unitaris...")
            print("🛡️ [Tests] Executant regressió de tests unitaris...")
            cmd = ["pytest", "-v", "-x", "--tb=short", str(unit_dir)]
            return self._run_pytest_command(cmd, workspace_dir, env, "tests unitaris de regressió")

        return True, ""

    def _request_surgical_fix(
        self,
        files_data: list[dict[str, Any]],
        error_log: str,
        system_prompt: str,
        workspace_dir: Path,
    ) -> list[dict[str, Any]]:
        """Sol·licita al LLM una auto-correcció quirúrgica a partir de l'error de PyTest.

        Args:
            files_data: Llista actual de fitxers generats/modificats.
            error_log: Traça d'error de PyTest retallada.
            system_prompt: Prompt de sistema amb el context del repositori.
            workspace_dir: Ruta del workspace on aplicar les correccions.

        Returns:
            list[dict[str, Any]]: Llista de fitxers fusionada amb les correccions.
        """
        print("\n🔄 [DeveloperAgent] Sol·licitant auto-correcció quirúrgica al Workspace...")
        files_summary_text = "\n".join(
            [f"Fitxer: {f['path']}\n{f['content']}\n" for f in files_data]
        )
        fix_prompt = DEVELOPER_FIX_PROMPT.format(
            code_policy=self.code_policy,
            files_summary=files_summary_text,
            error_log=error_log,
        )

        try:
            raw_response = self.llm.generate_task_spec(
                fix_prompt,
                system_prompt,
                response_schema=DeveloperPlan,
            )
            fix_data = self._parse_json_response(raw_response)
            new_files = fix_data.get("files", [])
            if new_files:
                files_dict = {f["path"]: f for f in files_data}
                for item in new_files:
                    files_dict[item["path"]] = item
                files_data = list(files_dict.values())
                self._write_files_to_workspace(new_files, workspace_dir)
        except Exception as err:
            self.logger.error(f"Error durant la re-generació al Workspace: {err}")

        return files_data

    def _publish_solution_and_create_pr(
        self,
        issue: Any,
        branch_name: str,
        workspace_dir: Path,
        files_data: list[dict[str, Any]],
        summary: str,
        attempt: int,
    ) -> dict[str, Any]:
        """Fa commit dels fitxers validats al workspace, neteja el directori i obre la PR.

        Args:
            issue: Objecte Issue de PyGithub.
            branch_name: Branca remota on pujar els canvis.
            workspace_dir: Ruta del workspace local.
            files_data: Llista de fitxers modificats/creats.
            summary: Resum dels canvis proporcionat pel LLM.
            attempt: Número d'intent en què s'han superat els tests.

        Returns:
            dict[str, Any]: Diccionari amb el resultat d'èxit i l'URL de la Pull Request.
        """
        files_to_commit = [
            {
                "path": item["path"],
                "content": (workspace_dir / item["path"]).read_text(encoding="utf-8"),
            }
            for item in files_data
        ]

        print(f"\n🚀 [DeveloperAgent] Publicant {len(files_to_commit)} fitxers a '{branch_name}'...")
        commit_msg = f"feat: resolució Issue #{issue.number} ({summary})"
        self.github.commit_and_push_files(branch_name, files_to_commit, commit_msg)
        shutil.rmtree(workspace_dir, ignore_errors=True)

        files_summary = "\n".join([f"- `{item['path']}`" for item in files_to_commit])
        pr_body = (
            "Aquesta Pull Request ha estat generada automàticament per l'**Agent Desenvolupador "
            "(Workspace Sincronitzat)**.\n\n"
            f"- **Issue resolta:** #{issue.number}\n"
            f"- **Branca origen:** `{branch_name}`\n"
            f"- **Fitxers modificats/creats:**\n{files_summary}\n"
            f"- **Tests executats:** Passats satisfactòriament en {attempt} intent/s"
        )

        pr_result = self.github.create_pull_request(
            title=f"feat: resolució automàtica Issue #{issue.number} - {issue.title}",
            body=pr_body,
            head_branch=branch_name,
            base_branch="main",
        )
        pr_url = pr_result.get("url") if pr_result else None
        self.logger.info(f"Pull Request creada correctament: {pr_url or 'N/A'}")

        return {
            "success": True,
            "attempts": attempt,
            "files_count": len(files_to_commit),
            "pr_url": pr_url,
        }

    def develop_and_test(self, issue_number: int, max_retries: int = 3) -> dict[str, Any]:
        """Desenvolupa, prova i publica automàticament la solució per a una Issue de GitHub.

        Args:
            issue_number: Número de la Issue de GitHub a implementar.
            max_retries: Nombre màxim d'intents d'auto-correcció amb PyTest (per defecte 3).

        Returns:
            dict[str, Any]: Resultat de l'execució amb `success`, `attempts` i metadades de la PR.
        """
        self.logger.info(f"Iniciant desenvolupament automàtic per a la Issue #{issue_number}")
        print(f"\n🤖 [DeveloperAgent] Carregant la Issue #{issue_number} des de GitHub...")
        issue = self.github.get_issue(issue_number)

        workspace_dir = self._prepare_workspace_environment(issue_number)
        self._download_branch_content(workspace_dir, ref="main")

        branch_name = f"feature/issue-{issue_number}"
        self.logger.info(f"Creant branca remota '{branch_name}'...")
        print(f"🌿 [DeveloperAgent] Creant la branca remota '{branch_name}' a partir de 'main'...")
        self.github.create_branch(base_branch="main", new_branch=branch_name)

        repo_tree = self.github.get_repository_tree(ref="main")
        system_prompt = DEVELOPER_SYSTEM_PROMPT.format(
            code_policy=self.code_policy,
            repo_tree="\n".join(repo_tree) if repo_tree else "Repositori buit",
            existing_files_content=self._read_workspace_source_files(workspace_dir),
        )

        prompt = f"Títol de la Issue: {issue.title}\n\nEspecificació:\n{issue.body}"
        print("🤖 [DeveloperAgent] Generant codi i tests respectant la sintaxi Python i el context existent...")
        raw_response = self.llm.generate_task_spec(
            prompt,
            system_prompt,
            response_schema=DeveloperPlan,
        )

        try:
            data = self._parse_json_response(raw_response)
        except Exception as e:
            self.logger.error(f"Error en extreure el JSON multi-fitxer: {e}")
            shutil.rmtree(workspace_dir, ignore_errors=True)
            return {"success": False, "attempts": 0}

        files_data = data.get("files", [])
        if not files_data:
            self.logger.warning("La IA no ha especificat cap fitxer per modificar/crear.")
            shutil.rmtree(workspace_dir, ignore_errors=True)
            return {"success": False, "attempts": 0}

        self._write_files_to_workspace(files_data, workspace_dir)
        env = self._build_workspace_env(workspace_dir)

        for attempt in range(1, max_retries + 1):
            self.logger.info(f"Executant bateria de tests al Workspace (Intent {attempt}/{max_retries})")
            print(f"\n🧪 Executant bateria de tests al Workspace (Intent {attempt}/{max_retries})...")
            tests_passed, error_log = self._run_workspace_tests(workspace_dir, files_data, env)

            if tests_passed:
                self.logger.info("Tots els tests han passat al Workspace satisfactòriament.")
                print("✅ Tots els tests han passat al Workspace!")
                return self._publish_solution_and_create_pr(
                    issue=issue,
                    branch_name=branch_name,
                    workspace_dir=workspace_dir,
                    files_data=files_data,
                    summary=data.get("summary", "multi-fitxer"),
                    attempt=attempt,
                )

            self.logger.warning(f"Els tests han fallat (Intent {attempt}).")
            print(f"❌ Els tests han fallat (Intent {attempt}).")
            trimmed_log = error_log[:3500]
            print(f"--- Error de PyTest ---\n{trimmed_log}")

            if attempt < max_retries:
                files_data = self._request_surgical_fix(
                    files_data, trimmed_log, system_prompt, workspace_dir
                )

        shutil.rmtree(workspace_dir, ignore_errors=True)
        self.logger.error("L'agent ha assolit el límit de reintents sense poder resoldre els tests.")
        print("❌ L'agent ha assolit el límit de reintents sense poder resoldre els tests.")
        return {"success": False, "attempts": max_retries}

    def remediate_pull_request(self, pr_number: int, max_retries: int = 3) -> dict[str, Any]:
        """Refactoritza els fitxers d'una Pull Request segons els comentaris del Code Review.

        Args:
            pr_number: Número identificador de la Pull Request a remediar.
            max_retries: Nombre màxim d'intents d'execució i correcció de tests.

        Returns:
            dict[str, Any]: Diccionari amb `success` (bool) i `branch` (str, si té èxit).
        """
        self.logger.info(f"Iniciant remediació multi-fitxer per a la PR #{pr_number}")
        print(f"\n🛠️ [DeveloperAgent] Iniciant remediació multi-fitxer per a la PR #{pr_number}...")

        pr = self.github.repo.get_pull(pr_number)
        branch_name = pr.head.ref
        review_comments = self.github.get_pr_review_comments(pr_number)

        if not review_comments:
            self.logger.warning("No s'han trobat comentaris de Code Review.")
            print("⚠️ No s'han trobat comentaris de Code Review.")
            return {"success": False}

        workspace_dir = self._prepare_workspace_environment(pr_number)
        self._download_branch_content(workspace_dir, ref=branch_name)

        repo_tree = self.github.get_repository_tree(ref=branch_name)
        system_prompt = DEVELOPER_SYSTEM_PROMPT.format(
            code_policy=self.code_policy,
            repo_tree="\n".join(repo_tree) if repo_tree else "",
            existing_files_content=self._read_workspace_source_files(workspace_dir),
        )
        remediation_prompt = DEVELOPER_REMEDIATION_PROMPT.format(
            code_policy=self.code_policy,
            review_comments=review_comments,
        )

        raw_response = self.llm.generate_task_spec(
            remediation_prompt,
            system_prompt,
            response_schema=DeveloperPlan,
        )

        try:
            data = self._parse_json_response(raw_response)
            files_data = data.get("files", [])
            if not files_data:
                shutil.rmtree(workspace_dir, ignore_errors=True)
                return {"success": False}

            self._write_files_to_workspace(files_data, workspace_dir)
            env = self._build_workspace_env(workspace_dir)

            for attempt in range(1, max_retries + 1):
                tests_passed, error_log = self._run_workspace_tests(workspace_dir, files_data, env)
                if tests_passed:
                    self.logger.info("Tots els fitxers remediats han passat els tests!")
                    print("✅ Tots els fitxers remediats han passat els tests!")
                    files_to_commit = [
                        {
                            "path": item["path"],
                            "content": (workspace_dir / item["path"]).read_text(encoding="utf-8"),
                        }
                        for item in files_data
                    ]
                    self.github.commit_and_push_files(
                        branch_name,
                        files_to_commit,
                        "fix: remediació multi-fitxer segons Code Review",
                    )
                    shutil.rmtree(workspace_dir, ignore_errors=True)
                    return {"success": True, "branch": branch_name}

                if attempt < max_retries:
                    files_data = self._request_surgical_fix(
                        files_data, error_log[:3500], system_prompt, workspace_dir
                    )

            self.logger.error("Els tests han fallat després de la remediació.")
            print("❌ Els tests han fallat després de la remediació.")
            shutil.rmtree(workspace_dir, ignore_errors=True)
            return {"success": False}
        except Exception as e:
            self.logger.error(f"Error en la remediació multi-fitxer: {e}")
            print(f"❌ Error en la remediació multi-fitxer: {e}")
            shutil.rmtree(workspace_dir, ignore_errors=True)
            return {"success": False}

