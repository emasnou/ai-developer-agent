from github import Github, GithubException
from src.utils.config import GITHUB_TOKEN, GITHUB_REPO

class GitHubService:
    def __init__(self):
        """Inicialitza la connexió amb l'API de GitHub utilitzant el Token."""
        self.client = Github(GITHUB_TOKEN)
        try:
            self.repo = self.client.get_repo(GITHUB_REPO)
            print(f"Connectat correctament al repositori: {self.repo.full_name}")
        except GithubException as e:
            print(f"Error en connectar al repositori '{GITHUB_REPO}': {e}")
            raise e

    def create_issue(self, title: str, body: str, labels: list[str] = None) -> dict:
        """
        Crea una nova tasca (Issue) al repositori de GitHub.
        
        :param title: Títol de la tasca.
        :param body: Descripció detallada, criteris d'acceptació i matriu de QA en Markdown.
        :param labels: Llista d'etiquetes (ex: ['enhancement', 'agent-created']).
        :return: Diccionari amb el número i la URL de la Issue creada.
        """
        try:
            labels = labels or ["agent-created"]
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=labels
            )
            print(f"Tasca creada amb èxit: #{issue.number} - {issue.title}")
            return {
                "number": issue.number,
                "url": issue.html_url,
                "title": issue.title
            }
        except GithubException as e:
            print(f"Error en crear la Issue a GitHub: {e}")
            raise e

    def get_issue(self, issue_number: int):
        """Obté la informació d'una Issue existent pel seu número."""
        try:
            return self.repo.get_issue(number=issue_number)
        except GithubException as e:
            print(f"Error en obtenir la Issue #{issue_number}: {e}")
            raise e

