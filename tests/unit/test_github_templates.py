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


def test_analyst_agent_decomposes_multi_story_with_sequential_order() -> None:
    """Verifica que AnalystAgent descompon un requeriment complex en múltiples Stories seqüencials i tancades."""
    import json

    multi_story_payload = {
        "requires_multiple_stories": True,
        "decomposition_rationale": (
            "Es divideix en 2 Stories seqüencials per separar el model de dades "
            "de la lògica d'integració CLI, garantint que cada pas compili i passi PyTest."
        ),
        "execution_sequence_summary": (
            "1r crear esquemes i validadors amb els seus tests unitaris -> "
            "2n integrar el servei i el menú CLI sobre els esquemes ja validats."
        ),
        "stories": [
            {
                "execution_order": 2,
                "title": "Integració al menú CLI",
                "body": "## 📝 Descripció i Història d'Usuari\nIntegrar el comandament al CLI.",
                "depends_on_orders": [1],
                "deliverable_summary": "Comandament CLI operatiu amb tests unitaris de flux.",
            },
            {
                "execution_order": 1,
                "title": "Esquemes Pydantic i validador base",
                "body": "## 📝 Descripció i Història d'Usuari\nDefinir models i validadors.",
                "depends_on_orders": [],
                "deliverable_summary": "Mòdul d'esquemes independent amb tests unitaris al 100%.",
            },
        ],
    }

    mock_llm: Any = MagicMock()
    mock_llm.generate_task_spec.return_value = json.dumps(multi_story_payload)

    created_counter = {"n": 100}

    def _fake_create_issue(title: str, body: str, labels: list[str] | None = None) -> dict[str, Any]:
        created_counter["n"] += 1
        num = created_counter["n"]
        return {
            "number": num,
            "title": title,
            "url": f"https://github.com/org/repo/issues/{num}",
            "body": body,
            "labels": labels or [],
        }

    mock_gh: Any = MagicMock()
    mock_gh.create_issue.side_effect = _fake_create_issue

    agent = AnalystAgent(llm_service=mock_llm, github_service=mock_gh)
    result = agent.process_requirement_and_create_issue(
        requirement="Sistema complet d'auditoria amb esquemes i CLI",
        issue_title="Sistema d'Auditoria",
    )

    assert result["multi_story"] is True
    assert result["stories_count"] == 2
    assert len(result["issues"]) == 2
    assert result["number"] == 101

    # Verifica que s'han ordenat per execution_order (1 abans que 2)
    seq = result["execution_sequence"]
    assert seq[0]["step"] == 1
    assert seq[0]["issue_number"] == 101
    assert "Esquemes Pydantic" in seq[0]["title"]
    assert seq[0]["depends_on_issues"] == []

    assert seq[1]["step"] == 2
    assert seq[1]["issue_number"] == 102
    assert "Integració al menú CLI" in seq[1]["title"]
    assert seq[1]["depends_on_issues"] == [101]

    # Verifica que el cos de la segona Issue conté l'enllaç a la Issue #101 i les garanties d'abast tancat
    second_call_kwargs = mock_gh.create_issue.call_args_list[1].kwargs
    assert "[Story 2/2]" in second_call_kwargs["title"]
    assert "Pla d'Execució Seqüencial i Abast Tancat" in second_call_kwargs["body"]
    assert "Issue #101" in second_call_kwargs["body"]
    assert "desenvolupament tancat" in second_call_kwargs["body"]

    # Verifica el text de seqüència recomanada
    assert "Issue #101" in result["recommended_sequence_text"]
    assert "Issue #102" in result["recommended_sequence_text"]
    assert "executar després de: #101" in result["recommended_sequence_text"]


def test_developer_agent_extract_and_resolve_dependencies() -> None:
    """Verifica l'extracció i resolució de dependències entre Stories obertes."""
    from types import SimpleNamespace
    from src.agents.developer_agent import DeveloperAgent

    issue_101 = SimpleNamespace(
        number=101,
        title="[Story 1/3] Esquemes base",
        body=(
            "## 🔢 Pla d'Execució Seqüencial i Abast Tancat\n"
            "- **Dependències Prèvies:** Cap (Primera Story de la seqüència — Base independent)\n"
        ),
    )
    issue_102 = SimpleNamespace(
        number=102,
        title="[Story 2/3] Servei de negoci",
        body=(
            "## 🔢 Pla d'Execució Seqüencial i Abast Tancat\n"
            "- **Dependències Prèvies:** Issue #101 ([Story 1/3] Esquemes base)\n"
        ),
    )
    issue_103 = SimpleNamespace(
        number=103,
        title="[Story 3/3] Interfície CLI",
        body=(
            "## 🔢 Pla d'Execució Seqüencial i Abast Tancat\n"
            "- **Dependències Prèvies:** Issue #102 ([Story 2/3] Servei de negoci)\n"
        ),
    )
    open_issues = [issue_101, issue_102, issue_103]

    assert DeveloperAgent.extract_issue_dependencies(issue_101.body) == []
    assert DeveloperAgent.extract_issue_dependencies(issue_102.body) == [101]
    assert DeveloperAgent.extract_issue_dependencies(issue_103.body) == [102]

    status_101 = DeveloperAgent.resolve_dependency_status(issue_101, open_issues)
    assert status_101["is_blocked"] is False
    assert "Llista per desenvolupar" in DeveloperAgent.format_issue_dependency_badge(
        issue_101, open_issues
    )

    # La 103 depèn de la 102, que alhora depèn de la 101 -> primera necessària és la 101
    status_103 = DeveloperAgent.resolve_dependency_status(issue_103, open_issues)
    assert status_103["is_blocked"] is True
    assert status_103["pending_dependencies"] == [102]
    assert status_103["first_required_issue"].number == 101
    badge_103 = DeveloperAgent.format_issue_dependency_badge(issue_103, open_issues)
    assert "Depèn de: #102" in badge_103
    assert "cal desenvolupar primer #101" in badge_103

    # Si la 101 ja s'ha tancat, la 102 passa a estar desbloquejada
    open_after_101 = [issue_102, issue_103]
    status_102_after = DeveloperAgent.resolve_dependency_status(issue_102, open_after_101)
    assert status_102_after["is_blocked"] is False
    assert "Dependències completades" in DeveloperAgent.format_issue_dependency_badge(
        issue_102, open_after_101
    )


def test_prompt_issue_selection_blocks_dependent_story_and_returns_to_menu(
    monkeypatch: Any, capsys: Any
) -> None:
    """Verifica que triar una Story amb dependències avisa l'usuari i torna al menú."""
    from types import SimpleNamespace
    from src.main import _prompt_issue_selection

    issue_101 = SimpleNamespace(
        number=101,
        title="[Story 1/2] Base de dades",
        body="- **Dependències Prèvies:** Cap\n",
    )
    issue_102 = SimpleNamespace(
        number=102,
        title="[Story 2/2] Endpoint API",
        body="- **Dependències Prèvies:** Issue #101 ([Story 1/2] Base de dades)\n",
    )
    open_issues = [issue_101, issue_102]

    # L'usuari intenta triar primer la 102 (bloquejada) i després tria la 101 (vàlida)
    inputs = iter(["102", "101"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    selected = _prompt_issue_selection(open_issues, "emasnou/test-repo")
    assert selected == 101

    captured = capsys.readouterr().out
    assert "Depèn de: #101" in captured
    assert "No es pot desenvolupar la Story #102" in captured
    assert "Cal desenvolupar primer la Story #101: '[Story 1/2] Base de dades'" in captured
    assert "Tornant al menú de selecció de Stories" in captured



