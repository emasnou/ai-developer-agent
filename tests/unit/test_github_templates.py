"""Tests unitaris per a les plantilles de GitHub (`.github/`) i la seva integració amb els agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from src.agents.analyst_agent import AnalystAgent
from src.agents.code_review_agent import CodeReviewAgent
from src.agents.developer_agent import DeveloperAgent
from src.utils.github_templates import (
    BUG_ISSUE_TEMPLATE_REL_PATH,
    FEATURE_ISSUE_TEMPLATE_REL_PATH,
    IMPROVEMENT_ISSUE_TEMPLATE_REL_PATH,
    PR_TEMPLATE_REL_PATH,
    load_github_template,
    render_improvement_issue_body,
    render_pull_request_body,
    strip_yaml_frontmatter,
)


def test_github_template_files_exist_and_have_expected_sections() -> None:
    """Verifica que totes les plantilles recomanades de `.github/` existeixen i tenen l'estructura esperada."""
    pr_template = load_github_template(PR_TEMPLATE_REL_PATH, strip_frontmatter=False)
    assert "## 📋 Resum dels Canvis" in pr_template
    assert "Closes #{{ISSUE_NUMBER}}" in pr_template
    assert "{{FILES_SUMMARY}}" in pr_template
    assert "OWASP Top 10" in pr_template

    feature_template = load_github_template(FEATURE_ISSUE_TEMPLATE_REL_PATH, strip_frontmatter=True)
    assert "## 📝 Descripció i Història d'Usuari" in feature_template
    assert "## 🎯 Criteris d'Acceptació" in feature_template
    assert "## 🧪 Matriu de Proves de Qualitat" in feature_template

    improvement_template = load_github_template(
        IMPROVEMENT_ISSUE_TEMPLATE_REL_PATH, strip_frontmatter=True
    )
    assert "## 💡 Millora Recomanada" in improvement_template
    assert "{{PR_REFERENCE}}" in improvement_template
    assert "{{CODE_FILENAME}}" in improvement_template

    bug_template = load_github_template(BUG_ISSUE_TEMPLATE_REL_PATH, strip_frontmatter=True)
    assert "## 🐛 Descripció de l'Error" in bug_template
    assert "Given (Donat):" in bug_template


def test_strip_yaml_frontmatter_removes_metadata_header() -> None:
    """Verifica que strip_yaml_frontmatter elimina únicament el bloc YAML superior."""
    raw = (
        "---\n"
        'name: "Template de prova"\n'
        'labels: ["enhancement"]\n'
        "---\n\n"
        "## Cos de la Issue\n"
        "Contingut del document."
    )
    stripped = strip_yaml_frontmatter(raw)
    assert not stripped.startswith("---")
    assert "name:" not in stripped
    assert stripped.startswith("## Cos de la Issue")


def test_load_github_template_prioritizes_workspace_dir(tmp_path: Path) -> None:
    """Comprova que es prioritza la plantilla del repositori actiu sincronitzat al workspace.

    Args:
        tmp_path: Directori temporal de PyTest per simular un workspace multi-repositori.
    """
    custom_pr_file = tmp_path / ".github" / "pull_request_template.md"
    custom_pr_file.parent.mkdir(parents=True, exist_ok=True)
    custom_pr_file.write_text("# Plantilla PR Personalitzada: #{{ISSUE_NUMBER}}", encoding="utf-8")

    loaded = load_github_template(PR_TEMPLATE_REL_PATH, workspace_dir=tmp_path)
    assert loaded == "# Plantilla PR Personalitzada: #{{ISSUE_NUMBER}}"


def test_render_pull_request_body_replaces_all_placeholders(tmp_path: Path) -> None:
    """Verifica que render_pull_request_body omple tots els marcadors de la plantilla de PR.

    Args:
        tmp_path: Directori temporal de PyTest.
    """
    files = [
        {"path": "src/services/auth.py", "content": "# codi"},
        {"path": "tests/unit/test_auth.py", "content": "# test"},
    ]
    body = render_pull_request_body(
        issue_number=24,
        issue_title="Autenticació MFA",
        branch_name="feature/issue-24",
        files_to_commit=files,
        attempt=2,
        summary="Implementació de MFA amb TOTP",
        workspace_dir=tmp_path,
    )
    assert "Closes #24 (Autenticació MFA)" in body
    assert "`feature/issue-24`" in body
    assert "- `src/services/auth.py`" in body
    assert "- `tests/unit/test_auth.py`" in body
    assert "Passats satisfactòriament en 2 intent/s" in body
    assert "{{" not in body


