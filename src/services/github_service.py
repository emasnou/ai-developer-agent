"""Servei d'integració amb l'API de GitHub mitjançant PyGithub."""

from __future__ import annotations

from typing import Any, Optional

from github import Github, GithubException

from src.utils.config import AppConfig
from src.utils.logger import AgentLogger, StructuredAgentAdapter


class GitHubService:
    """Client d'alt nivell per gestionar Issues, branques, commits i Pull Requests a GitHub."""

    def __init__(
        self,
        token: Optional[str] = None,
        repo_name: Optional[str] = None,
    ) -> None:
        """Inicialitza la connexió amb l'API de GitHub utilitzant el Personal Access Token.

        Args:
            token: Token d'autenticació opcional (si no s'indica, es llegeix de la configuració).
            repo_name: Nom del repositori 'propietari/nom' opcional.

        Raises:
            ValueError: Si falten les variables GITHUB_TOKEN o GITHUB_REPO.
            GithubException: Si falla la connexió amb el repositori de GitHub.
        """
        cfg = AppConfig.from_env()
        resolved_token = token or cfg.github_token
        resolved_repo = repo_name or cfg.github_repo

        if not resolved_token:
            raise ValueError("Falta la variable GITHUB_TOKEN al fitxer .env")
        if not resolved_repo:
            raise ValueError("Falta la variable GITHUB_REPO al fitxer .env")

        base_logger = AgentLogger.get_logger("GitHubService")
        self.logger = StructuredAgentAdapter(base_logger, "GitHubService")
        self.client = Github(resolved_token)
        try:
            self.repo = self.client.get_repo(resolved_repo)
            self.logger.info(f"Connectat correctament al repositori: {self.repo.full_name}")
            print(f"Connectat correctament al repositori: {self.repo.full_name}")
        except GithubException as e:
            self.logger.error(f"Error en connectar al repositori '{resolved_repo}': {e}")
            print(f"❌ Error en connectar al repositori '{resolved_repo}': {e}")
            raise


    def create_issue(
        self, title: str, body: str, labels: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """Crea una nova tasca (Issue) al repositori de GitHub.

        Args:
            title: Títol de la Issue.
            body: Descripció detallada en format Markdown.
            labels: Llista opcional d'etiquetes a assignar (per defecte `['agent-created']`).

        Returns:
            dict[str, Any]: Diccionari amb `number`, `url` i `title` de la Issue creada.

        Raises:
            GithubException: Si es produeix un error a l'API de GitHub.
        """
        try:
            resolved_labels = labels or ["agent-created"]
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=resolved_labels,
            )
            self.logger.info(f"Tasca creada amb èxit: #{issue.number} - {issue.title}")
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
        """Obté la llista de totes les Issues obertes al repositori.

        Returns:
            list[Any]: Llista d'objectes Issue oberts a GitHub.

        Raises:
            GithubException: Si falla la consulta a l'API de GitHub.
        """
        try:
            return list(self.repo.get_issues(state="open"))
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
        try:
            return self.repo.get_issue(number=issue_number)
        except GithubException as e:
            self.logger.error(f"Error en obtenir la Issue #{issue_number}: {e}")
            print(f"❌ Error en obtenir la Issue #{issue_number}: {e}")
            raise

    def get_repository_tree(self, ref: str = "main") -> list[str]:
        """Obté la llista completa de camins (paths) de fitxers del repositori en una branca.

        Args:
            ref: Nom de la branca o referència de Git (per defecte `'main'`).

        Returns:
            list[str]: Llista de rutes relatives dels fitxers del repositori.
        """
        try:
            branch = self.repo.get_branch(ref)
            sha = branch.commit.sha
            tree = self.repo.get_git_tree(sha, recursive=True)
            return [
                element.path
                for element in tree.tree
                if element.type == "blob" and not element.path.startswith(".")
            ]
        except GithubException as e:
            self.logger.error(f"Error en obtenir l'arbre del repositori ({ref}): {e}")
            print(f"❌ Error en obtenir l'arbre del repositori: {e}")
            return []

    def get_file_content(self, file_path: str, ref: str = "main") -> str:
        """Obté el contingut de text d'un fitxer existent al repositori.

        Args:
            file_path: Ruta relativa del fitxer dins del repositori.
            ref: Branca o referència de Git d'on llegir el fitxer.

        Returns:
            str: Contingut descodificat en UTF-8 o cadena buida si no es pot llegir.
        """
        try:
            content_file = self.repo.get_contents(file_path, ref=ref)
            return content_file.decoded_content.decode("utf-8")
        except GithubException as e:
            self.logger.warning(f"No s'ha pogut llegir el fitxer {file_path} ({ref}): {e}")
            print(f"⚠️ No s'ha pogut llegir el fitxer {file_path}: {e}")
            return ""

    def create_branch(self, base_branch: str, new_branch: str) -> None:
        """Crea una nova branca remota a GitHub a partir d'una branca base.

        Args:
            base_branch: Nom de la branca d'origen (ex: `'main'`).
            new_branch: Nom de la nova branca a crear.

        Raises:
            GithubException: Si es produeix un error diferent de 422 (branca ja existent).
        """
        try:
            ref = self.repo.get_git_ref(f"heads/{base_branch}")
            self.repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=ref.object.sha)
            self.logger.info(f"Branca '{new_branch}' creada a GitHub.")
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
        """Crea o actualitza múltiples fitxers directament a una branca de GitHub via API.

        Args:
            branch_name: Nom de la branca de destinació.
            files: Llista de diccionaris amb les claus `'path'` i `'content'`.
            commit_message: Missatge de commit descriptiu seguint Conventional Commits.

        Raises:
            GithubException: Si falla la creació o actualització d'algun fitxer.
        """
        for file_info in files:
            file_path = file_info["path"]
            content = file_info["content"]
            try:
                existing_file = self.repo.get_contents(file_path, ref=branch_name)
                self.repo.update_file(
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
                    self.repo.create_file(
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
        base_branch: str = "main",
    ) -> Optional[dict[str, Any]]:
        """Obre una Pull Request (PR) automàticament a GitHub.

        Args:
            title: Títol de la Pull Request.
            body: Cos descriptiu en format Markdown.
            head_branch: Branca amb els canvis proposats.
            base_branch: Branca de destinació (per defecte `'main'`).

        Returns:
            Optional[dict[str, Any]]: Diccionari amb `number` i `url`, o None si ja existia.

        Raises:
            GithubException: Si falla la creació per un motiu diferent de PR duplicada (422).
        """
        try:
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch,
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
        """Obté la llista de Pull Requests obertes al repositori.

        Returns:
            list[Any]: Llista d'objectes PullRequest oberts.

        Raises:
            GithubException: Si falla la consulta a l'API de GitHub.
        """
        try:
            return list(self.repo.get_pulls(state="open"))
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
        try:
            pr = self.repo.get_pull(pr_number)
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
        try:
            pr = self.repo.get_pull(pr_number)
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
        try:
            pr = self.repo.get_pull(pr_number)
            comments = pr.get_issue_comments()
            return "".join(
                f"\n--- Comentari de {comment.user.login} ---\n{comment.body}\n"
                for comment in comments
            )
        except GithubException as e:
            self.logger.error(f"Error en obtenir els comentaris de la PR #{pr_number}: {e}")
            print(f"❌ Error en obtenir els comentaris de la PR #{pr_number}: {e}")
            raise
