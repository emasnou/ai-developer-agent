'''Agent Desenvolupador per a la resolució autònoma d Issues i tests al repositori.'''

from __future__ import annotations

import os
import re
import json
import ast
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List
import yaml

from src.services.llm_service import LLMService
from src.services.github_service import GitHubService
from src.prompts.developer_prompts import (
    DEVELOPER_SYSTEM_PROMPT,
    DEVELOPER_FIX_PROMPT,
    DEVELOPER_REMEDIATION_PROMPT,
)
from src.utils.logger import get_agent_logger


class DeveloperAgent:
    '''Agent responsable de desenvolupar codi, executar tests i crear PRs.'''

    def __init__(self) -> None:
        '''Inicialitza els serveis, política de codi i el logger d auditoria.'''
        self.logger = get_agent_logger('DeveloperAgent')
        self.llm = LLMService()
        self.github = GitHubService()
        policy_path = Path('docs/code_policy.md')
        self.code_policy = policy_path.read_text(encoding='utf-8') if policy_path.exists() else 'Aplica PEP8 i OWASP Top 10.'

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        '''Extreu i parseja un objecte JSON o YAML de la resposta del LLM de manera resilient.

        Args:
            text: Text rebut de la resposta del model.

        Returns:
            Dict[str, Any]: Diccionari amb el contingut parsejat.
        '''
        cleaned = re.sub(r'(json|yaml)?\s*', '', text)
        cleaned = re.sub(r'\s*$', '', cleaned)
        first_brace = cleaned.find('{')
        last_brace = cleaned.rfind('}')

        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_candidate = cleaned[first_brace:last_brace + 1]
        else:
            json_candidate = cleaned.strip()

        try:
            from json_repair import repair_json
            repaired = repair_json(json_candidate, return_objects=True)
            if isinstance(repaired, dict) and 'files' in repaired:
                return repaired
        except Exception:
            pass

        try:
            parsed_yaml = yaml.safe_load(cleaned)
            if isinstance(parsed_yaml, dict) and 'files' in parsed_yaml:
                return parsed_yaml
        except Exception:
            pass

        return json.loads(json_candidate, strict=False)

    def _prepare_workspace_environment(self, identifier: int) -> Path:
        '''Prepara el directori de treball aïllat per a la tasca.

        Args:
            identifier: Identificador d Issue o PR.

        Returns:
            Path: Ruta al directori de workspace creat.
        '''
        root_dir = Path('.').resolve()
        workspace_dir = root_dir / '.workspace' / f'task_{identifier}'
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)

        def ignore_patterns(path: str, names: List[str]) -> List[str]:
            ignored = ['.git', '__pycache__', '.pytest_cache', '.venv', 'venv']
            if '.workspace' in path:
                ignored.extend(names)
            return ignored

        shutil.copytree(root_dir, workspace_dir, ignore=ignore_patterns)
        return workspace_dir

    def _download_main_branch_content(self, workspace_dir: Path) -> None:
        '''Descarrega els fitxers de la branca main al workspace.

        Args:
            workspace_dir: Ruta del directori de treball.
        '''
        repo_tree = self.github.get_repository_tree(ref='main')
        for file_path in repo_tree:
            content = self.github.get_file_content(file_path, ref='main')
            if content is not None:
                target_file = workspace_dir / file_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(content, encoding='utf-8')

    def _read_workspace_source_files(self, workspace_dir: Path) -> str:
        '''Llegeix els fitxers font del workspace.

        Args:
            workspace_dir: Directori del workspace.

        Returns:
            str: Contingut unificat dels fitxers Python existents.
        '''
        src_path = workspace_dir / 'src'
        if not src_path.exists():
            return 'No hi ha fitxers existents a src/'
        contents: List[str] = []
        for file in src_path.rglob('*.py'):
            try:
                rel_path = file.relative_to(workspace_dir)
                text = file.read_text(encoding='utf-8')
                contents.append(f'--- FITXER ({rel_path}) ---\n{text}\n')
            except Exception as e:
                self.logger.warning(f'Error en llegir {file}: {e}')
        return '\n'.join(contents) if contents else 'Cap fitxer .py trobat a src/'

    def _write_files_to_workspace(self, files_list: List[Dict[str, str]], workspace_dir: Path) -> List[Path]:
        '''Escriu la llista de fitxers modificats dins del workspace.

        Args:
            files_list: Llista de fitxers amb ruta i contingut.
            workspace_dir: Directori de treball aïllat.

        Returns:
            List[Path]: Llista dels camins escrits.
        '''
        saved_paths: List[Path] = []
        for file_item in files_list:
            target_path = workspace_dir / file_item['path']
            target_path.parent.mkdir(parents=True, exist_ok=True)
            content = file_item['content']
            try:
                ast.parse(content)
            except SyntaxError as e:
                self.logger.warning(f'Alerta de sintaxi a {file_item["path"]}: {e}')
            target_path.write_text(content, encoding='utf-8')
            saved_paths.append(target_path)
        return saved_paths

    def develop_and_test(self, issue_number: int, max_retries: int = 3) -> Dict[str, Any]:
        '''Desenvolupa una Issue, executa bateries de test i obre una Pull Request.

        Args:
            issue_number: Número de la Issue a resoldre.
            max_retries: Nombre màxim de cicles d auto-correcció.

        Returns:
            Dict[str, Any]: Resultat del procés de desenvolupament.
        '''
        self.logger.info(f'Iniciant desenvolupament de la Issue #{issue_number}')
        issue = self.github.get_issue(issue_number)
        workspace_dir = self._prepare_workspace_environment(issue_number)
        self._download_main_branch_content(workspace_dir)

        branch_name = f'feature/issue-{issue_number}'
        self.github.create_branch(base_branch='main', new_branch=branch_name)
        self.logger.info(f'Branca remota {branch_name} creada per a la Issue #{issue_number}')

        repo_tree = self.github.get_repository_tree(ref='main')
        tree_str = '\n'.join(repo_tree) if repo_tree else 'Repositori buit'
        existing_files_content = self._read_workspace_source_files(workspace_dir)

        prompt = f'Títol de la Issue: {issue.title}\n\nEspecificació:\n{issue.body}'
        system_prompt = DEVELOPER_SYSTEM_PROMPT.format(
            code_policy=self.code_policy,
            repo_tree=tree_str,
            existing_files_content=existing_files_content,
        )

        try:
            raw_response = self.llm.generate_task_spec(prompt, system_prompt)
            data = self._parse_json_response(raw_response)
        except Exception as err:
            self.logger.error(f'Error en la generació inicial de codi per a la Issue #{issue_number}: {err}')
            shutil.rmtree(workspace_dir, ignore_errors=True)
            return {'success': False, 'attempts': 0}

        files_data = data.get('files', [])
        if not files_data:
            self.logger.warning(f'No s han generat fitxers per a la Issue #{issue_number}')
            shutil.rmtree(workspace_dir, ignore_errors=True)
            return {'success': False, 'attempts': 0}

        self._write_files_to_workspace(files_data, workspace_dir)
        env = os.environ.copy()
        src_workspace = str((workspace_dir / 'src').resolve())
        env['PYTHONPATH'] = f'{src_workspace}:{env.get("PYTHONPATH", "")}'
        pytest_cmd = ['pytest', '-v', str(workspace_dir / 'tests')]

        for attempt in range(1, max_retries + 1):
            self.logger.info(f'Executant bateria de tests per a Issue #{issue_number} (Intent {attempt}/{max_retries})')
            try:
                test_result = subprocess.run(pytest_cmd, capture_output=True, text=True, env=env, cwd=str(workspace_dir), timeout=30)
            except subprocess.TimeoutExpired:
                self.logger.error(f'Timeout de 30s en PyTest per a la Issue #{issue_number}')
                shutil.rmtree(workspace_dir, ignore_errors=True)
                return {'success': False, 'attempts': attempt}

            if test_result.returncode == 0:
                self.logger.info(f'Tots els tests han passat satisfactòriament a l intent {attempt} per a la Issue #{issue_number}')
                files_to_commit = [
                    {'path': item['path'], 'content': (workspace_dir / item['path']).read_text(encoding='utf-8')}
                    for item in files_data
                ]
                commit_msg = f'feat: resolució Issue #{issue_number} ({data.get("summary", "multi-fitxer")})'
                self.github.commit_and_push_files(branch_name, files_to_commit, commit_msg)
                shutil.rmtree(workspace_dir, ignore_errors=True)

                files_summary = '\n'.join([f'- `{item["path"]}`' for item in files_to_commit])
                pr_body = (
                    f'Aquesta Pull Request ha estat generada automàticament per l **Agent Desenvolupador**.\n\n'
                    f'- **Issue resolta:** #{issue_number}\n'
                    f'- **Branca origen:** `{branch_name}`\n'
                    f'- **Fitxers:**\n{files_summary}\n'
                    f'- **Tests:** Passats en {attempt} intent/s'
                )
                pr_result = self.github.create_pull_request(
                    title=f'feat: resolució automàtica Issue #{issue_number} - {issue.title}',
                    body=pr_body,
                    head_branch=branch_name,
                    base_branch='main',
                )
                self.logger.info(f'Pull Request creada per a la Issue #{issue_number}: {pr_result.get("url")}')
                return {'success': True, 'attempts': attempt, 'files_count': len(files_to_commit), 'pr_url': pr_result.get('url')}
            else:
                self.logger.warning(f'PyTest ha fallat a l intent {attempt} per a la Issue #{issue_number}')
                error_log = test_result.stdout or test_result.stderr
                if attempt < max_retries:
                    files_summary_text = '\n'.join([f'Fitxer: {f["path"]}\n{f["content"]}\n' for f in files_data])
                    fix_prompt = DEVELOPER_FIX_PROMPT.format(
                        code_policy=self.code_policy,
                        files_summary=files_summary_text,
                        error_log=error_log,
                    )
                    try:
                        raw_response = self.llm.generate_task_spec(fix_prompt, system_prompt)
                        data = self._parse_json_response(raw_response)
                        files_data = data.get('files', files_data)
                        self._write_files_to_workspace(files_data, workspace_dir)
                    except Exception as fix_err:
                        self.logger.error(f'Error en re-generar codi durant l intent {attempt}: {fix_err}')

        shutil.rmtree(workspace_dir, ignore_errors=True)
        self.logger.error(f'No s ha pogut resoldre la Issue #{issue_number} després de {max_retries} intents')
        return {'success': False, 'attempts': max_retries}

    def remediate_pull_request(self, pr_number: int, max_retries: int = 3) -> Dict[str, Any]:
        '''Remedia una Pull Request existent basant-se en el Code Review.

        Args:
            pr_number: Número de la Pull Request a remediar.
            max_retries: Nombre màxim de cicles de correcció.

        Returns:
            Dict[str, Any]: Resultat de la remediació.
        '''
        self.logger.info(f'Iniciant procés de remediació per a la PR #{pr_number}')
        pr = self.github.repo.get_pull(pr_number)
        branch_name = pr.head.ref
        review_comments = self.github.get_pr_review_comments(pr_number)

        if not review_comments:
            self.logger.warning(f'No s han trobat comentaris de revisió per a la PR #{pr_number}')
            return {'success': False}

        workspace_dir = self._prepare_workspace_environment(pr_number)
        self._download_main_branch_content(workspace_dir)
        repo_tree = self.github.get_repository_tree(ref=branch_name)
        tree_str = '\n'.join(repo_tree) if repo_tree else ''
        existing_files_content = self._read_workspace_source_files(workspace_dir)

        remediation_prompt = DEVELOPER_REMEDIATION_PROMPT.format(code_policy=self.code_policy, review_comments=review_comments)
        system_prompt = DEVELOPER_SYSTEM_PROMPT.format(code_policy=self.code_policy, repo_tree=tree_str, existing_files_content=existing_files_content)

        try:
            raw_response = self.llm.generate_task_spec(remediation_prompt, system_prompt)
            data = self._parse_json_response(raw_response)
            files_data = data.get('files', [])
            if not files_data:
                shutil.rmtree(workspace_dir, ignore_errors=True)
                return {'success': False}

            self._write_files_to_workspace(files_data, workspace_dir)
            env = os.environ.copy()
            src_workspace = str((workspace_dir / 'src').resolve())
            env['PYTHONPATH'] = f'{src_workspace}:{env.get("PYTHONPATH", "")}'
            pytest_cmd = ['pytest', '-v', str(workspace_dir / 'tests')]
            test_result = subprocess.run(pytest_cmd, capture_output=True, text=True, env=env, cwd=str(workspace_dir), timeout=30)

            if test_result.returncode == 0:
                files_to_commit = [
                    {'path': item['path'], 'content': (workspace_dir / item['path']).read_text(encoding='utf-8')}
                    for item in files_data
                ]
                self.github.commit_and_push_files(branch_name, files_to_commit, 'fix: remediació multi-fitxer segons Code Review')
                shutil.rmtree(workspace_dir, ignore_errors=True)
                self.logger.info(f'Remediació de la PR #{pr_number} completada satisfactòriament a la branca {branch_name}')
                return {'success': True, 'branch': branch_name}
            else:
                self.logger.error(f'Tests fallats després de la remediació de la PR #{pr_number}')
                shutil.rmtree(workspace_dir, ignore_errors=True)
                return {'success': False}
        except Exception as exc:
            self.logger.error(f'Error en remediació per a la PR #{pr_number}: {exc}')
            shutil.rmtree(workspace_dir, ignore_errors=True)
            return {'success': False}
