"""Servei d'integració multi-repositori amb l'API de GitHub mitjançant PyGithub."""

from __future__ import annotations

import re
from typing import Any, Optional

from github import Github, GithubException

from src.utils.config import AppConfig
from src.utils.logger import AgentLogger, StructuredAgentAdapter

REPO_NAME_REGEX: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")


def validate_repo_name(repo_name: str) -> bool:
    """Valida que el nom del repositori compleixi el format 'propietari/nom' de forma segura.

    Prevé atacs d'injecció de rutes (Path Traversal - OWASP A03/A04) impedint seqüències '..'
    o formats malformjats.

    Args:
        repo_name: Nom del repositori a validar (ex: 'emasnou/ai-developer-agent').

    Returns:
        bool: True si el nom és sintàcticament segur i vàlid, False altrament.
    """
    if not repo_name or not isinstance(repo_name, str):
        return False
    cleaned = repo_name.strip()
    if ".." in cleaned:
        return False
    return bool(REPO_NAME_REGEX.match(cleaned))


class GitHubService:
    """Client d'alt nivell per gestionar múltiples repositoris, Issues, branques i PRs a GitHub."""

    def __init__(
        self,
        token: Optional[str] = None,
        repo_name: Optional[str] = None,
        require_repo: bool = True,
        client: Optional[Any] = None,
    ) -> None:
        """Inicialitza la connexió amb l'API de GitHub i selecciona el repositori si s'indica.

        Args:
            token: Token d'autenticació opcional (si no s'indica, es llegeix de la configuració).
            repo_name: Nom del repositori 'propietari/nom' opcional.
            require_repo: Si és True, exigeix disposar d'un repositori inicial connectat.
            client: Instància opcional del client PyGithub (útil per a injecció en tests).

        Raises:
            ValueError: Si falta GITHUB_TOKEN o si `require_repo` és True i no hi ha repositori.
            GithubException: Si falla la connexió amb el repositori de GitHub.
        """
        cfg = AppConfig.from_env()
        resolved_token = token or cfg.github_token
        resolved_repo = repo_name if repo_name is not None else cfg.github_repo

        if not resolved_token and client is None:
            raise ValueError("Falta la variable GITHUB_TOKEN al fitxer .env")

        base_logger = AgentLogger.get_logger("GitHubService")
        self.logger = StructuredAgentAdapter(base_logger, "GitHubService")
        self._configured_repos: tuple[str, ...] = cfg.github_repos
        self.client: Any = client if client is not None else Github(resolved_token)
        self.repo: Optional[Any] = None
        self._active_repo_name: Optional[str] = None

        if resolved_repo:
            self.set_active_repository(resolved_repo)
        elif require_repo:
            raise ValueError("Falta la variable GITHUB_REPO al fitxer .env o seleccionar un repositori")

    @property
    def active_repo_name(self) -> Optional[str]:
        """Retorna el nom complet ('propietari/nom') del repositori actiu actual.

        Returns:
            Optional[str]: Nom del repositori actiu o None si no se n'ha seleccionat cap.
        """
        if self.repo is not None:
            return getattr(self.repo, "full_name", self._active_repo_name)
        return self._active_repo_name

    def _require_active_repo(self) -> Any:
        """Garanteix que hi ha un repositori actiu seleccionat abans d'operar.

        Returns:
            Any: Objecte Repository de PyGithub actiu.

        Raises:
            ValueError: Si no hi ha cap repositori actiu seleccionat.
        """
        if self.repo is None:
            raise ValueError("No s'ha seleccionat cap repositori de GitHub sobre el qual treballar.")
        return self.repo

    def set_active_repository(self, repo_name: str) -> str:
        """Canvia i connecta el repositori de GitHub actiu sobre el qual treballaran els agents.

        Args:
            repo_name: Identificador del repositori en format 'propietari/nom'.

        Returns:
            str: Nom complet validat del repositori connectat (`full_name`).

        Raises:
            ValueError: Si el format del nom del repositori no és vàlid.
            GithubException: Si el repositori no existeix o no s'hi té accés.
        """
        cleaned_name = repo_name.strip() if isinstance(repo_name, str) else ""
        if not validate_repo_name(cleaned_name):
            raise ValueError(
                f"Format de repositori invàlid: '{repo_name}'. Ha de ser 'propietari/nom'."
            )

        try:
            self.repo = self.client.get_repo(cleaned_name)
            self._active_repo_name = getattr(self.repo, "full_name", cleaned_name)
            self.logger.info(f"Connectat correctament al repositori: {self._active_repo_name}")
            print(f"Connectat correctament al repositori: {self._active_repo_name}")
            return str(self._active_repo_name)
        except GithubException as e:
            self.logger.error(f"Error en connectar al repositori '{cleaned_name}': {e}")
            print(f"❌ Error en connectar al repositori '{cleaned_name}': {e}")
            raise

    def list_available_repositories(self, max_repos: int = 30) -> list[str]:
        """Obté la llista de repositoris de GitHub disponibles per treballar.

        Combina els repositoris preconfigurats a l'entorn (`GITHUB_REPOS` / `GITHUB_REPO`)
        amb els repositoris accessibles per l'usuari autenticat a l'API de GitHub.

        Args:
            max_repos: Nombre màxim de repositoris a consultar de l'API (per defecte 30).

        Returns:
            list[str]: Llista de noms complets ('propietari/nom') sense duplicats.
        """
        repos: list[str] = [r for r in self._configured_repos if validate_repo_name(r)]
        if self.active_repo_name and self.active_repo_name not in repos:
            repos.insert(0, self.active_repo_name)

        try:
            user_repos = self.client.get_user().get_repos(sort="updated")
            for idx, repo_obj in enumerate(user_repos):
                if idx >= max_repos:
                    break
                full_name = getattr(repo_obj, "full_name", None)
                if full_name and full_name not in repos:
                    repos.append(full_name)
        except Exception as e:
            self.logger.warning(f"No s'ha pogut obtenir el llistat remot de repositoris: {e}")

        return repos

    def get_default_branch(self) -> str:
        """Obté el nom de la branca principal per defecte del repositori actiu.

        Returns:
            str: Nom de la branca per defecte (ex: 'main' o 'master').
        """
        repo = self._require_active_repo()
        return getattr(repo, "default_branch", None) or "main"

    def create_issue(
        self, title: str, body: str, labels: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """Crea una nova tasca (Issue) al repositori de GitHub actiu.

        Args:
            title: Títol de la Issue.
            body: Descripció detallada en format Markdown.
            labels: Llista opcional d'etiquetes a assignar (per defecte `['agent-created']`).

        Returns:
            dict[str, Any]: Diccionari amb `number`, `url` i `title` de la Issue creada.

        Raises:
            GithubException: Si es produeix un error a l'API de GitHub.
        """
        repo = self._require_active_repo()
        try:
            resolved_labels = labels or ["agent-created"]
            issue = repo.create_issue(title=title, body=body, labels=resolved_labels)
            self.logger.info(
                f"[{self.active_repo_name}] Tasca creada amb èxit: #{issue.number} - {issue.title}"
            )
            print(f"Tasca creada amb èxit: #{issue.number} - {issue.title}")
            return {
                "number": issue.number,
                "url": issue.html_url,
                "title": issue.title,
            }
        except GithubException as e:
            self.logger.error(f"Error en crear la Issue a GitHub: {e}")
            print(f"❌ Error en crear la Issue a GitHub: {e}")
            raise

    def get_open_issues(self) -> list[Any]:
        """Obté la llista de totes les Issues obertes al repositori actiu (excloent PRs).

        Returns:
            list[Any]: Llista d'objectes Issue oberts a GitHub.

        Raises:
            GithubException: Si falla la consulta a l'API de GitHub.
        """
        repo = self._require_active_repo()
        try:
            all_open = list(repo.get_issues(state="open"))
            return [iss for iss in all_open if getattr(iss, "pull_request", None) is None]
        except GithubException as e:
            self.logger.error(f"Error en obtenir les Issues obertes: {e}")
            print(f"❌ Error en obtenir les Issues obertes: {e}")
            raise

    def get_issue(self, issue_number: int) -> Any:
        """Obté la informació d'una Issue existent pel seu número identificador.

        Args:
            issue_number: Número de la Issue a GitHub.

        Returns:
            Any: Objecte Issue de PyGithub.

        Raises:
            GithubException: Si la Issue no existeix o falla la consulta.
        """
        repo = self._require_active_repo()
        try:
            return repo.get_issue(number=issue_number)
        except GithubException as e:
            self.logger.error(f"Error en obtenir la Issue #{issue_number}: {e}")
            print(f"❌ Error en obtenir la Issue #{issue_number}: {e}")
            raise

    def get_repository_tree(self, ref: Optional[str] = None) -> list[str]:
        """Obté la llista de camins de fitxers del repositori actiu, incloent GitHub Actions.

        Inclou els fitxers dins de `.github/` (com `.github/workflows/*.yml` per a desplegaments)
        i exclou altres directoris ocults interns.

        Args:
            ref: Nom de la branca o referència de Git (per defecte la branca principal del repo).

        Returns:
            list[str]: Llista de rutes relatives dels fitxers del repositori.
        """
        repo = self._require_active_repo()
        resolved_ref = ref or self.get_default_branch()
        try:
            branch = repo.get_branch(resolved_ref)
            sha = branch.commit.sha
            tree = repo.get_git_tree(sha, recursive=True)
            return [
                element.path
                for element in tree.tree
                if element.type == "blob"
                and (not element.path.startswith(".") or element.path.startswith(".github/"))
            ]
        except GithubException as e:
            self.logger.error(f"Error en obtenir l'arbre del repositori ({resolved_ref}): {e}")
            print(f"❌ Error en obtenir l'arbre del repositori: {e}")
            return []

    def get_file_content(self, file_path: str, ref: Optional[str] = None) -> str:
        """Obté el contingut de text d'un fitxer existent al repositori actiu.

        Args:
            file_path: Ruta relativa del fitxer dins del repositori.
            ref: Branca o referència de Git d'on llegir el fitxer.

        Returns:
            str: Contingut descodificat en UTF-8 o cadena buida si no es pot llegir.
        """
        repo = self._require_active_repo()
        resolved_ref = ref or self.get_default_branch()
        try:
            content_file = repo.get_contents(file_path, ref=resolved_ref)
            return content_file.decoded_content.decode("utf-8")
        except GithubException as e:
            self.logger.warning(f"No s'ha pogut llegir el fitxer {file_path} ({resolved_ref}): {e}")
            print(f"⚠️ No s'ha pogut llegir el fitxer {file_path}: {e}")
            return ""

    def create_branch(self, base_branch: str, new_branch: str) -> None:
        """Crea una nova branca remota al repositori actiu a partir d'una branca base.

        Args:
            base_branch: Nom de la branca d'origen (ex: `'main'`).
            new_branch: Nom de la nova branca a crear.

        Raises:
            GithubException: Si es produeix un error diferent de 422 (branca ja existent).
        """
        repo = self._require_active_repo()
        try:
            ref = repo.get_git_ref(f"heads/{base_branch}")
            repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=ref.object.sha)
            self.logger.info(f"Branca '{new_branch}' creada a GitHub ({self.active_repo_name}).")
            print(f"🌿 Branca '{new_branch}' creada a GitHub.")
        except GithubException as e:
            if e.status == 422:
                self.logger.info(f"La branca '{new_branch}' ja existia a GitHub.")
                print(f"ℹ️ La branca '{new_branch}' ja existia a GitHub.")
            else:
                self.logger.error(f"Error en crear la branca '{new_branch}': {e}")
                print(f"❌ Error en crear la branca '{new_branch}': {e}")
                raise

    def commit_and_push_files(
        self, branch_name: str, files: list[dict[str, str]], commit_message: str
    ) -> None:
        """Crea o actualitza múltiples fitxers directament a una branca del repositori actiu.

        Args:
            branch_name: Nom de la branca de destinació.
            files: Llista de diccionaris amb les claus `'path'` i `'content'`.
            commit_message: Missatge de commit descriptiu seguint Conventional Commits.

        Raises:
            GithubException: Si falla la creació o actualització d'algun fitxer.
        """
        repo = self._require_active_repo()
        for file_info in files:
            file_path = file_info["path"]
            content = file_info["content"]
            try:
                existing_file = repo.get_contents(file_path, ref=branch_name)
                repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    sha=existing_file.sha,
                    branch=branch_name,
                )
                self.logger.info(f"Fitxer actualitzat a '{branch_name}': {file_path}")
                print(f"📝 Fitxer actualitzat a la branca '{branch_name}': {file_path}")
            except GithubException as e:
                if e.status == 404:
                    repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=content,
                        branch=branch_name,
                    )
                    self.logger.info(f"Fitxer afegit a '{branch_name}': {file_path}")
                    print(f"➕ Fitxer afegit a la branca '{branch_name}': {file_path}")
                else:
                    self.logger.error(f"Error en fer commit del fitxer {file_path}: {e}")
                    print(f"❌ Error en fer commit del fitxer {file_path}: {e}")
                    raise

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Obre una Pull Request (PR) automàticament al repositori actiu.

        Args:
            title: Títol de la Pull Request.
            body: Cos descriptiu en format Markdown.
            head_branch: Branca amb els canvis proposats.
            base_branch: Branca de destinació (per defecte la branca principal del repositori).

        Returns:
            Optional[dict[str, Any]]: Diccionari amb `number` i `url`, o None si ja existia.

        Raises:
            GithubException: Si falla la creació per un motiu diferent de PR duplicada (422).
        """
        repo = self._require_active_repo()
        resolved_base = base_branch or self.get_default_branch()
        try:
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=resolved_base,
            )
            self.logger.info(f"Pull Request creada amb èxit: #{pr.number} - {pr.html_url}")
            print(f"🔀 Pull Request creada amb èxit: #{pr.number} - {pr.html_url}")
            return {"number": pr.number, "url": pr.html_url}
        except GithubException as e:
            if e.status == 422:
                self.logger.info(f"Ja existeix una Pull Request oberta per a '{head_branch}'.")
                print("ℹ️ Ja existeix una Pull Request oberta per a aquesta branca.")
                return None
            self.logger.error(f"Error en crear la PR: {e}")
            print(f"❌ Error en crear la PR: {e}")
            raise

    def get_pull_requests(self) -> list[Any]:
        """Obté la llista de Pull Requests obertes al repositori actiu.

        Returns:
            list[Any]: Llista d'objectes PullRequest oberts.

        Raises:
            GithubException: Si falla la consulta a l'API de GitHub.
        """
        repo = self._require_active_repo()
        try:
            return list(repo.get_pulls(state="open"))
        except GithubException as e:
            self.logger.error(f"Error en obtenir les Pull Requests: {e}")
            print(f"❌ Error en obtenir les Pull Requests: {e}")
            raise

    def get_pull_request_files(self, pr_number: int) -> str:
        """Obté el diff (patch) de tots els fitxers modificats en una Pull Request.

        Args:
            pr_number: Número identificador de la Pull Request.

        Returns:
            str: Cadena amb els noms de fitxer i els seus respectius patches unificats.

        Raises:
            GithubException: Si falla la recuperació dels fitxers de la PR.
        """
        repo = self._require_active_repo()
        try:
            pr = repo.get_pull(pr_number)
            files = pr.get_files()
            diff_parts = [
                f"\n--- Fitxer: {file.filename} ---\nPatch / Canvis:\n{file.patch}\n"
                for file in files
            ]
            return "".join(diff_parts)
        except GithubException as e:
            self.logger.error(f"Error en obtenir els canvis de la PR #{pr_number}: {e}")
            print(f"❌ Error en obtenir els canvis de la PR #{pr_number}: {e}")
            raise

    def post_pr_comment(self, pr_number: int, comment_body: str) -> None:
        """Publica un comentari de revisió o auditoria a una Pull Request.

        Args:
            pr_number: Número identificador de la Pull Request.
            comment_body: Contingut del comentari en format Markdown.

        Raises:
            GithubException: Si falla la publicació del comentari.
        """
        repo = self._require_active_repo()
        try:
            pr = repo.get_pull(pr_number)
            pr.create_issue_comment(comment_body)
            self.logger.info(f"Comentari de Code Review publicat a la PR #{pr_number}.")
            print(f"💬 Comentari de Code Review publicat a la PR #{pr_number}.")
        except GithubException as e:
            self.logger.error(f"Error en publicar el comentari a la PR #{pr_number}: {e}")
            print(f"❌ Error en publicar el comentari a la PR #{pr_number}: {e}")
            raise

    def get_pr_review_comments(self, pr_number: int) -> str:
        """Obté tots els comentaris de revisió/auditoria publicats en una Pull Request.

        Args:
            pr_number: Número identificador de la Pull Request.

        Returns:
            str: Historial concatenat dels comentaris amb l'autor i el cos.

        Raises:
            GithubException: Si falla la lectura dels comentaris de la PR.
        """
        repo = self._require_active_repo()
        try:
            pr = repo.get_pull(pr_number)
            comments = pr.get_issue_comments()
            return "".join(
                f"\n--- Comentari de {comment.user.login} ---\n{comment.body}\n"
                for comment in comments
            )
        except GithubException as e:
            self.logger.error(f"Error en obtenir els comentaris de la PR #{pr_number}: {e}")
            print(f"❌ Error en obtenir els comentaris de la PR #{pr_number}: {e}")
            raise
