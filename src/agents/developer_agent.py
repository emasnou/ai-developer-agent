"""Agent Desenvolupador per a la generació, validació amb PyTest i remediació de codi en workspaces aïllats."""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
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
from src.utils.adr_manager import materialize_adr_file
from src.utils.changelog_updater import update_changelog_file
from src.utils.doc_updater import update_all_documentation
from src.utils.github_templates import render_pull_request_body
from src.utils.json_parser import parse_developer_json_response

_SENSITIVE_ENV_VARS: tuple[str, ...] = (
    "GITHUB_TOKEN",
    "GITHUB_REPO",
    "GITHUB_REPOS",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
)
_WORKSPACE_IGNORED_ITEMS: set[str] = {
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
        repo_name: Optional[str] = None,
    ) -> None:
        """Inicialitza el DeveloperAgent amb injecció opcional de serveis, política i logger.

        Args:
            llm_service: Instància opcional de LLMService per a injecció de dependències.
            github_service: Instància opcional de GitHubService per a injecció de dependències.
            repo_name: Nom opcional del repositori (`owner/repo`) sobre el qual treballar.
        """
        super().__init__(
            agent_name="DeveloperAgent",
            llm_service=llm_service,
            github_service=github_service,
            repo_name=repo_name,
        )

    def _get_workspace_repo_slug(self) -> str:
        """Obté un identificador de directori segur basat en el repositori actiu.

        Returns:
            str: Nom del repositori normalitzat (`owner__repo`) o `'default_repo'`.
        """
        repo_name = self.active_repo_name
        if not repo_name:
            return "default_repo"
        return repo_name.strip().replace("/", "__")

    @staticmethod
    def extract_issue_dependencies(issue_body: Optional[str]) -> list[int]:
        """Extreu els números de les Stories/Issues prèvies de les quals depèn una Issue.

        Analitza la secció de dependències del cos Markdown generat per l'Analista
        (p.ex. `- **Dependències Prèvies:** Issue #101 ...`) o declaracions explícites
        (`Depèn de: #10`, `Depends on: #10`).

        Args:
            issue_body: Contingut en Markdown del cos de la Issue de GitHub.

        Returns:
            list[int]: Llista ordenada i sense duplicats dels IDs d'Issues prèvies requerides.
        """
        if not issue_body or not isinstance(issue_body, str):
            return []

        dep_numbers: list[int] = []
        pattern = re.compile(
            r"(?im)^\s*(?:[-*]\s*)?\**(?:depend[èe]ncies(?:\s+pr[èe]vies)?|"
            r"dep[èe]n\s+de|depends\s+on|blocked\s+by)\**\s*:\s*\**\s*([^\n]+)"
        )
        for match in pattern.finditer(issue_body):
            line_value = match.group(1).strip()
            if re.match(r"^(?:cap|none|n/a)\b", line_value, flags=re.IGNORECASE):
                continue
            for num_str in re.findall(r"(?<!Pas\s)#(\d+)\b", line_value, flags=re.IGNORECASE):
                num = int(num_str)
                if num > 0 and num not in dep_numbers:
                    dep_numbers.append(num)
        return dep_numbers

    @classmethod
    def resolve_dependency_status(
        cls, issue: Any, open_issues: list[Any]
    ) -> dict[str, Any]:
        """Avalua si una Story té dependències pendents respecte a les Issues encara obertes.

        Si una Story depèn d'una altra que al seu torn depèn d'una anterior, recorre
        la cadena de dependències per identificar quina és la primera Story que cal
        desenvolupar.

        Args:
            issue: Objecte Issue seleccionat per desenvolupar.
            open_issues: Llista d'objectes Issue actualment oberts al repositori.

        Returns:
            dict[str, Any]: Diccionari amb `dependencies` (`list[int]`),
                `pending_dependencies` (`list[int]`), `is_blocked` (`bool`) i
                `first_required_issue` (`Optional[Any]`).
        """
        current_num = getattr(issue, "number", None)
        open_by_num: dict[int, Any] = {
            getattr(iss, "number"): iss
            for iss in open_issues
            if getattr(iss, "number", None) is not None
        }
        all_deps = [
            d
            for d in cls.extract_issue_dependencies(getattr(issue, "body", None))
            if d != current_num
        ]
        pending_deps = [d for d in all_deps if d in open_by_num]

        first_required: Optional[Any] = None
        if pending_deps:
            visited: set[int] = set()
            cursor_num = pending_deps[0]
            while cursor_num in open_by_num and cursor_num not in visited:
                visited.add(cursor_num)
                candidate_issue = open_by_num[cursor_num]
                first_required = candidate_issue
                sub_deps = [
                    d
                    for d in cls.extract_issue_dependencies(
                        getattr(candidate_issue, "body", None)
                    )
                    if d != cursor_num and d in open_by_num and d not in visited
                ]
                if not sub_deps:
                    break
                cursor_num = sub_deps[0]

        return {
            "dependencies": all_deps,
            "pending_dependencies": pending_deps,
            "is_blocked": bool(pending_deps),
            "first_required_issue": first_required,
        }

    @classmethod
    def format_issue_dependency_badge(cls, issue: Any, open_issues: list[Any]) -> str:
        """Formata l'etiqueta informativa de dependències per mostrar al menú de selecció.

        Args:
            issue: Objecte Issue a mostrar al menú.
            open_issues: Llista de totes les Issues obertes al repositori.

        Returns:
            str: Text descriptiu amb la dependència i l'estat (pendent o llista per desenvolupar).
        """
        status = cls.resolve_dependency_status(issue, open_issues)
        all_deps: list[int] = status["dependencies"]
        pending_deps: list[int] = status["pending_dependencies"]
        first_req = status["first_required_issue"]

        if not all_deps:
            return " [🔗 Dependències: Cap — ✅ Llista per desenvolupar]"

        deps_str = ", ".join(f"#{d}" for d in all_deps)
        if pending_deps:
            first_num = getattr(first_req, "number", pending_deps[0])
            return (
                f" [🔗 Depèn de: {deps_str} — ⏳ Bloquejada: cal desenvolupar primer #{first_num}]"
            )
        return f" [🔗 Depèn de: {deps_str} — ✅ Dependències completades]"

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

    def _is_local_repository(self, root_dir: Optional[Path] = None) -> bool:
        """Comprova si el repositori actiu correspon al propi repositori local d'execució.

        Args:
            root_dir: Directori arrel local opcional (per defecte el directori actual).

        Returns:
            bool: `True` si s'està treballant sobre el repositori local o sense repo explícit.
        """
        resolved_root = (root_dir or Path(".")).resolve()
        active_repo = self.active_repo_name
        return active_repo is None or active_repo.endswith(f"/{resolved_root.name}")

    def _prepare_workspace_environment(self, issue_number: int) -> Path:
        """Crea un directori de workspace aïllat per al repositori i Issue actuals.

        Si el repositori actiu correspon al propi projecte local o no s'ha especificat,
        duplica l'arbre local excloent secrets (`.env`) i logs. Si és un altre repositori
        de GitHub, inicialitza un workspace net per descarregar-hi el contingut remot.

        Args:
            issue_number: Número d'Issue o PR que identifica el workspace.

        Returns:
            Path: Ruta absoluta del directori del workspace creat.
        """
        root_dir = Path(".").resolve()
        repo_slug = self._get_workspace_repo_slug()
        workspace_dir = root_dir / ".workspace" / repo_slug / f"issue_{issue_number}"

        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)

        active_repo = self.active_repo_name
        is_local_repo = self._is_local_repository(root_dir)

        if not is_local_repo:
            self.logger.info(
                f"Inicialitzant workspace net per al repositori '{active_repo}': {workspace_dir}"
            )
            print(
                f"📦 [DeveloperAgent] Preparant workspace per a '{active_repo}': {workspace_dir}..."
            )
            workspace_dir.mkdir(parents=True, exist_ok=True)
            return workspace_dir

        self.logger.info(f"Duplicant entorn local cap al workspace: {workspace_dir}")
        print(f"📦 [DeveloperAgent] Duplicant entorn local cap al workspace: {workspace_dir}...")

        def ignore_patterns(path: str, names: list[str]) -> list[str]:
            ignored = [n for n in names if n in _WORKSPACE_IGNORED_ITEMS or n.endswith(".env")]
            if ".workspace" in path:
                ignored.extend(names)
            return ignored

        shutil.copytree(root_dir, workspace_dir, ignore=ignore_patterns)
        return workspace_dir

    def _download_branch_content(
        self, workspace_dir: Path, ref: str = "main", overwrite_existing: bool = True
    ) -> None:
        """Descarrega i sincronitza al workspace el contingut d'una branca remota de GitHub.

        Args:
            workspace_dir: Ruta del workspace local on escriure els fitxers.
            ref: Nom de la branca o referència de Git a sincronitzar (per defecte 'main').
            overwrite_existing: Si és `False`, conserva els fitxers ja copiats de l'entorn
                local per evitar sobrescriure correccions locals amb versions remotes antigues.
        """
        self.logger.info(f"Sincronitzant contingut de la branca '{ref}' de GitHub al workspace...")
        print(f"📥 [DeveloperAgent] Sincronitzant contingut de la branca '{ref}' al workspace...")
        repo_tree = self.github.get_repository_tree(ref=ref)

        for file_path in repo_tree:
            target_file = workspace_dir / file_path
            if not overwrite_existing and target_file.exists():
                continue
            content = self.github.get_file_content(file_path, ref=ref)
            if content is not None:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(content, encoding="utf-8")

    def _download_main_branch_content(self, workspace_dir: Path) -> None:
        """Sincronitza al workspace el contingut de la branca principal de GitHub.

        Args:
            workspace_dir: Ruta del workspace local.
        """
        default_branch = self._resolve_default_branch()
        self._download_branch_content(workspace_dir, ref=default_branch)

    def _resolve_default_branch(self) -> str:
        """Obté el nom de la branca principal del repositori actiu de manera segura.

        Returns:
            str: Nom de la branca per defecte (ex: `'main'` o `'master'`).
        """
        if hasattr(self.github, "get_default_branch"):
            branch = self.github.get_default_branch()
            if isinstance(branch, str) and branch.strip():
                return branch.strip()
        return "main"

    def _read_workspace_source_files(self, workspace_dir: Path) -> str:
        """Llegeix el contingut dels fitxers font i workflows sincronitzats al workspace.

        Args:
            workspace_dir: Ruta del workspace local.

        Returns:
            str: Contingut concatenat dels fitxers Python i workflows de GitHub Actions.
        """
        candidate_files: list[Path] = []
        src_path = workspace_dir / "src"
        if src_path.exists():
            candidate_files.extend(sorted(src_path.rglob("*.py")))
        else:
            candidate_files.extend(
                sorted(
                    p
                    for p in workspace_dir.rglob("*.py")
                    if not any(part.startswith("test") for part in p.relative_to(workspace_dir).parts)
                )
            )

        workflows_path = workspace_dir / ".github" / "workflows"
        if workflows_path.exists():
            candidate_files.extend(sorted(workflows_path.glob("*.yml")))
            candidate_files.extend(sorted(workflows_path.glob("*.yaml")))

        if not candidate_files:
            return "No hi ha fitxers existents al directori src/"

        contents: list[str] = []
        for file in candidate_files:
            try:
                rel_path = file.relative_to(workspace_dir)
                text = file.read_text(encoding="utf-8")
                contents.append(f"--- FITXER ({rel_path}) ---\n{text}\n")
            except Exception as e:
                self.logger.warning(f"Error en llegir el fitxer del workspace {file}: {e}")

        return "\n".join(contents) if contents else "Cap fitxer trobat al workspace"

    @staticmethod
    def _repair_python_syntax_typos(content: str) -> str:
        """Repara errors tipogràfics freqüents del LLM en diccionaris Python si `ast.parse` falla.

        Corrigeix patrons com `"key=""value",` o `"key": ""value",` generats accidentalment
        dins de literals de diccionari quan el model omet els dos punts (`:`).

        Args:
            content: Codi font Python original amb error de sintaxi.

        Returns:
            str: Codi font reparat si passa `ast.parse`, o el contingut original altrament.
        """
        repaired = re.sub(
            r'"([A-Za-z_][A-Za-z0-9_.-]*)=?"\s*"([^"\n]*)"(\s*[,}\n])',
            r'"\1": "\2"\3',
            content,
        )
        repaired = re.sub(
            r'("[A-Za-z_][A-Za-z0-9_.-]*"\s*:\s*)""([^"\n]*)"(\s*[,}\n])',
            r'\1"\2"\3',
            repaired,
        )
        if repaired != content:
            try:
                ast.parse(repaired)
                return repaired
            except SyntaxError:
                pass
        return content

    @staticmethod
    def _collect_python_syntax_errors(
        files_list: list[dict[str, Any]], workspace_dir: Path
    ) -> str:
        """Comprova si algun fitxer Python generat conté errors de sintaxi abans d'executar PyTest.

        Args:
            files_list: Llista de fitxers generats pel LLM.
            workspace_dir: Ruta del workspace local.

        Returns:
            str: Detall dels errors de sintaxi trobats o cadena buida si tot és vàlid.
        """
        errors: list[str] = []
        for file_item in files_list:
            rel_path = file_item.get("path", "")
            if not rel_path.endswith(".py"):
                continue
            target_path = workspace_dir / rel_path
            source = (
                target_path.read_text(encoding="utf-8")
                if target_path.exists()
                else file_item.get("content", "")
            )
            try:
                ast.parse(source, filename=rel_path)
            except SyntaxError as exc:
                line_text = (exc.text or "").strip()
                errors.append(
                    f"SyntaxError a {rel_path} (línia {exc.lineno}): {exc.msg}\n"
                    f"  Línia conflictiva: {line_text}"
                )
        return "\n".join(errors)

    def _write_files_to_workspace(
        self, files_list: list[dict[str, Any]], workspace_dir: Path
    ) -> list[Path]:
        """Escriu els fitxers modificats o creats dins del workspace aïllat i en valida la sintaxi.

        Args:
            files_list: Llista de diccionaris amb `path` i `content`.
            workspace_dir: Ruta del workspace local.

        Returns:
            list[Path]: Llista de rutes dels fitxers escrits.

        Raises:
            ValueError: Si una ruta de fitxer intenta sortir del workspace (Path Traversal).
        """
        saved_paths: list[Path] = []
        resolved_workspace = workspace_dir.resolve()
        for file_item in files_list:
            target_path = (workspace_dir / file_item["path"]).resolve()
            if not target_path.is_relative_to(resolved_workspace):
                raise ValueError(
                    f"Ruta de fitxer no permesa fora del workspace: '{file_item['path']}'"
                )
            target_path.parent.mkdir(parents=True, exist_ok=True)
            content = file_item["content"]

            if target_path.suffix == ".py":
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    repaired = self._repair_python_syntax_typos(content)
                    if repaired != content:
                        content = repaired
                        file_item["content"] = repaired
                        self.logger.info(
                            f"Reparada automàticament errada tipogràfica de sintaxi a {file_item['path']}."
                        )
                    else:
                        self.logger.warning(
                            f"Alerta de sintaxi/indentació a {file_item['path']}: {e}"
                        )

            target_path.write_text(content, encoding="utf-8")
            saved_paths.append(target_path)
            self.logger.info(f"Fitxer actualitzat al Workspace: {file_item['path']}")
            print(f"📄 Fitxer actualitzat al Workspace: {file_item['path']}")

        return saved_paths

    def _apply_adr_plan_if_present(
        self, data: dict[str, Any], files_data: list[dict[str, Any]], workspace_dir: Path
    ) -> list[dict[str, Any]]:
        """Materialitza el registre ADR si s'ha definit una decisió d'arquitectura.

        Args:
            data: Diccionari de resposta de l'anàlisi de DeveloperPlan.
            files_data: Llista actual de fitxers gestionats per la tasca.
            workspace_dir: Ruta del directori aïllat del workspace.

        Returns:
            list[dict[str, Any]]: Llista actualitzada de fitxers incloent l'ADR creat.
        """
        adr_data = data.get("adr")
        if not adr_data:
            return files_data

        try:
            adr_dir = workspace_dir / "docs" / "adr"
            created_path = materialize_adr_file(adr_data, adr_dir)
            rel_path = created_path.relative_to(workspace_dir).as_posix()
            content = created_path.read_text(encoding="utf-8")
            existing_match = next((f for f in files_data if f["path"] == rel_path), None)
            if existing_match:
                existing_match["content"] = content
            else:
                files_data.append({"path": rel_path, "action": "create", "content": content})
            self.logger.info(f"ADR materialitzat correctament al workspace: {rel_path}")
        except Exception as exc:
            self.logger.warning(f"No s'ha pogut materialitzar el registre ADR: {exc}")

        return files_data

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

    @staticmethod
    def _trim_pytest_output(error_log: str, max_chars: int = 4000) -> str:
        """Retalla la sortida de PyTest preservant sempre la secció de FAILURES/ERRORS final.

        Args:
            error_log: Sortida completa (stdout/stderr) de l'execució de PyTest.
            max_chars: Límit màxim de caràcters a retornar.

        Returns:
            str: Traça d'error rellevant amb el detall de l'asserció o excepció.
        """
        if len(error_log) <= max_chars:
            return error_log

        for marker in ("=== FAILURES ===", "=== ERRORS ===", "short test summary info"):
            idx = error_log.find(marker)
            if idx != -1:
                relevant = error_log[idx:]
                if len(relevant) <= max_chars:
                    return relevant
                return relevant[-max_chars:]

        head_len = min(600, max_chars // 4)
        tail_len = max_chars - head_len - 35
        return f"{error_log[:head_len]}\n...[sortida PyTest retallada]...\n{error_log[-tail_len:]}"

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
                failure_excerpt = self._trim_pytest_output(output, max_chars=1500)
                self.logger.error(f"Els {phase_label} han fallat:\n{failure_excerpt}")
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
            cmd = [sys.executable, "-m", "pytest", "-v", "-x", "--tb=short", *targeted_tests]
            passed, output = self._run_pytest_command(cmd, workspace_dir, env, "tests específics")
            if not passed:
                return False, output

        unit_dir = workspace_dir / "tests" / "unit"
        if unit_dir.exists():
            self.logger.info("Executant regressió de tests unitaris...")
            print("🛡️ [Tests] Executant regressió de tests unitaris...")
            cmd = [sys.executable, "-m", "pytest", "-v", "-x", "--tb=short", str(unit_dir)]
            return self._run_pytest_command(cmd, workspace_dir, env, "tests unitaris de regressió")

        return True, ""

    @staticmethod
    def _extract_failing_test_context(
        error_log: str, workspace_dir: Path, files_data: list[dict[str, Any]]
    ) -> str:
        """Extreu el contingut dels fitxers de test esmentats a l'error que no siguin a `files_data`.

        Args:
            error_log: Sortida d'error de PyTest.
            workspace_dir: Ruta del workspace local.
            files_data: Fitxers actualment gestionats per la tasca.

        Returns:
            str: Bloc de context amb els fitxers de test que han fallat, o cadena buida.
        """
        tracked_paths = {f.get("path", "") for f in files_data}
        matched_tests = sorted(set(re.findall(r"(tests/[A-Za-z0-9_/.-]+\.py)", error_log)))
        extra_contexts: list[str] = []
        for rel_test in matched_tests:
            if rel_test in tracked_paths:
                continue
            test_file = workspace_dir / rel_test
            if test_file.is_file():
                try:
                    content = test_file.read_text(encoding="utf-8")
                    extra_contexts.append(
                        f"Fitxer de test de regressió que ha fallat (NOMÉS LECTURA): {rel_test}\n{content}\n"
                    )
                except Exception:
                    continue
        return "\n".join(extra_contexts)

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
        extra_test_context = self._extract_failing_test_context(error_log, workspace_dir, files_data)
        if extra_test_context:
            files_summary_text = f"{files_summary_text}\n{extra_test_context}"

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

    def _sync_workspace_changelog(
        self,
        workspace_dir: Path,
        files_to_commit: list[dict[str, str]],
        commit_msg: str,
    ) -> None:
        """Actualitza automàticament el CHANGELOG.md del workspace si hi ha nous canvis.

        Args:
            workspace_dir: Ruta del workspace local.
            files_to_commit: Llista de fitxers que s'inclouran al commit.
            commit_msg: Missatge en format Conventional Commits de la tasca resolta.
        """
        changelog_path = workspace_dir / "CHANGELOG.md"
        if not changelog_path.exists():
            return
        if any(item["path"] == "CHANGELOG.md" for item in files_to_commit):
            return
        if update_changelog_file(changelog_path=changelog_path, commits=[commit_msg]):
            files_to_commit.append(
                {
                    "path": "CHANGELOG.md",
                    "content": changelog_path.read_text(encoding="utf-8"),
                }
            )
            self.logger.info("CHANGELOG.md actualitzat automàticament al Workspace.")

    def _sync_workspace_documentation(
        self,
        workspace_dir: Path,
        files_to_commit: list[dict[str, str]],
    ) -> None:
        """Sincronitza automàticament la referència d'API i l'índex d'ADRs dins del workspace.

        Args:
            workspace_dir: Ruta del workspace local on s'han escrit els fitxers nous o modificats.
            files_to_commit: Llista de fitxers que s'inclouran al commit de la Pull Request.
        """
        if not (workspace_dir / "src").exists() or not (workspace_dir / "docs").exists():
            return
        try:
            updated_paths = update_all_documentation(root_dir=workspace_dir)
        except Exception as err:
            self.logger.warning(f"No s'ha pogut auto-sincronitzar la documentació del workspace: {err}")
            return

        existing_by_path = {item["path"]: item for item in files_to_commit}
        for rel_path in updated_paths:
            doc_file = workspace_dir / rel_path
            if not doc_file.exists():
                continue
            content = doc_file.read_text(encoding="utf-8")
            if rel_path in existing_by_path:
                existing_by_path[rel_path]["content"] = content
            else:
                files_to_commit.append({"path": rel_path, "content": content})
            self.logger.info(f"Documentació actualitzada automàticament al Workspace: {rel_path}")

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
        commit_msg = f"feat(issue-{issue.number}): resolució Issue #{issue.number} ({summary})"
        self._sync_workspace_changelog(workspace_dir, files_to_commit, commit_msg)
        self._sync_workspace_documentation(workspace_dir, files_to_commit)

        print(f"\n🚀 [DeveloperAgent] Publicant {len(files_to_commit)} fitxers a '{branch_name}'...")
        self.github.commit_and_push_files(branch_name, files_to_commit, commit_msg)

        # Renderitzem el cos de la PR abans d'eliminar el workspace per permetre usar
        # la plantilla .github/pull_request_template.md pròpia del repositori actiu
        pr_body = render_pull_request_body(
            issue_number=issue.number,
            issue_title=issue.title,
            branch_name=branch_name,
            files_to_commit=files_to_commit,
            attempt=attempt,
            summary=summary,
            workspace_dir=workspace_dir,
        )
        shutil.rmtree(workspace_dir, ignore_errors=True)

        default_branch = self._resolve_default_branch()
        pr_result = self.github.create_pull_request(
            title=f"feat: resolució automàtica Issue #{issue.number} - {issue.title}",
            body=pr_body,
            head_branch=branch_name,
            base_branch=default_branch,
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

        raw_deps = self.extract_issue_dependencies(getattr(issue, "body", None))
        if raw_deps and hasattr(self.github, "get_open_issues"):
            open_issues = self.github.get_open_issues()
            if isinstance(open_issues, list):
                dep_status = self.resolve_dependency_status(issue, open_issues)
                if dep_status["is_blocked"]:
                    first_req = dep_status["first_required_issue"]
                    first_req_num = getattr(
                        first_req, "number", dep_status["pending_dependencies"][0]
                    )
                    first_req_title = getattr(first_req, "title", f"Issue #{first_req_num}")
                    pending_str = ", ".join(f"#{d}" for d in dep_status["pending_dependencies"])
                    self.logger.warning(
                        f"La Issue #{issue_number} té dependències obertes pendents ({pending_str}). "
                        f"Cal desenvolupar primer la Issue #{first_req_num}."
                    )
                    print(
                        f"\n⛔ [DeveloperAgent] No es pot desenvolupar la Story #{issue_number} "
                        f"perquè té dependències pendents ({pending_str})."
                    )
                    print(
                        f"👉 Cal desenvolupar primer la Story #{first_req_num}: '{first_req_title}'."
                    )
                    return {
                        "success": False,
                        "attempts": 0,
                        "blocked_by_dependencies": True,
                        "pending_dependencies": dep_status["pending_dependencies"],
                        "first_required_issue": first_req_num,
                    }

        default_branch = self._resolve_default_branch()

        workspace_dir = self._prepare_workspace_environment(issue_number)
        self._download_branch_content(
            workspace_dir,
            ref=default_branch,
            overwrite_existing=not self._is_local_repository(),
        )

        branch_name = f"feature/issue-{issue_number}"
        self.logger.info(f"Creant branca remota '{branch_name}'...")
        print(
            f"🌿 [DeveloperAgent] Creant la branca remota '{branch_name}' "
            f"a partir de '{default_branch}'..."
        )
        self.github.create_branch(base_branch=default_branch, new_branch=branch_name)

        repo_tree = self.github.get_repository_tree(ref=default_branch)
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
        files_data = self._apply_adr_plan_if_present(data, files_data, workspace_dir)

        if not files_data:
            self.logger.warning("La IA no ha especificat cap fitxer per modificar/crear.")
            shutil.rmtree(workspace_dir, ignore_errors=True)
            return {"success": False, "attempts": 0}

        self._write_files_to_workspace(files_data, workspace_dir)
        syntax_errors = self._collect_python_syntax_errors(files_data, workspace_dir)
        if syntax_errors:
            self.logger.warning(
                f"Detectats errors de sintaxi AST abans d'executar PyTest; aplicant auto-correcció prèvia:\n{syntax_errors}"
            )
            files_data = self._request_surgical_fix(
                files_data, syntax_errors, system_prompt, workspace_dir
            )
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
            trimmed_log = self._trim_pytest_output(error_log, max_chars=4000)
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
                    remediation_msg = "fix: remediació multi-fitxer segons Code Review"
                    self._sync_workspace_changelog(workspace_dir, files_to_commit, remediation_msg)
                    self._sync_workspace_documentation(workspace_dir, files_to_commit)
                    self.github.commit_and_push_files(
                        branch_name,
                        files_to_commit,
                        remediation_msg,
                    )
                    shutil.rmtree(workspace_dir, ignore_errors=True)
                    return {"success": True, "branch": branch_name}

                if attempt < max_retries:
                    files_data = self._request_surgical_fix(
                        files_data,
                        self._trim_pytest_output(error_log, max_chars=4000),
                        system_prompt,
                        workspace_dir,
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
