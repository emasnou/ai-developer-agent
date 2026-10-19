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

    def create_branch(self, base_branch: str, new_branch: str):
        """Crea una nova branca de Git a partir d'una branca base (ex: 'main')."""
        try:
            ref = self.repo.get_git_ref(f"heads/{base_branch}")
            self.repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=ref.object.sha)
            print(f"🌿 Branca '{new_branch}' creada correctament a GitHub.")
        except GithubException as e:
            if e.status == 422: # La branca ja existeix
                print(f"⚠️ La branca '{new_branch}' ja existia.")
            else:
                print(f"❌ Error en crear la branca '{new_branch}': {e}")
                raise e

    def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str = "main") -> dict:
        """Obre una Pull Request (PR) automàticament a GitHub."""
        try:
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch
            )
            print(f"🔀 Pull Request creada amb èxit: #{pr.number} - {pr.html_url}")
            return {"number": pr.number, "url": pr.html_url}
        except GithubException as e:
            print(f"❌ Error en crear la PR: {e}")
            raise e
        
    def get_open_issues(self) -> list:
        """Obté la llista de totes les Issues obertes al repositori (excloent les Pull Requests)."""
        try:
            issues = self.repo.get_issues(state="open")
            # En l'API de GitHub, les PRs també tenen la interfície d'Issue. Les filtrem:
            open_issues = [issue for issue in issues if issue.pull_request is None]
            return open_issues
        except GithubException as e:
            print(f"❌ Error en obtenir les Issues obertes de GitHub: {e}")
            raise e
    def create_branch(self, base_branch: str, new_branch: str):
        """Crea una nova branca de Git a partir d'una branca base (ex: 'main')."""
        try:
            ref = self.repo.get_git_ref(f"heads/{base_branch}")
            self.repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=ref.object.sha)
            print(f"🌿 Branca '{new_branch}' creada a GitHub.")
        except GithubException as e:
            if e.status == 422: # La branca ja existeix
                print(f"ℹ️ La branca '{new_branch}' ja existia a GitHub.")
            else:
                print(f"❌ Error en crear la branca '{new_branch}': {e}")
                raise e

    def commit_and_push_files(self, branch_name: str, files: list[dict], commit_message: str):
        """
        Crea o actualitza fitxers directament a la branca de GitHub via API.
        :param files: Llista de diccionaris [{'path': 'src/xxx.py', 'content': '...'}, ...]
        """
        for file_info in files:
            file_path = file_info["path"]
            content = file_info["content"]
            try:
                # Comprovar si el fitxer ja existeix a la branca
                existing_file = self.repo.get_contents(file_path, ref=branch_name)
                self.repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    sha=existing_file.sha,
                    branch=branch_name
                )
                print(f"📝 Fitxer actualitzat a la branca '{branch_name}': {file_path}")
            except GithubException as e:
                if e.status == 404: # El fitxer no existeix, el creem de nou
                    self.repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=content,
                        branch=branch_name
                    )
                    print(f"➕ Fitxer afegit a la branca '{branch_name}': {file_path}")
                else:
                    print(f"❌ Error en fer commit del fitxer {file_path}: {e}")
                    raise e

    def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str = "main") -> dict:
        """Obre una Pull Request (PR) automàticament a GitHub."""
        try:
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch
            )
            print(f"🔀 Pull Request creada amb èxit: #{pr.number} - {pr.html_url}")
            return {"number": pr.number, "url": pr.html_url}
        except GithubException as e:
            if e.status == 422: # PR ja existent
                print("ℹ️ Ja existeix una Pull Request oberta per a aquesta branca.")
            else:
                print(f"❌ Error en crear la PR: {e}")
                raise e
    def get_pull_requests(self) -> list:
        """Obté la llista de Pull Requests obertes."""
        try:
            return list(self.repo.get_pulls(state="open"))
        except GithubException as e:
            print(f"❌ Error en obtenir les Pull Requests: {e}")
            raise e

    def get_pull_request_files(self, pr_number: int) -> str:
        """Obté el contingut dels fitxers canviats en una Pull Request."""
        try:
            pr = self.repo.get_pull(pr_number)
            files = pr.get_files()
            diff_text = ""
            for file in files:
                diff_text += f"\n--- Fitxer: {file.filename} ---\n"
                diff_text += f"Patch / Canvis:\n{file.patch}\n"
            return diff_text
        except GithubException as e:
            print(f"❌ Error en obtenir els canvis de la PR #{pr_number}: {e}")
            raise e

    def post_pr_comment(self, pr_number: int, comment_body: str):
        """Publica un comentari de revisió a la Pull Request."""
        try:
            pr = self.repo.get_pull(pr_number)
            pr.create_issue_comment(comment_body)
            print(f"💬 Comentari de Code Review publicat a la PR #{pr_number}.")
        except GithubException as e:
            print(f"❌ Error en publicar el comentari a la PR #{pr_number}: {e}")
            raise e   
    def get_pr_review_comments(self, pr_number: int) -> str:
        """Obté tots els comentaris de revisió/auditoria publicats a la PR."""
        try:
            pr = self.repo.get_pull(pr_number)
            comments = pr.get_issue_comments()
            review_history = ""
            for comment in comments:
                review_history += f"\n--- Comentari de {comment.user.login} ---\n{comment.body}\n"
            return review_history
        except GithubException as e:
            print(f"❌ Error en obtenir els comentaris de la PR #{pr_number}: {e}")
            raise e
        
    def get_repository_tree(self, ref: str = "main") -> list[str]:
        """Obté la llista completa de camins (paths) de fitxers del repositori."""
        try:
            # 1. Obtenim la referència del commit/branca (SHA)
            branch = self.repo.get_branch(ref)
            sha = branch.commit.sha
            
            # 2. Obtenim l'arbre de Git passant el SHA com a primer argument
            tree = self.repo.get_git_tree(sha, recursive=True)
            
            # 3. Filtrem per obtenir només fitxers de codi/configuració rellevants
            file_paths = [
                element.path for element in tree.tree 
                if element.type == "blob" and not element.path.startswith(".")
            ]
            return file_paths
        except GithubException as e:
            print(f"❌ Error en obtenir l'arbre del repositori: {e}")
            return []

    def get_file_content(self, file_path: str, ref: str = "main") -> str:
        """Obté el contingut de text d'un fitxer existent al repositori."""
        try:
            content_file = self.repo.get_contents(file_path, ref=ref)
            return content_file.decoded_content.decode("utf-8")
        except GithubException as e:
            print(f"⚠️ No s'ha pogut llegir el fitxer {file_path}: {e}")
            return "" 