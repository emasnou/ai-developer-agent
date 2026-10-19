import pytest
from src.agents.developer_agent import DeveloperAgent
from src.services.github_service import GitHubService

class TestDeveloperGitHubIntegration:
    """Tests d'integració per validar la comunicació entre DeveloperAgent i GitHubService."""

    @pytest.fixture
    def setup_services(self):
        """Fixture per inicialitzar els serveis de GitHub i l'Agent Desenvolupador."""
        github_service = GitHubService()
        developer_agent = DeveloperAgent()
        return github_service, developer_agent

    def test_github_connection_and_repository_access(self, setup_services):
        """Verifica que el servei es connecta al repositori configurat a les variables d'entorn."""
        github_service, _ = setup_services
        
        assert github_service.repo is not None
        assert github_service.repo.full_name is not None
        print(f"\n✅ Connectat correctament al repositori: {github_service.repo.full_name}")

    def test_developer_agent_can_fetch_open_issues(self, setup_services):
        """Verifica que l'agent pot recuperar la llista de Issues obertes del repositori."""
        github_service, developer_agent = setup_services
        
        open_issues = github_service.get_open_issues()
        
        assert isinstance(open_issues, list)
        print(f"\n✅ S'han trobat {len(open_issues)} Issue(s) oberta(es) al repositori.")

    def test_developer_agent_fetches_specific_issue_details(self, setup_services):
        """Verifica que el DeveloperAgent pot llegir el títol i contingut d'una Issue existent."""
        github_service, developer_agent = setup_services
        
        open_issues = github_service.get_open_issues()
        
        if not open_issues:
            pytest.skip("No hi ha Issues obertes al repositori per provar la lectura de detalls.")
            
        target_issue = open_issues[0]
        fetched_issue = developer_agent.github.get_issue(target_issue.number)
        
        assert fetched_issue.number == target_issue.number
        assert fetched_issue.title == target_issue.title
        assert fetched_issue.body is not None
        
        print(f"\n✅ L'Agent ha extret correctament la Issue #{fetched_issue.number}: '{fetched_issue.title}'")