def test_analyst_agent_uses_feature_issue_template_in_prompt(tmp_path: Path) -> None:
    """Verifica que AnalystAgent injecta la plantilla d'Issue configurada al prompt del LLM.

    Args:
        tmp_path: Directori temporal per provar una plantilla d'Issue personalitzada.
    """
    custom_template = tmp_path / "custom_feature.md"
    custom_template.write_text(
        "---\nname: Custom\n---\n## Secció Personalitzada BDD\n- [ ] Criteri QA",
        encoding="utf-8",
    )

    mock_llm: Any = MagicMock()
    mock_llm.generate_task_spec.return_value = "## Secció Personalitzada BDD\n- [x] Criteri QA"
    mock_gh: Any = MagicMock()
    mock_gh.create_issue.return_value = {
        "number": 10,
        "title": "Nova funcionalitat",
        "url": "https://github.com/org/repo/issues/10",
    }

    agent = AnalystAgent(
        llm_service=mock_llm,
        github_service=mock_gh,
        issue_template_path=custom_template,
    )
    res = agent.process_requirement_and_create_issue("Afegir filtre", "feat: filtre")

    assert res["number"] == 10
    called_system_prompt = mock_llm.generate_task_spec.call_args[0][1]
    assert "## Secció Personalitzada BDD" in called_system_prompt
    assert "name: Custom" not in called_system_prompt


def test_developer_agent_publish_uses_pr_template(tmp_path: Path) -> None:
    """Verifica que DeveloperAgent._publish_solution_and_create_pr usa la plantilla de PR.

    Args:
        tmp_path: Directori temporal per aïllar el workspace de prova.
    """
    workspace_dir = tmp_path / "ws_issue_15"
    (workspace_dir / "src").mkdir(parents=True)
    (workspace_dir / "src" / "app.py").write_text("x: int = 1\n", encoding="utf-8")

    mock_gh: Any = MagicMock()
    mock_gh.get_default_branch.return_value = "main"
    mock_gh.create_pull_request.return_value = {
        "number": 99,
        "url": "https://github.com/org/repo/pull/99",
    }

    agent = DeveloperAgent(llm_service=MagicMock(), github_service=mock_gh)
    dummy_issue: Any = MagicMock()
    dummy_issue.number = 15
    dummy_issue.title = "Millora de caché"

    result = agent._publish_solution_and_create_pr(
        issue=dummy_issue,
        branch_name="feature/issue-15",
        workspace_dir=workspace_dir,
        files_data=[{"path": "src/app.py", "action": "create_or_modify", "content": "x: int = 1\n"}],
        summary="Afegida caché en memòria",
        attempt=1,
    )

    assert result["success"] is True
    assert result["pr_url"] == "https://github.com/org/repo/pull/99"
    pr_call_kwargs = mock_gh.create_pull_request.call_args.kwargs
    assert "## 📋 Resum dels Canvis" in pr_call_kwargs["body"]
    assert "Closes #15 (Millora de caché)" in pr_call_kwargs["body"]
    assert "- `src/app.py`" in pr_call_kwargs["body"]


def test_code_review_agent_uses_improvement_issue_template() -> None:
    """Verifica que CodeReviewAgent formata les Issues de millora amb la plantilla de `.github/`."""
    mock_llm: Any = MagicMock()
    mock_llm.generate_task_spec.return_value = (
        '{"improvements": [{"title": "enhancement: optimitzar consultes", '
        '"description": " reduir crides repetides.\\n\\n'
        '**Proposta d\'implementació:**\\nAfegir memoització."}]}'
    )

    mock_gh: Any = MagicMock()
    mock_pr = MagicMock()
    mock_file_code = MagicMock()
    mock_file_code.filename = "src/services/github_service.py"
    mock_file_test = MagicMock()
    mock_file_test.filename = "tests/unit/test_multi_repo.py"
    mock_pr.get_files.return_value = [mock_file_code, mock_file_test]
    mock_gh.repo.get_pull.return_value = mock_pr
    mock_gh.create_issue.return_value = {
        "number": 55,
        "title": "enhancement: optimitzar consultes",
        "url": "https://github.com/org/repo/issues/55",
    }

    agent = CodeReviewAgent(llm_service=mock_llm, github_service=mock_gh)
    created = agent.create_future_improvement_issues(pr_number=12, review_report="Informe")

    assert len(created) == 1
    call_kwargs = mock_gh.create_issue.call_args.kwargs
    assert "PR #12" in call_kwargs["body"]
    assert "`src/services/github_service.py`" in call_kwargs["body"]
    assert "`tests/unit/test_multi_repo.py`" in call_kwargs["body"]
    assert "Afegir memoització." in call_kwargs["body"]
    assert "agent-review" in call_kwargs["labels"]


def test_render_improvement_issue_body_without_explicit_split() -> None:
    """Verifica que render_improvement_issue_body genera una proposta per defecte si el text és simple."""
    rendered = render_improvement_issue_body(
        description="Cal afegir validació d'esquema addicional.",
        code_filename="src/main.py",
        test_filename="tests/unit/test_main.py",
        pr_number=8,
    )
    assert "PR #8" in rendered
    assert "Cal afegir validació d'esquema addicional." in rendered
    assert "Refactoritzar `src/main.py`" in rendered

