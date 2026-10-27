"""Tests unitaris per a la gestió multi-repositori, selecció al menú CLI i aïllament de workspaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.agents.analyst_agent import AnalystAgent
from src.agents.developer_agent import DeveloperAgent
from src.main import handle_analyst_option, handle_repository_selection, main
from src.services.github_service import GitHubService, validate_repo_name
from src.utils.config import parse_repo_list


class _DummyRepo:
    """Objecte simulat de repositori de PyGithub per a proves unitàries."""

    def __init__(self, full_name: str, default_branch: str = "main") -> None:
        self.full_name = full_name
        self.default_branch = default_branch


class _DummyTreeElement:
    """Element simulat de l'arbre Git de PyGithub."""

    def __init__(self, path: str, elem_type: str = "blob") -> None:
        self.path = path
        self.type = elem_type


def test_parse_repo_list_merges_and_deduplicates() -> None:
    """Verifica que parse_repo_list extreu la llista sense duplicats i prioritza el repo per defecte."""
    repos = parse_repo_list("org/repo-u, org/repo-dos , org/repo-u", "org/repo-dos")
    assert repos == ("org/repo-dos", "org/repo-u")

    empty_repos = parse_repo_list("", None)
    assert empty_repos == ()


def test_validate_repo_name_security() -> None:
    """Comprova la validació estricta del nom del repositori contra Path Traversal (OWASP)."""
    assert validate_repo_name("emili/ai-developer-agent") is True
    assert validate_repo_name("org_1/project.api-v2") is True

    assert validate_repo_name("") is False
    assert validate_repo_name("nom_sense_propietari") is False
    assert validate_repo_name("../etc/passwd") is False
    assert validate_repo_name("org/../../secret") is False
    assert validate_repo_name("org/repo/extra") is False
    assert validate_repo_name("org/repo amb espais") is False


def test_github_service_list_and_switch_active_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que GitHubService permet llistar repositoris disponibles i canviar el repositori actiu."""
    monkeypatch.setattr("src.services.github_service.GITHUB_REPOS", ("org/repo-alpha", "org/repo-beta"))

    mock_client = MagicMock()
    mock_user = MagicMock()
    mock_user.get_repos.return_value = [
        _DummyRepo("org/repo-beta"),
        _DummyRepo("org/repo-gamma"),
    ]
    mock_client.get_user.return_value = mock_user
    mock_client.get_repo.side_effect = lambda name: _DummyRepo(name, default_branch="develop")

    service = GitHubService(token="fake-token", repo_name=None, require_repo=False, client=mock_client)
    assert service.active_repo_name is None

    with pytest.raises(ValueError, match="No hi ha cap repositori actiu"):
        _ = service.repo

    available = service.list_available_repositories()
    assert available == ["org/repo-alpha", "org/repo-beta", "org/repo-gamma"]

    selected = service.set_active_repository("org/repo-gamma")
    assert selected == "org/repo-gamma"
    assert service.active_repo_name == "org/repo-gamma"
    assert service.get_default_branch() == "develop"


def test_github_service_tree_includes_github_workflows() -> None:
    """Comprova que get_repository_tree inclou els workflows de GitHub Actions (.github/workflows)."""
    mock_client = MagicMock()
    mock_repo = MagicMock()
    mock_repo.full_name = "org/repo-ci"
    mock_tree = MagicMock()
    mock_tree.tree = [
        _DummyTreeElement("src/app.py"),
        _DummyTreeElement(".github/workflows/deploy.yml"),
        _DummyTreeElement(".git/config"),
        _DummyTreeElement(".env"),
    ]
    mock_repo.get_git_tree.return_value = mock_tree
    mock_client.get_repo.return_value = mock_repo

    service = GitHubService(token="fake-token", repo_name="org/repo-ci", client=mock_client)
    files = service.get_repository_tree(ref="main")

    assert "src/app.py" in files
    assert ".github/workflows/deploy.yml" in files
    assert ".git/config" not in files
    assert ".env" not in files


def test_developer_agent_workspace_isolation_per_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que el DeveloperAgent aïlla el workspace segons el repositori seleccionat."""
    monkeypatch.chdir(tmp_path)
    policy_dir = tmp_path / "docs"
    policy_dir.mkdir()
    (policy_dir / "code_policy.md").write_text("Política de test", encoding="utf-8")

    mock_gh_a = MagicMock()
    mock_gh_a.active_repo_name = "org/servei-pagaments"
    dev_a = DeveloperAgent(
        llm_service=MagicMock(),
        github_service=mock_gh_a,
        repo_name="org/servei-pagaments",
    )

    ws_a = dev_a._prepare_workspace_environment(issue_number=42)
    assert ws_a == tmp_path / ".workspace" / "org__servei-pagaments" / "issue_42"
    assert ws_a.exists()

    written = dev_a._write_files_to_workspace(
        [
            {"path": ".github/workflows/deploy.yml", "content": "name: Deploy\non: [push]\n"},
            {"path": "src/main.py", "content": "def salut() -> str:\n    return 'hola'\n"},
        ],
        ws_a,
    )
    assert len(written) == 2
    source_context = dev_a._read_workspace_source_files(ws_a)
    assert ".github/workflows/deploy.yml" in source_context
    assert "src/main.py" in source_context

    with pytest.raises(ValueError, match="fora del workspace"):
        dev_a._write_files_to_workspace(
            [{"path": "../../fora.py", "content": "evil = True"}],
            ws_a,
        )


def test_cli_menu_displays_selected_repo_and_routes_actions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verifica que el menú mostra el repositori seleccionat a l'inici i el propaga a les opcions."""
    mock_service = MagicMock()
    mock_service.active_repo_name = None
    mock_service.list_available_repositories.return_value = [
        "emili/repo-backend",
        "emili/repo-frontend",
    ]

    def _set_repo(name: str) -> str:
        mock_service.active_repo_name = name
        return name

    mock_service.set_active_repository.side_effect = _set_repo

    inputs = iter(["1", "2", "6"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    main(github_service=mock_service)
    captured = capsys.readouterr().out

    assert "📂 REPOSITORI ACTIU: Cap repositori seleccionat" in captured
    assert "[1] emili/repo-backend" in captured
    assert "[2] emili/repo-frontend" in captured
    assert "✅ Repositori actiu seleccionat: emili/repo-frontend" in captured
    assert "📂 REPOSITORI ACTIU: emili/repo-frontend" in captured


def test_analyst_option_uses_selected_repository(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verifica que l'opció d'Analista crea la Issue sobre el repositori actiu seleccionat."""
    mock_service = MagicMock()
    mock_service.active_repo_name = "emili/repo-backend"
    mock_service.create_issue.return_value = {
        "number": 7,
        "title": "Desplegament amb GitHub Actions",
        "url": "https://github.com/emili/repo-backend/issues/7",
    }

    mock_llm = MagicMock()
    mock_llm.generate_task_spec.return_value = "## Especificació de tasca"
    monkeypatch.setattr(AnalystAgent, "llm", property(lambda self: mock_llm))

    inputs = iter(["Desplegament amb GitHub Actions", "Afegir workflow de deploy"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    handle_analyst_option(github_service=mock_service)
    captured = capsys.readouterr().out

    assert "📂 Repositori de treball: emili/repo-backend" in captured
    assert "https://github.com/emili/repo-backend/issues/7" in captured
    mock_service.create_issue.assert_called_once()

